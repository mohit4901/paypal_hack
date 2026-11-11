# EvidenceBench-v2: Final Dataset Audit Report

## 1. Executive Summary & Honest Provenance Status

EvidenceBench-v2 (`ai/data/processed/evidencebench_v2/`) is an internally curated 3,000-pair NLI dataset created by [`scripts/curate_evidencebench_v2.py`](file:///Users/mohitmudgil/Desktop/paypal/scripts/curate_evidencebench_v2.py).

- **Total Pairs**: 3,000 (`1,000` `SUPPORTED`, `1,000` `CONTRADICTED`, `1,000` `INSUFFICIENT_EVIDENCE` overall)
- **Exact Claim+Evidence Pair Duplicates**: 0 across the entire 3,000-pair corpus (`0` train/test or val/test overlap).
- **Synthetic vs External Provenance**:
  - **Tiers 1, 2, and 4 (2,100 pairs = 70%)**: **100% synthetic** (`is_synthetic: true`), generated deterministically from authored e-commerce templates with randomized order IDs, tracking IDs, dates, amounts, and names. **No independent real-world merchant dispute trial data is included.**
  - **Tier 3 (900 pairs = 30%)**: Drawn from `ai/data/processed/feverous/train.jsonl` (`is_synthetic: false`), **but degraded by placeholder transformation** (see Section 4 below).

---

## 2. Exact Reconciled Split & Class Support Counts (Verified Directly on Disk)

In `curate_evidencebench_v2.py`, partitioning was executed **within each `(tier, family)` group** (70%/15%/15% random slice per group) rather than label-stratified across the global split. Consequently, individual split class counts vary slightly around 33.3%:

| Split | File | Total Pairs | `SUPPORTED` | `CONTRADICTED` | `INSUFFICIENT_EVIDENCE` | Tiers (T1 / T2 / T3 / T4) |
|---|---|---:|---:|---:|---:|---|
| **Train** | `train.jsonl` | 2,100 | **703** | **702** | **695** | 420 / 840 / 630 / 210 |
| **Validation** | `validation.jsonl` | 450 | **146** | **154** | **150** | 90 / 180 / 135 / 45 |
| **Internal Test** | `test.jsonl` | 450 | **151** | **144** | **155** | 90 / 180 / 135 / 45 |
| **Total** | | **3,000** | **1,000** | **1,000** | **1,000** | **600 / 1,200 / 900 / 300** |

---

## 3. Grouped Split & Template Leakage Findings

- **Actual Split Mechanism**: Pairs were grouped by `(tier, family)` and split 70/15/15 *within* every group (`seed=1337`).
- **Implication**: While zero identical strings overlap between splits, **all 12 Tier-2 template families and Tier-1/Tier-4 template patterns appear in train, validation, and test** (differing only in randomized entity values). Therefore, high Tier-1 (`100%`), Tier-2 (`97.22%`), and Tier-4 (`93.33%`) accuracy reflects in-family generalization rather than zero-shot generalization to unseen template structures.

---

## 4. FEVEROUS Transformation Audit Findings (Tier 3, 900 Pairs)

Inspection of [`scripts/curate_evidencebench_v2.py`](file:///Users/mohitmudgil/Desktop/paypal/scripts/curate_evidencebench_v2.py#L333-L350) and `ai/data/processed/evidencebench_v2/{train,validation,test}.jsonl` revealed a critical transformation flaw:

1. Because `evidence_text` in `ai/data/processed/feverous/train.jsonl` was empty or ended with `_title` for all 900 sampled claims, **`900 / 900` (100%) of Tier-3 examples** (`630/630` train, `135/135` val, `135/135` test) were converted into generic title placeholders instead of factual evidence sentences.
2. Furthermore, `make_tier3()` introduced a **label-correlated lexical cue**:
   - `SUPPORTED` & `CONTRADICTED` (600 pairs: 427 train, 86 val, 87 test) received: `"Authoritative encyclopedia document regarding {title}."`
   - `INSUFFICIENT_EVIDENCE` (300 pairs: 203 train, 49 val, 48 test) received: `"Authoritative encyclopedia record regarding {title}."`
3. Because `SUPPORTED` and `CONTRADICTED` examples lacked the actual Wikipedia evidence sentences needed to confirm or refute claims, Tier-3 test accuracy dropped to **59.26% (`80/135`)** and produced **all 37 false contradictions (`29 SUP→CON + 8 INSUF→CON`)** on the test set.

---

## 5. Quality Gates Status

| Quality Gate | Target | Observed Result | Audit Status |
|---|---|---|---|
| Total Size & Global Class Balance | 3,000 (1,000/1,000/1,000) | 3,000 (1,000/1,000/1,000) | **PASSED** |
| Exact Duplicate Pair Rate | 0 | 0 exact duplicates (`train∩test = 0`, `val∩test = 0`) | **PASSED** |
| Unseen Template-Family Holdout | Unseen families in test | Split *within* `(tier, family)` groups | **UNVERIFIED / NOT HELD OUT** |
| FEVEROUS Evidence Content Fidelity | Genuine factual evidence | 900/900 collapsed to `"document/record regarding {title}"` | **FAILED (DEGRADED)** |
| Independent Real-World Merchant Trial | Live merchant disputes | 0 real merchant disputes in v2 | **NOT PERFORMED** |
