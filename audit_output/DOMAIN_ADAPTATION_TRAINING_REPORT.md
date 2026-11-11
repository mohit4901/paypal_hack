# Domain Adaptation Training Report (EvidenceBench-v2)

**Generated**: 2026-11-10T13:19:40.921604+00:00 (Reconciled from raw predictions `audit_output/seed42_test_predictions.jsonl`)
**Runtime**: 14.79 minutes on `mps`
**Protected Legacy Model (`ai/artifacts/best_model`)**: SHA-256 verified untouched before & after training.

---

## 1. Validation Model Selection (EvidenceBench-v2 Val, N=450: 146 SUP / 154 CON / 150 INSUF)

| Config | Mode | LR | Best Epoch | Val Acc | Val Macro F1 | Val INSUF→CON Rate |
|---|---|---:|---:|---:|---:|---:|
| Zero-shot Baseline | frozen | — | — | 0.5356 | 0.5349 | 0.3600 |
| Legacy `best_model` (v1) | frozen | — | — | 0.2822 | 0.2791 | 0.6800 |
| `B_linear_probe` | linear_probe | 0.0001 | 3 | 0.6800 | 0.6805 | 0.1467 |
| `C_top2_unfreeze` | top2 | 5e-06 | 4 | 0.7289 | 0.7278 | 0.2000 |
| **`C_top4_unfreeze`** | **top4** | **5e-06** | **3** | **0.8933** | **0.8913** | **0.0333** |

**Selected Winner (by Validation Macro F1)**: `C_top4_unfreeze`

---

## 2. Multi-Seed Evaluation Protocol & Reproducibility (`C_top4_unfreeze`)

> **Protocol Disclosure**: All three seed checkpoints (`42`, `1337`, `2026`) were evaluated independently on the exact same frozen test split ($N=450$) strictly after training. **No test result was used for checkpoint selection, hyperparameter tuning, or threshold modification.** Seed `42` (`best/`) is retained as the primary locked candidate strictly because it achieved the highest predeclared Validation Macro F1 (`0.8913`).

| Seed | Val Acc (N=450) | Val Macro F1 | Test Acc (N=450) | Test Macro F1 | Test INSUF→CON Rate (`x/155`) |
|---:|---:|---:|---:|---:|---:|
| **42 (Primary Locked)** | **0.8933** | **0.8913** | **0.8600** | **0.8589** | **0.0516 (8/155)** |
| 1337 | 0.8867 | 0.8858 | 0.8578 | 0.8577 | 0.0581 (9/155) |
| 2026 | 0.8889 | 0.8876 | 0.8622 | 0.8616 | 0.0581 (9/155) |
| **Mean ± Std (3 seeds)** | **0.8896 ± 0.0028** | **0.8882 ± 0.0023** | **0.8600 ± 0.0018** | **0.8594 ± 0.0016** | **0.0559 ± 0.0030** |

---

## 3. Primary Locked Candidate Evaluation — Seed 42 (`ai/artifacts/candidates/deberta_v3_inr_v1/best/`)

> *Disclosure: EvidenceBench-v2 internal test (N=450) is an internally curated benchmark split (Tier-1/2/4 synthetic + Tier-3 FEVEROUS placeholders), NOT an independent real-world merchant trial.*

- **Primary Checkpoint**: `ai/artifacts/candidates/deberta_v3_inr_v1/best/` (exact byte copy of `C_top4_unfreeze/`, Seed 42, Epoch 3)
- **Raw Predictions Log**: `audit_output/seed42_test_predictions.jsonl`
- **Model SHA-256 (`model.safetensors`)**: `2afd4cf10a28b274445073c6fc3c880c54708d5886ca3a2c54ed45857a94e2ea`
- **Model Size**: 711.80 MB (`184,424,451` params total; `28,944,387` updated during training)
- **Inference Latency**: `13.05 ms/sample` on `mps` (batch_size=16)
- **Accuracy**: **0.8600** (`387 / 450`)
- **Macro F1**: **0.8589** (`0.858864`)
- **ECE (10 bins)**: `0.0404` | **Brier Score**: `0.1907`

### False Contradiction Metrics (Explicit Definitions)
1. **Conditional `INSUFFICIENT_EVIDENCE -> CONTRADICTED` Rate**:
   $$\frac{\text{Pred}=\text{CONTRADICTED} \land \text{True}=\text{INSUFFICIENT\_EVIDENCE}}{\text{Total } \text{INSUFFICIENT\_EVIDENCE}} = \frac{8}{155} = \mathbf{5.16\%}\ (0.051613)$$
2. **Overall False-Contradiction Rate over Non-Contradicted Ground Truth (including `SUPPORTED -> CONTRADICTED`)**:
   $$\frac{(\text{Pred}=\text{CON} \land \text{True}=\text{SUP}) + (\text{Pred}=\text{CON} \land \text{True}=\text{INSUF})}{\text{Total } \text{SUPPORTED} + \text{Total } \text{INSUFFICIENT\_EVIDENCE}} = \frac{29 + 8}{151 + 155} = \frac{37}{306} = \mathbf{12.09\%}\ (0.120915)$$
   *(As a share of all $N=450$ test examples: $37 / 450 = 8.22\%$.)*

### Per-Class Metrics (Recomputed from `seed42_test_predictions.jsonl`)
| Class | Support | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| `SUPPORTED` | 151 | 0.8769 | 0.7550 | 0.8114 |
| `CONTRADICTED` | 144 | 0.7886 | 0.9583 | 0.8652 |
| `INSUFFICIENT_EVIDENCE` | 155 | 0.9310 | 0.8710 | 0.9000 |

### Reconciled Confusion Matrix (Actual rows × Predicted cols)
*(Row totals match true test split support: 151 SUPPORTED, 144 CONTRADICTED, 155 INSUFFICIENT_EVIDENCE = 450 total)*

| Actual \ Predicted | SUPPORTED | CONTRADICTED | INSUFFICIENT_EVIDENCE | Row Total |
|---|---:|---:|---:|---:|
| **SUPPORTED** | **114** | 29 | 8 | **151** |
| **CONTRADICTED** | 4 | **138** | 2 | **144** |
| **INSUFFICIENT_EVIDENCE** | 12 | 8 | **135** | **155** |
| **Column Total** | 130 | 175 | 145 | **450** |

### Per-Tier Diagnostic Breakdown (Seed 42 Test, $N=450$)
| Tier | N | Accuracy | `SUP → CON` | `INSUF → CON` | Notes |
|---|---:|---:|---:|---:|---|
| Tier 1 (Synthetic Merchant) | 90 | **100.00%** | 0 | 0 | Synthetic template split within group |
| Tier 2 (Synthetic Contrastive INR) | 180 | **97.22%** | 0 | 0 | Synthetic template split within families |
| Tier 3 (FEVEROUS Replay) | 135 | **59.26%** | 29 | 8 | **All 37 false contradictions occur here** due to missing evidence facts (`_title` placeholder collapse) |
| Tier 4 (Synthetic Colloquial) | 45 | **93.33%** | 0 | 0 | Synthetic template split within group |

---

## 4. Diagnostic Hidden Set (N=30) Comparison

| System | Hidden Acc (N=30) | INSUF→CON Rate (`x/10`) |
|---|---:|---:|
| Rules-only Baseline | 0.4333 (13/30) | 0.0000 (0/10) |
| Legacy `best_model` (v1) | 0.4333 (13/30) | 0.3000 (3/10) |
| Pretrained Zero-Shot | 0.5667 (17/30) | 0.6000 (6/10) |
| Candidate (`deberta_v3_inr_v1`, Seed 42) | 0.8000 (24/30) | 0.3000 (3/10) |

---

## 5. Production Authority Decision
- **90% Target Achieved on Test?**: **NO** (`86.00%` on EvidenceBench-v2 Internal Test).
- **Production Authority**: **Rules-first Deterministic Gatekeeper + Assistive Candidate Semantic Analysis**.
- Because overall non-contradicted false contradiction rate is `12.09%` (`37/306`, precision `0.7886` on `CONTRADICTED`), the neural model never overrides deterministic rules or submits evidence autonomously.
