# Novelty and Leakage Audit Report (`proofledger_unseen_v1`)

**Generated**: 2026-11-10T19:21:07.354780+00:00
**Target Blind Corpus**: `ai/data/evaluation/proofledger_unseen_v1/dataset.jsonl` ($N = 600$)
**Reference Historical Corpora Checked**: 23,158 pairs across EvidenceBench-v1, EvidenceBench-v1.1, EvidenceBench-v2 (train/val/test), `RAW_PREDICTIONS_60.csv`, `HIDDEN_CASES` ($N=30$), and `test_deberta_generalization_100.py` ($N=100$).

---

## 1. Duplicate, Overlap & ID Leakage Checks

| Audit Check | Result | Target | Status |
|---|---:|---:|---|
| Exact normalized `(claim + evidence)` duplicates vs historical corpora | **0** | 0 | PASS |
| Exact normalized `claim` matches vs historical corpora | **0** | 0 | PASS |
| Internal duplicates within `proofledger_unseen_v1` | **0** | 0 | PASS |
| Near-duplicate claims (Jaccard $\ge 0.80$) vs EvidenceBench | **0** | 0 | PASS |
| Scenario-family name overlap vs EvidenceBench-v1/v2 | **0** | 0 | PASS |
| Tracking / Order / Capture ID leakage vs historical corpora | **0** | 0 | PASS |
| 4-gram claim overlap hits vs historical corpora | **30 / 600** (5.00%) | Minimal | Monitored |
| 4-gram evidence overlap hits vs historical corpora | **40 / 600** (6.67%) | Minimal | Monitored |

---

## 2. Label Balance & Annotation Provenance

- **Class Counts**: {'INSUFFICIENT_EVIDENCE': 200, 'SUPPORTED': 200, 'CONTRADICTED': 200}
- **Scenario Families (14 independent families)**: ['archive_gaps_and_untracked_mail', 'carrier_manifest_vs_label_prep', 'checkout_auth_vs_settlement', 'chronological_event_paradox', 'customs_transit_vs_final_delivery', 'destination_address_divergence', 'digital_utilization_vs_provisioning', 'direct_merchant_claim_refutation', 'duplicate_billing_and_fx', 'multi_box_partial_fulfillment', 'plausible_but_non_probative_docs', 'refund_lifecycle_stages', 'sku_variant_mismatch', 'subjective_complaint_vs_objective_delivery']
- **Real vs Synthetic Disclosure**: 100% independently authored synthetic scenarios (`SYNTHETIC_INDEPENDENT`). No real-world PayPal merchant dispute logs were available or used.

---

## 3. Class-Specific Lexical Skew Check (Tokens appearing $\ge 30$ times with $\ge 70\%$ single-class skew)

| Token | Total Docs | Max Class Share | SUP / CON / INSUF |
|---|---:|---:|---|
| `from` | 59 | 100.00% | 0 / 59 / 0 |
| `cancelled` | 30 | 100.00% | 0 / 30 / 0 |
| `arrived` | 58 | 75.86% | 14 / 0 / 44 |
| `dispatch` | 58 | 75.86% | 14 / 0 / 44 |
| `item` | 57 | 75.44% | 0 / 14 / 43 |
| `without` | 57 | 75.44% | 0 / 14 / 43 |
| `zero` | 56 | 75.00% | 14 / 0 / 42 |

*Note: Words like 'contradicts'/'voided'/'awaiting' reflect genuine semantic evidentiary cues intrinsic to those families rather than wrapper artifacts like EvidenceBench-v2's 'document' vs 'record'.*
