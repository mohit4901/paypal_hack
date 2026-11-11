# ProofLedger Hybrid AI Architecture & Verification Pipeline

**Date:** 2026-10-30  
**Status:** Approved for Production Deployment  
**Architecture Version:** 2.0 (Hybrid Rule + NLI + Tamper-Evident Ledger + Human Review)

---

## 1. Architectural Philosophy & Problem Definition

In digital goods dispute resolution, automated evidence verification faces a fundamental trade-off:
- **Pure Machine Learning Models** are susceptible to boundary distortions, hallucinations, and out-of-distribution template shifts. A model might approve a claim based on superficial phrase matching or falsely classify missing proof as a direct contradiction.
- **Pure Rule-Based Systems** are rigid and brittle. They fail when evidence wording departs from exact keyword patterns, yet they possess deterministic accuracy on structured fields (e.g. order IDs, currency amounts, timestamps).

**ProofLedger resolves this via a 4-Layer Hybrid Pipeline**:
Deterministic validation enforces transaction linkage, payment-state consistency, recipient matching, and chronological constraints against available source records. The pretrained DeBERTa NLI backbone provides natural language comprehension over unstructured logs, the evidence compiler synthesizes source citations into a SHA-256 tamper-evident event chain, and mandatory seller review ensures human oversight before any dispute submission.

```
                              [ RAW SOURCE EVIDENCE ]
                    (PayPal API Logs + Delivery Records)
                                      │
                                      ▼
             ┌─────────────────────────────────────────────────┐
             │       LAYER 1: DETERMINISTIC VALIDATOR          │
             │  • Order ID & Reference Consistency             │
             │  • Explicit SOURCE_MISMATCH Detection           │
             │  • Event Chronology & Sequence Constraints      │
             │  • Email & Identity Cross-Verification          │
             │  • Conflicting Delivery Outcome Detection       │
             └────────────────────────┬────────────────────────┘
                                      │
                                      ▼
             ┌─────────────────────────────────────────────────┐
             │      LAYER 2: PRETRAINED DeBERTa-v3 NLI         │
             │  • Natural Language Inference (500K+ MNLI/FEVER)│
             │  • Mapped Labels: SUPP / CONTRA / INSUF         │
             │  • Semantic Nuance & Contextual Alignment       │
             └────────────────────────┬────────────────────────┘
                                      │
                                      ▼
             ┌─────────────────────────────────────────────────┐
             │         LAYER 3: EVIDENCE COMPILER              │
             │  • Rule-Model Disagreement Escalation           │
             │  • Source-Linked Evidence Citation Bundling     │
             │  • SHA-256 Tamper-Evident Event Chain Logging   │
             │  • Evidence Readiness Diagnostic Formulation    │
             └────────────────────────┬────────────────────────┘
                                      │
                                      ▼
             ┌─────────────────────────────────────────────────┐
             │           LAYER 4: HUMAN APPROVAL               │
             │  • Seller Review of Readiness & Source Records  │
             │  • Failed Checks & Disagreements Inspection     │
             │  • Mandatory Explicit Approval Before Submit    │
             └─────────────────────────────────────────────────┘
```

---

## 2. Detailed Pipeline Layers

### Layer 1: Deterministic Validator (`src/models/deterministic_validator.py`)
- **Scope & Role**: Enforces transaction linkage, payment-state consistency, recipient matching, and chronological constraints against available source records.
- **Order Consistency & Source Mismatch**:
  Scans all evidence records for transaction references. If evidence exclusively belongs to a different transaction reference (`other_order_id != target_order_id`), the validator flags an explicit `source_mismatch_detected: True`. This is categorized as **`INSUFFICIENT_EVIDENCE` (Evidence Linkage Failure)** rather than a factual refutation.
- **Event Chronology**:
  Parses ISO 8601 timestamps and checks that delivery download does not precede payment capture. Impossible sequences trigger `CONTRADICTED`.
- **Delivery Conflict Detection**:
  Scans records for concurrent `SUCCESS` and `FAILED` delivery statuses on the same order. Conflicting statuses trigger `CONTRADICTED`.
- **Recipient Verification**:
  Extracts RFC 5322 email patterns across PayPal API logs and delivery logs. Name-only matches without email corroboration are flagged as insufficient for identity proof.

> [!IMPORTANT]
> **Deterministic Boundary**: Deterministic rules only validate the records received. They cannot independently prove that the original event was authentic, that the source account was uncompromised, or that an email address belongs to the real customer. They enforce structural constraints against available source data.

### Layer 2: Pretrained DeBERTa-v3 NLI (`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`)
- **Backbone Weights**: Multi-task NLI model pretrained on MNLI, FEVER, and ANLI.
- **Runtime Label Mapping**:
  - `entailment` $\rightarrow$ `SUPPORTED`
  - `contradiction` $\rightarrow$ `CONTRADICTED`
  - `neutral` $\rightarrow$ `INSUFFICIENT_EVIDENCE`
- **Output Confidence**: Reported as raw softmax output. Uncalibrated model scores are never presented as calibrated dispute probabilities.

### Layer 3: Evidence Compiler & Tamper-Evident Chain (`src/models/evidence_compiler.py`)
- **Attribution & Citation**:
  Every assertion in the compiled dossier is linked to explicit source identifiers (`[SOURCE_TYPE|EVIDENCE_ID]`). The compiler never synthesizes or hallucinates evidence IDs.
- **Disagreement Handling**:
  If the Deterministic Validator outputs `INSUFFICIENT_EVIDENCE` (e.g. source linkage failure) but the NLI model outputs `CONTRADICTED`, the compiler flags `rule_model_disagreement: true` and marks `human_review_required: true`.
- **Tamper-Evident Event Chain (`EventLog`)**:
  Appends each evidence event with a SHA-256 hash incorporating the previous event's hash (`genesis` $\rightarrow H_1 \rightarrow H_2 \dots$).
  *Technical Boundary*: The hash chain reveals post-hoc tampering or alteration of recorded events; it does not by itself prove the authenticity or real-world veracity of the original source records.

### Layer 4: Mandatory Human Review & Safety Gates
- Every API response returns `human_review_required: true` and `human_approved: false`.
- **Explicit Seller Review**: Reviewers are shown original records, failed checks, and model disagreements.
- **No Auto-Submission**: ProofLedger never auto-submits dispute packages to PayPal. Sellers must review all flagged discrepancies and explicitly confirm submission.
- **Product Scope**: ProofLedger assists sellers in organizing and validating fulfilment evidence. It does not determine PayPal Seller Protection eligibility, replace PayPal's dispute process, or guarantee dispute outcomes.

---

## 3. Discrepancy & Edge-Case Handling Rules

| Scenario | Layer 1 (Rules) | Layer 2 (NLI) | Layer 3 (Compiler Action) | Final Recommendation |
|---|---|---|---|---|
| **Evidence from Unrelated Transaction** | `source_mismatch: False` (`INSUFFICIENT`) | `CONTRADICTED` | Disagreement flagged. Source mismatch highlighted. | "Order linkage failure. Evidence belongs to a different order. Do not submit." |
| **Missing Delivery Timestamp** | `delivery_recorded: True` | `INSUFFICIENT` | Unmentioned date detail marked missing. | "Delivery confirmed but date is unverified. Obtain timestamp log." |
| **Conflicting Delivery Records** | `no_conflicting_delivery: False` (`CONTRADICTED`) | `CONTRADICTED` | Both systems agree on contradiction. | "Affirmative delivery failure record found. Do not submit." |
| **Payment Status = PENDING** | `capture_completed: False` (`INSUFFICIENT`) | `INSUFFICIENT` | Both systems recognize lack of terminal completion. | "Payment is pending. Wait for completed capture confirmation." |
| **Matching Name, Different Email** | `recipient_match: False` (`INSUFFICIENT`) | `INSUFFICIENT` / `CONTRADICTED` | Identity mismatch flagged. | "Recipient email differs from buyer account. Obtain identity proof." |

---

## 4. Verification & Production Deployment Status

- **API Runtime (`src/api/main.py`)**:
  Default model path configured to `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`.
- **Test Suite Passing**:
  60/60 unit and API tests passing (`48 unit tests + 12 FastAPI integration tests`).
- **Research Artifacts Preserved**:
  Fine-tuned checkpoints safely preserved in `artifacts/checkpoints/` and `artifacts/best_model/` for future academic and diagnostic study.

