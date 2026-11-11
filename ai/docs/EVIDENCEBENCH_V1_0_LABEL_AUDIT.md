# EvidenceBench v1.0 Label & Schema Audit Report

**Date:** 2026-10-30  
**Status:** Audit & Reconciliation Completed  
**Benchmark Target:** `data/processed/evidencebench/` (Seed: 42)

---

## 1. Context & Purpose of Audit

A critical question was raised regarding an apparent discrepancy between earlier documentation notes and the latest diagnostic evaluation report for the adversarial challenge split (`challenge_test.jsonl` — 400 rows).

Earlier informal documentation noted:
- `unsupported_detail_in_correct_claim`: CONTRADICTED (?)
- `correct_date_wrong_recipient`: CONTRADICTED
- `correct_payment_no_delivery_proof`: INSUFFICIENT_EVIDENCE
- `only_one_of_multiple_supports`: INSUFFICIENT_EVIDENCE (?)

In the latest diagnostic evaluation:
- `challenge_unsupported_detail_in_correct_claim` was evaluated against ground truth `INSUFFICIENT_EVIDENCE`.
- `challenge_only_one_of_multiple_supports` was evaluated against ground truth `CONTRADICTED`.

This audit reconciles the ground truth by examining:
1. The generator source code (`src/data/generate_evidencebench.py`).
2. The raw generated dataset file on disk (`data/processed/evidencebench/challenge_test.jsonl`).
3. The dataset schema and generation report (`schema.json`, `generation_report.json`).
4. The semantic rationale of each scenario class.

---

## 2. Definitive Reconciliation of Ground Truth

### A. Generator Source Code Verification (`src/data/generate_evidencebench.py`)

1. **`ChallengeUnsupportedDetails` (lines 1003–1036)**:
   - **Scenario Family Name**: `challenge_unsupported_detail_in_correct_claim`
   - **Evidence**: Payment completed (`amount=$X`) + delivery confirmed (`delivered to Buyer`).
   - **Claim**: *"Payment was completed and file was delivered to buyer, and the buyer gave a 5-star rating."*
   - **Assigned Label**: `INSUFFICIENT_EVIDENCE`
   - **Rationale in Code**: `"Payment and delivery are supported, but the 5-star rating is not evidenced."`
   - **Semantic Logic**: The 5-star rating is an unmentioned extraneous detail. It is not refuted by the records; there is simply no evidence regarding a review rating. In standard natural language inference (NLI), an unmentioned positive attribute is `NEUTRAL` / `INSUFFICIENT_EVIDENCE`, not a `CONTRADICTION`.

2. **`ChallengeCorrectDateWrongRecipient` (lines 1039–1066)**:
   - **Scenario Family Name**: `challenge_correct_date_wrong_recipient`
   - **Evidence**: Delivery to `Recipient_B` on date $D$.
   - **Claim**: *"Delivered to Buyer_A on date D."*
   - **Assigned Label**: `CONTRADICTED`
   - **Rationale in Code**: `"Date is correct but recipient is {other}, not {buyer}."`
   - **Semantic Logic**: Direct entity contradiction.

3. **`ChallengeCorrectPaymentNoDelivery` (lines 1068–1092)**:
   - **Scenario Family Name**: `challenge_correct_payment_no_delivery_proof`
   - **Evidence**: Payment completed. No delivery record.
   - **Claim**: *"Buyer paid for and received file."*
   - **Assigned Label**: `INSUFFICIENT_EVIDENCE`
   - **Rationale in Code**: `"Payment confirmed but no delivery or download record available."`
   - **Semantic Logic**: Receipt is claimed, but the seller has provided zero delivery confirmation. Standard `INSUFFICIENT_EVIDENCE`.

4. **`ChallengeOnlyOneSupports` (lines 1094–1126)**:
   - **Scenario Family Name**: `challenge_only_one_of_multiple_supports`
   - **Evidence Record 1**: Delivery `SUCCESSFUL` at timestamp $T_1$.
   - **Evidence Record 2**: Delivery `FAILED (recipient not found)` at timestamp $T_2$ ($T_1 + 5\text{ min}$).
   - **Claim**: *"The file was successfully delivered to buyer."*
   - **Assigned Label**: `CONTRADICTED`
   - **Rationale in Code**: `"First event records delivery success, but a subsequent event records delivery failure."`
   - **Semantic Logic**: The file delivery outcome failed on the final recorded attempt. In dispute adjudication, an affirmative delivery failure log directly contradicts an unqualified claim of successful delivery.

### B. Raw Dataset File Verification (`data/processed/evidencebench/challenge_test.jsonl`)

Direct parsing of the 400 lines on disk yields:
```text
challenge_correct_date_wrong_recipient             CONTRADICTED              100 examples
challenge_correct_payment_no_delivery_proof        INSUFFICIENT_EVIDENCE     100 examples
challenge_only_one_of_multiple_supports            CONTRADICTED              100 examples
challenge_unsupported_detail_in_correct_claim      INSUFFICIENT_EVIDENCE     100 examples
```
- Total `CONTRADICTED`: 200
- Total `INSUFFICIENT_EVIDENCE`: 200
- Total `SUPPORTED`: 0

### C. Resolution of the Discrepancy

- The generator source code, the generation timestamp (`2026-10-28T08:48:01Z`), the SHA-256 hash manifest, and the raw JSONL on disk have **always** defined:
  - `challenge_unsupported_detail_in_correct_claim` as **`INSUFFICIENT_EVIDENCE`**
  - `challenge_only_one_of_multiple_supports` as **`CONTRADICTED`**
- The earlier informal table snippet was an authoring transcription error in the early scratch notes where someone conflated the standard-split `unsupported_claim_details` (which claims wrong dollar amount = CONTRADICTED) with the challenge-split `challenge_unsupported_detail_in_correct_claim` (which claims extra 5-star rating = INSUFFICIENT).
- **Audit Conclusion**: No post-hoc dataset label changes occurred. The diagnostic evaluation evaluated the exact, untouched ground-truth labels generated on October 28.

---

## 3. EvidenceBench v1.0 Scenario Flaws Documented

While the challenge set labels are internally consistent with their code generators, the audit confirms two substantive semantic design flaws in the wider EvidenceBench v1.0 benchmark:

1. **Non-Terminal State Asymmetry (`status=PENDING`)**:
   - In `PaymentCapturedVsCreated`: A `status=PENDING` capture is labeled `CONTRADICTED` for the claim *"PayPal confirmed payment capture"*.
   - In `RefundClaimMissingConfirmation`: A `status=PENDING` refund is labeled `INSUFFICIENT_EVIDENCE` for the claim *"A refund was issued"*.
   - *Impact*: Inconsistent supervision for non-terminal dispute statuses. A pending authorization is missing proof of capture confirmation, not proof that capture was refused.
2. **Order Linkage vs Factual Refutation (`evidence_from_unrelated_transaction`)**:
   - Evidence showing delivery for `order_318854` is labeled `CONTRADICTED` for a claim about `order_448518`.
   - *Semantic reality*: Proving item B was delivered does not disprove that item A was delivered. It is an **evidence linkage failure** (`SOURCE_MISMATCH`), which leaves the claim unproven (`INSUFFICIENT_EVIDENCE`).
3. **Absence of SUPPORTED Class in Held-Out Splits**:
   - Both `test.jsonl` (1,664 rows) and `challenge_test.jsonl` (400 rows) contain **0 SUPPORTED examples**.
   - *Impact*: Any metric claiming "100% 3-class Macro-F1" on these splits was mathematically distorted, as the `SUPPORTED` class was completely unrepresented.

All v1.0 files remain permanently locked as historical records.

