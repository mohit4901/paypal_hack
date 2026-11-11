# PROOFLEDGER AI RESEARCH REPORT
## PHASE 2: PRETRAINED MODEL AUDIT & THE "100% EVIDENCEBENCH" INVESTIGATION

**Audit Date:** November 5, 2026  
**Investigator:** Applied NLP Research Scientist  
**Focus:** Pretrained Checkpoint Configuration, Label Mappings & EvidenceBench 100% Deconstruction  
**Evaluated Model:** `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` (HuggingFace Hub / Local Cache)  
**Dataset Inspected:** `ai/data/processed/evidencebench/test.jsonl` ($N=1,664$)  

---

### 1. Pretrained Model Architecture & Class Mapping Verification

We inspected the actual binary config of `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` using `AutoConfig` and `AutoModelForSequenceClassification`:

```json
{
  "_name_or_path": "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
  "architectures": ["DebertaV2ForSequenceClassification"],
  "id2label": {
    "0": "entailment",
    "1": "neutral",
    "2": "contradiction"
  },
  "label2id": {
    "contradiction": 2,
    "entailment": 0,
    "neutral": 1
  },
  "num_labels": 3,
  "vocab_size": 128000
}
```

#### Exact Label Mapping Verification
The mapping from pre-trained NLI heads to ProofLedger application labels is:
- **Index 0:** `entailment` $\longrightarrow$ **`AppLabel.SUPPORTED`**
- **Index 1:** `neutral` $\longrightarrow$ **`AppLabel.INSUFFICIENT_EVIDENCE`**
- **Index 2:** `contradiction` $\longrightarrow$ **`AppLabel.CONTRADICTED`**

> [!NOTE]
> In `ai/src/evaluation/diagnostic_audit.py` (lines 114–122), this remapping is implemented dynamically:
> `out_idx_to_app_idx[0] = LABEL2ID["SUPPORTED"]` (Index 0)  
> `out_idx_to_app_idx[1] = LABEL2ID["INSUFFICIENT_EVIDENCE"]` (Index 2)  
> `out_idx_to_app_idx[2] = LABEL2ID["CONTRADICTED"]` (Index 1)  
> The evaluation script correctly maps indices; the reported accuracy was not an off-by-one artifact.

---

### 2. Deconstructing the "100% Accuracy" on EvidenceBench Test Split

In `ai/artifacts/diagnostic_audit/audit_summary.json`, `pretrained_deberta` reported an astonishing **100.0% accuracy (1,664 / 1,664)** on the EvidenceBench test split.

We performed a line-by-line autopsy of `ai/data/processed/evidencebench/test.jsonl`. The investigation revealed that **the 100% score is a synthetic illusion caused by an unnaturally polarized test partition**:

#### Finding A: The Test Split Completely Lacks the `SUPPORTED` Class
The class distribution of `test.jsonl` ($N=1,664$) is:
- `SUPPORTED`: **0 examples (0.0%)**
- `CONTRADICTED`: **832 examples (50.0%)**
- `INSUFFICIENT_EVIDENCE`: **832 examples (50.0%)**

The test split was not balanced. It omitted positive fulfillment cases entirely.

#### Finding B: The Entire Split Consists of Exactly TWO Trivial Template Families
Every single example in `test.jsonl` belongs to one of two extreme, mutually exclusive synthetic generators:

1. **First 832 Examples (Rows 1 – 832): `conflicting_delivery_events`**
   - *Premise:* `File <X> delivery SUCCESSFUL ... File <X> delivery FAILED (recipient not found) ...`
   - *Hypothesis:* `The file <X> was successfully delivered for order <Y>.`
   - *NLI Structure:* The premise contains the explicit string literal `"delivery FAILED"`. Any baseline NLI model trained on MNLI recognizes that `"FAILED"` directly contradicts `"was successfully delivered"`.
   - *Pretrained Model Accuracy:* **832 / 832 = 100.0%**.

2. **Second 832 Examples (Rows 833 – 1664): `plausible_but_unestablished`**
   - *Premise:* `Payment COMPLETED order=<X> payer=<Name>.`
   - *Hypothesis:* `The buyer <Name> is satisfied with the product <Y>.`
   - *NLI Structure:* The premise mentions a financial payment. The hypothesis asserts emotional satisfaction. In standard NLI, paying for a product never entails personal satisfaction. The model trivially assigns 99% probability to `"neutral"`.
   - *Pretrained Model Accuracy:* **832 / 832 = 100.0%**.

#### Confusion Matrix of `pretrained_deberta` on EvidenceBench Test Split:
```text
Ground Truth \ Pred      SUPPORTED   CONTRADICTED   INSUFFICIENT
SUPPORTED (0)                0             0              0
CONTRADICTED (832)           0           832              0
INSUFFICIENT (832)           0             0            832
```

---

### 3. Conclusion: The Test Split Was a Toy Benchmark

The 100% accuracy of the pretrained model on EvidenceBench test split does **NOT** indicate that `MoritzLaurer/DeBERTa-v3` is a perfect financial dispute classifier.
It merely proves that the EvidenceBench test generator constructed a caricature test set of trivial binary opposites (`"delivery FAILED"` vs `"is satisfied"`).

When evaluated on the realistic 60-claim holdout—where claims involve nuanced enterprise logs, tracking scans, and partial proofs—the pretrained model's accuracy drops from **100.0% to 75.00%**.

