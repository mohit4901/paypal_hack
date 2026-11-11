#!/usr/bin/env python3
"""
Run experiments manager — executes the planned experiment suite and records results.

Experiments:
  exp_001 — Domain-only (EvidenceBench), lr=2e-5   [runs as background task]
  exp_002 — Domain-only (EvidenceBench), lr=1e-5
  exp_003 — Mixed (EvidenceBench + FEVEROUS), lr=2e-5

Usage:
    python -m src.training.run_experiments [--exp exp_001] [--all]
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from src.training.train_classifier import train
from src.utils.logging_config import setup_logging

logger = setup_logging(name="run_experiments")

EXPERIMENTS = [
    {
        "id": "exp_001_domain_only_2e5",
        "description": "Domain-only (EvidenceBench), lr=2e-5",
        "data_dir": "data/processed/evidencebench",
        "base_model": "artifacts/checkpoints/smoke_test/best",
        "output_dir": "artifacts/checkpoints/exp_001_domain_only",
        "epochs": 5,
        "batch_size": 8,
        "lr": 2e-5,
        "max_length": 256,
        "seed": 42,
        "use_feverous": False,
    },
    {
        "id": "exp_002_domain_only_1e5",
        "description": "Domain-only (EvidenceBench), lr=1e-5",
        "data_dir": "data/processed/evidencebench",
        "base_model": "artifacts/checkpoints/smoke_test/best",
        "output_dir": "artifacts/checkpoints/exp_002_domain_only_1e5",
        "epochs": 5,
        "batch_size": 8,
        "lr": 1e-5,
        "max_length": 256,
        "seed": 42,
        "use_feverous": False,
    },
    {
        "id": "exp_003_mixed_2e5",
        "description": "Mixed (EvidenceBench + FEVEROUS), lr=2e-5",
        "data_dir": "data/processed/evidencebench",
        "base_model": "artifacts/checkpoints/smoke_test/best",
        "output_dir": "artifacts/checkpoints/exp_003_mixed",
        "epochs": 5,
        "batch_size": 8,
        "lr": 2e-5,
        "max_length": 256,
        "seed": 42,
        "use_feverous": True,
        "feverous_dir": "data/processed/feverous",
    },
]

EXPERIMENT_TABLE_PATH = Path("artifacts/reports/experiment_table.json")


def load_table() -> list:
    if EXPERIMENT_TABLE_PATH.exists():
        with open(EXPERIMENT_TABLE_PATH) as f:
            return json.load(f)
    return []


def save_table(table: list):
    EXPERIMENT_TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(EXPERIMENT_TABLE_PATH, "w") as f:
        json.dump(table, f, indent=2)


def run_experiment(exp: dict) -> dict:
    logger.info(f"Starting {exp['id']}: {exp['description']}")
    result = train(
        data_dir=exp["data_dir"],
        base_model=exp["base_model"],
        output_dir=exp["output_dir"],
        epochs=exp["epochs"],
        batch_size=exp["batch_size"],
        lr=exp["lr"],
        seed=exp["seed"],
        max_length=exp["max_length"],
        use_feverous=exp.get("use_feverous", False),
        feverous_dir=exp.get("feverous_dir"),
    )
    entry = {
        "experiment_id": exp["id"],
        "description": exp["description"],
        "started_at": result.get("completed_at", "unknown"),
        "hyperparams": result.get("hyperparams", {}),
        "epochs_completed": result.get("epochs_completed", 0),
        "best_epoch": result.get("best_epoch", -1),
        "best_val_macro_f1": result.get("best_val_macro_f1", 0.0),
        "elapsed_s": result.get("elapsed_s", 0),
        "checkpoint_path": f"{exp['output_dir']}/best",
        "status": "completed",
    }
    return entry


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--exp", help="Run a specific experiment ID")
    parser.add_argument("--all", action="store_true", help="Run all experiments")
    args = parser.parse_args()

    table = load_table()
    completed_ids = {e["experiment_id"] for e in table}

    exps_to_run = EXPERIMENTS
    if args.exp:
        exps_to_run = [e for e in EXPERIMENTS if e["id"] == args.exp]
    elif not args.all:
        print("Use --all to run all experiments or --exp <id> for a specific one.")
        print("Experiments defined:")
        for e in EXPERIMENTS:
            status = "✓ completed" if e["id"] in completed_ids else "○ pending"
            print(f"  [{status}] {e['id']}: {e['description']}")
        exit(0)

    for exp in exps_to_run:
        if exp["id"] in completed_ids:
            logger.info(f"Skipping {exp['id']} — already completed.")
            continue
        entry = run_experiment(exp)
        table.append(entry)
        save_table(table)
        logger.info(f"  {exp['id']}: best_val_macro_f1={entry['best_val_macro_f1']:.4f}")

    logger.info(f"\nExperiment table: {EXPERIMENT_TABLE_PATH}")
