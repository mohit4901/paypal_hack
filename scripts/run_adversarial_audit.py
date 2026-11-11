#!/usr/bin/env python3
"""
Step 7: Adversarial Robustness, Counterfactual Minimal-Pair & Lexical-Shortcut Audit.

Evaluates:
  1. 72-pair Adversarial Challenge Set across all 12 phenomena
     (ai/data/evaluation/proofledger_unseen_v1/adversarial_challenge.jsonl)
     for Candidate, Pretrained, Legacy, Rules-Only, and Production Hybrid.
  2. Counterfactual Shortcut & Minimal-Pair Probes on Candidate vs Pretrained:
     - Trigger word invariance ("document", "record", "confirmed", "delivered", "cancelled")
     - Format invariance (prose vs JSON payload vs audit log table vs bulleted ticket)
     - Negation polarity flips & numeric/currency perturbations
     - Irrelevant distractor padding sensitivity

Writes:
  - FINAL_RELEASE/INDEPENDENT_GENERALIZATION_AUDIT/ADVERSARIAL_PREDICTIONS.json
  - FINAL_RELEASE/INDEPENDENT_GENERALIZATION_AUDIT/ADVERSARIAL_ROBUSTNESS_REPORT.md
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ai"))
sys.path.insert(0, str(ROOT / "ai" / "src"))

from src.models.evidence_verifier import EvidenceVerifier
from src.models.input_format import EvidenceRecord
from backend.services.dispute_service import DisputeVerificationService

ADV_PATH = ROOT / "ai" / "data" / "evaluation" / "proofledger_unseen_v1" / "adversarial_challenge.jsonl"
AUDIT_DIR = ROOT / "FINAL_RELEASE" / "INDEPENDENT_GENERALIZATION_AUDIT"

CANDIDATE_PATH = str(ROOT / "ai" / "artifacts" / "candidates" / "deberta_v3_inr_v1" / "best")
PRETRAINED_ID = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
LEGACY_PATH = str(ROOT / "ai" / "artifacts" / "best_model")


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_counterfactual_probes() -> List[Dict[str, Any]]:
    """
    Minimal counterfactual pairs designed to test lexical shortcut reliance,
    format invariance, negation polarity, and distractor robustness.
    """
    return [
        # 1. Lexical cue "document" / "record" inserted into neutral/insufficient evidence
        {
            "probe_id": "CF-LEX-DOC-01",
            "category": "lexical_shortcut_neutral_cue",
            "description": "Adding neutral metadata mentioning 'document' and 'record' without proving delivery",
            "claim": "The buyer signed for parcel TRK-5501 at their front door.",
            "base_evidence": "Warehouse note for TRK-5501: shipping label created on 2026-09-10; pickup scan not yet received.",
            "perturbed_evidence": "Document record ID-900 for TRK-5501: warehouse document records label created on 2026-09-10; pickup scan not yet received.",
            "expected_base": "INSUFFICIENT_EVIDENCE",
            "expected_perturbed": "INSUFFICIENT_EVIDENCE",
        },
        # 2. Lexical cue "delivered" in negative / non-delivery context ("not yet delivered")
        {
            "probe_id": "CF-LEX-DELIV-02",
            "category": "lexical_shortcut_delivered_negation",
            "description": "Contains word 'delivered' inside negated/undelivered status",
            "claim": "Order ORD-9901 was delivered to the buyer on Sept 14.",
            "base_evidence": "Carrier status for ORD-9901 as of Sept 14: in transit at regional hub.",
            "perturbed_evidence": "Carrier status for ORD-9901 as of Sept 14: package has NOT been delivered yet; still in transit at regional hub.",
            "expected_base": "INSUFFICIENT_EVIDENCE",
            "expected_perturbed": "CONTRADICTED",
        },
        # 3. Lexical cue "cancelled" in benign non-contradicting clause
        {
            "probe_id": "CF-LEX-CANCEL-03",
            "category": "lexical_shortcut_benign_cancelled",
            "description": "Word 'cancelled' refers to fee/insurance rather than shipment",
            "claim": "Package TRK-8820 reached the buyer's address on Sept 18.",
            "base_evidence": "FedEx POD for TRK-8820: signed delivery completed on Sept 18 at recipient porch.",
            "perturbed_evidence": "FedEx POD for TRK-8820: optional Saturday redirect was cancelled by merchant so standard delivery completed on Sept 18 at recipient porch.",
            "expected_base": "SUPPORTED",
            "expected_perturbed": "SUPPORTED",
        },
        # 4. Lexical cue "confirmed" applied only to order placement, not delivery
        {
            "probe_id": "CF-LEX-CONF-04",
            "category": "lexical_shortcut_confirmed_scope",
            "description": "Email confirmed order placement/invoice, NOT carrier delivery",
            "claim": "The parcel for INV-3044 arrived at the customer's address.",
            "base_evidence": "Merchant email log for INV-3044: order receipt sent to buyer on Oct 2.",
            "perturbed_evidence": "Merchant email log for INV-3044: confirmed order placement and confirmed invoice receipt on Oct 2; no carrier tracking attached.",
            "expected_base": "INSUFFICIENT_EVIDENCE",
            "expected_perturbed": "INSUFFICIENT_EVIDENCE",
        },
        # 5. Format invariance: Prose -> JSON -> Pipe Audit Row -> Ticket
        {
            "probe_id": "CF-FMT-PROSE-05A",
            "category": "format_invariance_supported",
            "description": "Same delivery proof in plain prose vs JSON object",
            "claim": "DHL shipment 441902 was delivered to Berlin on 2026-09-21.",
            "base_evidence": "DHL tracking 441902 shows final delivery in Berlin on 2026-09-21 signed at reception.",
            "perturbed_evidence": '{"source": "DHL_WEBHOOK", "tracking": "441902", "timestamp": "2026-09-21T14:22:00Z", "city": "Berlin", "status": "DELIVERED", "pod": "signed at reception"}',
            "expected_base": "SUPPORTED",
            "expected_perturbed": "SUPPORTED",
        },
        {
            "probe_id": "CF-FMT-TABLE-05B",
            "category": "format_invariance_contradicted",
            "description": "Same refund contradiction in prose vs pipe-delimited ledger row",
            "claim": "No refund was issued for transaction TXN-6621.",
            "base_evidence": "Payment ledger shows TXN-6621 had a full refund of 95.00 EUR completed on Sept 11.",
            "perturbed_evidence": "=== LEDGER ===\nTXN_ID | TYPE | AMOUNT | CURRENCY | STATUS | DATE\nTXN-6621 | FULL_REFUND | 95.00 | EUR | COMPLETED | 2026-09-11",
            "expected_base": "CONTRADICTED",
            "expected_perturbed": "CONTRADICTED",
        },
        # 6. Numeric / currency minimal flip
        {
            "probe_id": "CF-NUM-AMT-06",
            "category": "minimal_numeric_flip",
            "description": "Exact amount 149.00 USD vs mismatched 49.00 USD",
            "claim": "PayPal captured 149.00 USD for invoice INV-7712.",
            "base_evidence": "PayPal capture record for INV-7712: status COMPLETED, gross amount 149.00 USD.",
            "perturbed_evidence": "PayPal capture record for INV-7712: status COMPLETED, gross amount 49.00 USD.",
            "expected_base": "SUPPORTED",
            "expected_perturbed": "CONTRADICTED",
        },
        {
            "probe_id": "CF-NUM-CCY-07",
            "category": "minimal_currency_flip",
            "description": "Currency USD vs GBP with identical digits",
            "claim": "The buyer paid 120.00 USD for booking BK-3310.",
            "base_evidence": "Settlement ledger for BK-3310: settled payment 120.00 USD.",
            "perturbed_evidence": "Settlement ledger for BK-3310: settled payment 120.00 GBP.",
            "expected_base": "SUPPORTED",
            "expected_perturbed": "CONTRADICTED",
        },
        # 7. Entity / city swap minimal flip
        {
            "probe_id": "CF-ENT-ADDR-08",
            "category": "minimal_entity_swap",
            "description": "Delivered to Seattle vs Delivered to Denver",
            "claim": "Package TRK-1180 was delivered to Denver, CO.",
            "base_evidence": "UPS tracking TRK-1180 confirms delivery in Denver, CO at 11:05 AM.",
            "perturbed_evidence": "UPS tracking TRK-1180 confirms delivery in Seattle, WA at 11:05 AM.",
            "expected_base": "SUPPORTED",
            "expected_perturbed": "CONTRADICTED",
        },
        # 8. Distractor / noise tolerance (adding irrelevant invoice metadata should not flip)
        {
            "probe_id": "CF-NOISE-09",
            "category": "irrelevant_distractor_noise",
            "description": "Appending irrelevant policy boilerplate to insufficient tracking stub",
            "claim": "The digital license key for ORD-5102 was activated by the buyer.",
            "base_evidence": "Payment capture CAP-5102 succeeded for ORD-5102; license email queued.",
            "perturbed_evidence": "Payment capture CAP-5102 succeeded for ORD-5102; license email queued. [System notice: server backup passed at 02:00 UTC; support hours Mon-Fri; VAT rate 0%; PDF invoice template v4.2 rendered].",
            "expected_base": "INSUFFICIENT_EVIDENCE",
            "expected_perturbed": "INSUFFICIENT_EVIDENCE",
        },
    ]


def eval_verifier_on_list(verifier: EvidenceVerifier, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    preds = []
    for row in rows:
        ev = [EvidenceRecord("ev_1", "RECORD", None, row["evidence"])]
        out = verifier.predict(row["claim"], ev)
        preds.append({
            "sample_id": row["sample_id"],
            "scenario_family": row["scenario_family"],
            "gold_label": row["gold_label"],
            "pred_label": out["label"],
            "operational_decision": out["decision"],
            "is_abstained": bool(out.get("is_abstained", False)),
            "confidence": out["confidence"],
            "scores": out["scores"],
        })
    return preds


def eval_service_on_list(model_override: str, rows: List[Dict[str, Any]], rules_only: bool) -> List[Dict[str, Any]]:
    os.environ["PROOFLEDGER_MODEL_PATH"] = model_override
    svc = DisputeVerificationService()
    preds = []
    for row in rows:
        ev = [{"evidence_id": "ev_1", "source_type": "RECORD", "timestamp": None, "content": row["evidence"]}]
        res = svc.verify_single_claim(row["claim"], ev, transaction_reference="")
        ai_info = res.get("ai_model", {})
        det_trig = bool(res.get("deterministic_rule_triggered", False))
        pred_lbl = res["verdict"] if (rules_only or det_trig) else (ai_info.get("label") or res["verdict"])
        preds.append({
            "sample_id": row["sample_id"],
            "scenario_family": row["scenario_family"],
            "gold_label": row["gold_label"],
            "pred_label": pred_lbl,
            "operational_decision": res["verdict"],
            "is_abstained": bool(res.get("is_abstained", False) or res["verdict"] == "NEEDS_HUMAN_REVIEW"),
            "deterministic_rule_triggered": det_trig,
        })
    os.environ.pop("PROOFLEDGER_MODEL_PATH", None)
    return preds


def summarize_adv(preds: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(preds)
    acc = sum(1 for r in preds if r["pred_label"] == r["gold_label"]) / n
    non_con = [r for r in preds if r["gold_label"] != "CONTRADICTED"]
    fcr = sum(1 for r in non_con if r["pred_label"] == "CONTRADICTED") / len(non_con)
    ins = [r for r in preds if r["gold_label"] == "INSUFFICIENT_EVIDENCE"]
    ins_fcr = sum(1 for r in ins if r["pred_label"] == "CONTRADICTED") / len(ins)
    by_fam = defaultdict(list)
    for r in preds:
        by_fam[r["scenario_family"]].append(r)
    fam_summary = {}
    for fam in sorted(by_fam):
        sub = by_fam[fam]
        fam_nc = [x for x in sub if x["gold_label"] != "CONTRADICTED"]
        fam_fc = sum(1 for x in fam_nc if x["pred_label"] == "CONTRADICTED")
        fam_summary[fam] = {
            "n": len(sub),
            "correct": sum(1 for x in sub if x["pred_label"] == x["gold_label"]),
            "accuracy": round(sum(1 for x in sub if x["pred_label"] == x["gold_label"]) / len(sub), 4),
            "false_contradictions": fam_fc,
        }
    return {
        "n": n,
        "correct": sum(1 for r in preds if r["pred_label"] == r["gold_label"]),
        "accuracy": round(acc, 4),
        "insuf_to_con_rate": round(ins_fcr, 4),
        "overall_fcr": round(fcr, 4),
        "abstained_count": sum(1 for r in preds if r.get("is_abstained")),
        "per_family": fam_summary,
    }


def main():
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    adv_rows = load_jsonl(ADV_PATH)
    assert len(adv_rows) == 72, f"Expected 72 adversarial rows, got {len(adv_rows)}"

    cand_v = EvidenceVerifier(model_path=CANDIDATE_PATH)
    cand_v.load()
    pre_v = EvidenceVerifier(model_path=PRETRAINED_ID)
    pre_v.load()
    leg_v = EvidenceVerifier(model_path=LEGACY_PATH)
    leg_v.load()

    adv_preds = {
        "A_candidate": eval_verifier_on_list(cand_v, adv_rows),
        "B_pretrained": eval_verifier_on_list(pre_v, adv_rows),
        "C_legacy": eval_verifier_on_list(leg_v, adv_rows),
        "D_rules_only": eval_service_on_list("/tmp/rules_only_adv", adv_rows, rules_only=True),
        "E_hybrid": eval_service_on_list(CANDIDATE_PATH, adv_rows, rules_only=False),
    }
    adv_summaries = {k: summarize_adv(v) for k, v in adv_preds.items()}

    # Counterfactual Probes (Candidate vs Pretrained)
    probes = build_counterfactual_probes()
    probe_results = []
    for p in probes:
        c_base = cand_v.predict(p["claim"], [EvidenceRecord("ev_1", "RECORD", None, p["base_evidence"])])
        c_pert = cand_v.predict(p["claim"], [EvidenceRecord("ev_1", "RECORD", None, p["perturbed_evidence"])])
        p_base = pre_v.predict(p["claim"], [EvidenceRecord("ev_1", "RECORD", None, p["base_evidence"])])
        p_pert = pre_v.predict(p["claim"], [EvidenceRecord("ev_1", "RECORD", None, p["perturbed_evidence"])])
        probe_results.append({
            "probe_id": p["probe_id"],
            "category": p["category"],
            "description": p["description"],
            "expected_base": p["expected_base"],
            "expected_perturbed": p["expected_perturbed"],
            "candidate_base": c_base["label"],
            "candidate_base_conf": round(c_base["confidence"], 4),
            "candidate_perturbed": c_pert["label"],
            "candidate_perturbed_conf": round(c_pert["confidence"], 4),
            "candidate_passed_both": (c_base["label"] == p["expected_base"] and c_pert["label"] == p["expected_perturbed"]),
            "pretrained_base": p_base["label"],
            "pretrained_perturbed": p_pert["label"],
            "pretrained_passed_both": (p_base["label"] == p["expected_base"] and p_pert["label"] == p["expected_perturbed"]),
        })

    # Inspect candidate failure examples on adversarial set
    cand_failures = [
        {
            "sample_id": r["sample_id"],
            "family": r["scenario_family"],
            "gold": r["gold_label"],
            "pred": r["pred_label"],
            "conf": round(r["confidence"], 4),
            "claim": next(x["claim"] for x in adv_rows if x["sample_id"] == r["sample_id"]),
            "evidence": next(x["evidence"] for x in adv_rows if x["sample_id"] == r["sample_id"]),
        }
        for r in adv_preds["A_candidate"]
        if r["pred_label"] != r["gold_label"]
    ]

    bundle = {
        "adversarial_dataset": "ai/data/evaluation/proofledger_unseen_v1/adversarial_challenge.jsonl",
        "n_adversarial": len(adv_rows),
        "summaries": adv_summaries,
        "candidate_failures": cand_failures,
        "counterfactual_probes": probe_results,
        "raw_predictions": adv_preds,
    }
    (AUDIT_DIR / "ADVERSARIAL_PREDICTIONS.json").write_text(json.dumps(bundle, indent=2), encoding="utf-8")

    # Build clean factual Markdown report
    lines = [
        "# Adversarial Robustness & Counterfactual Shortcut Audit",
        "",
        f"**Challenge Dataset**: `ai/data/evaluation/proofledger_unseen_v1/adversarial_challenge.jsonl` (`N = {len(adv_rows)}` across 12 phenomenon categories)",
        "",
        "## 1. Overall Adversarial Challenge Performance (N = 72)",
        "",
        "| System | Accuracy | Correct / N | INSUF->CON Rate | Overall FCR | Abstained (NEEDS_HUMAN_REVIEW) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    labels_map = {
        "A_candidate": "A. Candidate Fine-Tuned DeBERTa-v3",
        "B_pretrained": "B. Pretrained MoritzLaurer DeBERTa-v3 NLI",
        "C_legacy": "C. Legacy `best_model`",
        "D_rules_only": "D. Rules-Only Deterministic",
        "E_hybrid": "E. Production Hybrid (Rules + Candidate)",
    }
    for k in ["A_candidate", "B_pretrained", "C_legacy", "D_rules_only", "E_hybrid"]:
        s = adv_summaries[k]
        lines.append(
            f"| {labels_map[k]} | {s['accuracy']*100:.2f}% | {s['correct']} / {s['n']} | "
            f"{s['insuf_to_con_rate']*100:.2f}% | {s['overall_fcr']*100:.2f}% | {s['abstained_count']} |"
        )

    lines += [
        "",
        "## 2. Per-Phenomenon Breakdown (12 Challenge Categories, 6 pairs each)",
        "",
        "| Phenomenon | Candidate Acc | Pretrained Acc | Legacy Acc | Rules Acc | Hybrid Acc | Candidate False Contradictions |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    families = sorted(adv_summaries["A_candidate"]["per_family"].keys())
    for fam in families:
        ca = adv_summaries["A_candidate"]["per_family"][fam]
        pr = adv_summaries["B_pretrained"]["per_family"][fam]
        le = adv_summaries["C_legacy"]["per_family"][fam]
        ru = adv_summaries["D_rules_only"]["per_family"][fam]
        hy = adv_summaries["E_hybrid"]["per_family"][fam]
        lines.append(
            f"| `{fam}` | {ca['accuracy']*100:.1f}% ({ca['correct']}/{ca['n']}) | "
            f"{pr['accuracy']*100:.1f}% | {le['accuracy']*100:.1f}% | {ru['accuracy']*100:.1f}% | "
            f"{hy['accuracy']*100:.1f}% | {ca['false_contradictions']} |"
        )

    cand_cf_pass = sum(1 for p in probe_results if p["candidate_passed_both"])
    pre_cf_pass = sum(1 for p in probe_results if p["pretrained_passed_both"])
    lines += [
        "",
        "## 3. Minimal Counterfactual & Lexical Shortcut Probes (10 Paired Probes)",
        "",
        f"- **Candidate (`deberta_v3_inr_v1`) passed both base and perturbed**: `{cand_cf_pass} / {len(probe_results)}`",
        f"- **Pretrained baseline passed both base and perturbed**: `{pre_cf_pass} / {len(probe_results)}`",
        "",
        "| Probe ID | Category | Expected (Base -> Pert) | Candidate (Base -> Pert) | Pretrained (Base -> Pert) | Cand Pass |",
        "|---|---|---|---|---|---|",
    ]
    for p in probe_results:
        lines.append(
            f"| `{p['probe_id']}` | `{p['category']}` | `{p['expected_base']}` -> `{p['expected_perturbed']}` | "
            f"`{p['candidate_base']}` ({p['candidate_base_conf']:.2f}) -> `{p['candidate_perturbed']}` ({p['candidate_perturbed_conf']:.2f}) | "
            f"`{p['pretrained_base']}` -> `{p['pretrained_perturbed']}` | {'PASS' if p['candidate_passed_both'] else 'FAIL'} |"
        )

    lines += [
        "",
        f"## 4. Candidate Adversarial Error Log ({len(cand_failures)} errors out of {len(adv_rows)})",
        "",
    ]
    if not cand_failures:
        lines.append("Zero candidate errors recorded on the adversarial set.")
    else:
        for err in cand_failures:
            lines.append(
                f"- **`{err['sample_id']}`** (`{err['family']}`): Gold=`{err['gold']}`, Pred=`{err['pred']}` (conf={err['conf']:.3f})  \n"
                f"  Claim: _{err['claim']}_  \n"
                f"  Evidence: `{err['evidence'][:180]}{'...' if len(err['evidence']) > 180 else ''}`"
            )

    (AUDIT_DIR / "ADVERSARIAL_ROBUSTNESS_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Adversarial audit complete: Candidate={adv_summaries['A_candidate']['accuracy']*100:.2f}%, Pretrained={adv_summaries['B_pretrained']['accuracy']*100:.2f}%, CF pass={cand_cf_pass}/{len(probe_results)}")


if __name__ == "__main__":
    main()

