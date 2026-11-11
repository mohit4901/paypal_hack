# EvidenceBench v1.1 Benchmark Validation & Reservation Report

**Date:** 2026-10-30  
**Benchmark Target:** `data/processed/evidencebench_v1_1/`  
**Dataset Generation Seed:** `1042`  
**Version:** 1.1

---

## 1. Motivation for Benchmark Revision

The diagnostic audit of EvidenceBench v1.0 identified two significant structural limitations:
1. **Unrepresented Class in Held-Out Test Splits**: Both `test.jsonl` and `challenge_test.jsonl` had zero `SUPPORTED` examples, preventing complete three-class evaluation.
2. **Semantic Inconsistencies in Non-Terminal Payment States**: `status=PENDING` was supervised as `CONTRADICTED` in payment capture scenarios, but as `INSUFFICIENT_EVIDENCE` in refund scenarios.

---

## 2. EvidenceBench v1.1 Design Specifications

1. **Reconciled Semantics**:
   - `PaymentCapturedVsCreated`: `status=PENDING` is standardized to `INSUFFICIENT_EVIDENCE` for the claim *"PayPal confirmed payment capture"*. (An uncompleted authorization does not disprove future capture; it represents lack of confirmed proof).
   - `RefundClaimMissingConfirmation`: `status=PENDING` remains `INSUFFICIENT_EVIDENCE`.
2. **Group-Based Scenario Family Split (Seed: 1042)**:
   - Partitioned strictly by scenario family with zero family overlap between train, validation, and test.
3. **Representation Across All 3 Classes in All Splits**:
   - Training, validation, and test splits all contain robust counts of `SUPPORTED`, `CONTRADICTED`, and `INSUFFICIENT_EVIDENCE`.

---

## 3. Verified Split Distribution & Manifest

| Split | N Examples | SUPPORTED | CONTRADICTED | INSUFFICIENT_EVIDENCE | Scenario Families Included |
|---|:---:|:---:|:---:|:---:|---|
| **Train** | 6,656 | 1,636 (24.6%) | 1,790 (26.9%) | 3,230 (48.5%) | 16 scenario families |
| **Validation** | 1,664 | 209 (12.6%) | 623 (37.4%) | 832 (50.0%) | `missing_evidence`, `order_id_mismatch`, `tampered_event_history`, `unsupported_claim_details` |
| **Reserved Test** | 1,664 | **688 (41.3%)** | **554 (33.3%)** | **422 (25.4%)** | `course_access_granted_vs_accessed`, `evidence_from_unrelated_transaction`, `fully_supported_claim`, `payment_captured_vs_created` |
| **Challenge Test** | 400 | 0 (0.0%) | 200 (50.0%) | 200 (50.0%) | 4 adversarial challenge families |

---

## 4. Strict Benchmark Reservation Policy

> [!CAUTION]
> In accordance with rigorous ML governance principles:
> 1. **Zero Inspection of Test Split**: The test split `data/processed/evidencebench_v1_1/test.jsonl` has been generated and validated for structural schema compliance only.
> 2. **No Model Selection or Hyperparameter Tuning**: No model has been evaluated on `test.jsonl` of v1.1. It is strictly frozen as an untouched test set for the next scientific experiment.
> 3. **Validation Set Governance**: Future model tuning must occur exclusively against `data/processed/evidencebench_v1_1/validation.jsonl`.

