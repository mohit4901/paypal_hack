"""
Evaluation pipeline: compute metrics on a saved model checkpoint.

Usage:
    python -m src.evaluation.evaluate \
        --model-path artifacts/checkpoints/run_001/best \
        --data-dir data/processed/evidencebench \
        --split test \
        --output-dir artifacts/reports
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
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)

from src.models.labels import APP_LABEL_NAMES
from src.utils.logging_config import setup_logging
from src.utils.reproducibility import set_seed

logger = setup_logging(name="evaluate")

LABEL2ID = {l: i for i, l in enumerate(APP_LABEL_NAMES)}


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
        premise = row["evidence_text"] or "[NO EVIDENCE]"
    else:
        premise = "[NO EVIDENCE]"
    hypothesis = row.get("claim", row.get("claim_text", ""))
    return premise, hypothesis


def evaluate_model(
    model_path: str,
    data_dir: str,
    split: str = "test",
    output_dir: str = "artifacts/reports",
    max_rows: Optional[int] = None,
    batch_size: int = 16,
    max_length: int = 256,
    seed: int = 42,
) -> Dict[str, Any]:
    set_seed(seed)

    import torch
    from torch.utils.data import DataLoader, Dataset
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")

    data_file = Path(data_dir) / f"{split}.jsonl"
    rows = _load_jsonl(str(data_file), max_rows)
    logger.info(f"Evaluating on {split}: {len(rows)} examples from {data_file}")

    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSequenceClassification.from_pretrained(model_path)
    model.to(device)
    model.eval()

    # Read actual model id2label
    cfg = model.config
    id2label = {int(k): v for k, v in cfg.id2label.items()}
    logger.info(f"Model id2label: {id2label}")

    out_idx_to_app_idx = {}
    for idx, name in id2label.items():
        name_str = str(name).strip().upper()
        if name_str in ("ENTAILMENT", "SUPPORTED", "SUPPORTS"):
            out_idx_to_app_idx[idx] = LABEL2ID["SUPPORTED"]
        elif name_str in ("CONTRADICTION", "CONTRADICTED", "REFUTES"):
            out_idx_to_app_idx[idx] = LABEL2ID["CONTRADICTED"]
        elif name_str in ("NEUTRAL", "INSUFFICIENT_EVIDENCE", "NOT ENOUGH INFO"):
            out_idx_to_app_idx[idx] = LABEL2ID["INSUFFICIENT_EVIDENCE"]
        else:
            out_idx_to_app_idx[idx] = LABEL2ID["INSUFFICIENT_EVIDENCE"]
    logger.info(f"Mapped output index to App index: {out_idx_to_app_idx}")

    class EvalDataset(Dataset):
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
                premise, hypothesis,
                truncation=True, max_length=self.max_length,
                padding="max_length", return_tensors="pt",
            )
            return {
                "input_ids": enc["input_ids"].squeeze(),
                "attention_mask": enc["attention_mask"].squeeze(),
                "label": label_id,
            }

    ds = EvalDataset(rows, tokenizer, max_length)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=False, num_workers=0)

    all_preds, all_labels = [], []
    latencies = []

    with torch.no_grad():
        for batch in loader:
            t0 = time.time()
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            latencies.append(time.time() - t0)
            raw_preds = outputs.logits.argmax(dim=-1).cpu().numpy()
            mapped = [out_idx_to_app_idx.get(int(p), int(p)) for p in raw_preds]
            all_preds.extend(mapped)
            all_labels.extend(batch["label"].numpy().tolist())

    acc = accuracy_score(all_labels, all_preds)
    macro_f1 = f1_score(all_labels, all_preds, average="macro", zero_division=0)
    weighted_f1 = f1_score(all_labels, all_preds, average="weighted", zero_division=0)
    report = classification_report(
        all_labels, all_preds,
        labels=list(range(3)),
        target_names=APP_LABEL_NAMES, output_dict=True, zero_division=0,
    )
    cm = confusion_matrix(all_labels, all_preds, labels=list(range(3))).tolist()

    # Per-class metrics
    prec, rec, f1, support = precision_recall_fscore_support(
        all_labels, all_preds, labels=list(range(3)), zero_division=0
    )
    per_class = {
        APP_LABEL_NAMES[i]: {
            "precision": round(float(prec[i]), 4),
            "recall": round(float(rec[i]), 4),
            "f1": round(float(f1[i]), 4),
            "support": int(support[i]),
        }
        for i in range(3)
    }

    # Contradiction recall specifically
    contradiction_idx = LABEL2ID.get("CONTRADICTED", 1)
    insuf_idx = LABEL2ID.get("INSUFFICIENT_EVIDENCE", 2)
    contradiction_recall = per_class["CONTRADICTED"]["recall"]
    insuf_recall = per_class["INSUFFICIENT_EVIDENCE"]["recall"]

    # False positive rate (FPR) and False discovery rate (FDR) for SUPPORTED
    supported_idx = LABEL2ID.get("SUPPORTED", 0)
    fp_supported = sum(
        1 for p, l in zip(all_preds, all_labels)
        if p == supported_idx and l != supported_idx
    )
    total_non_supported = sum(1 for l in all_labels if l != supported_idx)
    total_pred_supported = sum(1 for p in all_preds if p == supported_idx)
    fpr = fp_supported / total_non_supported if total_non_supported > 0 else 0.0
    fdr = fp_supported / total_pred_supported if total_pred_supported > 0 else 0.0

    # Represented-classes macro-F1 (for splits like challenge_test where some classes have support=0)
    active_labels = [i for i in range(3) if support[i] > 0]
    represented_macro_f1 = float(np.mean([f1[i] for i in active_labels])) if active_labels else 0.0

    # Bootstrap uncertainty (1000 resamples, stratified by label)
    n_bootstrap = 1000
    bootstrap_f1s = []
    rng = np.random.default_rng(seed)
    all_labels_arr = np.array(all_labels)
    all_preds_arr = np.array(all_preds)
    for _ in range(n_bootstrap):
        idx = rng.integers(0, len(all_labels), size=len(all_labels))
        bscore = f1_score(
            all_labels_arr[idx], all_preds_arr[idx],
            average="macro", zero_division=0
        )
        bootstrap_f1s.append(bscore)
    ci_lo = float(np.percentile(bootstrap_f1s, 2.5))
    ci_hi = float(np.percentile(bootstrap_f1s, 97.5))

    avg_latency_ms = round(np.mean(latencies) * 1000 / batch_size, 2)

    result = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "model_path": model_path,
        "dataset": data_dir,
        "split": split,
        "n_examples": len(rows),
        "accuracy": round(acc, 4),
        "macro_f1": round(macro_f1, 4),
        "macro_f1_95ci": [round(ci_lo, 4), round(ci_hi, 4)],
        "weighted_f1": round(weighted_f1, 4),
        "contradiction_recall": round(contradiction_recall, 4),
        "insufficient_evidence_recall": round(insuf_recall, 4),
        "false_positive_rate_supported": round(fpr, 4),
        "false_discovery_rate_supported": round(fdr, 4),
        "represented_classes_macro_f1": round(represented_macro_f1, 4),
        "per_class": per_class,
        "confusion_matrix": cm,
        "confusion_matrix_labels": APP_LABEL_NAMES,
        "avg_inference_latency_ms_per_example": avg_latency_ms,
        "device": str(device),
    }

    report_path = out / f"eval_{split}_{Path(model_path).name}.json"
    with open(report_path, "w") as f:
        json.dump(result, f, indent=2)

    logger.info(
        f"Eval {split}: acc={acc:.4f} macro_f1={macro_f1:.4f} "
        f"contradiction_recall={contradiction_recall:.4f} "
        f"insuf_recall={insuf_recall:.4f}"
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--data-dir", default="data/processed/evidencebench")
    parser.add_argument("--split", default="test")
    parser.add_argument("--output-dir", default="artifacts/reports")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-length", type=int, default=256)
    args = parser.parse_args()
    result = evaluate_model(
        model_path=args.model_path,
        data_dir=args.data_dir,
        split=args.split,
        output_dir=args.output_dir,
        batch_size=args.batch_size,
        max_length=args.max_length,
    )
    print(json.dumps(result, indent=2))

