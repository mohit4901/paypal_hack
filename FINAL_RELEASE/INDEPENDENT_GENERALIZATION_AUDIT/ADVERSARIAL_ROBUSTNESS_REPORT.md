# Adversarial Robustness & Counterfactual Shortcut Audit

**Challenge Dataset**: `ai/data/evaluation/proofledger_unseen_v1/adversarial_challenge.jsonl` (`N = 72` across 12 phenomenon categories)

## 1. Overall Adversarial Challenge Performance (N = 72)

| System | Accuracy | Correct / N | INSUF->CON Rate | Overall FCR | Abstained (NEEDS_HUMAN_REVIEW) |
|---|---:|---:|---:|---:|---:|
| A. Candidate Fine-Tuned DeBERTa-v3 | 86.11% | 62 / 72 | 14.29% | 7.84% | 2 |
| B. Pretrained MoritzLaurer DeBERTa-v3 NLI | 66.67% | 48 / 72 | 53.57% | 29.41% | 1 |
| C. Legacy `best_model` | 55.56% | 40 / 72 | 39.29% | 29.41% | 4 |
| D. Rules-Only Deterministic | 40.28% | 29 / 72 | 0.00% | 0.00% | 0 |
| E. Production Hybrid (Rules + Candidate) | 84.72% | 61 / 72 | 14.29% | 7.84% | 2 |

## 2. Per-Phenomenon Breakdown (12 Challenge Categories, 6 pairs each)

| Phenomenon | Candidate Acc | Pretrained Acc | Legacy Acc | Rules Acc | Hybrid Acc | Candidate False Contradictions |
|---|---:|---:|---:|---:|---:|---:|
| `compound_hypotheses` | 100.0% (6/6) | 66.7% | 66.7% | 33.3% | 100.0% | 0 |
| `conflicting_dates` | 66.7% (4/6) | 66.7% | 83.3% | 33.3% | 50.0% | 0 |
| `emotional_noise` | 83.3% (5/6) | 83.3% | 50.0% | 33.3% | 83.3% | 1 |
| `long_irrelevant_context` | 100.0% (6/6) | 83.3% | 66.7% | 50.0% | 100.0% | 0 |
| `lowercase_informal` | 100.0% (6/6) | 66.7% | 66.7% | 33.3% | 100.0% | 0 |
| `misleading_relevant` | 83.3% (5/6) | 66.7% | 50.0% | 66.7% | 83.3% | 0 |
| `missing_fields` | 100.0% (6/6) | 83.3% | 33.3% | 50.0% | 100.0% | 0 |
| `negation_double_neg` | 66.7% (4/6) | 66.7% | 50.0% | 33.3% | 66.7% | 2 |
| `partial_evidence` | 100.0% (6/6) | 83.3% | 50.0% | 33.3% | 100.0% | 0 |
| `reordered_evidence` | 66.7% (4/6) | 66.7% | 50.0% | 33.3% | 66.7% | 0 |
| `shortcut_trap` | 100.0% (6/6) | 50.0% | 66.7% | 50.0% | 100.0% | 0 |
| `typos` | 66.7% (4/6) | 16.7% | 33.3% | 33.3% | 66.7% | 1 |

## 3. Minimal Counterfactual & Lexical Shortcut Probes (10 Paired Probes)

- **Candidate (`deberta_v3_inr_v1`) passed both base and perturbed**: `9 / 10`
- **Pretrained baseline passed both base and perturbed**: `7 / 10`

| Probe ID | Category | Expected (Base -> Pert) | Candidate (Base -> Pert) | Pretrained (Base -> Pert) | Cand Pass |
|---|---|---|---|---|---|
| `CF-LEX-DOC-01` | `lexical_shortcut_neutral_cue` | `INSUFFICIENT_EVIDENCE` -> `INSUFFICIENT_EVIDENCE` | `INSUFFICIENT_EVIDENCE` (0.98) -> `INSUFFICIENT_EVIDENCE` (0.97) | `CONTRADICTED` -> `INSUFFICIENT_EVIDENCE` | PASS |
| `CF-LEX-DELIV-02` | `lexical_shortcut_delivered_negation` | `INSUFFICIENT_EVIDENCE` -> `CONTRADICTED` | `INSUFFICIENT_EVIDENCE` (0.79) -> `CONTRADICTED` (0.99) | `CONTRADICTED` -> `CONTRADICTED` | PASS |
| `CF-LEX-CANCEL-03` | `lexical_shortcut_benign_cancelled` | `SUPPORTED` -> `SUPPORTED` | `SUPPORTED` (1.00) -> `SUPPORTED` (1.00) | `SUPPORTED` -> `SUPPORTED` | PASS |
| `CF-LEX-CONF-04` | `lexical_shortcut_confirmed_scope` | `INSUFFICIENT_EVIDENCE` -> `INSUFFICIENT_EVIDENCE` | `INSUFFICIENT_EVIDENCE` (0.60) -> `INSUFFICIENT_EVIDENCE` (0.98) | `INSUFFICIENT_EVIDENCE` -> `INSUFFICIENT_EVIDENCE` | PASS |
| `CF-FMT-PROSE-05A` | `format_invariance_supported` | `SUPPORTED` -> `SUPPORTED` | `SUPPORTED` (0.99) -> `SUPPORTED` (0.94) | `SUPPORTED` -> `SUPPORTED` | PASS |
| `CF-FMT-TABLE-05B` | `format_invariance_contradicted` | `CONTRADICTED` -> `CONTRADICTED` | `CONTRADICTED` (1.00) -> `CONTRADICTED` (0.99) | `CONTRADICTED` -> `CONTRADICTED` | PASS |
| `CF-NUM-AMT-06` | `minimal_numeric_flip` | `SUPPORTED` -> `CONTRADICTED` | `SUPPORTED` (0.99) -> `CONTRADICTED` (0.99) | `SUPPORTED` -> `CONTRADICTED` | PASS |
| `CF-NUM-CCY-07` | `minimal_currency_flip` | `SUPPORTED` -> `CONTRADICTED` | `SUPPORTED` (0.98) -> `CONTRADICTED` (0.92) | `INSUFFICIENT_EVIDENCE` -> `CONTRADICTED` | PASS |
| `CF-ENT-ADDR-08` | `minimal_entity_swap` | `SUPPORTED` -> `CONTRADICTED` | `SUPPORTED` (1.00) -> `CONTRADICTED` (0.91) | `SUPPORTED` -> `CONTRADICTED` | PASS |
| `CF-NOISE-09` | `irrelevant_distractor_noise` | `INSUFFICIENT_EVIDENCE` -> `INSUFFICIENT_EVIDENCE` | `SUPPORTED` (0.69) -> `SUPPORTED` (0.54) | `INSUFFICIENT_EVIDENCE` -> `INSUFFICIENT_EVIDENCE` | FAIL |

## 4. Candidate Adversarial Error Log (10 errors out of 72)

- **`ADV1-002-412c70d8`** (`typos`): Gold=`CONTRADICTED`, Pred=`INSUFFICIENT_EVIDENCE` (conf=0.995)  
  Claim: _The parcel was successfully delivered to the buyer._  
  Evidence: `FedEx log shows parcl 88412 returend to sendr dock un-delvered.`
- **`ADV1-003-3578a929`** (`typos`): Gold=`INSUFFICIENT_EVIDENCE`, Pred=`CONTRADICTED` (conf=0.831)  
  Claim: _The carrier picked up the shipment._  
  Evidence: `Warehose printed lable 771290 but no carrierr pickup scan exsts.`
- **`ADV1-018-bdce2da1`** (`emotional_noise`): Gold=`INSUFFICIENT_EVIDENCE`, Pred=`CONTRADICTED` (conf=0.944)  
  Claim: _Buyer logged 10 hours on the coaching portal._  
  Evidence: `Merchant insists buyer is dishonest, attaching only a blank order summary PDF.`
- **`ADV1-026-c2b3c401`** (`reordered_evidence`): Gold=`CONTRADICTED`, Pred=`INSUFFICIENT_EVIDENCE` (conf=0.994)  
  Claim: _Parcel 55102 was delivered to Seattle WA._  
  Evidence: `Destination in scan: Miami FL 33101. Expected buyer city: Seattle WA 98101. Parcel: 55102.`
- **`ADV1-029-d0fb303e`** (`reordered_evidence`): Gold=`CONTRADICTED`, Pred=`INSUFFICIENT_EVIDENCE` (conf=0.965)  
  Claim: _120.00 USD was settled to merchant account._  
  Evidence: `Status: VOIDED. Capture attempt: NONE. Order total: 120.00 USD.`
- **`ADV1-038-e2cbb11f`** (`conflicting_dates`): Gold=`CONTRADICTED`, Pred=`SUPPORTED` (conf=0.944)  
  Claim: _Delivery scan occurred after the 2026-09-01 purchase._  
  Evidence: `Carrier delivered parcel on 2026-08-10, whereas buyer placed order on 2026-09-01.`
- **`ADV1-041-641368a1`** (`conflicting_dates`): Gold=`CONTRADICTED`, Pred=`INSUFFICIENT_EVIDENCE` (conf=0.977)  
  Claim: _Tracking archive proves fulfillment of the 2026 invoice._  
  Evidence: `Invoice generated in 2026; tracking archive cited by seller is dated 2023.`
- **`ADV1-051-0d3f84d4`** (`negation_double_neg`): Gold=`INSUFFICIENT_EVIDENCE`, Pred=`CONTRADICTED` (conf=0.505)  
  Claim: _Buyer opened and accepted the parcel._  
  Evidence: `Log shows no confirmation that buyer did not open the parcel, nor any delivery receipt.`
- **`ADV1-054-4c8c9961`** (`negation_double_neg`): Gold=`INSUFFICIENT_EVIDENCE`, Pred=`CONTRADICTED` (conf=0.690)  
  Claim: _Carrier scan confirms doorstep drop-off._  
  Evidence: `Seller states tracking is not unavailable, though no carrier scan appears in evidence.`
- **`ADV1-068-bd298229`** (`misleading_relevant`): Gold=`INSUFFICIENT_EVIDENCE`, Pred=`SUPPORTED` (conf=0.508)  
  Claim: _Buyer received working unit at their home address._  
  Evidence: `Merchant attached signed warehouse QA checklist confirming product passed power-on test before boxing.`
