# ProofLedger AI Model & Verification Architecture: Final Report

> **AI Evidence Reasoning — ProofLedger**
>
> ProofLedger uses a fine-tuned DeBERTa-v3 model to assist with semantic alignment between merchant claims and submitted evidence.
>
> The candidate achieved 86.00% accuracy and 0.8589 Macro F1 on an internally curated 450-example EvidenceBench-v2 test split. This benchmark contains synthetic merchant scenarios and transformed FEVEROUS examples; it is not an independent real-world PayPal merchant dispute evaluation.
>
> Evaluation identified a significant weakness in the transformed FEVEROUS subset, including false contradiction predictions. Accordingly, model predictions remain advisory and cannot override deterministic transaction verification, delivery evidence requirements, or mandatory merchant approval.
>
> The production workflow retains a rules-first safety architecture. Human review and explicit merchant approval are required before evidence submission.

## 1. Executive Summary & Core Architectural Decision

In financial dispute arbitration, **deterministic fail-closed safety supersedes heuristic neural confidence**. An AI system that overrides amount mismatches or falsely claims delivery confirmation creates direct financial liability.

Through controlled domain-adaptation fine-tuning of `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` on **EvidenceBench-v2** (with exact head permutation `[0:entailment, 1:neutral, 2:contradiction] → [0:SUPPORTED, 1:CONTRADICTED, 2:INSUFFICIENT_EVIDENCE]`):

- **Pretrained Zero-Shot Baseline**: 53.56% validation accuracy / 49.11% test accuracy ($N=450$)
- **Legacy v1 `best_model` (protected & untouched)**: 28.22% val / 30.22% test ($N=450$) / 43.33% hidden ($N=30$)
- **Locked Primary Candidate (`ai/artifacts/candidates/deberta_v3_inr_v1/best/`, `C_top4_unfreeze`, Seed 42)**:
  - **Validation ($N=450$, 146 SUP / 154 CON / 150 INSUF)**: **89.33%** accuracy (Macro F1 `0.8913`)
  - **Internal Test ($N=450$, 151 SUP / 144 CON / 155 INSUF)**: **86.00%** accuracy (`387/450`), Macro F1 **0.8589**, ECE **0.0404**, Brier Score **0.1907**, Latency **13.05 ms/sample** on `mps`, Size **711.80 MB** (`184,424,451` params total)
  - **Three-Seed Checkpoints (`42, 1337, 2026`) on Frozen Test ($N=450$)**: `86.00%` / `85.78%` / `86.22%` (Mean ± Std: `86.00% ± 0.18%`, Macro F1 `0.8594 ± 0.0016`)

> **Test Protocol Disclosure**: All three seed checkpoints (`42`, `1337`, `2026`) were evaluated independently on the exact same frozen test split ($N=450$) strictly after validation selection. No test result was used for checkpoint selection, hyperparameter tuning, or threshold tuning. Seed `42` (`best/`) is retained as the primary locked candidate strictly because it won predeclared validation Macro F1 (`0.8913`).  
> *Benchmark Disclosure*: EvidenceBench-v2 internal test ($N=450$) is an internally curated benchmark split (synthetic INR tiers + FEVEROUS title placeholders), **NOT** an independent real-world merchant validation trial.

---

## 2. False Contradiction Metrics (Explicit Definitions — Seed 42 Test, $N=450$)

| Metric | Formula (Numerator / Denominator) | Observed Count | Rate |
|---|---|---:|---:|
| **1. Conditional `INSUF → CON` Rate** | `Pred=CON ∧ True=INSUF` / `Total INSUF` | `8 / 155` | **5.16%** (`0.051613`) |
| **2. Overall False-Contradiction Rate (over Non-Contradicted GT)** | `(SUP→CON + INSUF→CON)` / `(Total SUP + Total INSUF)` | `(29 + 8) / (151 + 155) = 37 / 306` | **12.09%** (`0.120915`) |
| **3. False-Contradiction Share of Full Test Set** | `(SUP→CON + INSUF→CON)` / `Total Test N` | `37 / 450` | **8.22%** (`0.082222`) |

*(Note: All 37 false contradictions occurred in Tier 3 FEVEROUS title-placeholder examples; Tier 1, Tier 2, and Tier 4 synthetic INR tiers had `0 / 215` non-contradicted false contradictions.)*

---

## 3. Reconciled Confusion Matrix & Per-Class Metrics (Seed 42 Test, $N=450$)

| Actual \ Predicted | SUPPORTED | CONTRADICTED | INSUFFICIENT_EVIDENCE | Support | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| **SUPPORTED** | **114** | 29 | 8 | **151** | 0.8769 | 0.7550 | 0.8114 |
| **CONTRADICTED** | 4 | **138** | 2 | **144** | 0.7886 | 0.9583 | 0.8652 |
| **INSUFFICIENT_EVIDENCE** | 12 | 8 | **135** | **155** | 0.9310 | 0.8710 | 0.9000 |

---

## 4. Candidate Artifact Lineage & Legacy Protection

- **Protected Legacy Checkpoint (`ai/artifacts/best_model/`)**: Untouched (`model.safetensors` SHA-256 `0e4d8903a24b7c8d45c63023a9d71425153f8919e6acbfa331337aaf088f4617`, `config.json` SHA-256 `3225bdc1cd7b0e6f483e96b810cd67f24a6bba6ba374289101b800ec299e63b7`).
- **Task-9902 Candidate Lineage**: `ai/artifacts/candidates/deberta_v3_inr_v1/best/` is an exact byte-for-byte copy of `ai/artifacts/candidates/deberta_v3_inr_v1/C_top4_unfreeze/` (Seed 42, Epoch 3). Both share identical SHA-256 hashes across all 5 files (`model.safetensors`: `2afd4cf10a28b274445073c6fc3c880c54708d5886ca3a2c54ed45857a94e2ea`, `config.json`: `af0fdd4ab7e322bd74da1726dafc4c3319a23d14b063058a3145a5b0dcf1c836`, `tokenizer.json`: `38b659758bd3a259baf2613299e09ba570f695b60c8275abd336a5bb6ead3e25`, `tokenizer_config.json`: `fe9a0072cdff367b5ead84896493bf17b3dc67ab74d1256936155599b6cdd459`, `special_tokens_map.json`: `b2f1b2f15f29a6b6d9d6ea4eca1675d2c231a71477f151d48f79cc83a625ba21`).
- **Sibling Seed Checkpoints**: `C_top4_unfreeze_seed1337` (`61793d6019afe70bf35d2237cb34e34f400f1fdb42d14bd2a52fc15a06ed5195`) and `C_top4_unfreeze_seed2026` (`fb2809b985bda937364b48d51b19fd1f113eafa9564b506300899d440321c2d9`).
- **Note on `evidencebench_v2_deberta_v3/`**: Does **not** exist in this repository (`ai/artifacts/candidates/deberta_v3_inr_v1/` is the sole canonical EvidenceBench-v2 candidate artifact path).
- **Production Authority**: **Rules-first Deterministic Gatekeeper + Assistive Semantic Alignment** (`86.00% < 90%`, `CONTRADICTED` precision `0.7886`, overall false-contradiction rate `12.09%`, and unverified real-world merchant performance).

---

## 5. Independent Unseen Data Generalization Audit (`proofledger_unseen_v1`)

Subsequent to freezing all weights, an independent generalization audit was conducted on `N = 600` unseen synthetic merchant claims (`14` brand-new scenario families across `5` formatting styles, `0` overlaps with `23,158` historical examples) and `N = 72` adversarial stress examples (full deliverables under `FINAL_RELEASE/INDEPENDENT_GENERALIZATION_AUDIT/INDEPENDENT_GENERALIZATION_REPORT.md`):

- **5-System Unseen Benchmark ($N = 600$, `mps`)**:
  - **Candidate (`deberta_v3_inr_v1/best`)**: **82.00%** Accuracy (`[79.00%, 85.00%]`), **0.8226** Macro F1, **11.50%** `INSUF->CON`, **5.75%** Overall FCR (`0.00%` `SUP->CON`), **0.1000** Raw ECE (`49.41 ms` p50).
  - **Pretrained (`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`)**: **66.00%** Accuracy, **0.6484** Macro F1, **34.50%** `INSUF->CON`, **21.75%** Overall FCR, **0.2594** ECE (`p = 2.438e-12` vs Candidate).
  - **Legacy (`ai/artifacts/best_model`)**: **36.67%** Accuracy, **0.3891** Macro F1, **66.00%** `INSUF->CON`, **62.00%** Overall FCR (`p = 6.651e-40` vs Candidate).
  - **Rules-Only Deterministic**: **35.67%** Accuracy, **0.2132** Macro F1, **0.00%** FCR (`p = 2.730e-61` vs Candidate).
  - **Production Hybrid (`Rules-First + Candidate`, post-fix)**: **82.00%** Accuracy, **0.8226** Macro F1, **5.75%** Overall FCR, **0.0572** ECE / **0.2794** Brier with validation-fitted `T=1.36` (fixing the pre-audit `79.67%` `"download"` keyword heuristic regression and stale `T=5.0` over-smoothing).
- **Fixed-Seed Random Subsample (`N=150, seed=20261111`, sampled from same 600-pair set)**: Candidate & Hybrid **82.00%** (`0.8166` Macro F1) vs Pretrained **67.33%** (`0.6713`).
- **Adversarial Challenge (`N=72`) & Counterfactual Probes (`10`)**: Candidate **86.11%** (Hybrid **84.72%**, `9/10` probes) vs Pretrained **66.67%** (`7/10` probes).
- **Remaining Domain Blind Spots**: Weak on `chronological_event_paradox` (`33.3%`), `sku_variant_mismatch` (`52.4%`, overall `CONTRADICTED` recall `69.0%`), unassessed on real-world PayPal merchant dispute logs, and dataset is internally authored synthetic rather than externally human-adjudicated.
- **Audit Conclusion**: **`GENERALIZATION DEMONSTRATED ON INDEPENDENT SYNTHETIC DATA`** (`REAL-WORLD GENERALIZATION NOT ASSESSED`).
