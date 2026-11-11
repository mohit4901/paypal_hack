"""
Optimized fine-tuning for ProofLedger — best stable model configuration.

Key design choices for stability and peak performance:
  - Small batch size (4) → more gradient updates per epoch, better generalization
  - Effective batch = 16 via gradient accumulation (stable updates)
  - Low LR (1e-5) → gentle domain adaptation, prevents catastrophic forgetting
  - Cosine annealing schedule → smooth LR decay, avoids sharp valleys
  - Longer warmup (15%) → stabilizes early training
  - Early stopping patience=5 → waits longer before giving up
  - Max 20 epochs → enough for transformer convergence (5000 would overfit)
  - Label smoothing → reduces overconfidence, improves calibration
  - Best checkpoint by validation macro-F1

Why NOT 5000 epochs:
  - Transformers converge in 3-10 epochs (pre-trained weights already know language)
  - Beyond ~10 epochs: train_loss → 0 but val_loss explodes (overfitting)
  - 5000 epochs × 25 min = 86 days on Apple MPS

Usage:
    python -m src.training.train_best \
        --data-dir data/processed/evidencebench \
        --output-dir artifacts/checkpoints/best_run
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from src.models.labels import APP_LABEL_NAMES
from src.utils.logging_config import setup_logging
from src.utils.reproducibility import set_seed

logger = setup_logging(name="train_best")

LABEL2ID = {l: i for i, l in enumerate(APP_LABEL_NAMES)}
ID2LABEL = {i: l for l, i in LABEL2ID.items()}


def _load_jsonl(path: str, max_rows: Optional[int] = None) -> List[Dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if max_rows and i >= max_rows:
                break
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _get_text(row: Dict) -> tuple[str, str]:
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
    elif "evidence_text" in row:
        premise = row.get("evidence_text", "[NO EVIDENCE]")
    else:
        premise = "[NO EVIDENCE]"
    hypothesis = row.get("claim", "")
    return premise, hypothesis


def train_best(
    data_dir: str = "data/processed/evidencebench",
    base_model: str = "artifacts/checkpoints/smoke_test/best",
    output_dir: str = "artifacts/checkpoints/best_run",
    # ── Key stability parameters ──────────────────────────────────────────
    epochs: int = 20,           # Enough for convergence; early stopping exits when plateau
    batch_size: int = 4,        # Small batch = more updates = better generalization
    grad_accum: int = 4,        # Effective batch = 4×4 = 16 (stable gradient estimates)
    lr: float = 1e-5,           # Low LR = gentle domain adaptation
    max_length: int = 256,
    warmup_ratio: float = 0.15, # 15% warmup = stable ramp-up
    weight_decay: float = 0.01,
    label_smoothing: float = 0.1,  # Prevents overconfident predictions
    patience: int = 5,          # Wait 5 val checks before early stopping
    seed: int = 42,
    use_feverous: bool = False,
    feverous_dir: Optional[str] = None,
    max_feverous_rows: int = 10000,
) -> Dict[str, Any]:
    set_seed(seed)

    import torch
    from torch.utils.data import DataLoader, Dataset
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        get_cosine_schedule_with_warmup,
    )
    from sklearn.metrics import (
        accuracy_score,
        classification_report,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
    )

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Device
    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")
    logger.info(f"Device: {device} | Batch: {batch_size} | GradAccum: {grad_accum} | Effective batch: {batch_size * grad_accum}")
    logger.info(f"LR: {lr} | Warmup: {warmup_ratio*100:.0f}% | Label smoothing: {label_smoothing} | Patience: {patience}")

    # Load data
    train_rows = _load_jsonl(f"{data_dir}/train.jsonl")
    val_rows = _load_jsonl(f"{data_dir}/validation.jsonl")

    if use_feverous and feverous_dir:
        fev_path = Path(feverous_dir)
        for split_file in sorted(fev_path.glob("train*.jsonl")):
            extra = _load_jsonl(str(split_file), max_feverous_rows)
            train_rows.extend(extra)
            logger.info(f"Added {len(extra)} FEVEROUS rows")
            break

    logger.info(f"Train: {len(train_rows)} | Val: {len(val_rows)}")

    tokenizer = AutoTokenizer.from_pretrained(base_model)

    class NLIDataset(Dataset):
        def __init__(self, rows, tokenizer, max_length):
            self.rows = rows
            self.tokenizer = tokenizer
            self.max_length = max_length

        def __len__(self): return len(self.rows)

        def __getitem__(self, idx):
            row = self.rows[idx]
            premise, hypothesis = _get_text(row)
            label_id = LABEL2ID.get(row.get("label", "INSUFFICIENT_EVIDENCE"), 2)
            enc = self.tokenizer(
                premise, hypothesis,
                truncation=True, max_length=self.max_length,
                padding="max_length", return_tensors="pt",
            )
            return {
                "input_ids": enc["input_ids"].squeeze(),
                "attention_mask": enc["attention_mask"].squeeze(),
                "labels": torch.tensor(label_id, dtype=torch.long),
            }

    train_ds = NLIDataset(train_rows, tokenizer, max_length)
    val_ds = NLIDataset(val_rows, tokenizer, max_length)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=batch_size * 4, shuffle=False, num_workers=0)

    # Model
    model = AutoModelForSequenceClassification.from_pretrained(
        base_model, num_labels=3, id2label=ID2LABEL, label2id=LABEL2ID,
        ignore_mismatched_sizes=True,
    )
    model.to(device)

    # Class weights
    label_counts = [0, 0, 0]
    for row in train_rows:
        label_counts[LABEL2ID.get(row.get("label", "INSUFFICIENT_EVIDENCE"), 2)] += 1
    total = sum(label_counts)
    class_weights = torch.tensor(
        [total / (3 * c) if c > 0 else 1.0 for c in label_counts], dtype=torch.float
    ).to(device)
    logger.info(f"Label counts: {dict(zip(APP_LABEL_NAMES, label_counts))}")
    logger.info(f"Class weights: {[round(w, 4) for w in class_weights.tolist()]}")

    # Optimizer — separate LR for backbone vs classifier head
    no_decay = ["bias", "LayerNorm.weight"]
    optimizer_groups = [
        {"params": [p for n, p in model.named_parameters() if not any(nd in n for nd in no_decay)], "weight_decay": weight_decay},
        {"params": [p for n, p in model.named_parameters() if any(nd in n for nd in no_decay)], "weight_decay": 0.0},
    ]
    optimizer = torch.optim.AdamW(optimizer_groups, lr=lr)

    # Cosine schedule with warmup
    total_steps = (len(train_loader) // grad_accum) * epochs
    warmup_steps = int(total_steps * warmup_ratio)
    scheduler = get_cosine_schedule_with_warmup(optimizer, warmup_steps, total_steps)

    # Loss with label smoothing
    loss_fn = torch.nn.CrossEntropyLoss(weight=class_weights, label_smoothing=label_smoothing)

    logger.info(f"Total optimizer steps: {total_steps} | Warmup steps: {warmup_steps}")

    history = []
    best_val_f1 = -1.0
    best_secondary = -1.0
    best_epoch = -1
    patience_count = 0
    start_time = time.time()
    best_dir = out / "best"

    for epoch in range(1, epochs + 1):
        # ── Training ──────────────────────────────────────────────────────
        model.train()
        train_loss = 0.0
        optimizer.zero_grad()

        for step, batch in enumerate(train_loader):
            ids = batch["input_ids"].to(device)
            mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            out_model = model(input_ids=ids, attention_mask=mask)
            loss = loss_fn(out_model.logits, labels) / grad_accum
            loss.backward()
            train_loss += loss.item() * grad_accum

            if (step + 1) % grad_accum == 0 or (step + 1) == len(train_loader):
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()

        avg_train_loss = train_loss / len(train_loader)
        current_lr = scheduler.get_last_lr()[0]

        # ── Validation ────────────────────────────────────────────────────
        model.eval()
        val_preds, val_labels_list = [], []
        val_loss = 0.0
        with torch.no_grad():
            for batch in val_loader:
                ids = batch["input_ids"].to(device)
                mask = batch["attention_mask"].to(device)
                labels = batch["labels"].to(device)
                out_model = model(input_ids=ids, attention_mask=mask)
                val_loss += loss_fn(out_model.logits, labels).item()
                preds = out_model.logits.argmax(dim=-1).cpu().numpy()
                val_preds.extend(preds.tolist())
                val_labels_list.extend(labels.cpu().numpy().tolist())

        avg_val_loss = val_loss / len(val_loader)
        val_acc = float(accuracy_score(val_labels_list, val_preds))
        val_f1 = float(f1_score(val_labels_list, val_preds, average="macro", zero_division=0))
        per_class_p = precision_score(val_labels_list, val_preds, average=None, zero_division=0)
        per_class_r = recall_score(val_labels_list, val_preds, average=None, zero_division=0)
        per_class_f1 = f1_score(val_labels_list, val_preds, average=None, zero_division=0)
        cm = confusion_matrix(val_labels_list, val_preds).tolist()

        # Secondary criteria: Contradiction recall and Insufficient-Evidence recall
        contra_idx = LABEL2ID.get("CONTRADICTED", 1)
        insuf_idx = LABEL2ID.get("INSUFFICIENT_EVIDENCE", 2)
        contra_recall = float(per_class_r[contra_idx])
        insuf_recall = float(per_class_r[insuf_idx])
        secondary_score = (contra_recall + insuf_recall) / 2.0

        epoch_stats = {
            "epoch": epoch,
            "train_loss": round(avg_train_loss, 4),
            "val_loss": round(avg_val_loss, 4),
            "val_accuracy": round(val_acc, 4),
            "val_macro_f1": round(val_f1, 4),
            "contra_recall": round(contra_recall, 4),
            "insuf_recall": round(insuf_recall, 4),
            "lr": round(current_lr, 8),
            "per_class_precision": {APP_LABEL_NAMES[i]: round(float(per_class_p[i]), 4) for i in range(3)},
            "per_class_recall": {APP_LABEL_NAMES[i]: round(float(per_class_r[i]), 4) for i in range(3)},
            "per_class_f1": {APP_LABEL_NAMES[i]: round(float(per_class_f1[i]), 4) for i in range(3)},
            "confusion_matrix": cm,
        }
        history.append(epoch_stats)

        elapsed = time.time() - start_time
        logger.info(
            f"Epoch {epoch:3d}/{epochs} | "
            f"train_loss={avg_train_loss:.4f} | val_loss={avg_val_loss:.4f} | "
            f"val_acc={val_acc:.4f} | val_macro_f1={val_f1:.4f} | "
            f"contra_rec={contra_recall:.4f} | insuf_rec={insuf_recall:.4f} | "
            f"lr={current_lr:.2e} | elapsed={elapsed/60:.1f}min"
        )
        logger.info(
            f"           Per-class F1: "
            f"SUPPORTED={per_class_f1[0]:.4f} "
            f"CONTRADICTED={per_class_f1[1]:.4f} "
            f"INSUF={per_class_f1[2]:.4f}"
        )

        # Save checkpoint every epoch
        ckpt_dir = out / f"epoch_{epoch:03d}"
        model.save_pretrained(str(ckpt_dir))
        tokenizer.save_pretrained(str(ckpt_dir))

        # Best checkpoint selection:
        # Primary: validation macro-F1. Secondary: average of contradiction recall & insufficient evidence recall
        is_new_best = False
        if val_f1 > best_val_f1 + 1e-5:
            is_new_best = True
        elif abs(val_f1 - best_val_f1) <= 1e-5 and secondary_score > best_secondary:
            is_new_best = True

        if is_new_best:
            best_val_f1 = val_f1
            best_secondary = secondary_score
            best_epoch = epoch
            patience_count = 0
            if best_dir.exists():
                import shutil
                shutil.rmtree(best_dir)
            model.save_pretrained(str(best_dir))
            tokenizer.save_pretrained(str(best_dir))
            logger.info(
                f"           ✓ NEW BEST val_macro_f1={val_f1:.4f} "
                f"(contra_rec={contra_recall:.4f}, insuf_rec={insuf_recall:.4f}) → saved to {best_dir}"
            )
        else:
            patience_count += 1
            logger.info(f"           No improvement ({patience_count}/{patience}). Best so far: {best_val_f1:.4f} @ epoch {best_epoch}")
            if patience_count >= patience:
                logger.info(f"Early stopping: no val-F1 improvement for {patience} epochs.")
                break

        # Save history after every epoch
        with open(out / "training_result.json", "w") as f:
            json.dump({
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "base_model": base_model,
                "epochs_completed": epoch,
                "best_epoch": best_epoch,
                "best_val_macro_f1": best_val_f1,
                "training_history": history,
                "elapsed_s": round(time.time() - start_time, 1),
                "device": str(device),
                "hyperparams": {
                    "lr": lr, "batch_size": batch_size, "grad_accum": grad_accum,
                    "effective_batch": batch_size * grad_accum,
                    "max_length": max_length, "warmup_ratio": warmup_ratio,
                    "weight_decay": weight_decay, "label_smoothing": label_smoothing,
                    "patience": patience, "seed": seed, "epochs_max": epochs,
                    "schedule": "cosine_with_warmup",
                },
            }, f, indent=2)

    total_elapsed = time.time() - start_time
    logger.info(f"\n{'='*60}")
    logger.info(f"Training complete!")
    logger.info(f"Best epoch: {best_epoch}  |  Best val macro-F1: {best_val_f1:.4f}")
    logger.info(f"Total time: {total_elapsed/60:.1f} min  |  Device: {device}")
    logger.info(f"Best model saved → {best_dir}")
    logger.info(f"{'='*60}")

    return {"best_val_macro_f1": best_val_f1, "best_epoch": best_epoch, "best_dir": str(best_dir)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Optimized DeBERTa fine-tuning for ProofLedger")
    parser.add_argument("--data-dir", default="data/processed/evidencebench")
    parser.add_argument("--base-model", default="artifacts/checkpoints/smoke_test/best")
    parser.add_argument("--output-dir", default="artifacts/checkpoints/best_run")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--grad-accum", type=int, default=4)
    parser.add_argument("--lr", type=float, default=1e-5)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--patience", type=int, default=5)
    parser.add_argument("--label-smoothing", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--use-feverous", action="store_true")
    parser.add_argument("--feverous-dir", default="data/processed/feverous")
    args = parser.parse_args()
    train_best(
        data_dir=args.data_dir,
        base_model=args.base_model,
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        grad_accum=args.grad_accum,
        lr=args.lr,
        max_length=args.max_length,
        patience=args.patience,
        label_smoothing=args.label_smoothing,
        seed=args.seed,
        use_feverous=args.use_feverous,
        feverous_dir=args.feverous_dir,
    )
