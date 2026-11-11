# Model Selection & Comparative Architecture Report

**Date:** 2026-10-30  
**Authors:** ML Research & Production AI Architecture Group  
**Document Status:** Formal Architecture Decision (ADR-004)

---

## 1. Executive Summary & Production Decision

Following an exhaustive diagnostic audit of all models and benchmarks:
- **Fine-Tuned DeBERTa-v3 (Epoch 9 Checkpoint)** is **FORMALLY REJECTED** as an isolated verifier for production deployment.
- **Pretrained DeBERTa-v3 (`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`)** is **ACCEPTED** as the core NLI semantic reasoning backbone.
- **Production Architecture**: A **4-Layer Hybrid Pipeline** combining deterministic transaction verification, pretrained NLI inference, evidence compilation with source linkage, and mandatory seller human approval.

---

## 2. Definitive Model Benchmark Comparison

All metrics below are computed from identical saved prediction arrays and ground-truth labels using `scikit-learn`.

> [!IMPORTANT]
> Because the standard test split and challenge test split contain **0 SUPPORTED examples**, we report both **Represented 2-Class Macro-F1** (over `CONTRADICTED` and `INSUFFICIENT_EVIDENCE`) and **Fixed 3-Class Macro-F1** (with unrepresented `SUPPORTED` precision/recall/F1 = 0, zero_division=0). Full 3-class evaluation cannot be meaningfully computed on test splits where $N_{\text{SUP}} = 0$.

### Performance Matrix

| Evaluation Dataset Split | Evaluation Metric | Baseline A (Deterministic Validator) | Baseline B (Pretrained DeBERTa-v3) | Baseline C (TF-IDF + LR) | Candidate D (Fine-Tuned Epoch 9) |
|---|---|:---:|:---:|:---:|:---:|
| **Validation Split**<br>*(1,664 rows, 3 classes)* | **Accuracy**<br>**3-Class Macro-F1**<br>Contradiction Recall<br>Insufficient Recall<br>SUPPORTED Recall<br>**SUPPORTED FPR**<br>**SUPPORTED FDR** | 41.23%<br>0.1946<br>0.00%<br>100.00%<br>0.00%<br>**0.00%**<br>N/A (0 pred) | 91.77%<br>**0.9279**<br>98.72% (619/627)<br>81.20% (557/686)<br>100.00% (351/351)<br>**0.76%** (10/1,313)<br>**2.77%** (10/361) | 45.31%<br>0.4524<br>54.39%<br>—<br>—<br>—<br>— | **93.09%**<br>**0.9339**<br>99.68% (625/627)<br>83.53% (573/686)<br>100.00% (351/351)<br>**2.59%** (34/1,313)<br>**8.83%** (34/385) |
| **Standard Test Split**<br>*(1,664 rows, 2 classes)* | **Accuracy**<br>**Rep. 2-Class Macro-F1**<br>3-Class Macro-F1<br>Contradiction Recall<br>Insufficient Recall<br>**SUPPORTED FPR**<br>**SUPPORTED FDR** | 75.00%<br>0.7333<br>0.4889<br>50.00% (416/832)<br>100.00% (832/832)<br>**0.00%** (0/1,664)<br>N/A (0 pred) | **100.00%**<br>**1.0000**<br>0.6667 (SUP=0)<br>100.00% (832/832)<br>100.00% (832/832)<br>**0.00%** (0/1,664)<br>**N/A** (0 pred) | 27.52%<br>0.1835<br>0.1835<br>8.29%<br>46.75%<br>20.37%<br>— | 25.00%<br>0.2001<br>0.1334 (SUP=0)<br>50.00% (416/832)<br>0.00% (0/832)<br>**0.06%** (1/1,664)<br>**100.0%** (1/1) |
| **Adversarial Challenge**<br>*(400 rows, 2 classes)* | **Accuracy**<br>**Rep. 2-Class Macro-F1**<br>3-Class Macro-F1<br>Contradiction Recall<br>Insufficient Recall<br>**SUPPORTED FPR**<br>**SUPPORTED FDR** | —<br>—<br>—<br>—<br>—<br>—<br>— | **100.00%**<br>**1.0000**<br>0.6667 (SUP=0)<br>100.00% (200/200)<br>100.00% (200/200)<br>**0.00%** (0/400)<br>**N/A** (0 pred) | —<br>—<br>—<br>—<br>—<br>—<br>— | 25.00%<br>0.2000<br>0.1333 (SUP=0)<br>50.00% (100/200)<br>0.00% (0/200)<br>**0.00%** (0/400)<br>**N/A** (0 pred) |

---

## 3. Detailed Scientific Audit of Model Performance

### A. Generalization Failure of the Fine-Tuned Model (Diagnostic Hypotheses)

The empirical failure of the fine-tuned model on unseen scenario families is an observed fact (93.09% validation vs. 25.00% test). Based on detailed error analysis, we formulate the following diagnostic hypotheses:

1. **Diagnostic Hypothesis 1 — Shortcut Learning on Missing Details**:
   In the training dataset, scenario families such as `unsupported_claim_details` (416 examples) paired evidence of a valid delivery with a claim mentioning an altered detail (e.g. amount $50 vs $35), all labeled `CONTRADICTED`. Error analysis suggests the model internalized a heuristic: *"If the hypothesis asserts attributes not present in the premise, classify as CONTRADICTED"*.
   When evaluated on held-out test families where information is missing (`delivery_timestamp_missing` where the timestamp is unstated, or `plausible_but_unestablished` where buyer satisfaction is unstated), the model classified them as `CONTRADICTED` (>96% softmax probability), reducing `INSUFFICIENT_EVIDENCE` recall to 0.00%. While this shortcut is strongly supported by error analysis, its status remains a diagnostic hypothesis rather than an independently proven causal mechanism.
2. **Diagnostic Hypothesis 2 — Conflicting Records Inversion**:
   In training, duplicate conflicting timestamps (`tampered_event_history`) were labeled `INSUFFICIENT_EVIDENCE`. On the test set, `conflicting_delivery_events` (one success, one failure) were labeled `CONTRADICTED`. The fine-tuned model classified 416/416 of these as `INSUFFICIENT_EVIDENCE`.
3. **Observed False-Supported Predictions**:
   On the validation set, the fine-tuned model produced **34 false-supported predictions** (FDR: 8.83% = 34 / 385), primarily on `conflicting_status_snapshots` where the token `"COMPLETED"` appeared alongside `"DECLINED"`. On the test set, it produced 1 false-supported prediction. Claims of "zero false-supported predictions" or "zero hallucinations" are factually incorrect and retracted.

### B. Why Pretrained DeBERTa Generalizes More Robustly

1. **Pretraining Priors**:
   `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` was trained on diverse natural language inference corpora (MNLI, FEVER, ANLI), retaining broad semantic entailment:
   - Unstated details naturally align with `NEUTRAL` (`INSUFFICIENT_EVIDENCE`).
   - Direct opposing outcomes (SUCCESSFUL vs FAILED) align with `CONTRADICTION` (`CONTRADICTED`).
2. **Comparative Safety Profile**:
   On the validation set, the pretrained model produced **10 false-supported predictions** (FDR: **2.77%** = 10 / 361), compared to 34 for the fine-tuned model (FDR: 8.83%).
3. **Represented-Class Boundary Performance**:
   On both the 1,664-row standard test set and the 400-row challenge test set of v1.0, the pretrained model correctly categorized the represented classes (`CONTRADICTED` and `INSUFFICIENT_EVIDENCE`). On the 3-class EvidenceBench v1.1 test set (with all classes represented: 688 SUP, 554 CON, 422 INS), it achieved 80.77% accuracy, 0.7836 Macro-F1, and 100% contradiction recall.

---

## 4. Production Candidate Selection

| Evaluation Criterion | Candidate D (Fine-Tuned) | Candidate B (Pretrained DeBERTa) | Selected Production Candidate |
|---|:---:|:---:|:---:|
| In-distribution validation accuracy | **93.09%** | 91.77% | — |
| Unseen template accuracy (v1.0 represented) | 25.00% | **100.00% (rep)** | **Pretrained** |
| EvidenceBench v1.1 3-class test accuracy | — | **80.77%** | **Pretrained** |
| Contradiction recall on test | 50.00% | **100.00%** | **Pretrained** |
| Insufficient evidence recall (v1.1 test) | 0.00% (v1.0) | **56.40%** (v1.1) | **Pretrained** |
| False Discovery Rate on validation | 8.83% | **2.77%** | **Pretrained** |
| General logical reasoning robustness | Collapsed on unseen | Robust across templates | **Pretrained** |

**Selection Decision:**  
The production default for ProofLedger is locked to **Pretrained DeBERTa-v3** (`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`), deployed within our 4-layer hybrid verification architecture.

---

## 5. What Remains Unproven & Future Experiment Strategy

1. **Synthetic vs Real-World Generalization**:
   Performance on EvidenceBench benchmarks (synthetic domain templates) does not prove real-world PayPal dispute resolution effectiveness. Real disputes involve unstructured merchant emails, messy tracking PDFs, and third-party portal exports.
2. **Untouched Benchmark Governance**:
   EvidenceBench v1.1 test split was evaluated once as an audit checkpoint. Future tuning must occur exclusively against development/validation partitions.
3. **Experimental Fine-Tuning Agenda**:
   Future adaptation must be treated as experimental rather than pre-ordained:
   - **Baseline**: Frozen pretrained DeBERTa-v3.
   - **Exploratory Configurations**: LoRA with rank $r=8$ and $r=16$ as starting exploration points (not assumed optimal).
   - **Regularization**: Joint training with general NLI replay (e.g. FEVEROUS/MNLI) to test whether entailment neutrality can be preserved.
   - **Primary Objective**: Improving `INSUFFICIENT_EVIDENCE` recall (currently 56.40% on v1.1) and reducing false `SUPPORTED` decisions, rather than merely maximizing overall accuracy.

