"""
Training pipeline for fine-tuning DeBERTa-v3 on ProofLedger NLI data.

Usage:
    python -m src.training.train_classifier \
        --data-dir data/processed/evidencebench \
        --base-model MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli \
        --output-dir artifacts/checkpoints/run_001 \
        --epochs 5 \
        --batch-size 8 \
        --lr 2e-5 \
        --seed 42
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from src.models.labels import APP_LABEL_NAMES, APP_TO_IDX, IDX_TO_APP, AppLabel
from src.utils.logging_config import setup_logging
from src.utils.reproducibility import set_seed

logger = setup_logging(name="train_classifier")

LABEL2ID = {l: i for i, l in enumerate(APP_LABEL_NAMES)}
ID2LABEL = {i: l for l, i in LABEL2ID.items()}


def _load_jsonl(path: str, max_rows: Optional[int] = None) -> List[Dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if max_rows and i >= max_rows:
                break
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _get_text(row: Dict) -> tuple[str, str]:
    """Return (premise, hypothesis) from a dataset row."""
    # EvidenceBench
    if "evidence" in row:
        ev_parts = []
        for ev in row["evidence"]:
            if isinstance(ev, dict):
                eid = ev.get("evidence_id", "")
                src = ev.get("source_type", "")
                ts = ev.get("timestamp", "")
                content = ev.get("content", "")
                part = f"[{src.upper()}|{eid}]"
                if ts:
                    part += f" {ts}"
                part += f": {content}"
                ev_parts.append(part)
        premise = " | ".join(ev_parts) if ev_parts else "[NO EVIDENCE]"
    # FEVEROUS parsed
    elif "evidence_text" in row:
        premise = row["evidence_text"] or "[NO EVIDENCE]"
    else:
        premise = "[NO EVIDENCE]"

    hypothesis = row.get("claim", row.get("claim_text", ""))
    return premise, hypothesis


def train(
    data_dir: str,
    base_model: str,
    output_dir: str,
    epochs: int = 5,
    batch_size: int = 8,
    lr: float = 2e-5,
    seed: int = 42,
    max_length: int = 256,
    grad_accum: int = 2,
    warmup_ratio: float = 0.1,
    weight_decay: float = 0.01,
    patience: int = 2,
    smoke_test: bool = False,
    use_feverous: bool = False,
    feverous_dir: Optional[str] = None,
) -> Dict[str, Any]:
    set_seed(seed)

    import torch
    from torch.utils.data import DataLoader, Dataset
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        get_linear_schedule_with_warmup,
    )
    from sklearn.metrics import classification_report, f1_score, confusion_matrix

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Device
    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")
    logger.info(f"Training device: {device}")

    # Load data
    data_path = Path(data_dir)
    max_train = 200 if smoke_test else None
    max_eval = 50 if smoke_test else None

    train_rows = _load_jsonl(str(data_path / "train.jsonl"), max_train)
    val_rows = _load_jsonl(str(data_path / "validation.jsonl"), max_eval)

    if use_feverous and feverous_dir:
        fev_path = Path(feverous_dir)
        for split_file in fev_path.glob("*.jsonl"):
            if "train" in split_file.stem:
                extra = _load_jsonl(str(split_file), max_train)
                train_rows.extend(extra)
                logger.info(f"Added {len(extra)} FEVEROUS rows from {split_file.name}")
                break

    logger.info(f"Train: {len(train_rows)}, Val: {len(val_rows)}")

    # Tokenizer
    logger.info(f"Loading tokenizer from {base_model}")
    tokenizer = AutoTokenizer.from_pretrained(base_model)

    class NLIDataset(Dataset):
        def __init__(self, rows, tokenizer, max_length):
            self.rows = rows
            self.tokenizer = tokenizer
            self.max_length = max_length

        def __len__(self):
            return len(self.rows)

        def __getitem__(self, idx):
            row = self.rows[idx]
            premise, hypothesis = _get_text(row)
            label_str = row.get("label", "INSUFFICIENT_EVIDENCE")
            label_id = LABEL2ID.get(label_str, 2)

            enc = self.tokenizer(
                premise,
                hypothesis,
                truncation=True,
                max_length=self.max_length,
                padding="max_length",
                return_tensors="pt",
            )
            return {
                "input_ids": enc["input_ids"].squeeze(),
                "attention_mask": enc["attention_mask"].squeeze(),
                "labels": torch.tensor(label_id, dtype=torch.long),
            }

    train_ds = NLIDataset(train_rows, tokenizer, max_length)
    val_ds = NLIDataset(val_rows, tokenizer, max_length)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=batch_size * 2, shuffle=False, num_workers=0)

    # Model
    logger.info(f"Loading model from {base_model}")
    model = AutoModelForSequenceClassification.from_pretrained(
        base_model,
        num_labels=3,
        id2label=ID2LABEL,
        label2id=LABEL2ID,
        ignore_mismatched_sizes=True,
    )
    model.to(device)

    # Compute class weights for imbalance
    label_counts = [0, 0, 0]
    for row in train_rows:
        l = LABEL2ID.get(row.get("label", "INSUFFICIENT_EVIDENCE"), 2)
        label_counts[l] += 1
    total = sum(label_counts)
    class_weights = torch.tensor(
        [total / (3 * c) if c > 0 else 1.0 for c in label_counts],
        dtype=torch.float,
    ).to(device)
    logger.info(f"Class weights: {class_weights.tolist()}")

    # Optimizer and scheduler
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    total_steps = (len(train_loader) // grad_accum) * epochs
    warmup_steps = int(total_steps * warmup_ratio)
    scheduler = get_linear_schedule_with_warmup(optimizer, warmup_steps, total_steps)

    loss_fn = torch.nn.CrossEntropyLoss(weight=class_weights)

    # Training loop
    history = []
    best_val_f1 = -1.0
    best_epoch = -1
    patience_count = 0
    start_time = time.time()

    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        optimizer.zero_grad()

        for step, batch in enumerate(train_loader):
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            loss = loss_fn(outputs.logits, labels)
            loss = loss / grad_accum
            loss.backward()

            if (step + 1) % grad_accum == 0 or (step + 1) == len(train_loader):
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()

            train_loss += loss.item() * grad_accum

        avg_train_loss = train_loss / len(train_loader)

        # Validation
        model.eval()
        val_preds, val_labels = [], []
        val_loss = 0.0
        with torch.no_grad():
            for batch in val_loader:
                input_ids = batch["input_ids"].to(device)
                attention_mask = batch["attention_mask"].to(device)
                labels = batch["labels"].to(device)
                outputs = model(input_ids=input_ids, attention_mask=attention_mask)
                loss = loss_fn(outputs.logits, labels)
                val_loss += loss.item()
                preds = outputs.logits.argmax(dim=-1).cpu().numpy()
                val_preds.extend(preds.tolist())
                val_labels.extend(labels.cpu().numpy().tolist())

        avg_val_loss = val_loss / len(val_loader)
        val_f1 = f1_score(val_labels, val_preds, average="macro", zero_division=0)
        report = classification_report(
            val_labels, val_preds,
            target_names=APP_LABEL_NAMES,
            output_dict=True,
            zero_division=0,
        )
        cm = confusion_matrix(val_labels, val_preds).tolist()

        epoch_stats = {
            "epoch": epoch,
            "train_loss": round(avg_train_loss, 4),
            "val_loss": round(avg_val_loss, 4),
            "val_macro_f1": round(val_f1, 4),
            "val_classification_report": report,
            "confusion_matrix": cm,
        }
        history.append(epoch_stats)

        logger.info(
            f"Epoch {epoch}/{epochs} | train_loss={avg_train_loss:.4f} "
            f"val_loss={avg_val_loss:.4f} val_macro_f1={val_f1:.4f}"
        )

        # Checkpoint saving
        ckpt_dir = out / f"checkpoint_epoch_{epoch}"
        model.save_pretrained(str(ckpt_dir))
        tokenizer.save_pretrained(str(ckpt_dir))

        # Best model selection by validation macro-F1
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            best_epoch = epoch
            patience_count = 0
            best_dir = out / "best"
            model.save_pretrained(str(best_dir))
            tokenizer.save_pretrained(str(best_dir))
            logger.info(f"  ✓ New best val macro-F1: {val_f1:.4f} → saved to {best_dir}")
        else:
            patience_count += 1
            logger.info(f"  No improvement. Patience: {patience_count}/{patience}")
            if patience_count >= patience and not smoke_test:
                logger.info("Early stopping triggered.")
                break

    elapsed = time.time() - start_time
    result = {
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "base_model": base_model,
        "data_dir": data_dir,
        "output_dir": output_dir,
        "epochs_completed": epoch,
        "best_epoch": best_epoch,
        "best_val_macro_f1": best_val_f1,
        "training_history": history,
        "elapsed_s": round(elapsed, 1),
        "device": str(device),
        "hyperparams": {
            "lr": lr, "batch_size": batch_size, "max_length": max_length,
            "grad_accum": grad_accum, "warmup_ratio": warmup_ratio,
            "weight_decay": weight_decay, "patience": patience, "seed": seed,
            "epochs": epochs, "use_feverous": use_feverous,
        },
        "smoke_test": smoke_test,
    }

    with open(out / "training_result.json", "w") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Training complete. Best val macro-F1={best_val_f1:.4f} (epoch {best_epoch}). Elapsed={elapsed:.0f}s")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data/processed/evidencebench")
    parser.add_argument("--base-model", default="MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli")
    parser.add_argument("--output-dir", default="artifacts/checkpoints/run_001")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--use-feverous", action="store_true")
    parser.add_argument("--feverous-dir", default="data/processed/feverous")
    args = parser.parse_args()
    train(
        data_dir=args.data_dir,
        base_model=args.base_model,
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        seed=args.seed,
        max_length=args.max_length,
        smoke_test=args.smoke_test,
        use_feverous=args.use_feverous,
        feverous_dir=args.feverous_dir,
    )

