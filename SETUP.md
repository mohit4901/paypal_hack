# ProofLedger Setup & Verification Guide

## 1. Prerequisites

- **Python**: `3.9+`
- **Node.js**: `18+` (with `npm`)
- **Google Chrome** *(optional, only required for `scripts/e2e_browser_verify.py`)*
- **PayPal Developer Sandbox Credentials** *(required only for live PayPal Sandbox API sync/submission)*

---

## 2. Environment Configuration

Copy the template and configure environment variables in `.env` (or `ai/.env`):

```bash
cp .env.example .env
```

Key variables:
- `PAYPAL_CLIENT_ID` & `PAYPAL_CLIENT_SECRET`: PayPal Sandbox REST credentials (`https://api-m.sandbox.paypal.com`).
- `PROOFLEDGER_SIGNING_KEY`: Server-side HMAC/digest signing secret used for evidence approval binding in development/production.
- `PROOFLEDGER_MODEL_PATH` *(optional)*: Overrides default checkpoint resolution (`ai/artifacts/candidates/deberta_v3_inr_v1/best`). If the configured checkpoint directory or `model.safetensors` is missing, the backend **fails closed** with `MODEL_UNAVAILABLE`.

---

## 3. Model Weights Placement

Large binary `.safetensors` files exceed GitHub's 100 MB file limit and are excluded from version control via `.gitignore`. Config and tokenizer files are already committed in:

```
ai/artifacts/candidates/deberta_v3_inr_v1/best/
```

To enable neural NLI inference locally, extract `proofledger_candidate_weights.zip` from the repository root (or GitHub Release asset) so `model.safetensors` sits at:

```
ai/artifacts/candidates/deberta_v3_inr_v1/best/model.safetensors
```

Expected SHA-256 (`FINAL_RELEASE/SHA256_CHECKSUMS.txt`):
`2afd4cf10a28b274445073c6fc3c880c54708d5886ca3a2c54ed45857a94e2ea`

---

## 4. Running the Application Locally

### Backend API (`127.0.0.1:8000`)

```bash
pip install -r requirements.txt

PYTHONPATH="$(pwd):$(pwd)/ai:$(pwd)/ai/src" \
python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Verify readiness:
```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/api/v2/ai/status
```

### Frontend Workspace (`127.0.0.1:5173`)

In a second terminal:
```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173` (interactive FastAPI docs at `http://127.0.0.1:8000/docs`).

---

## 5. Verification & Test Suites

```bash
# 1. Frontend rules unit tests & production bundle check
node --test frontend/tests/frontend_rules.test.mjs
cd frontend && npm run build

# 2. Offline AI & backend pytest suite (312 tests)
python3 -m pytest ai/tests/ \
  backend/test_sprint_final_features.py \
  backend/test_paypal_dispute_rescue_suite.py \
  backend/test_phase2_6_security.py \
  backend/test_phase2_5_acceptance.py \
  backend/test_calibration_and_metrics_consistency.py \
  backend/test_all_module_imports.py \
  backend/test_backend_api.py \
  backend/test_comprehensive_audit_remediation.py \
  backend/test_cryptographic_trust_boundary_7_attacks.py \
  backend/test_lifecycle_and_provenance_audit.py \
  backend/test_production_credential_isolation.py -q

# 3. Live backend integration & fail-closed missing-checkpoint smoke test
python3 scripts/run_smoke_test.py

# 4. Headless Chrome E2E browser suite (stops/starts :8000 and :5173 cleanly)
python3 scripts/e2e_browser_verify.py
```
