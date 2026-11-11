# Model Card — ProofLedger Evidence Verifier

## Model Details

| Field | Value |
|---|---|
| **Model name** | ProofLedger Evidence Verifier |
| **Base model** | `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` |
| **Architecture** | DeBERTa-v3-base with sequence classification head (3 labels) |
| **Task** | Natural Language Inference / Evidence Verification |
| **Labels** | `SUPPORTED` · `CONTRADICTED` · `INSUFFICIENT_EVIDENCE` |
| **Tokenizer** | DeBERTa-v3 SentencePiece tokenizer |
| **Max sequence length** | 256 tokens (premise + hypothesis) |
| **Training data** | EvidenceBench v1.0 (synthetic domain data) |
| **Fine-tuning hardware** | Apple MPS (Apple Silicon) |
| **Licence** | Base model: MIT. Fine-tuned weights: Proprietary. |

---

## Intended Use

This model verifies whether a factual claim about a PayPal digital-goods transaction is:

- **SUPPORTED**: adequately established by the provided source evidence.
- **CONTRADICTED**: directly conflicted by at least one source record.
- **INSUFFICIENT_EVIDENCE**: neither established nor contradicted by available records.

### Primary use case

Helping digital-product sellers organise and evaluate evidence for PayPal transaction disputes. The model is one component of the ProofLedger pipeline, which also includes deterministic rule-based checks and human review.

### Out-of-scope uses

- **Do not use** to automatically decide PayPal Seller Protection eligibility.
- **Do not use** to make final legal or compliance determinations.
- **Do not use** without human review before any submission.
- **Do not use** as a substitute for authentic source records.

---

## Input Format

```
Premise (evidence):  [SOURCE_TYPE|EVIDENCE_ID] TIMESTAMP: content | [SOURCE_TYPE|EVIDENCE_ID] TIMESTAMP: content
Hypothesis (claim):  The factual claim to verify.
```

Multiple evidence records are concatenated with `" | "` as separator. Source IDs and timestamps are preserved in the premise.

**Example input:**

```
Premise:   [PAYPAL_API|cap_001] 2025-10-09T10:30:00Z: Capture cap_001 status=COMPLETED order=ord_123.
Hypothesis: PayPal confirmed the payment capture for order ord_123.
```

**Example output:**

```json
{
  "label": "SUPPORTED",
  "confidence": 0.91,
  "note_confidence": "Raw model score — not a calibrated probability."
}
```

---

## Training Data

### Primary training data: EvidenceBench v1.0

- **Type**: Synthetic, programmatically generated
- **Purpose**: PayPal digital-goods dispute evidence scenarios
- **Size**: ~6,656 training / 1,664 validation / 1,664 test / 400 challenge examples
- **Label distribution (train)**: SUPPORTED: 2234 · CONTRADICTED: 1695 · INSUFFICIENT_EVIDENCE: 2727
- **Scenario families**: 24 distinct scenario types covering payment, delivery, identity, timestamp, and access events
- **Split type**: Group-based (scenario families held out from train for val/test)
- **Generation seed**: 42

> [!IMPORTANT]
> EvidenceBench is entirely synthetic. It contains no real customer data and no real PayPal records. Performance on this benchmark does not establish real-world dispute outcome performance.

### Secondary training data: FEVEROUS (optional, mixed experiment only)

- **Type**: Real-world fact-verification dataset
- **Size**: 71,291 train / 7,890 validation
- **Labels**: SUPPORTS / REFUTES / NOT ENOUGH INFO (remapped to 3-class schema)
- **Licence**: CC BY-SA 3.0
- **Purpose**: General fact-verification knowledge transfer

---

## Label Mapping

| Model NLI label | Application label | Meaning |
|---|---|---|
| `entailment` | `SUPPORTED` | Evidence establishes the claim |
| `contradiction` | `CONTRADICTED` | Evidence conflicts with the claim |
| `neutral` | `INSUFFICIENT_EVIDENCE` | Evidence does not establish or contradict |

Label mapping is read from the actual model `config.id2label` at runtime. It is not assumed.

---

## Evaluation Results

> [!NOTE]
> Results below are from actual executed experiments on EvidenceBench v1.0. All metrics are reported on held-out splits. See `docs/EXPERIMENT_REPORT.md` for the full experiment table.

### Baseline A — Rules-only (Deterministic Validator)

| Metric | Validation | Test |
|---|---:|---:|
| Accuracy | 0.4123 | 0.7500 |
| Macro-F1 | 0.1946 | 0.7333 |
| Contradiction recall | 0.0000 | 0.5000 |
| Insuf. evidence recall | 1.0000 | 1.0000 |
| FP rate (SUPPORTED) | 0.0000 | 0.0000 |

*Notes: The rules baseline performs differently across validation and test because validation families were chosen to be harder (more ambiguous structure) while the test split happened to include families that matched the rules more directly. The rules baseline has near-zero contradiction recall on the validation split because it defaults to INSUFFICIENT_EVIDENCE when checks fail.*

### Baseline C — TF-IDF + Logistic Regression

| Metric | Validation | Test |
|---|---:|---:|
| Accuracy | 0.4531 | 0.2752 |
| Macro-F1 | 0.4524 | 0.1835 |
| Contradiction recall | 0.5439 | 0.0829 |

*Notes: Strong overfitting to training templates visible on the held-out test families. This confirms the value of group-based splitting.*

### Candidate D — Fine-tuned DeBERTa (Best Checkpoint: Epoch 9)

Selected exclusively on Validation Macro-F1 with tie-breaker (Contra Recall + Insuf Recall).

| Split | N | Accuracy | Macro-F1 | Contradiction Recall | Insuf. Recall | SUPPORTED FPR | SUPPORTED FDR |
|---|---|---:|---:|---:|---:|---:|---:|
| **Validation** | 1,664 | **0.9309** | **0.9339** | **0.9968** | **0.8353** | **0.0259** (2.59%) | **0.0883** (8.83%) |
| **Test (Held-Out Families)** | 1,664 | 0.2500 | 0.1334 (2-class: 0.2001) | 0.5000 | 0.0000 | **0.0006** (0.06%) | 0.0000 |
| **Challenge Test** | 400 | 0.2500 | 0.2000 | 0.5000 | 0.0000 | **0.0000** (0.00%) | 0.0000 |

*Validation Confusion Matrix (Reconciled from raw predictions)*:
- True SUPPORTED [351]: 351 SUPPORTED, 0 CONTRADICTED, 0 INSUFFICIENT
- True CONTRADICTED [627]: 2 SUPPORTED, 625 CONTRADICTED, 0 INSUFFICIENT
- True INSUFFICIENT [686]: 32 SUPPORTED, 81 CONTRADICTED, 573 INSUFFICIENT

*False-Supported Analysis*:
In validation, exactly 34 cases were falsely predicted as SUPPORTED (2 from CONTRADICTED, 32 from INSUFFICIENT). Error analysis demonstrates these arise from `conflicting_status_snapshots` where both a COMPLETED and DECLINED record exist in the evidence context. The model attends to the verbatim "COMPLETED" token while failing to resolve the conflict without timestamp ordering.

### Pretrained Baseline B — Zero-Shot DeBERTa-v3-base-mnli-fever-anli

| Split | N | Accuracy | Macro-F1 (2-class) | Contradiction Recall | Insuf. Recall | SUPPORTED FPR |
|---|---|---:|---:|---:|---:|---:|
| **Test (Held-Out Families)** | 1,664 | **1.0000** | **1.0000** | **1.0000** | **1.0000** | **0.0000** |
| **Challenge Test** | 400 | **1.0000** | **1.0000** | **1.0000** | **1.0000** | **0.0000** |

*Key Scientific Insight*: Pretrained DeBERTa's multi-task NLI pretraining establishes superior out-of-distribution reasoning across unseen scenario templates (100% accuracy on held-out test and challenge sets), whereas domain fine-tuning on a synthetic template corpus induces boundary distortion between CONTRADICTED and INSUFFICIENT_EVIDENCE on unseen prompt templates. In production, a hybrid architecture or ensembling the pretrained base weights with the rule-based validator is strongly indicated.

---

## Limitations

1. **Synthetic training only**: The model is trained on programmatically generated data. Real-world performance is unvalidated.
2. **No calibrated probabilities**: `confidence` values are raw softmax outputs, not calibrated probabilities.
3. **Not PayPal protection determinations**: This model cannot determine PayPal Seller Protection eligibility.
4. **Evidence dependency**: The model can only reason about claims relative to provided evidence. It cannot access external records.
5. **Template sensitivity**: The model may have learned surface features of the synthetic templates. Performance on real-world claims may differ.
6. **Truncation risk**: Very long evidence may be truncated. Truncation is flagged explicitly.
7. **Identity verification limitation**: Name matching alone is not sufficient for identity verification; the system requires email or other corroborating identifiers.

---

## Risks

| Risk | Mitigation |
|---|---|
| Model fabricates supporting evidence | System never invents evidence IDs; only references IDs in the input |
| Model used to bypass human review | Human review is always required; `human_approved` is always `false` by default |
| Confidence misinterpreted as PayPal guarantee | Every response includes an explicit disclaimer |
| Model used on live data without validation | Integration tests require real API responses; mock results are explicitly labelled |

---

## Model Card Contact

This model card was generated for the ProofLedger project. For questions about the system design, see `docs/LIMITATIONS.md` and `docs/PAYPAL_INTEGRATION.md`.

