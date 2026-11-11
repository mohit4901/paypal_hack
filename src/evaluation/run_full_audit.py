"""
Run full post-training diagnostic audit script across all models and splits.
"""
from __future__ import annotations

import json
from pathlib import Path
import torch

from src.evaluation.diagnostic_audit import run_model_inference

def main():
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    print(f"Audit running on device: {device}")

    output_dir = Path("artifacts/diagnostic_audit")
    output_dir.mkdir(parents=True, exist_ok=True)

    splits = {
        "validation": "data/processed/evidencebench/validation.jsonl",
        "test": "data/processed/evidencebench/test.jsonl",
        "challenge_test": "data/processed/evidencebench/challenge_test.jsonl",
    }

    models = {
        "best_model_epoch9": "artifacts/best_model",
        "pretrained_deberta": "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
    }

    summary = {}

    for m_key, m_path in models.items():
        summary[m_key] = {}
        for s_key, s_path in splits.items():
            print(f"\n--- Running {m_key} on {s_key} ({s_path}) ---")
            res = run_model_inference(
                model_path=m_path,
                data_path=s_path,
                device=device,
                batch_size=32,
                max_length=256,
            )

            # Save full records (with predictions, logits, probs)
            records = res.pop("records")
            full_out_path = output_dir / f"predictions_{m_key}_{s_key}.jsonl"
            with open(full_out_path, "w", encoding="utf-8") as f:
                for r in records:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")

            # Save metrics
            metrics_out_path = output_dir / f"metrics_{m_key}_{s_key}.json"
            with open(metrics_out_path, "w", encoding="utf-8") as f:
                json.dump(res, f, indent=2)

            summary[m_key][s_key] = {
                "n_examples": res["n_examples"],
                "accuracy": res["accuracy"],
                "macro_f1": res["macro_f1"],
                "represented_macro_f1": res["represented_classes_macro_f1"],
                "weighted_f1": res["weighted_f1"],
                "contradiction_recall": res["contradiction_recall"],
                "insufficient_evidence_recall": res["insufficient_evidence_recall"],
                "supported_recall": res["supported_recall"],
                "supported_fpr": res["supported_fpr"],
                "supported_fdr": res["supported_fdr"],
                "confusion_matrix": res["confusion_matrix"],
                "per_class": res["per_class"],
                "raw_id2label": res["raw_id2label"],
                "out_idx_to_app_idx": res["out_idx_to_app_idx"],
            }
            print(f"Result for {m_key} on {s_key}:")
            print(f"  Accuracy: {res['accuracy']:.4f}")
            print(f"  Macro-F1: {res['macro_f1']:.4f} (Rep: {res['represented_classes_macro_f1']:.4f})")
            print(f"  Contradiction Recall: {res['contradiction_recall']:.4f}")
            print(f"  Insuf Recall: {res['insufficient_evidence_recall']:.4f}")
            print(f"  Supported FPR: {res['supported_fpr']:.4f}")
            print(f"  Supported FDR: {res['supported_fdr']}")
            print(f"  Confusion Matrix: {res['confusion_matrix']}")

    summary_path = output_dir / "audit_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\nAudit complete! Summary saved to {summary_path}")

if __name__ == "__main__":
    main()

