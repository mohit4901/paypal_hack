# ProofLedger Backend & AI Integration Completion Report

**Date:** 2026-10-30  
**Status:** Backend & AI Pipeline Ready  
**Scope:** Execution of all remaining backend tasks: EvidenceBench v1.1 frozen test evaluation, SOURCE_MISMATCH validation, PayPal sandbox integration, and dispute evidence submission endpoint.

---

## 1. EvidenceBench v1.1 Frozen Test Evaluation (Pretrained DeBERTa-v3)

In accordance with our strict governance plan, the selected production NLI model (`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`) was evaluated **exactly ONCE** on the untouched, reserved **EvidenceBench v1.1 test split** (`data/processed/evidencebench_v1_1/test.jsonl`).

Unlike v1.0, EvidenceBench v1.1 represents **all three classes** in its held-out test split across unseen scenario families (`course_access_granted_vs_accessed`, `evidence_from_unrelated_transaction`, `fully_supported_claim`, `payment_captured_vs_created`).

### Measured Empirical Test Metrics

| Metric | Measured Value (v1.1 Held-Out Test) | Notes |
|---|:---:|---|
| **Total Test Examples** | **1,664** | 3-class test with all classes represented: 688 SUPPORTED (41.35%), 554 CONTRADICTED (33.29%), 422 INSUFFICIENT (25.36%) |
| **Accuracy** | **80.77%** (1,344 / 1,664) | Zero tuning performed against this split |
| **Three-Class Macro-F1** | **0.7836** | 95% CI: [0.7637, 0.8022] (empirical bootstrap, 1,000 resamples, seed=42) |
| **Weighted-F1** | **0.8017** | Class-weighted representation |
| **Contradiction Recall** | **100.00%** (554 / 554) | Zero missed contradictions on this split (100% recall) |
| **Contradiction Precision** | **86.16%** (554 / 643) | 554 correct CONTRADICTED, 88 false from INSUFFICIENT, 1 false from SUPPORTED |
| **SUPPORTED Recall** | **80.23%** (552 / 688) | Identifies 552 of 688 verified claims |
| **Insufficient Evidence Recall** | **56.40%** (238 / 422) | 238 correct, 96 falsely SUPPORTED (22.75%), 88 falsely CONTRADICTED (20.85%) |
| **SUPPORTED False Positive Rate (FPR)** | **9.84%** (96 / 976) | Denominator: all true non-supported examples ($554 + 422 = 976$) |
| **SUPPORTED False Discovery Rate (FDR)** | **14.81%** (96 / 648) | Denominator: all predicted SUPPORTED examples ($552 + 96 = 648$) |

#### Verified Confusion Matrix (v1.1 Test Split)
```
                          Predicted SUPPORTED   Predicted CONTRADICTED   Predicted INSUFFICIENT
  True SUPPORTED [688]                    552                        1                      135
  True CONTRADICTED [554]                   0                      554                        0
  True INSUFFICIENT [422]                  96                       88                      238
```

### Scientific Insight & Safety Guardrails:
- **Benchmark Specificity**: These metrics establish baseline performance on the synthetic EvidenceBench v1.1 benchmark, not real-world PayPal dispute resolution.
- **Model Limitations**: The system identifies contradictions effectively on the held-out benchmark (100% recall, 86.16% precision). However, **it does not always leave missing evidence open**: exactly 96 insufficient-evidence cases were falsely classified as SUPPORTED (FDR: 14.81%). 
- **Risk Mitigation**: This exact risk motivates our Layer 1 deterministic validation (enforcing transaction linkage, payment status, and email consistency) and Layer 4 mandatory human approval before any dispute package is assembled or submitted.

---

## 2. SOURCE_MISMATCH Verification

We verified the exact behaviour of `DeterministicValidator` and `EvidenceCompiler` on unrelated transaction submissions:
- **Scenario**: Claim refers to `order_448518`, but the attached delivery log refers to `order_318854`.
- **Verified Behavior**:
  1. `DeterministicValidator` checks transaction reference consistency. Because evidence exclusively belongs to a different order, it flags:
     `{'check': 'source_mismatch_detected', 'passed': True, 'message': "Evidence linkage failure: records belong to ['order_318854'], not claimed order order_448518."}`
  2. The validator sets its deterministic label to **`INSUFFICIENT_EVIDENCE`** (linkage failure), explicitly avoiding an affirmative claim of contradiction.
  3. `EvidenceCompiler` recognizes `source_mismatch_detected` and guarantees the final readiness assessment outputs:
     - `final_label: "INSUFFICIENT_EVIDENCE"`
     - `readiness_issues: ["Evidence transaction linkage failure: records belong to an unrelated transaction.", ...]`
     - `evidence_readiness: "NOT_READY"`
     - `human_review_required: True`

---

## 3. PayPal Sandbox Integration Status

### Authentic Sandbox Testing Execution
The sandbox integration runner (`src/integrations/paypal_sandbox_tests.py`) was executed:
- **Environment Status**: Neither `PAYPAL_CLIENT_ID` nor `PAYPAL_CLIENT_SECRET` are currently configured in this shell environment.
- **Reporting Rule Compliance**: The test runner exited with status **`BLOCKED`** and logged:
  `[⚠] credentials_configured: BLOCKED — PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET not set.`
- **Zero Mocking**: No mocked success responses were fabricated. As required by our compliance guidelines, unconfigured credentials are honestly reported as blocked until the user provides active sandbox keys.

### Expanded Sandbox Client Capabilities (`src/integrations/paypal_client.py`)
Implemented complete REST integration methods:
1. `create_order(amount, currency, description)`: Creates sandbox order intent `CAPTURE`.
2. `capture_order(order_id)`: Captures authorization in sandbox.
3. `get_order(order_id)` & `get_capture(capture_id)`: Retrieves authentic transaction snapshots.
4. `list_disputes(page_size)` & `get_dispute(dispute_id)`: Reads active customer disputes (with permission detection for `CUSTOMER_DISPUTE.READ`).
5. `provide_dispute_evidence(dispute_id, evidence_type, evidence_info, notes)`: Submits evidence dossiers to PayPal Customer Dispute API.
6. `verify_webhook_signature(...)`: Validates incoming webhook payloads against PayPal's verification endpoint.

---

## 4. FastAPI Service Integration & Endpoints

The FastAPI service (`src/api/main.py`) has been mounted with the full dispute workflow and safety gates:
- `POST /predict`: Hybrid claim verification with DeBERTa NLI + deterministic checks.
- `POST /batch-predict`: Batch verification up to 50 items.
- `POST /validate-evidence`: Lightweight deterministic-only validation.
- `POST /paypal/disputes/{dispute_id}/submit-evidence`: Authentic dispute evidence submission endpoint.
  - **Mandatory Gate**: Strictly enforces `seller_human_approved: True`. Rejects automated submissions with HTTP 400.
  - **Credential Safety**: Returns HTTP 503 if sandbox credentials are not configured, rather than inventing fake submission confirmations.
- `GET /metrics`: Safe retrieval of precomputed benchmark summaries.
- `GET /model/info`: Runtime model inspection.

### Test Suite Execution
- **Unit Tests**: 48 passed (`pytest tests/unit -v`).
- **API Tests**: 15 passed (`pytest tests/api -v`), including human-approval validation, dispute ID mismatch rejection, and unconfigured sandbox 503 handling.
- **Total Test Suite**: **63 / 63 passed**.

---

## 5. Summary & Next Steps

The backend, AI pipeline, and PayPal integration layers are stable, reproducible, and compliant.

**Ready for Next Phase**:
1. When user is ready to connect PayPal sandbox, export `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET`.
2. Proceed to frontend dashboard construction.

