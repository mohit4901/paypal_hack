# ProofLedger — PayPal Dispute Rescue

ProofLedger is an evidence verification and grounded dispute-response assistant built for PayPal merchants, focusing specifically on **Merchandise or Service Not Received (`MERCHANDISE_OR_SERVICE_NOT_RECEIVED`)** disputes.

## Scope & Safety Architecture

- **Deterministic Rules-First Authority**: Order linkage, PayPal payment capture matching, amount/currency matching, and carrier tracking syntax (`FORMAT_VALID`) are enforced deterministically.
- **Assistive Semantic NLI**: Pretrained and domain-adapted DeBERTa-v3 NLI provides non-autonomous semantic alignment signals and sentence-level source grounding. It can never override a deterministic mismatch or fabricate delivery confirmation.
- **Mandatory Merchant Review & Approval**: Evidence submission requires server-side SHA-256 evidence digest binding (`POST /api/v2/disputes/{dispute_id}/approve-evidence`). Any edit after approval automatically invalidates the previous approval.
- **Honest Provenance Separation**: Live PayPal Sandbox REST API data (`PAYPAL_SANDBOX_LIVE`) is strictly separated from local demo scenarios (`LOCAL_DEMO — NOT A PAYPAL DISPUTE`).

## AI Evidence Reasoning — ProofLedger

ProofLedger uses a fine-tuned DeBERTa-v3 model to assist with semantic alignment between merchant claims and submitted evidence.

The candidate achieved 86.00% accuracy and 0.8589 Macro F1 on an internally curated 450-example EvidenceBench-v2 test split. This benchmark contains synthetic merchant scenarios and transformed FEVEROUS examples; it is not an independent real-world PayPal merchant dispute evaluation.

Evaluation identified a significant weakness in the transformed FEVEROUS subset, including false contradiction predictions. Accordingly, model predictions remain advisory and cannot override deterministic transaction verification, delivery evidence requirements, or mandatory merchant approval.

The production workflow retains a rules-first safety architecture. Human review and explicit merchant approval are required before evidence submission.

### Independent Unseen Generalization Audit (`proofledger_unseen_v1`)

To evaluate out-of-distribution generalization beyond EvidenceBench-v2, an independent leak-free synthetic audit corpus (`N = 600` across 14 novel scenario families + `N = 72` adversarial stress suite; 0 exact or near-duplicate overlaps against 23,158 historical rows) was evaluated in [`FINAL_RELEASE/INDEPENDENT_GENERALIZATION_AUDIT/INDEPENDENT_GENERALIZATION_REPORT.md`](FINAL_RELEASE/INDEPENDENT_GENERALIZATION_AUDIT/INDEPENDENT_GENERALIZATION_REPORT.md):

- **Candidate (`ai/artifacts/candidates/deberta_v3_inr_v1/best`) & Production Hybrid**: **82.00%** accuracy, **0.8226** Macro F1, **11.50%** `INSUF->CON` rate, **5.75%** Overall False-Contradiction Rate, and **0.0572** ECE under validation-fitted `T=1.36` (vs **66.00%** / `0.6484` / `21.75%` Overall FCR for Pretrained `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`, $p = 2.438 \times 10^{-12}$, and **36.67%** / `62.00%` Overall FCR for Legacy `ai/artifacts/best_model`).
- **Adversarial Robustness (`N = 72`) & Counterfactual Probes (`10` pairs)**: Candidate achieved **86.11%** accuracy (Production Hybrid **84.72%**, `9/10` counterfactual pass) vs **66.67%** Pretrained (`7/10` pass).
- **Documented Limitations & Outcome**: **`GENERALIZATION DEMONSTRATED ON INDEPENDENT SYNTHETIC DATA`** / **`REAL-WORLD GENERALIZATION NOT ASSESSED`**. Notable weaknesses remain on chronological prose ordering (`33.3%`), subtle SKU variant mismatches (`52.4%`, `CONTRADICTED` recall `69.0%`), and synthetic in-house authorship (not real PayPal dispute logs or external human adjudication). Overriding the checkpoint path is supported via `PROOFLEDGER_MODEL_PATH` (defaulting to `ai/artifacts/candidates/deberta_v3_inr_v1/best`, failing closed with `MODEL_UNAVAILABLE` if missing).

## Live PayPal Integration

- OAuth 2.0 Client Credentials against `https://api-m.sandbox.paypal.com`
- Disputes API (`GET /v1/customer/disputes`, `GET /v1/customer/disputes/{id}`, `POST /v1/customer/disputes/{id}/provide-evidence`)
- Read-only Model Context Protocol (MCP) JSON-RPC interface (`/api/v2/mcp`)

## Quick Start

See [`SETUP.md`](SETUP.md) for detailed instructions.

```bash
# Install Python dependencies
pip install -r requirements.txt

# Start Backend (FastAPI on port 8000)
uvicorn backend.main:app --host 127.0.0.1 --port 8000

# Start Frontend (React + Vite on port 5173)
cd frontend && npm install && npm run dev
```

## Verification & Testing

```bash
# Run full automated test suite (ai/tests + backend/)
python3 -m pytest ai/tests/ backend/ -q

# Run live headless Chrome End-to-End browser verification
python3 scripts/e2e_browser_verify.py
```

## License

Released under the [MIT License](LICENSE).
