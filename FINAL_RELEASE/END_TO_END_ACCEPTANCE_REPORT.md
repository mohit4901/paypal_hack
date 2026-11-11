# ProofLedger End-to-End Acceptance Report

## 1. Unique Automated Test Count (`pytest ai/tests/ backend/ --collect-only -q`)

- **Total Unique Tests Executed**: **324**
- **Passed**: **324 (100%)**
- **Failed / Skipped**: **0**
- **Runtime**: 95.79s (`python3 -m pytest ai/tests/ backend/ -q`)

### Breakdown by Test Category
| Category | Files | Count |
|---|---|---:|
| **Unit Tests** | `ai/tests/unit/test_lifecycle_validation.py` (52), `ai/tests/unit/test_proofledger.py` (48), `backend/test_all_module_imports.py` (60), `backend/test_calibration_and_metrics_consistency.py` (1) | **161** |
| **API & Integration Tests** | `ai/tests/api/test_api.py` (15), `ai/tests/api/test_webhook.py` (14), `backend/test_backend_api.py` (13), `backend/test_comprehensive_audit_remediation.py` (13), `backend/test_lifecycle_and_provenance_audit.py` (9), `backend/test_paypal_dispute_rescue_suite.py` (19), `backend/test_phase2_5_acceptance.py` (5), `backend/test_sprint_final_features.py` (3) | **91** |
| **Live PayPal Sandbox & Model Eval** | `backend/test_paypal_live.py` (6), `backend/test_paypal_sandbox_complete_lifecycle.py` (5), `backend/test_deberta_generalization_100.py` (1) | **12** |
| **Security & Trust Boundary Tests** | `ai/tests/security/test_adversarial_audit*.py` (27), `backend/test_cryptographic_trust_boundary_7_attacks.py` (11), `backend/test_phase2_6_security.py` (15), `backend/test_production_credential_isolation.py` (7) | **60** |
| **Total Unique Tests** | | **324** |

---

## 2. Live Headless Google Chrome E2E Browser Verification (`scripts/e2e_browser_verify.py`)

Executed against live FastAPI (`127.0.0.1:8000`) + live Vite React (`127.0.0.1:5173`) via Chrome DevTools Protocol:
- Verified responsive layout with **0 horizontal overflow** at `1440x900` (desktop), `1280x800` (laptop), and `390x844` (mobile).
- Verified Inbox renders honest `LOCAL DEMO — NOT A PAYPAL DISPUTE` provenance and zero forbidden placeholder strings (`PP-D-EXAMPLE`, `"Illustrative interface specification"`).
- Verified real-time **10-stage SSE analysis stream** (`POST /analyze-stream`), evidence taxonomy (`VERIFIED_ON_MERCHANT_RECORD`, `FORMAT_VALID`, `LOOKUP_NOT_CONFIGURED`), live re-analysis on tracking edit, server-side SHA-256 approval sealing (`EAPPR-...`), immediate approval invalidation on post-approval draft edit, and **0 uncaught JS exceptions**.
- Vite production build (`cd frontend && npm run build`) compiles cleanly (`dist/assets/index-wG85BYr2.js`, 308.20 kB, built in 1.04s).

---

## 3. Live PayPal Sandbox Verification (`scripts/test_live_paypal_sandbox_dispute_flow.py`)

- OAuth 2.0 Client Credentials token acquired in `1028.56ms` from `https://api-m.sandbox.paypal.com`.
- `GET /v1/customer/disputes` returned **HTTP 200** (`Paypal-Debug-Id: f9491489e3ad1`, latency `1105.68ms`, `items: []`).
- Read-only MCP tool `list_disputes` succeeded (`HTTP 200`); mutation tool `create_refund` blocked (`SECURITY_PROHIBITED`, `-32000`).
- Local scenario `DSP-3EU95140-01` honestly returned HTTP 404 `RESOURCE_NOT_FOUND` (`debug_id: f240973116103`) on live endpoint and recorded `LOCAL_SIMULATED_SUBMISSION` locally. Live `provide-evidence` against a real PayPal dispute ID remains **UNVERIFIED** (0 live buyer disputes in Sandbox), and automated carrier lookup remains **NOT CONFIGURED** (`LOOKUP_NOT_CONFIGURED`).
