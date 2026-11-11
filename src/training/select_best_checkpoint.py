"""
Select the best checkpoint from completed experiment runs.

Reads training_result.json files from all checkpoint directories and
selects the best model by validation macro-F1.

Usage:
    python -m src.training.select_best_checkpoint \
        --checkpoints-dir artifacts/checkpoints \
        --output-dir artifacts/best_model
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from src.utils.logging_config import setup_logging

logger = setup_logging(name="select_best_checkpoint")


def select_best(checkpoints_dir: str, output_dir: str) -> dict:
    ckpt_root = Path(checkpoints_dir)
    best = {"val_f1": -1.0, "path": None, "exp": None}

    for result_file in sorted(ckpt_root.rglob("training_result.json")):
        with open(result_file) as f:
            result = json.load(f)
        val_f1 = result.get("best_val_macro_f1", -1.0)
        exp_dir = result_file.parent
        best_subdir = exp_dir / "best"

        if val_f1 > best["val_f1"] and best_subdir.exists():
            best = {"val_f1": val_f1, "path": str(best_subdir), "exp": str(exp_dir), "result": result}
            logger.info(f"New candidate: {exp_dir.name} val_macro_f1={val_f1:.4f}")

    if best["path"] is None:
        logger.warning("No completed experiments found with a 'best' checkpoint.")
        return best

    out = Path(output_dir)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(best["path"], out)
    logger.info(f"\n✓ Best checkpoint: {best['exp']}")
    logger.info(f"  val_macro_f1 = {best['val_f1']:.4f}")
    logger.info(f"  Copied to: {out}")

    selection_record = {
        "selected_checkpoint": best["path"],
        "val_macro_f1": best["val_f1"],
        "experiment": best["exp"],
        "selection_criterion": "validation macro-F1 (highest)",
        "note": (
            "Test set evaluation must be run AFTER checkpoint selection is frozen. "
            "Do not re-select based on test set results."
        ),
    }
    with open(out / "selection_record.json", "w") as f:
        json.dump(selection_record, f, indent=2)

    return best


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoints-dir", default="artifacts/checkpoints")
    parser.add_argument("--output-dir", default="artifacts/best_model")
    args = parser.parse_args()
    result = select_best(args.checkpoints_dir, args.output_dir)
    if result["path"]:
        print(f"Best: {result['exp']} (val_macro_f1={result['val_f1']:.4f})")
