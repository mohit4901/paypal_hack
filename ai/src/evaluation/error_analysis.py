"""
Error analysis — categorize and display model prediction errors.

Usage:
    python -m src.evaluation.error_analysis \
        --model-path artifacts/checkpoints/exp_001_domain_only/best \
        --data-dir data/processed/evidencebench \
        --split test \
        --output-dir artifacts/reports
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.models.labels import APP_LABEL_NAMES
from src.utils.logging_config import setup_logging

logger = setup_logging(name="error_analysis")

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
        parts = [
            f"[{e.get('source_type', '')}|{e.get('evidence_id', '')}]: {e.get('content', '')}"
            for e in row["evidence"] if isinstance(e, dict)
        ]
        premise = " | ".join(parts) if parts else "[NO EVIDENCE]"
    elif "evidence_text" in row:
        premise = row.get("evidence_text", "[NO EVIDENCE]")
    else:
        premise = "[NO EVIDENCE]"
    hypothesis = row.get("claim", "")
    return premise, hypothesis


def run_error_analysis(
    model_path: str,
    data_dir: str,
    split: str = "test",
    output_dir: str = "artifacts/reports",
    max_rows: Optional[int] = None,
    batch_size: int = 16,
    max_length: int = 256,
    n_examples_per_category: int = 10,
) -> Dict[str, Any]:
    import torch
    from torch.utils.data import DataLoader, Dataset
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    split_name = "validation" if split == "val" else split
    data_file = Path(data_dir) / f"{split_name}.jsonl"
    if not data_file.exists() and split == "validation":
        data_file = Path(data_dir) / "val.jsonl"
    rows = _load_jsonl(str(data_file), max_rows)

    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")

    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSequenceClassification.from_pretrained(model_path)
    model.to(device)
    model.eval()

    cfg = model.config
    id2label = {int(k): v for k, v in cfg.id2label.items()}
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

    class EvalDS(Dataset):
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

    ds = EvalDS(rows, tokenizer, max_length)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=False, num_workers=0)

    all_preds, all_labels = [], []
    with torch.no_grad():
        for batch in loader:
            outputs = model(
                input_ids=batch["input_ids"].to(device),
                attention_mask=batch["attention_mask"].to(device),
            )
            raw_preds = outputs.logits.argmax(dim=-1).cpu().numpy().tolist()
            all_preds.extend([out_idx_to_app_idx.get(p, p) for p in raw_preds])
            all_labels.extend(batch["label"].numpy().tolist())

    # Categorize errors
    errors: Dict[str, List[Dict]] = {
        "false_support": [],          # predicted SUPPORTED, actually not
        "missed_contradiction": [],   # predicted not CONTRADICTED, actually CONTRADICTED
        "insuf_as_contradiction": [], # predicted CONTRADICTED, actually INSUFFICIENT
        "correct": [],                # correct predictions (sample)
    }

    for row, pred, true_label in zip(rows, all_preds, all_labels):
        pred_str = ID2LABEL[pred]
        true_str = ID2LABEL[true_label]
        entry = {
            "scenario_family": row.get("scenario_family", "unknown"),
            "claim": row.get("claim", "")[:200],
            "evidence_count": len(row.get("evidence", [])),
            "true_label": true_str,
            "predicted_label": pred_str,
            "label_rationale": row.get("label_rationale", "")[:200],
        }
        if pred_str == "SUPPORTED" and true_str != "SUPPORTED":
            errors["false_support"].append(entry)
        if true_str == "CONTRADICTED" and pred_str != "CONTRADICTED":
            errors["missed_contradiction"].append(entry)
        if pred_str == "CONTRADICTED" and true_str == "INSUFFICIENT_EVIDENCE":
            errors["insuf_as_contradiction"].append(entry)
        if pred == true_label:
            errors["correct"].append(entry)

    # Truncate to n_examples_per_category
    for k in errors:
        errors[k] = errors[k][:n_examples_per_category]

    # Summary statistics
    n = len(all_labels)
    correct_count = sum(1 for p, l in zip(all_preds, all_labels) if p == l)
    category_sizes = {
        "false_support_total": sum(
            1 for p, l in zip(all_preds, all_labels)
            if ID2LABEL[p] == "SUPPORTED" and ID2LABEL[l] != "SUPPORTED"
        ),
        "missed_contradiction_total": sum(
            1 for p, l in zip(all_preds, all_labels)
            if ID2LABEL[l] == "CONTRADICTED" and ID2LABEL[p] != "CONTRADICTED"
        ),
        "insuf_as_contradiction_total": sum(
            1 for p, l in zip(all_preds, all_labels)
            if ID2LABEL[p] == "CONTRADICTED" and ID2LABEL[l] == "INSUFFICIENT_EVIDENCE"
        ),
    }

    result = {
        "model_path": model_path,
        "dataset": data_dir,
        "split": split,
        "n_examples": n,
        "overall_accuracy": round(correct_count / n, 4) if n > 0 else 0,
        "error_category_totals": category_sizes,
        "error_examples": errors,
        "note": (
            "Examples are sampled for analysis. No sensitive customer data is exposed "
            "(all data is synthetic)."
        ),
    }

    report_path = out / f"error_analysis_{split}_{Path(model_path).name}.json"
    with open(report_path, "w") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Error analysis saved → {report_path}")
    logger.info(f"  False support: {category_sizes['false_support_total']}")
    logger.info(f"  Missed contradiction: {category_sizes['missed_contradiction_total']}")
    logger.info(f"  Insuf as contradiction: {category_sizes['insuf_as_contradiction_total']}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--data-dir", default="data/processed/evidencebench")
    parser.add_argument("--split", default="test")
    parser.add_argument("--output-dir", default="artifacts/reports")
    parser.add_argument("--max-rows", type=int, default=None)
    args = parser.parse_args()
    run_error_analysis(
        model_path=args.model_path,
        data_dir=args.data_dir,
        split=args.split,
        output_dir=args.output_dir,
        max_rows=args.max_rows,
    )
