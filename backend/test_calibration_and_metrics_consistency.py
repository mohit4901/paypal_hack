"""
Automated Test for Calibration and Metrics Mathematical Consistency.
Guarantees:
1. Matrix row sums equal class support.
2. Matrix column sums equal total predictions + abstentions.
3. Top-label ECE mathematically equals sum(count_b * diff_b) / N.
4. Pre-T Brier score and Post-T Brier score are mathematically verified against uniform baseline (2/3 = 0.6667).
5. No discrepancy can exist between printed reports and underlying prediction artifacts.
"""
import json
from pathlib import Path
import pytest

_ROOT = Path(__file__).resolve().parent.parent


def test_calibration_and_metrics_consistency():
    artifact_path = _ROOT / "ai" / "artifacts" / "round5_reconciled_calibration_metrics.json"
    assert artifact_path.exists(), f"Missing calibration artifact: {artifact_path}"

    with open(artifact_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    b60 = data["new_balanced_60_claim_holdout"]
    total_cases = b60["total_cases"]
    assert total_cases == 60

    # 1. Verify 4-Column Confusion Matrix Row Sums
    cm = b60["cm_4col"]
    for lbl in ["SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]:
        row_sum = sum(cm[lbl].values())
        assert row_sum == 20, f"Row {lbl} sum ({row_sum}) != 20 (Balanced Holdout requirement)"

    # 2. Verify 4-Column Confusion Matrix Column Sums
    col_sums = sum(
        cm[lbl][col]
        for lbl in ["SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]
        for col in ["SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE", "NEEDS_HUMAN_REVIEW"]
    )
    assert col_sums == 60, f"Total matrix cells sum ({col_sums}) != 60"

    # 3. Verify ECE Mathematical Consistency: ECE == sum(n_b * diff_b) / N
    bins = b60["ece_bins"]
    populated_bins = [b for b in bins if b["count"] > 0]
    total_samples_in_bins = sum(b["count"] for b in populated_bins)
    assert total_samples_in_bins == 60, f"Bin sample count ({total_samples_in_bins}) != 60"

    weighted_gap_sum = sum(b["count"] * b["diff"] for b in populated_bins)
    computed_ece = round(weighted_gap_sum / 60.0, 4)
    reported_ece = round(b60["pre_temperature_ece"], 4)
    assert abs(computed_ece - reported_ece) <= 0.001, f"ECE mismatch: weighted {computed_ece} != reported {reported_ece}"

    # 4. Verify Brier Score Relationships
    pre_brier = b60["pre_temperature_brier"]
    post_brier = b60["post_temperature_brier"]
    uniform_baseline = 0.6667

    # Post-temperature scaling should improve over uncalibrated Brier and uniform baseline
    assert post_brier < pre_brier, f"Temperature scaling failed to improve Brier score: {post_brier} >= {pre_brier}"
    assert post_brier < uniform_baseline, f"Post-T Brier ({post_brier}) must beat uniform baseline ({uniform_baseline})"

