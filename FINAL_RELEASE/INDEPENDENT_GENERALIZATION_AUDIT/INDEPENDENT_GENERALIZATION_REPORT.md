# Independent Unseen Data Generalization & Model Authenticity Audit Report

**Audit Date**: 2026-11-11  
**Primary Subject**: Candidate DeBERTa-v3 NLI Checkpoint (`ai/artifacts/candidates/deberta_v3_inr_v1/best/`)  
**Reference Baselines**: `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` (Pretrained), `ai/artifacts/best_model/` (Legacy Fine-Tuned), Rules-Only Deterministic Engine, Production Hybrid (`Rules-First + Candidate`)  
**Primary Outcome Designation**: **`GENERALIZATION DEMONSTRATED ON INDEPENDENT SYNTHETIC DATA`** *(Co-designation: **`REAL-WORLD GENERALIZATION NOT ASSESSED`** — zero independent real-world PayPal merchant dispute transcripts were available or evaluated; additionally, `chronological_event_paradox` and `sku_variant_mismatch` sub-families show bounded generalization).*

---

## Executive Summary

An independent evaluation protocol was constructed from scratch (`proofledger_unseen_v1`: **600** balanced unseen examples across **14 new scenario families** and **5 formatting styles**, plus **72** adversarial challenge pairs across **12 stress phenomena** and **10** minimal counterfactual probes) with **0** exact claim/evidence overlaps, **0** near-duplicates (Jaccard $\ge 0.80$), **0** scenario-family overlaps, and **0** entity/ID overlaps against 23,158 historical training/test examples.

On the 600-example unseen benchmark, the fine-tuned candidate **`deberta_v3_inr_v1/best`** achieved **82.00% accuracy** (95% CI: `[79.00%, 85.00%]`), **0.8226 Macro F1** (`[0.7924, 0.8521]`), **11.50% `INSUFFICIENT_EVIDENCE -> CONTRADICTED` rate**, and **5.75% Overall False-Contradiction Rate**, outperforming:
- Exact Pretrained baseline (`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`): **+16.00 pp** accuracy (**82.00%** vs **66.00%**, exact McNemar $p = 2.438 \times 10^{-12}$) and **-16.00 pp** Overall FCR (**5.75%** vs **21.75%**).
- Legacy deployed checkpoint (`ai/artifacts/best_model`): **+45.33 pp** accuracy (**82.00%** vs **36.67%**, $p = 6.651 \times 10^{-40}$) and **-56.25 pp** Overall FCR (**5.75%** vs **62.00%**).
- Rules-only deterministic baseline: **+46.33 pp** accuracy (**82.00%** vs **35.67%**, $p = 2.73 \times 10^{-61}$).

At the same time, the audit uncovered **critical integration & reasoning findings** (three of which were subsequently fixed and re-verified, while real-world domain gaps remain documented):
1. **Production Loader & Provenance Bugs Remediated**: Previously `.env` (`MODEL_PATH=MoritzLaurer/...`), hardcoded `"ai/artifacts/best_model"` references in `backend/services/dispute_service.py` / `backend/routes/ai.py` / `backend/routes/system.py`, and silent fallback behavior in `backend/services/dispute_rescue_ai.py` caused default runs to hit legacy `best_model` or mask offline state. Production code now loads `deberta_v3_inr_v1/best` cleanly, exposes `PROOFLEDGER_MODEL_PATH`, logs active checkpoint provenance in `verification_runs`, and fails closed (`MODEL_UNAVAILABLE` / `MODEL_OFFLINE`).
2. **Rules-First Hybrid Keyword Regression (`79.67%` -> `82.00%` after fix)**: Initial evaluation revealed a broad `"download" in claim_lower` heuristic in `dispute_service.py` overriding **14 / 42** `SUPPORTED` claims in `digital_utilization_vs_provisioning` to `INSUFFICIENT_EVIDENCE` (`p = 0.0001221`). Replaced with evidence-grounded `DeterministicValidator.check_provisioning_without_download()` inspecting explicit provisioning-only/zero-download telemetry rather than claim text alone; post-fix Hybrid matches Candidate (`82.00%` on $N=600$, `84.72%` on adversarial $N=72$).
3. **Stale `T=5.0` Calibration Fixed (`ECE 0.2574 -> 0.0572`)**: Candidate raw softmax scores achieve **0.1000 10-bin ECE** (Brier `0.2958`), whereas inherited `T=5.0` degraded ECE to **0.2574** (Brier `0.3755`). Replaced `T=5.0` with validation-fitted `T=1.36` (fitted strictly on `EvidenceBench-v2/validation.jsonl`, $N=450$, reducing validation NLL `0.4068 -> 0.3879`, applied only to `deberta_v3_inr_v1`), bringing unseen Hybrid ECE down to **0.0572** (`Brier = 0.2794`).
4. **Domain Reasoning Blind Spots Remain**: Candidate underperforms Pretrained on `chronological_event_paradox` (**33.3%** vs **66.7%**) and `sku_variant_mismatch` (**52.4%** vs **64.3%**), with overall `CONTRADICTED` recall at **69.0%** (`62/200` predicted `INSUFFICIENT_EVIDENCE`) and high confidence on some subtle errors.
5. **Independence Scope Caveat**: `proofledger_unseen_v1` (`N=600`) has **0** overlap against 23,158 historical examples, but was authored within the same project rather than externally human-adjudicated; the `N=150` random slice is a deterministic subset of those same 600 examples.

---

## 1. Frozen Artifact Identity & Model Authenticity

Full file inventory and SHA-256 checksums are recorded in [`MODEL_IDENTITY_AND_HASHES.json`](MODEL_IDENTITY_AND_HASHES.json).

| Artifact | Path / ID | `model.safetensors` SHA-256 | Dtype / Tensors | Size (weights / dir) | Label Mapping Verified |
|---|---|---|---|---|---|
| **Candidate (`deberta_v3_inr_v1`)** | `ai/artifacts/candidates/deberta_v3_inr_v1/best` | `2afd4cf10a28b274445073c6fc3c880c54708d5886ca3a2c54ed45857a94e2ea` | `F32` / `202` tensors | `737.7 MB` / `746.4 MB` | `{0: SUPPORTED, 1: CONTRADICTED, 2: INSUFFICIENT_EVIDENCE}` |
| **Legacy (`best_model`)** | `ai/artifacts/best_model` | `0e4d8903a24b7c8d45c63023a9d71425153f8919e6acbfa331337aaf088f4617` | `F16` / `202` tensors | `368.9 MB` / `377.5 MB` | `{0: SUPPORTED, 1: CONTRADICTED, 2: INSUFFICIENT_EVIDENCE}` |
| **Pretrained Baseline** | `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` (`6f5cf0a2...`) | `06d6fd89edd4f97816831626daafbdb0b029cf63bae8edc0bccab1d64e2e7707` | `F16, I64` / `203` tensors | `368.9 MB` / `380.0 MB` | `{0: entailment->SUP, 1: neutral->INSUF, 2: contradiction->CON}` |

- Verified Safetensors headers, `classifier.weight [3, 768]`, `classifier.bias [3]`, tokenizer (`DebertaV2TokenizerFast`, vocab `128,000`, `max_length = 512`), and production inference input order (`premise = formatted_evidence`, `hypothesis = claim`).
- Zero EvidenceBench-v1/v2 weights or thresholds were altered during evaluation.

---

## 2. Independent Blind Dataset Construction & Leakage Verification

Details preserved in [`UNSEEN_DATASET.jsonl`](UNSEEN_DATASET.jsonl), [`UNSEEN_DATASET_MANIFEST.json`](UNSEEN_DATASET_MANIFEST.json), and [`NOVELTY_AND_LEAKAGE_AUDIT.md`](NOVELTY_AND_LEAKAGE_AUDIT.md).

- **Corpus Size & Balance**: `N = 600` (`200 SUPPORTED`, `200 CONTRADICTED`, `200 INSUFFICIENT_EVIDENCE`), SHA-256 `e747bcf5cea3e70f8e438f9f69cd94de09552fced964c155fd08db8169bcb799`.
- **Novelty vs 23,158 Historical Examples** (EvidenceBench-v1/v1.1/v2 train/val/test + `RAW_PREDICTIONS_60.csv` + `HIDDEN_CASES` + `test_deberta_generalization_100.py`):
  - Exact `(claim + evidence)` duplicates: **0**
  - Exact normalized `claim` matches: **0**
  - Internal duplicates: **0**
  - Near-duplicate claims (Jaccard $\ge 0.80$): **0**
  - Scenario-family name overlap: **0** (14 newly authored families across 5 formatting wrappers: prose memos, JSON payloads, pipe-delimited ledger tables, ticket attachments, carrier webhook stubs)
  - Tracking / order / capture ID leakage: **0**
- **Adversarial Stress Suite**: `N = 72` (`adversarial_challenge.jsonl`) across 12 stress categories (6 pairs each) plus `10` minimal counterfactual pairs.

---

## 3. Main 5-System Benchmark Results (`N = 600`, Apple Silicon MPS)

All metrics computed strictly from raw prediction JSONLs by `scripts/compute_unseen_metrics.py` (`METRICS.json`, `CONFUSION_MATRICES.json`).

| System | Accuracy (95% CI) | Macro F1 (95% CI) | `INSUF->CON` Rate (95% CI) | Overall FCR* (95% CI) | Raw ECE (10-bin) | Brier Score | p50 / p95 Latency |
|---|---|---|---|---|---|---|---|
| **A. Candidate (`deberta_v3_inr_v1`)** | **82.00%** `[79.00, 85.00]` | **0.8226** `[0.7924, 0.8521]` | **11.50%** `[7.32, 16.00]` | **5.75%** `[3.63, 8.08]` | **0.1000** | **0.2958** | `49.41 / 83.18 ms` |
| **B. Pretrained Baseline** | 66.00% `[62.17, 69.83]` | 0.6484 `[0.6081, 0.6873]` | 34.50% `[27.92, 40.98]` | 21.75% `[17.72, 25.86]` | 0.2594 | 0.5951 | `45.35 / 72.80 ms` |
| **C. Legacy (`best_model`)** | 36.67% `[32.83, 40.33]` | 0.3891 `[0.3497, 0.4258]` | 66.00% `[59.22, 72.54]` | 62.00% `[57.44, 66.99]` | 0.4884 | 1.0737 | `43.51 / 56.06 ms` |
| **D. Rules-Only Deterministic** | 35.67% `[31.83, 39.50]` | 0.2132 `[0.1868, 0.2395]` | **0.00%** `[0.00, 0.00]` | **0.00%** `[0.00, 0.00]` | N/A | N/A | `0.025 / 0.033 ms` |
| **E. Production Hybrid (Rules + Cand, post-fix)** | **82.00%** `[79.00, 85.00]` | **0.8226** `[0.7924, 0.8521]` | **11.50%** `[7.32, 16.00]` | **5.75%** `[3.63, 8.08]` | 0.1000 (**0.0572** @ $T=1.36$) | 0.2958 (**0.2794** @ $T=1.36$) | `48.06 / 70.00 ms` |

*(Pre-remediation Hybrid scored `79.67%` Accuracy / `0.8016` Macro F1 / `0.2574` ECE @ $T=5.0$ before fixing the broad `"download"` heuristic and stale $T=5.0$ parameter.)*

*\*Definition Separation*:
- `INSUF->CON Rate = CM[INSUFFICIENT_EVIDENCE][CONTRADICTED] / N(INSUFFICIENT_EVIDENCE = 200)` (`23 / 200 = 11.50%` for Candidate).
- `Overall False-Contradiction Rate = (CM[INSUF][CON] + CM[SUP][CON]) / (N(INSUF) + N(SUP))` (`(23 + 0) / 400 = 5.75%` for Candidate). `SUP->CON` is `0.00%` (`0 / 200`).

### Paired Significance Tests vs Candidate (N = 600, Exact McNemar)
- **Candidate vs Pretrained**: `+16.00 pp` (95% CI: `[+11.67, +20.33]`), discordant `144 vs 48`, $\chi^2_{cc} = 47.01$, $p = 2.438 \times 10^{-12}$.
- **Candidate vs Legacy**: `+45.33 pp` (`[+39.67, +51.00]`), discordant `361 vs 89`, $\chi^2_{cc} = 163.20$, $p = 6.651 \times 10^{-40}$.
- **Candidate vs Rules-Only**: `+46.33 pp` (`[+41.67, +51.00]`), discordant `304 vs 26`, $\chi^2_{cc} = 232.51$, $p = 2.730 \times 10^{-61}$.
- **Candidate vs Hybrid (post-fix)**: `0.00 pp` (identical `492 / 600` on $N=600$, `0` false rule triggers vs `14` pre-fix).

### Candidate Confusion Matrix & Per-Class Metrics (N = 600)

| True \ Pred | `SUPPORTED` | `CONTRADICTED` | `INSUFFICIENT_EVIDENCE` | Support | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| **`SUPPORTED`** | **180** | 0 | 20 | 200 | 0.9836 | 0.9000 | **0.9399** |
| **`CONTRADICTED`** | 0 | **138** | 62 | 200 | 0.8571 | 0.6900 | **0.7645** |
| **`INSUFFICIENT_EVIDENCE`** | 3 | 23 | **174** | 200 | 0.6797 | 0.8700 | **0.7632** |

---

## 4. Per-Family Breakdown (Candidate vs Pretrained, 14 Novel Families)

| Scenario Family | N | Candidate Acc (FCR) | Pretrained Acc (FCR) | Key Observation |
|---|---:|---:|---:|---|
| `carrier_manifest_vs_label_prep` | 45 | **100.0%** (0.0%) | 97.8% (0.0%) | Strong label-vs-pickup distinction |
| `multi_box_partial_fulfillment` | 45 | **100.0%** (0.0%) | 75.6% (0.0%) | Eliminates multi-parcel overclaiming |
| `plausible_but_non_probative_docs` | 42 | **100.0%** (0.0%) | 81.0% (0.0%) | Rejects non-probative docs without FCR |
| `digital_utilization_vs_provisioning` | 42 | **100.0%** (0.0%) | 76.2% (28.6%) | Post-fix Hybrid now matches Candidate (100.0%) |
| `customs_transit_vs_final_delivery` | 45 | **93.3%** (10.0%) | 64.4% (50.0%) | Major improvement over pretrained FCR |
| `archive_gaps_and_untracked_mail` | 42 | **92.9%** (10.7%) | 83.3% (25.0%) | Handles missing archive proof cleanly |
| `direct_merchant_claim_refutation` | 42 | **92.9%** (0.0%) | 66.7% (0.0%) | Strong refutation detection |
| `refund_lifecycle_stages` | 42 | **92.9%** (10.7%) | 45.2% (67.9%) | Eliminates pretrained refund-stage FCR |
| `duplicate_billing_and_fx` | 42 | **88.1%** (0.0%) | 66.7% (0.0%) | Accurate duplicate/FX reconciliation |
| `checkout_auth_vs_settlement` | 42 | 66.7% (50.0%) | 33.3% (50.0%) | Still confuses auth hold with contradiction |
| `destination_address_divergence` | 45 | 66.7% (0.0%) | 66.7% (50.0%) | Under-recalls CONTRADICTED (prefers INSUF) |
| `subjective_complaint_vs_objective_delivery` | 42 | 66.7% (0.0%) | 33.3% (17.9%) | +33.4 pp over Pretrained, conservative |
| `sku_variant_mismatch` | 42 | 52.4% (0.0%) | **64.3%** (14.3%) | Subtle SKU mismatch frequently calls INSUF |
| `chronological_event_paradox` | 42 | 33.3% (0.0%) | **66.7%** (0.0%) | **Weakness**: struggles with date ordering |

---

## 5. Fixed-Seed Random Subset & Adversarial Challenge Summary

- **Fixed-Seed Random Unstratified Subset (`N = 150`, `seed = 20261111`, sampled from the same `600`-pair corpus)**:
  - Candidate & Post-Fix Hybrid: **82.00%** Acc, **0.8166** Macro F1, **12.50%** `INSUF->CON`, **5.83%** Overall FCR.
  - Pretrained: **67.33%** Acc, **0.6713** Macro F1, **29.17%** `INSUF->CON`, **16.50%** Overall FCR.
  - Legacy: **38.00%** Acc (**0.4026** F1, **62.14%** FCR); Rules-Only: **34.00%** (**0.1986** F1).
- **Adversarial Robustness Set (`N = 72`, 12 Phenomena)** & **Counterfactual Probes (`10` pairs)** (see [`ADVERSARIAL_ROBUSTNESS_REPORT.md`](ADVERSARIAL_ROBUSTNESS_REPORT.md)):
  - Candidate: **86.11%** (`62/72`), `INSUF->CON = 14.29%`, `Overall FCR = 7.84%` vs Production Hybrid **84.72%** (`61/72`) vs Pretrained **66.67%** (`48/72`, Overall FCR `29.41%`).
  - Scored **100%** (`6/6`) on `compound_hypotheses`, `long_irrelevant_context`, `lowercase_informal`, `missing_fields`, `partial_evidence`, and `shortcut_trap`.
  - Scored **66.7%** (`4/6`) on `typos`, `reordered_evidence`, `conflicting_dates`, and `negation_double_neg`.
  - Passed **9 / 10** counterfactual lexical-cue & minimal-perturbation probes (`Pretrained`: `7 / 10`), passing neutral `"document"`/`"record"`, `"confirmed"`, `"cancelled"` redirect, JSON/table format shifts, and numeric/currency/city flips, while failing `CF-NOISE-09` (inferring digital key activation from payment capture + queued email text).
- **Safe Abstention (`NEEDS_HUMAN_REVIEW`, `top1 < 0.55` or `margin < 0.12`)**:
  - Triggered on only **1.50%** (`9 / 600`) of unseen inputs (`4 CONTRADICTED`, `3 SUPPORTED`, `2 INSUF`), shifting selective accuracy slightly (`82.00% -> 82.23%`) with essentially unchanged selective FCR (`5.75% -> 5.82%`). Low-confidence gating catches edge ambiguity rather than confident temporal errors.

---

## 6. Answers to the 10 Mandatory Scientific Audit Questions

1. **Learned semantics vs templates?** Genuinely learned semantic claim-evidence alignment across 14 novel families & 5 styles (`82.00%` Acc, `0` train/test duplicates, `+16.00 pp` over Pretrained, `9/10` counterfactual invariance), though weak on prose chronological paradoxes (`33.3%`) and SKU variant mismatches (`52.4%`).
2. **Comparison to `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`?** `+16.00 pp` Accuracy, `+0.1742` Macro F1, `-23.00 pp` `INSUF->CON`, `-16.00 pp` Overall FCR, `-0.1595` ECE; only regresses on `chronological_event_paradox` and `sku_variant_mismatch` due to conservative contradiction recall (`69.0%` vs `91.5%`).
3. **Why did `best_model` fail & does candidate fix it?** Legacy `best_model` collapsed into aggressive over-contradiction (`62.00%` Overall FCR, `58.00%` `SUP->CON`, `0.4884` ECE, `36.67%` Acc). Candidate fixes `SUP->CON` (`0.00%`), reduces `Overall FCR` (`5.75%`), and cuts raw ECE (`0.1000`).
4. **Did EvidenceBench-v2 lexical shortcuts transfer?** Neutral cue probes (`"document"`, `"record"`, `"confirmed"`, `"cancelled"`) and `shortcut_trap` (`100%`) confirm wrapper shortcuts did NOT transfer blindly, though provisioning words (`"license email queued"` in `CF-NOISE-09`) can still trigger premature `SUPPORTED`.
5. **Unseen False Contradiction Rates?** `INSUF->CON = 11.50%` (`23/200`), `SUP->CON = 0.00%` (`0/200`), `Overall FCR = 5.75%` (`23/400`).
6. **Probability calibration?** Raw softmax scores are moderately well-calibrated (`ECE = 0.1000`, `Brier = 0.2958`). Legacy `T=5.0` degraded ECE (`0.2574`); after replacing it with validation-fitted `T=1.36` (from `EvidenceBench-v2/validation.jsonl`, `N=450`), Hybrid ECE improved to **`0.0572`** (`Brier = 0.2794`).
7. **Does Abstention help?** Marginal effect (`1.50%` abstention rate, `+0.23 pp` selective accuracy) because misclassifications often occur with high confidence. Confidence-based abstention alone is not yet a sufficient safety gate.
8. **Does Production Hybrid protect cleanly?** Yes after remediation: evidence-driven `check_provisioning_without_download()` and linkage checks protect PayPal fulfillment flows (`APPLICATION_INTEGRATION_SMOKE_TEST.md`) without causing the `14` false-insufficient claim-keyword regressions (`82.00%` on $N=600$, `84.72%` on $N=72$).
9. **Weak / unsafe scenarios?** Prose date ordering (`chronological_event_paradox`), SKU attribute mismatch, auth-hold vs contradiction (`checkout_auth_vs_settlement`), double negation, typos, and **any live real-world PayPal disputes** (untested).
10. **Minimum prerequisites before real PayPal merchant reliance?** Advisory-only labeling + mandatory merchant sign-off, deterministic PayPal REST API ground-truth verification, fixing `INV-` hyphen order-ID regex in `DeterministicValidator`, expanding temporal/SKU adversarial training, and validating against externally adjudicated real PayPal merchant disputes.

---

## 7. Application Integration & Regression Checks Summary

- **Live End-to-End Smoke Test** (`APPLICATION_INTEGRATION_SMOKE_TEST.md`): Verified staging ZIP extraction, live HTTP backend (`:8019`) loading candidate weights, `POST /verify-claims` (live neural verdicts + rule overrides + fixed SQLite `model_checkpoint` metadata), `POST /analyze-stream` (11 SSE events), mandatory merchant approval gate (`HTTP 400`), fail-closed missing-checkpoint server (`:8020` -> `MODEL_UNAVAILABLE` & `HTTP 503`), and `frontend/npm run build` (`0` exit code).
- **Offline Pytest Regression Suites (Post-Remediation)**: **312 passed, 0 failed**:
  - `ai/tests/` + core backend acceptance/security suites (`test_sprint_final_features.py`, `test_paypal_dispute_rescue_suite.py`, `test_phase2_6_security.py`, `test_phase2_5_acceptance.py` with updated candidate non-abstaining contract assertions, `test_calibration_and_metrics_consistency.py`): **199 passed**.
  - Remaining offline backend suites (`test_all_module_imports.py`, `test_backend_api.py`, `test_comprehensive_audit_remediation.py`, `test_cryptographic_trust_boundary_7_attacks.py`, `test_lifecycle_and_provenance_audit.py`, `test_production_credential_isolation.py`): **113 passed**.

---

## Final Audit Decision

**`GENERALIZATION DEMONSTRATED ON INDEPENDENT SYNTHETIC DATA`**  
*(Paired with explicit limitation disclosure: **`REAL-WORLD GENERALIZATION NOT ASSESSED`** — benchmark metrics reflect independently authored synthetic test cases, not production PayPal merchant dispute logs; production deployment must remain strictly **advisory-only with deterministic rules and mandatory human merchant review**.)*
