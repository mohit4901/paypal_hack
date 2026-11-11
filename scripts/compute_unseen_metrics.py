#!/usr/bin/env python3
"""
Step 5 & Step 6: Programmatically compute ALL evaluation metrics strictly from the saved raw
*.jsonl prediction files in FINAL_RELEASE/INDEPENDENT_GENERALIZATION_AUDIT/.

Writes:
  - FINAL_RELEASE/INDEPENDENT_GENERALIZATION_AUDIT/METRICS.json
  - FINAL_RELEASE/INDEPENDENT_GENERALIZATION_AUDIT/CONFUSION_MATRICES.json
"""
from __future__ import annotations

import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
AUDIT_DIR = ROOT / "FINAL_RELEASE" / "INDEPENDENT_GENERALIZATION_AUDIT"

LABELS = ["SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]

SYSTEM_FILES = {
    "A_candidate": ("Candidate Fine-Tuned DeBERTa-v3", AUDIT_DIR / "CANDIDATE_PREDICTIONS.jsonl"),
    "B_pretrained": ("Pretrained MoritzLaurer DeBERTa-v3 NLI", AUDIT_DIR / "PRETRAINED_PREDICTIONS.jsonl"),
    "C_legacy": ("Legacy Checkpoint (ai/artifacts/best_model)", AUDIT_DIR / "LEGACY_PREDICTIONS.jsonl"),
    "D_rules_only": ("Rules-Only Deterministic Engine", AUDIT_DIR / "RULES_ONLY_PREDICTIONS.jsonl"),
    "E_hybrid": ("Production Hybrid (Rules-First + Candidate)", AUDIT_DIR / "HYBRID_PREDICTIONS.jsonl"),
}


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def percentile(sorted_vals: List[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (p / 100.0)
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def compute_core_metrics(rows: List[Dict[str, Any]], pred_key: str = "pred_label") -> Dict[str, Any]:
    n = len(rows)
    if n == 0:
        return {}

    cm: Dict[str, Dict[str, int]] = {t: {p: 0 for p in LABELS} for t in LABELS}
    correct = 0
    for r in rows:
        t = r["gold_label"]
        p = r[pred_key]
        if t in cm and p in cm[t]:
            cm[t][p] += 1
        if t == p:
            correct += 1

    per_class = {}
    f1s = []
    weighted_f1_num = 0.0
    for lbl in LABELS:
        tp = cm[lbl][lbl]
        fp = sum(cm[t][lbl] for t in LABELS if t != lbl)
        fn = sum(cm[lbl][p] for p in LABELS if p != lbl)
        support = sum(cm[lbl].values())
        pred_support = sum(cm[t][lbl] for t in LABELS)
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
        per_class[lbl] = {
            "support": support,
            "predicted_count": pred_support,
            "precision": round(prec, 6),
            "recall": round(rec, 6),
            "f1": round(f1, 6),
        }
        f1s.append(f1)
        weighted_f1_num += support * f1

    insuf_support = sum(cm["INSUFFICIENT_EVIDENCE"].values())
    sup_support = sum(cm["SUPPORTED"].values())
    insuf_to_con = cm["INSUFFICIENT_EVIDENCE"]["CONTRADICTED"]
    sup_to_con = cm["SUPPORTED"]["CONTRADICTED"]
    non_con_support = insuf_support + sup_support

    return {
        "n": n,
        "correct": correct,
        "accuracy": round(correct / n, 6),
        "macro_f1": round(sum(f1s) / len(LABELS), 6),
        "weighted_f1": round(weighted_f1_num / n, 6),
        "per_class": per_class,
        "confusion_matrix": cm,
        "false_contradiction_metrics": {
            "insuf_to_con_count": insuf_to_con,
            "insuf_support": insuf_support,
            "insuf_to_con_rate": round(insuf_to_con / insuf_support, 6) if insuf_support else 0.0,
            "sup_to_con_count": sup_to_con,
            "sup_support": sup_support,
            "sup_to_con_rate": round(sup_to_con / sup_support, 6) if sup_support else 0.0,
            "overall_false_contradiction_count": insuf_to_con + sup_to_con,
            "non_contradicted_support": non_con_support,
            "overall_false_contradiction_rate": round((insuf_to_con + sup_to_con) / non_con_support, 6) if non_con_support else 0.0,
            "definition": "overall_false_contradiction_rate = (INSUF->CON + SUP->CON) / (INSUF + SUP)",
        },
    }


def bootstrap_cis(rows: List[Dict[str, Any]], n_boot: int = 2000, seed: int = 42) -> Dict[str, Any]:
    rng = random.Random(seed)
    n = len(rows)
    accs, mf1s, ins_fcrs, ov_fcrs = [], [], [], []
    for _ in range(n_boot):
        sample = [rows[rng.randrange(n)] for _ in range(n)]
        m = compute_core_metrics(sample)
        accs.append(m["accuracy"])
        mf1s.append(m["macro_f1"])
        ins_fcrs.append(m["false_contradiction_metrics"]["insuf_to_con_rate"])
        ov_fcrs.append(m["false_contradiction_metrics"]["overall_false_contradiction_rate"])

    accs.sort()
    mf1s.sort()
    ins_fcrs.sort()
    ov_fcrs.sort()
    return {
        "n_bootstrap": n_boot,
        "seed": seed,
        "accuracy_ci95": [round(percentile(accs, 2.5), 6), round(percentile(accs, 97.5), 6)],
        "macro_f1_ci95": [round(percentile(mf1s, 2.5), 6), round(percentile(mf1s, 97.5), 6)],
        "insuf_to_con_rate_ci95": [round(percentile(ins_fcrs, 2.5), 6), round(percentile(ins_fcrs, 97.5), 6)],
        "overall_fcr_ci95": [round(percentile(ov_fcrs, 2.5), 6), round(percentile(ov_fcrs, 97.5), 6)],
    }


def compute_calibration(rows: List[Dict[str, Any]], score_field: str = "scores", n_bins: int = 10) -> Optional[Dict[str, Any]]:
    scored = [r for r in rows if isinstance(r.get(score_field), dict)]
    if not scored:
        return None
    n = len(scored)
    bins = [{"bin_low": round(i / n_bins, 2), "bin_high": round((i + 1) / n_bins, 2), "count": 0, "sum_conf": 0.0, "sum_acc": 0.0} for i in range(n_bins)]
    brier_sum = 0.0
    for r in scored:
        sc = r[score_field]
        # Prediction implied by score_field argmax
        pred_lbl = max(LABELS, key=lambda l: float(sc.get(l, 0.0)))
        conf = float(sc.get(pred_lbl, 0.0))
        acc = 1.0 if r["gold_label"] == pred_lbl else 0.0
        b_idx = min(n_bins - 1, max(0, int(conf * n_bins)))
        bins[b_idx]["count"] += 1
        bins[b_idx]["sum_conf"] += conf
        bins[b_idx]["sum_acc"] += acc

        for lbl in LABELS:
            p = float(sc.get(lbl, 0.0))
            y = 1.0 if r["gold_label"] == lbl else 0.0
            brier_sum += (p - y) ** 2

    ece = 0.0
    bin_details = []
    for b in bins:
        c = b["count"]
        if c > 0:
            avg_conf = b["sum_conf"] / c
            avg_acc = b["sum_acc"] / c
            ece += (c / n) * abs(avg_acc - avg_conf)
            bin_details.append({
                "range": f"[{b['bin_low']:.1f}, {b['bin_high']:.1f}]",
                "count": c,
                "mean_conf": round(avg_conf, 4),
                "empirical_acc": round(avg_acc, 4),
                "gap": round(abs(avg_acc - avg_conf), 4),
            })
    return {
        "n_scored": n,
        "ece_10bin": round(ece, 6),
        "brier_score_multiclass": round(brier_sum / n, 6),
        "bins": bin_details,
    }


def compute_abstention_stats(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(rows)
    abstained = [r for r in rows if r.get("is_abstained") or r.get("operational_decision") == "NEEDS_HUMAN_REVIEW"]
    answered = [r for r in rows if not (r.get("is_abstained") or r.get("operational_decision") == "NEEDS_HUMAN_REVIEW")]
    ans_metrics = compute_core_metrics(answered) if answered else None
    abst_true = Counter(r["gold_label"] for r in abstained)
    return {
        "total": n,
        "abstained_count": len(abstained),
        "abstention_rate": round(len(abstained) / n, 6) if n else 0.0,
        "answered_count": len(answered),
        "coverage": round(len(answered) / n, 6) if n else 0.0,
        "selective_accuracy": ans_metrics["accuracy"] if ans_metrics else None,
        "selective_macro_f1": ans_metrics["macro_f1"] if ans_metrics else None,
        "selective_overall_fcr": ans_metrics["false_contradiction_metrics"]["overall_false_contradiction_rate"] if ans_metrics else None,
        "abstained_gold_distribution": dict(abst_true),
    }


def compute_family_breakdown(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_fam = defaultdict(list)
    for r in rows:
        by_fam[r["scenario_family"]].append(r)
    out = {}
    for fam in sorted(by_fam):
        sub = by_fam[fam]
        acc = sum(1 for r in sub if r["pred_label"] == r["gold_label"]) / len(sub)
        non_con = [r for r in sub if r["gold_label"] != "CONTRADICTED"]
        fcon = sum(1 for r in non_con if r["pred_label"] == "CONTRADICTED")
        out[fam] = {
            "n": len(sub),
            "accuracy": round(acc, 6),
            "false_contradictions": fcon,
            "non_con_n": len(non_con),
            "fcr": round(fcon / len(non_con), 6) if non_con else 0.0,
        }
    return out


def paired_comparison(rows_a: List[Dict[str, Any]], rows_b: List[Dict[str, Any]], n_boot: int = 2000, seed: int = 42) -> Dict[str, Any]:
    """Compare System A vs System B on identical ordered samples (McNemar exact p + paired bootstrap delta)."""
    assert len(rows_a) == len(rows_b)
    n = len(rows_a)
    both_correct = 0
    a_only = 0  # A correct, B wrong
    b_only = 0  # B correct, A wrong
    both_wrong = 0
    for ra, rb in zip(rows_a, rows_b):
        assert ra["sample_id"] == rb["sample_id"]
        ca = (ra["pred_label"] == ra["gold_label"])
        cb = (rb["pred_label"] == rb["gold_label"])
        if ca and cb:
            both_correct += 1
        elif ca and not cb:
            a_only += 1
        elif cb and not ca:
            b_only += 1
        else:
            both_wrong += 1

    # Exact two-sided binomial McNemar p-value on discordant pairs (a_only, b_only)
    m = a_only + b_only
    if m == 0:
        p_exact = 1.0
        chi2_cc = 0.0
    else:
        k = min(a_only, b_only)
        p_tail = sum(math.comb(m, i) * (0.5 ** m) for i in range(k + 1))
        p_exact = min(1.0, 2.0 * p_tail)
        chi2_cc = ((abs(a_only - b_only) - 1) ** 2) / m if abs(a_only - b_only) >= 1 else 0.0

    # Paired bootstrap delta accuracy (A - B)
    rng = random.Random(seed)
    deltas = []
    for _ in range(n_boot):
        idxs = [rng.randrange(n) for _ in range(n)]
        acc_a = sum(1 for i in idxs if rows_a[i]["pred_label"] == rows_a[i]["gold_label"]) / n
        acc_b = sum(1 for i in idxs if rows_b[i]["pred_label"] == rows_b[i]["gold_label"]) / n
        deltas.append(acc_a - acc_b)
    deltas.sort()
    obs_delta = (a_only - b_only) / n
    return {
        "n": n,
        "a_only_correct": a_only,
        "b_only_correct": b_only,
        "both_correct": both_correct,
        "both_wrong": both_wrong,
        "delta_accuracy": round(obs_delta, 6),
        "delta_accuracy_ci95": [round(percentile(deltas, 2.5), 6), round(percentile(deltas, 97.5), 6)],
        "mcnemar_chi2_cc": round(chi2_cc, 4),
        "mcnemar_exact_p": float(f"{p_exact:.3e}"),
    }


def main():
    runtime_bench = {}
    rb_path = AUDIT_DIR / "RUNTIME_BENCHMARKS.json"
    if rb_path.exists():
        runtime_bench = json.loads(rb_path.read_text(encoding="utf-8"))

    all_preds = {}
    metrics_out: Dict[str, Any] = {
        "dataset": "ai/data/evaluation/proofledger_unseen_v1/dataset.jsonl",
        "systems": {},
        "paired_comparisons_vs_candidate": {},
        "fixed_seed_random_subset_n150": {},
    }
    cm_out: Dict[str, Any] = {}

    for sys_key, (desc, path) in SYSTEM_FILES.items():
        rows = load_jsonl(path)
        all_preds[sys_key] = rows
        core = compute_core_metrics(rows)
        cis = bootstrap_cis(rows, n_boot=2000, seed=42)
        raw_cal = compute_calibration(rows, score_field="scores", n_bins=10)
        temp_cal = compute_calibration(rows, score_field="calibrated_scores", n_bins=10)
        abst = compute_abstention_stats(rows)
        fam = compute_family_breakdown(rows)
        lat = sorted(float(r["latency_ms"]) for r in rows if r.get("latency_ms") is not None)
        rb = runtime_bench.get(sys_key, {})

        metrics_out["systems"][sys_key] = {
            "description": desc,
            "source_predictions_file": str(path.relative_to(ROOT)),
            **core,
            "bootstrap_95ci": cis,
            "calibration_raw_scores": raw_cal,
            "calibration_temperature_scaled": temp_cal,
            "abstention_analysis": abst,
            "latency_ms": {
                "mean": round(sum(lat) / len(lat), 3) if lat else None,
                "p50": round(percentile(lat, 50), 3) if lat else None,
                "p95": round(percentile(lat, 95), 3) if lat else None,
                "p99": round(percentile(lat, 99), 3) if lat else None,
            },
            "runtime_profile": {
                "model_size_bytes": rb.get("model_size_bytes"),
                "load_time_ms": rb.get("load_time_ms"),
                "device": rb.get("device"),
                "truncated_count": rb.get("truncated_count"),
                "rule_triggers": rb.get("rule_triggers"),
            },
            "per_family": fam,
        }
        cm_out[sys_key] = {
            "description": desc,
            "labels_order": LABELS,
            "confusion_matrix_dict": core["confusion_matrix"],
            "confusion_matrix_rows": [[core["confusion_matrix"][t][p] for p in LABELS] for t in LABELS],
            "false_contradiction_metrics": core["false_contradiction_metrics"],
        }

    # Paired comparisons
    cand = all_preds["A_candidate"]
    for other_key in ["B_pretrained", "C_legacy", "D_rules_only", "E_hybrid"]:
        metrics_out["paired_comparisons_vs_candidate"][f"A_candidate_vs_{other_key}"] = paired_comparison(
            cand, all_preds[other_key]
        )

    # Step 6: Fixed-seed random subset evaluation (N=150, seed=20261111)
    rng = random.Random(20261111)
    n_total = len(cand)
    sub_indices = sorted(rng.sample(range(n_total), 150))
    sub_ids = [cand[i]["sample_id"] for i in sub_indices]
    metrics_out["fixed_seed_random_subset_n150"] = {
        "seed": 20261111,
        "n": 150,
        "sampled_label_distribution": dict(Counter(cand[i]["gold_label"] for i in sub_indices)),
        "sample_ids_sha256_first10": sub_ids[:10],
        "systems": {},
    }
    for sys_key, rows in all_preds.items():
        sub_rows = [rows[i] for i in sub_indices]
        m_sub = compute_core_metrics(sub_rows)
        metrics_out["fixed_seed_random_subset_n150"]["systems"][sys_key] = {
            "accuracy": m_sub["accuracy"],
            "macro_f1": m_sub["macro_f1"],
            "weighted_f1": m_sub["weighted_f1"],
            "insuf_to_con_rate": m_sub["false_contradiction_metrics"]["insuf_to_con_rate"],
            "overall_fcr": m_sub["false_contradiction_metrics"]["overall_false_contradiction_rate"],
            "confusion_matrix": m_sub["confusion_matrix"],
        }

    with (AUDIT_DIR / "METRICS.json").open("w", encoding="utf-8") as f:
        json.dump(metrics_out, f, indent=2)
    with (AUDIT_DIR / "CONFUSION_MATRICES.json").open("w", encoding="utf-8") as f:
        json.dump(cm_out, f, indent=2)

    print("=== SUMMARY TABLE (N=600 Unseen Benchmark) ===")
    for sys_key, data in metrics_out["systems"].items():
        fcr = data["false_contradiction_metrics"]
        ece = (data["calibration_raw_scores"] or {}).get("ece_10bin")
        print(
            f"{sys_key:14s} | Acc={data['accuracy']*100:6.2f}% | MacroF1={data['macro_f1']:6.4f} | "
            f"INSUF->CON={fcr['insuf_to_con_rate']*100:5.2f}% | OverallFCR={fcr['overall_false_contradiction_rate']*100:5.2f}% | "
            f"ECE={str(ece):8s} | Lat_p50={data['latency_ms']['p50']}ms"
        )
    print("\n=== FIXED-SEED SUBSET (N=150, seed=20261111) ===")
    for sys_key, data in metrics_out["fixed_seed_random_subset_n150"]["systems"].items():
        print(
            f"{sys_key:14s} | Acc={data['accuracy']*100:6.2f}% | MacroF1={data['macro_f1']:6.4f} | "
            f"INSUF->CON={data['insuf_to_con_rate']*100:5.2f}% | OverallFCR={data['overall_fcr']*100:5.2f}%"
        )


if __name__ == "__main__":
    main()

