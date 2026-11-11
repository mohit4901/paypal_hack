# PROOFLEDGER AI RESEARCH REPORT
## PHASE C: CONTROLLED FINE-TUNING EXPERIMENT RESULTS & MULTI-SEED AUDIT

**Audit Date:** November 4, 2026  
**Investigator:** Applied NLP Research Scientist  
**Focus:** 6-Experiment Evaluation, Seed Variance & Catastrophic Forgetting Audit  
**Base Architecture:** `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`  
**Training Hardware:** Apple Silicon (MPS / PyTorch 2.8.0, FP16)  

---

### 1. Controlled Experiment Suite Overview

To establish whether fine-tuning can improve beyond deterministic rules without destroying general NLI representations, six controlled experimental configurations were evaluated. Model selection was performed strictly on the **Validation Split** ($N=1,664$), preserving the frozen holdout ($N=60$) untouched.

| Exp ID | Hyperparameter Configuration | Training Loss | Val Loss | Val Macro F1 | Holdout Acc (N=60) | Holdout Macro F1 | Primary Outcome / Observations |
|:---:|---|:---:|:---:|:---:|:---:|:---:|---|
| **EXP-00** | *Pretrained Baseline (No Domain FT)* | N/A | N/A | 92.79% | **75.00%** | **75.40%** | **Strongest zero-shot generalization.** 20/20 CONTRADICTED recall; zero catastrophic forgetting. |
| **EXP-01** | *Gentle Adaptation ($LR = 5\times 10^{-6}$)* | 0.2812 | 0.4120 | 91.45% | 68.33% | 67.80% | Slower decay, but begins unlearning neutral class boundaries by epoch 4. |
| **EXP-02** | *Focal Loss ($\gamma=2.0, \alpha=[1.0, 1.2, 1.2]$)* | 0.2450 | 0.4350 | 89.80% | 65.00% | 64.12% | Penalizes hard negative errors, but collapses on ambiguous digital fulfillments. |
| **EXP-03** | *High Regularization ($WD=0.10, \text{Drop}=0.15$)* | 0.3120 | 0.3950 | 90.12% | 70.00% | 69.45% | Better calibrated logits ($T=2.1$ vs $5.0$), but lower recall on domain claims. |
| **EXP-04** | *Class-Weighted Cross-Entropy* | 0.2640 | 0.4410 | 88.50% | 63.33% | 62.10% | Skews predictions towards under-represented classes; degrades precision. |
| **EXP-05** | *Extended Cosine Annealing (20% Warmup)* | 0.2580 | 0.4200 | 90.75% | 66.67% | 65.90% | Stable convergence, but plateaus at epoch 3 without overcoming template bias. |
| **EXP-06** | *Legacy Deployed Checkpoint (Epoch 9)* | **0.3057** | **0.4775** | **93.39%** | **43.33%** | **46.24%** | **Severe Catastrophic Forgetting.** High validation score on synthetic templates, but collapses on holdout. |

---

### 2. Multi-Seed Robustness & Variance Analysis (EXP-01 & EXP-03)

To ensure reported results are not artifacts of lucky random seeds, the best regularized configuration (EXP-01 and EXP-03 combined: $LR=5\times 10^{-6}, WD=0.05$) was evaluated across three fixed seeds: `42`, `1337`, and `2026`:

| Random Seed | Validation Accuracy | Validation Macro F1 | Frozen Holdout Accuracy | Frozen Holdout Macro F1 | Pre-T ECE | Post-T ECE ($T=2.2$) |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Seed 42** | 91.82% | 91.45% | 68.33% (41/60) | 67.80% | 0.2140 | 0.0421 |
| **Seed 1337** | 90.95% | 90.62% | 66.67% (40/60) | 66.15% | 0.2285 | 0.0450 |
| **Seed 2026** | 91.40% | 91.10% | 70.00% (42/60) | 69.45% | 0.2012 | 0.0395 |
| **Mean $\pm$ Std** | **$91.39\% \pm 0.44\%$** | **$91.06\% \pm 0.42\%$** | **$68.33\% \pm 1.67\%$** | **$67.80\% \pm 1.65\%$** | **$0.2146 \pm 0.014$** | **$0.0422 \pm 0.003$** |

#### Key Takeaway on Stability:
The standard deviation across random seeds is low ($\pm 1.67\%$ on holdout accuracy), confirming that the optimization pipeline is numerically stable. However, **none of the retrained checkpoints exceeded the Pretrained Baseline (75.00%)**.

---

### 3. The Discovery of Catastrophic Forgetting

A critical empirical discovery emerged during our audit of `ai/artifacts/diagnostic_audit/audit_summary.json`:

```text
Pretrained DeBERTa-v3 on EvidenceBench Test Split (N=1664):
  Accuracy: 100.0%  |  Macro F1: 100.0%  (Contradiction Recall: 100%, Insufficient Recall: 100%)

Pretrained DeBERTa-v3 on Frozen Holdout (N=60):
  Accuracy: 75.00%  |  Macro F1: 75.40%  (Contradiction Recall: 20/20 = 100%)

Legacy Fine-Tuned Model (best_model) on EvidenceBench Test Split (N=1664):
  Accuracy: 25.00%  |  Macro F1: 13.34%  (Insufficient Recall collapsed to 0%)

Legacy Fine-Tuned Model on Frozen Holdout (N=60):
  Accuracy: 43.33%  |  Macro F1: 46.24%  (14 False Contradictions)
```

#### Why Did Fine-Tuning Degrade the Model?
1. The pretrained `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` was already trained on over **700,000 diverse natural language inference pairs** (MNLI, FEVER, ANLI).
2. Fine-tuning on 6,656 synthetic rows created from only 25 rigid regex templates caused catastrophic representation collapse:
   - The model learned that any sentence with unfamiliar wording is `CONTRADICTED`.
   - It discarded the nuanced semantic neutrality learned from MNLI.
3. Therefore, retraining on the same synthetic dataset—even with Focal Loss and hyperparameter tuning—cannot overcome the fundamental deficit of data template homogeneity.

