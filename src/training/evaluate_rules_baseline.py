"""Deterministic rules-only baseline evaluation against EvidenceBench."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix

from src.models.deterministic_validator import DeterministicValidator
from src.models.labels import APP_LABEL_NAMES, AppLabel
from src.utils.logging_config import setup_logging

logger = setup_logging(name="rules_baseline")
LABEL2ID = {l: i for i, l in enumerate(APP_LABEL_NAMES)}


def _load_jsonl(path: str) -> List[Dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def evaluate_rules_baseline(
    data_dir: str = "data/processed/evidencebench",
    output_dir: str = "artifacts/baseline",
) -> Dict:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    validator = DeterministicValidator()
    results = {}

    for split_name in ("validation", "test"):
        rows = _load_jsonl(f"{data_dir}/{split_name}.jsonl")
        preds, labels = [], []

        for row in rows:
            evidence = row.get("evidence", [])
            # Convert EvidenceBench evidence format to dict list for validator
            ev_dicts = [
                {
                    "evidence_id": e.get("evidence_id", ""),
                    "source_type": e.get("source_type", ""),
                    "timestamp": e.get("timestamp"),
                    "content": e.get("content", ""),
                }
                for e in evidence
            ] if isinstance(evidence, list) else []

            pred_label, _ = validator.run_all(
                claim=row.get("claim", ""),
                evidence=ev_dicts,
            )
            preds.append(LABEL2ID.get(pred_label.value, 2))
            labels.append(LABEL2ID.get(row.get("label", "INSUFFICIENT_EVIDENCE"), 2))

        acc = accuracy_score(labels, preds)
        macro_f1 = f1_score(labels, preds, average="macro", zero_division=0)
        report = classification_report(labels, preds, target_names=APP_LABEL_NAMES, labels=[0,1,2], output_dict=True, zero_division=0)
        cm = confusion_matrix(labels, preds).tolist()

        contradiction_recall = report.get("CONTRADICTED", {}).get("recall", 0.0)
        insuf_recall = report.get("INSUFFICIENT_EVIDENCE", {}).get("recall", 0.0)

        supported_idx = LABEL2ID["SUPPORTED"]
        fp_supported = sum(1 for p, l in zip(preds, labels) if p == supported_idx and l != supported_idx)
        total_non_supported = sum(1 for l in labels if l != supported_idx)
        fpr = fp_supported / total_non_supported if total_non_supported > 0 else 0.0

        results[split_name] = {
            "n_examples": len(rows),
            "accuracy": round(acc, 4),
            "macro_f1": round(macro_f1, 4),
            "contradiction_recall": round(contradiction_recall, 4),
            "insufficient_evidence_recall": round(insuf_recall, 4),
            "false_positive_rate_supported": round(fpr, 4),
            "per_class": report,
            "confusion_matrix": cm,
            "confusion_matrix_labels": APP_LABEL_NAMES,
        }
        logger.info(f"Rules-only {split_name}: acc={acc:.4f} macro_f1={macro_f1:.4f}")

    full_result = {
        "model": "Rules-only (Deterministic Baseline A)",
        "data_dir": data_dir,
        "results": results,
    }
    with open(out / "rules_baseline.json", "w") as f:
        json.dump(full_result, f, indent=2)
    return full_result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data/processed/evidencebench")
    parser.add_argument("--output-dir", default="artifacts/baseline")
    args = parser.parse_args()
    result = evaluate_rules_baseline(args.data_dir, args.output_dir)
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk not in ("per_class", "confusion_matrix")}
                      for k, v in result["results"].items()}, indent=2))
