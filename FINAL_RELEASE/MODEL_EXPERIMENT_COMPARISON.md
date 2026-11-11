# Model Experiment & Ablation Comparison (EvidenceBench-v2)

## 1. Validation Configuration Search ($N=450$: 146 SUP / 154 CON / 150 INSUF, Seed 42)

| Configuration | Trainable Params | LR | Best Epoch | Val Acc | Val Macro F1 | Val `INSUF→CON` Rate |
|---|---:|---:|---:|---:|---:|---:|
| Zero-Shot Pretrained (`MoritzLaurer`, remapped) | 0 | — | — | 53.56% | 0.5349 | 36.00% (`54/150`) |
| Legacy `best_model` (v1, untouched) | 0 | — | — | 28.22% | 0.2791 | 68.00% (`102/150`) |
| `B_linear_probe` (Head + Pooler) | 592,899 | 1e-4 | 3 | 68.00% | 0.6805 | 14.67% (`22/150`) |
| `C_top2_unfreeze` (Layers 10–11 + Head) | 14,768,643 | 5e-6 | 4 | 72.89% | 0.7278 | 20.00% (`30/150`) |
| **`C_top4_unfreeze` (Layers 8–11 + Head)** | **28,944,387** | **5e-6** | **3** | **89.33%** | **0.8913** | **3.33% (`5/150`)** |

*(Full 184M-param fine-tuning hit macOS MPS memory ceiling at 4.84 GiB MPS + 15.08 GiB system allocations; top-4 unfreezing prevented catastrophic forgetting and converged cleanly.)*

---

## 2. Three-Seed Checkpoint Evaluations on Same Frozen Test Set ($N=450$: 151 SUP / 144 CON / 155 INSUF)

*(Each checkpoint was evaluated independently on the frozen test split after training; no test metric influenced checkpoint selection. Seed 42 is retained as the primary locked candidate based on Validation Macro F1.)*

| Seed | Val Acc | Val Macro F1 | Test Acc | Test Macro F1 | Test `INSUF→CON` Rate (`x/155`) |
|---:|---:|---:|---:|---:|---:|
| **42 (Primary Locked)** | **89.33%** | **0.8913** | **86.00%** | **0.8589** | **5.16% (`8/155`)** |
| 1337 | 88.67% | 0.8858 | 85.78% | 0.8577 | 5.81% (`9/155`) |
| 2026 | 88.89% | 0.8876 | 86.22% | 0.8616 | 5.81% (`9/155`) |
| **3-Seed Mean ± Std** | **88.96% ± 0.28%** | **0.8882 ± 0.0023** | **86.00% ± 0.18%** | **0.8594 ± 0.0016** | **5.59% ± 0.30%** |

---

## 3. Primary Locked Candidate Test Metrics (Seed 42, $N=450$)

- **Exact Confusion Matrix** (`[SUP, CON, INSUF]`): `[[114, 29, 8], [4, 138, 2], [12, 8, 135]]` (Row sums: `151, 144, 155`)
- **Conditional `INSUFFICIENT_EVIDENCE → CONTRADICTED`**: `8 / 155 = 5.16%`
- **Overall False-Contradiction Rate (Non-Contradicted GT `(SUP+INSUF) → CON`)**: `(29 + 8) / (151 + 155) = 37 / 306 = 12.09%` (`8.22%` of all 450 test samples)
- **Per-Tier Test Accuracy**: Tier 1 `100.00%` (`90/90`), Tier 2 `97.22%` (`175/180`), Tier 3 FEVEROUS placeholder `59.26%` (`80/135`, accounting for all 37 false contradictions), Tier 4 `93.33%` (`42/45`)
- **Calibration & Latency**: ECE `0.0404` | Brier `0.1907` | Latency `13.05 ms/sample` (`mps`)
- **Rules-only Test Acc ($N=450$)**: `36.89%` (Macro F1 `0.2213`) | Diagnostic Hidden ($N=30$): `43.33%` (`0/10` false contradictions)
