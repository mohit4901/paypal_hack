# Dataset Card — ProofLedger Datasets

## Overview

ProofLedger uses three distinct data sources with different roles, licences, and provenance.

| Dataset | Type | Source | Licence | Role |
|---|---|---|---|---|
| FEVEROUS | Real-world public | Hugging Face / fever.ai | CC BY-SA 3.0 | General NLI pre-training / ablation |
| EvidenceBench | Synthetic (generated) | This project | Proprietary | Primary domain training + evaluation |
| PayPal Sandbox | API integration data | PayPal Sandbox | PayPal TOS | Integration testing only |

---

## Dataset 1 — FEVEROUS

| Field | Value |
|---|---|
| **Official name** | FEVEROUS: Fact Extraction and VERification Over Unstructured and Structured information |
| **HF dataset ID** | `fever/feverous` |
| **Paper** | [OpenReview](https://openreview.net/forum?id=h-flVCIlstW) |
| **DOI** | https://doi.org/10.5281/zenodo.4911508 |
| **Licence** | CC BY-SA 3.0 |
| **Downloaded from** | Hugging Face Hub (`fever/feverous`) |
| **Trust remote code** | Required (`trust_remote_code=True`) — script reviewed before use |
| **Splits used** | `train` (71,291) and `validation` (7,890) |
| **Blind test excluded** | Yes — the unlabelled test split is not used |

### Label encoding (actual, verified from dataset)

| Integer | String meaning | Mapped to |
|---|---|---|
| `0` | `SUPPORTS` | `SUPPORTED` |
| `1` | `REFUTES` | `CONTRADICTED` |
| `2` | `NOT ENOUGH INFO` | `INSUFFICIENT_EVIDENCE` |

### Evidence structure

FEVEROUS evidence is structured as reference lists:
- `content`: cell/sentence reference IDs (e.g., `Page_cell_1_2_0`)
- `context`: nested lists containing actual text fragments

The parser (`src/data/parse_feverous.py`) extracts text from `context` fields, filters out pure reference IDs, and concatenates the result as evidence text.

### Parsed statistics

| Split | Processed | Excluded | SUPPORTED | CONTRADICTED | INSUFFICIENT_EVIDENCE |
|---|---|---|---|---|---|
| train | 71,291 | 0 | 41,835 | 27,215 | 2,241 |
| validation | 7,890 | 0 | 3,908 | 3,481 | 501 |

### Attribution requirement

Any redistribution must preserve the CC BY-SA 3.0 licence and cite:

> Aly, R., et al. (2021). FEVEROUS: Fact Extraction and VERification Over Unstructured and Structured information. *Proceedings of NeurIPS 2021 Datasets and Benchmarks Track.*

---

## Dataset 2 — EvidenceBench

| Field | Value |
|---|---|
| **Type** | Fully synthetic — programmatically generated |
| **Generator** | `src/data/generate_evidencebench.py` |
| **Seed** | 42 (fixed for reproducibility) |
| **Licence** | Proprietary — synthetic only, no real customer data |
| **Contains real data** | **No** |
| **Contains real PayPal records** | **No** |

### Schema

```json
{
  "example_id": "evb_0000001",
  "scenario_family": "payment_captured_vs_created",
  "claim": "PayPal confirmed the payment capture for order order_123456.",
  "evidence": [
    {
      "evidence_id": "cap_789012",
      "source_type": "paypal_api",
      "timestamp": "2025-03-15T08:30:00Z",
      "content": "Capture cap_789012 status=COMPLETED amount=49.99 USD order=order_123456."
    }
  ],
  "label": "SUPPORTED",
  "label_rationale": "Capture event shows COMPLETED status matching the claimed order.",
  "is_synthetic": true
}
```

### Splits and counts

| Split | Count | Label distribution |
|---|---|---|
| train | 6,656 | SUPPORTED: 2234, CONTRADICTED: 1695, INSUFFICIENT_EVIDENCE: 2727 |
| validation | 1,664 | (group-separated families) |
| test | 1,664 | (group-separated families) |
| challenge_test | 400 | Adversarial cases |

### Split strategy

**Group-based splitting** by scenario family:
- 4 families held out for validation
- 4 different families held out for test
- Remaining families used for training
- No scenario family appears in more than one split

This prevents the model from learning template-specific surface patterns and being evaluated on identical patterns. TF-IDF+LR performance collapses on the test split (macro-F1 = 0.18), confirming the leakage prevention works.

### Scenario families (24 total)

1. payment_captured_vs_created
2. licence_issued_vs_accessed
3. file_sent_vs_downloaded
4. delivery_timestamp_mismatch
5. recipient_mismatch
6. order_id_mismatch
7. course_access_granted_vs_accessed
8. asset_version_mismatch
9. impossible_event_order
10. missing_evidence
11. conflicting_delivery_events
12. multiple_records_supporting
13. claim_broader_than_evidence
14. unsupported_claim_details
15. currency_amount_mismatch
16. refund_claim_missing_confirmation
17. evidence_from_unrelated_transaction
18. tampered_event_history
19. conflicting_status_snapshots
20. plausible_but_unestablished
21. fully_supported_claim
22. multiple_conflicting_records
23. incomplete_records_unknown_verdict
24. delivery_timestamp_missing

### Challenge families (4, for adversarial testing only)

1. challenge_unsupported_detail_in_correct_claim
2. challenge_correct_date_wrong_recipient
3. challenge_correct_payment_no_delivery_proof
4. challenge_only_one_of_multiple_supports

> [!CAUTION]
> The challenge_test.jsonl must NOT be used for model selection or hyperparameter tuning.

---

## Dataset 3 — PayPal Sandbox Records

| Field | Value |
|---|---|
| **Type** | API integration test records |
| **Source** | PayPal Sandbox API (real API, not production) |
| **Role** | Integration testing and schema validation only |
| **Used for training** | No |
| **Credentials required** | Yes — `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` |

### Access status

| Operation | Status | Reason |
|---|---|---|
| Authentication | BLOCKED | No sandbox credentials provided |
| List disputes | BLOCKED | Requires `CUSTOMER_DISPUTE.READ` scope |
| Get order | BLOCKED | No credentials |
| Webhook verification | SKIPPED | Requires incoming webhook delivery |
| Evidence submission | BLOCKED | Requires active dispute and `CUSTOMER_DISPUTE.UPDATE` scope |

See `data/processed/paypal_sandbox/integration_results.json` for detailed results.

### To unlock sandbox tests

1. Create a PayPal developer account at https://developer.paypal.com/
2. Create a sandbox app and obtain Client ID + Secret
3. Enable `CUSTOMER_DISPUTE.READ` and `CUSTOMER_DISPUTE.UPDATE` permissions
4. Set `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` environment variables
5. Run: `python -m src.integrations.paypal_sandbox_tests`

