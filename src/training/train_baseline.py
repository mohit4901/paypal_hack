"""
Baseline C — TF-IDF + Logistic Regression classifier.

This baseline is trained on the EvidenceBench training split and
evaluated on the same test split as the fine-tuned model.
Results are logged to artifacts/baseline/.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.pipeline import Pipeline

from src.models.labels import APP_LABEL_NAMES
from src.utils.logging_config import setup_logging
from src.utils.reproducibility import set_seed

logger = setup_logging(name="train_baseline")
LABEL2ID = {l: i for i, l in enumerate(APP_LABEL_NAMES)}


def _load_jsonl(path: str, max_rows: Optional[int] = None) -> List[Dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if max_rows and i >= max_rows:
                break
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _get_text(row: Dict) -> str:
    """Concatenate premise + hypothesis for TF-IDF."""
    if "evidence" in row:
        parts = [ev.get("content", "") for ev in row["evidence"] if isinstance(ev, dict)]
        premise = " ".join(parts) if parts else "[NO EVIDENCE]"
    elif "evidence_text" in row:
        premise = row.get("evidence_text", "[NO EVIDENCE]")
    else:
        premise = "[NO EVIDENCE]"
    hypothesis = row.get("claim", "")
    return f"{premise} [SEP] {hypothesis}"


def run_tfidf_baseline(
    data_dir: str = "data/processed/evidencebench",
    output_dir: str = "artifacts/baseline",
    seed: int = 42,
    max_train: Optional[int] = None,
) -> Dict:
    set_seed(seed)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    train_rows = _load_jsonl(f"{data_dir}/train.jsonl", max_train)
    val_rows = _load_jsonl(f"{data_dir}/validation.jsonl")
    test_rows = _load_jsonl(f"{data_dir}/test.jsonl")

    train_X = [_get_text(r) for r in train_rows]
    train_y = [LABEL2ID.get(r.get("label", "INSUFFICIENT_EVIDENCE"), 2) for r in train_rows]
    val_X = [_get_text(r) for r in val_rows]
    val_y = [LABEL2ID.get(r.get("label", "INSUFFICIENT_EVIDENCE"), 2) for r in val_rows]
    test_X = [_get_text(r) for r in test_rows]
    test_y = [LABEL2ID.get(r.get("label", "INSUFFICIENT_EVIDENCE"), 2) for r in test_rows]

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=50000,
            sublinear_tf=True,
            min_df=2,
        )),
        ("clf", LogisticRegression(
            max_iter=1000,
            C=1.0,
            class_weight="balanced",
            random_state=seed,
            solver="lbfgs",
            multi_class="multinomial",
        )),
    ])

    logger.info(f"Fitting TF-IDF+LR on {len(train_rows)} examples...")
    pipeline.fit(train_X, train_y)

    results = {}
    for split_name, X, y in [("validation", val_X, val_y), ("test", test_X, test_y)]:
        preds = pipeline.predict(X)
        acc = accuracy_score(y, preds)
        macro_f1 = f1_score(y, preds, average="macro", zero_division=0)
        weighted_f1 = f1_score(y, preds, average="weighted", zero_division=0)
        report = classification_report(y, preds, target_names=APP_LABEL_NAMES, output_dict=True, zero_division=0)
        cm = confusion_matrix(y, preds).tolist()

        contradiction_recall = report.get("CONTRADICTED", {}).get("recall", 0.0)
        insuf_recall = report.get("INSUFFICIENT_EVIDENCE", {}).get("recall", 0.0)

        supported_idx = LABEL2ID["SUPPORTED"]
        fp_supported = sum(1 for p, l in zip(preds, y) if p == supported_idx and l != supported_idx)
        total_non_supported = sum(1 for l in y if l != supported_idx)
        fpr = fp_supported / total_non_supported if total_non_supported > 0 else 0.0

        res = {
            "split": split_name,
            "n_examples": len(y),
            "accuracy": round(acc, 4),
            "macro_f1": round(macro_f1, 4),
            "weighted_f1": round(weighted_f1, 4),
            "contradiction_recall": round(contradiction_recall, 4),
            "insufficient_evidence_recall": round(insuf_recall, 4),
            "false_positive_rate_supported": round(fpr, 4),
            "per_class": report,
            "confusion_matrix": cm,
            "confusion_matrix_labels": APP_LABEL_NAMES,
        }
        results[split_name] = res
        logger.info(
            f"TF-IDF+LR {split_name}: acc={acc:.4f} macro_f1={macro_f1:.4f} "
            f"contradiction_recall={contradiction_recall:.4f}"
        )

    full_result = {
        "model": "TF-IDF + Logistic Regression (Baseline C)",
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "data_dir": data_dir,
        "seed": seed,
        "results": results,
    }

    report_path = out / "tfidf_lr_baseline.json"
    with open(report_path, "w") as f:
        json.dump(full_result, f, indent=2)
    logger.info(f"Baseline results saved → {report_path}")
    return full_result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data/processed/evidencebench")
    parser.add_argument("--output-dir", default="artifacts/baseline")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    result = run_tfidf_baseline(args.data_dir, args.output_dir, args.seed)
    print(json.dumps({k: v for k, v in result["results"].get("test", {}).items()
                      if k not in ("per_class", "confusion_matrix")}, indent=2))

