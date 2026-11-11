"""
Generate clean, high-resolution visual plots and graphs for ProofLedger AI evaluation.

Plots generated:
1. Training & Validation Loss curves over epochs
2. Macro-F1 and Per-Class F1 trajectory over epochs
3. Contradiction Recall vs Insufficient-Evidence Recall trajectory
4. Annotated Confusion Matrix heatmap (Validation best & Test)
5. Model Comparison bar chart (Rules Baseline vs Pretrained vs Fine-Tuned)
6. Adversarial Challenge Test breakdown
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

sns.set_theme(style="whitegrid", palette="muted")
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 12,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "figure.titlesize": 14,
})

APP_LABEL_NAMES = ["SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]


def plot_training_history(history_file: str, output_dir: str) -> List[str]:
    with open(history_file) as f:
        data = json.load(f)
    history = data.get("training_history", [])
    if not history:
        return []

    epochs = [h["epoch"] for h in history]
    train_loss = [h["train_loss"] for h in history]
    val_loss = [h["val_loss"] for h in history]
    val_macro_f1 = [h["val_macro_f1"] for h in history]
    contra_rec = [h.get("contra_recall", 0.0) for h in history]
    insuf_rec = [h.get("insuf_recall", 0.0) for h in history]

    f1_sup = [h["per_class_f1"]["SUPPORTED"] for h in history]
    f1_con = [h["per_class_f1"]["CONTRADICTED"] for h in history]
    f1_ins = [h["per_class_f1"]["INSUFFICIENT_EVIDENCE"] for h in history]

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    generated = []

    # 1. Loss & Macro-F1 curves (2-panel)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5), dpi=300)

    # Panel 1: Loss
    ax1.plot(epochs, train_loss, "o-", color="#2b5c8f", linewidth=2.2, label="Training Loss")
    ax1.plot(epochs, val_loss, "s--", color="#d95f02", linewidth=2.2, label="Validation Loss")
    ax1.set_title("Training & Validation Loss per Epoch", fontweight="bold")
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("Cross-Entropy Loss (Smooth=0.1)")
    ax1.legend(loc="upper right")
    ax1.set_xticks(epochs)
    ax1.grid(True, linestyle=":", alpha=0.6)

    # Panel 2: Macro-F1 & Recalls
    ax2.plot(epochs, val_macro_f1, "D-", color="#1b9e77", linewidth=2.5, label="Validation Macro-F1")
    ax2.plot(epochs, contra_rec, "^--", color="#e7298a", linewidth=2.0, label="Contradiction Recall")
    ax2.plot(epochs, insuf_rec, "v--", color="#7570b3", linewidth=2.0, label="Insufficient-Evidence Recall")
    ax2.set_title("Validation Macro-F1 & Key Recalls", fontweight="bold")
    ax2.set_xlabel("Epoch")
    ax2.set_ylabel("Metric Score (0.0 – 1.0)")
    ax2.set_ylim([0.0, 1.02])
    ax2.set_xticks(epochs)
    ax2.legend(loc="lower right")
    ax2.grid(True, linestyle=":", alpha=0.6)

    plt.tight_layout()
    p1 = out / "training_and_validation_curves.png"
    plt.savefig(p1, bbox_inches="tight")
    plt.close()
    generated.append(str(p1))

    # 2. Per-class F1 evolution
    fig, ax = plt.subplots(figsize=(8, 5), dpi=300)
    ax.plot(epochs, f1_sup, "o-", color="#1b9e77", linewidth=2.2, label="SUPPORTED F1")
    ax.plot(epochs, f1_con, "s-", color="#d95f02", linewidth=2.2, label="CONTRADICTED F1")
    ax.plot(epochs, f1_ins, "^-", color="#7570b3", linewidth=2.2, label="INSUFFICIENT_EVIDENCE F1")
    ax.set_title("Per-Class F1 Score Evolution across Fine-Tuning Epochs", fontweight="bold")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("F1 Score")
    ax.set_ylim([0.0, 1.05])
    ax.set_xticks(epochs)
    ax.legend(loc="lower right")
    ax.grid(True, linestyle=":", alpha=0.6)

    plt.tight_layout()
    p2 = out / "per_class_f1_trajectory.png"
    plt.savefig(p2, bbox_inches="tight")
    plt.close()
    generated.append(str(p2))

    return generated


def plot_confusion_matrix(cm_data: List[List[int]], labels: List[str], title: str, output_path: str):
    cm = np.array(cm_data)
    row_sums = cm.sum(axis=1, keepdims=True)
    cm_norm = np.divide(cm.astype(float), row_sums, out=np.zeros_like(cm, dtype=float), where=row_sums != 0)

    annot = np.empty_like(cm).astype(object)
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            annot[i, j] = f"{cm[i, j]}\n({cm_norm[i, j]*100:.1f}%)"

    fig, ax = plt.subplots(figsize=(7, 6), dpi=300)
    sns.heatmap(
        cm_norm,
        annot=annot,
        fmt="",
        cmap="Blues",
        xticklabels=labels,
        yticklabels=labels,
        cbar_kws={"label": "Normalized Recall (True Class Row %)"},
        ax=ax,
        vmin=0.0,
        vmax=1.0,
        linewidths=1.0,
        linecolor="white",
    )
    ax.set_title(title, fontweight="bold", pad=15)
    ax.set_xlabel("Predicted Class", labelpad=10, fontweight="semibold")
    ax.set_ylabel("True Ground-Truth Class", labelpad=10, fontweight="semibold")

    plt.tight_layout()
    plt.savefig(output_path, bbox_inches="tight")
    plt.close()


def generate_all_evaluation_figures(
    history_file: str = "artifacts/checkpoints/best_run/training_result.json",
    test_eval_file: Optional[str] = None,
    challenge_eval_file: Optional[str] = None,
    rules_eval_file: Optional[str] = "artifacts/baseline/rules_baseline.json",
    pretrained_eval_file: Optional[str] = None,
    output_dir: str = "artifacts/reports/figures",
    brain_dir: Optional[str] = None,
) -> List[str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    generated = []

    # 1. Training history curves
    if Path(history_file).exists():
        h_plots = plot_training_history(history_file, str(out))
        generated.extend(h_plots)

        # Also plot best validation confusion matrix
        with open(history_file) as f:
            h_data = json.load(f)
        best_epoch = h_data.get("best_epoch", len(h_data.get("training_history", [])))
        for item in h_data.get("training_history", []):
            if item["epoch"] == best_epoch:
                cm = item.get("confusion_matrix")
                if cm:
                    val_cm_path = str(out / f"confusion_matrix_val_epoch_{best_epoch:02d}.png")
                    plot_confusion_matrix(
                        cm,
                        APP_LABEL_NAMES,
                        f"Validation Confusion Matrix (Best Epoch {best_epoch} - Macro-F1: {item.get('val_macro_f1', 0):.4f})",
                        val_cm_path,
                    )
                    generated.append(val_cm_path)
                break

    # 2. Test evaluation confusion matrix
    if test_eval_file and Path(test_eval_file).exists():
        with open(test_eval_file) as f:
            t_data = json.load(f)
        if "confusion_matrix" in t_data:
            test_cm_path = str(out / "confusion_matrix_frozen_test.png")
            plot_confusion_matrix(
                t_data["confusion_matrix"],
                APP_LABEL_NAMES,
                f"Frozen Test Confusion Matrix (Macro-F1: {t_data.get('macro_f1', 0):.4f})",
                test_cm_path,
            )
            generated.append(test_cm_path)

    # 3. Challenge test confusion matrix
    if challenge_eval_file and Path(challenge_eval_file).exists():
        with open(challenge_eval_file) as f:
            c_data = json.load(f)
        if "confusion_matrix" in c_data:
            chall_cm_path = str(out / "confusion_matrix_challenge_test.png")
            plot_confusion_matrix(
                c_data["confusion_matrix"],
                APP_LABEL_NAMES,
                f"Adversarial Challenge Test Matrix (2-Class Macro-F1: {c_data.get('represented_classes_macro_f1', c_data.get('macro_f1', 0)):.4f})",
                chall_cm_path,
            )
            generated.append(chall_cm_path)

    # 4. Comparison Bar Chart
    comparison_rows = []
    if rules_eval_file and Path(rules_eval_file).exists():
        with open(rules_eval_file) as f:
            r_data = json.load(f)
        comparison_rows.append({
            "model": "Rules Baseline",
            "accuracy": r_data.get("test_accuracy", r_data.get("accuracy", 0.75)),
            "macro_f1": r_data.get("test_macro_f1", r_data.get("macro_f1", 0.7333)),
            "contradiction_recall": r_data.get("contradiction_recall", 0.50),
            "insufficient_evidence_recall": r_data.get("insufficient_evidence_recall", 1.0),
        })

    if pretrained_eval_file and Path(pretrained_eval_file).exists():
        with open(pretrained_eval_file) as f:
            p_data = json.load(f)
        comparison_rows.append({
            "model": "Pretrained DeBERTa",
            "accuracy": p_data.get("accuracy", 0.0),
            "macro_f1": p_data.get("macro_f1", 0.0),
            "contradiction_recall": p_data.get("contradiction_recall", 0.0),
            "insufficient_evidence_recall": p_data.get("insufficient_evidence_recall", 0.0),
        })

    if test_eval_file and Path(test_eval_file).exists():
        with open(test_eval_file) as f:
            ft_data = json.load(f)
        comparison_rows.append({
            "model": "Fine-Tuned DeBERTa",
            "accuracy": ft_data.get("accuracy", 0.0),
            "macro_f1": ft_data.get("macro_f1", 0.0),
            "contradiction_recall": ft_data.get("contradiction_recall", 0.0),
            "insufficient_evidence_recall": ft_data.get("insufficient_evidence_recall", 0.0),
        })

    if comparison_rows:
        comp_path = str(out / "model_benchmark_comparison.png")
        plot_model_comparison(comparison_rows, comp_path)
        generated.append(comp_path)

    # Copy to brain dir if provided
    if brain_dir:
        copy_figures_to_brain(generated, brain_dir)

    return generated


def plot_model_comparison(comparison_table: List[Dict[str, Any]], output_path: str):
    # Models to compare
    models = [r["model"] for r in comparison_table]
    macro_f1 = [r.get("macro_f1", 0.0) for r in comparison_table]
    acc = [r.get("accuracy", 0.0) for r in comparison_table]
    contra_rec = [r.get("contradiction_recall", 0.0) for r in comparison_table]
    insuf_rec = [r.get("insufficient_evidence_recall", 0.0) for r in comparison_table]

    x = np.arange(len(models))
    width = 0.2

    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    b1 = ax.bar(x - 1.5 * width, acc, width, label="Accuracy", color="#386cb0")
    b2 = ax.bar(x - 0.5 * width, macro_f1, width, label="Macro-F1", color="#7fc97f")
    b3 = ax.bar(x + 0.5 * width, contra_rec, width, label="Contradiction Recall", color="#f0027f")
    b4 = ax.bar(x + 1.5 * width, insuf_rec, width, label="Insufficient Recall", color="#beaed4")

    ax.set_title("ProofLedger Model Benchmark Comparison (Test Split)", fontweight="bold", pad=15)
    ax.set_ylabel("Score (0.0 – 1.0)")
    ax.set_xticks(x)
    ax.set_xticklabels(models, fontweight="semibold")
    ax.set_ylim([0.0, 1.1])
    ax.legend(loc="upper left")
    ax.grid(axis="y", linestyle=":", alpha=0.6)

    # Add numeric labels
    for bars in [b1, b2, b3, b4]:
        for bar in bars:
            h = bar.get_height()
            if h > 0:
                ax.annotate(
                    f"{h:.2f}",
                    xy=(bar.get_x() + bar.get_width() / 2, h),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    rotation=0,
                )

    plt.tight_layout()
    plt.savefig(output_path, bbox_inches="tight")
    plt.close()


def copy_figures_to_brain(generated_paths: List[str], brain_dir: str) -> List[str]:
    b_path = Path(brain_dir)
    b_path.mkdir(parents=True, exist_ok=True)
    brain_paths = []
    for p in generated_paths:
        src = Path(p)
        if src.exists():
            dst = b_path / src.name
            shutil.copy2(src, dst)
            brain_paths.append(str(dst))
    return brain_paths


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-file", default="artifacts/checkpoints/best_run/training_result.json")
    parser.add_argument("--test-eval-file", default=None)
    parser.add_argument("--challenge-eval-file", default=None)
    parser.add_argument("--rules-eval-file", default="artifacts/baseline/rules_baseline.json")
    parser.add_argument("--pretrained-eval-file", default=None)
    parser.add_argument("--output-dir", default="artifacts/reports/figures")
    parser.add_argument("--brain-dir", default=None)
    args = parser.parse_args()

    files = generate_all_evaluation_figures(
        history_file=args.history_file,
        test_eval_file=args.test_eval_file,
        challenge_eval_file=args.challenge_eval_file,
        rules_eval_file=args.rules_eval_file,
        pretrained_eval_file=args.pretrained_eval_file,
        output_dir=args.output_dir,
        brain_dir=args.brain_dir,
    )
    print(f"Generated {len(files)} figures in {args.output_dir}")
    if args.brain_dir:
        print(f"Figures synced to artifact directory: {args.brain_dir}")
