# ProofLedger API Reference (`v2.0.0`)

- **Base URL**: `http://127.0.0.1:8000`
- **REST Prefix**: `/api/v2`
- **Authentication**: `Authorization: Bearer <SELLER_API_KEY>` (tenant-scoped via `get_current_seller`)
- **Interactive Docs**: `http://127.0.0.1:8000/docs`

---

## 1. System, AI & MCP Endpoints

| Method | Path | Auth | Description |
| :--- | :--- | :---: | :--- |
| `GET` | `/health` | No | Service liveness and hash-chain ledger integrity check |
| `GET` | `/api/v2/system/status` | Opt | Aggregate readiness (Backend, SQLite, PayPal OAuth/Webhook, AI model) |
| `GET` | `/api/v2/ai/status` | No | Active checkpoint path, load status (`ONLINE` / `MODEL_UNAVAILABLE`), device, size |
| `POST` | `/api/v2/ai/test-inference` | Yes | Diagnostic NLI check; returns HTTP `503` if model unavailable |
| `POST` | `/api/v2/mcp` | No | Read-only JSON-RPC 2.0 MCP endpoint (`initialize`, `tools/list`, `tools/call`) |

---

## 2. Disputes, Evidence & Approval Lifecycle

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v2/disputes` | List seller disputes, tagging live PayPal (`PAYPAL_SANDBOX_LIVE`) vs. `LOCAL_DEMO_SCENARIO` |
| `GET` | `/api/v2/disputes/{dispute_id}` | Fetch single dispute details, evidence checklist, and provenance metadata |
| `POST` | `/api/v2/disputes/{dispute_id}/analyze-stream` | **SSE stream** (`text/event-stream`) across 10 verification stages ending with `complete` |
| `POST` | `/api/v2/disputes/{dispute_id}/prepare-response` | Synchronous rules-first + DeBERTa-v3 claim alignment and grounded draft generation |
| `POST` | `/api/v2/disputes/{dispute_id}/upload-evidence` | Multipart PDF/JPG/PNG upload (`<= 10 MB`); returns `file_id`, `file_sha256`, `proof_document_url` |
| `POST` | `/api/v2/disputes/{dispute_id}/approve-evidence` | Seals canonical SHA-256 `evidence_digest` in `evidence_approvals` and returns `approval_id` |
| `POST` | `/api/v2/disputes/{dispute_id}/provide-evidence` | Submits `PROOF_OF_FULFILLMENT` to PayPal API (live) or records `LOCAL_SIMULATED_SUBMISSION` (local demo) |
| `POST` | `/api/v2/disputes/verify-claims` | Batch deterministic + DeBERTa-v3 verification of custom claims against evidence |

### Error Contracts Enforced on Submission
- `400 MERCHANT_APPROVAL_REQUIRED` (`merchant_approved=false`)
- `400 LOCAL_DEMO_NOT_LIVE_PAYPAL` (`require_live_paypal=true` on a local demo identifier)
- `409 STALE_OR_MODIFIED_APPROVAL` (digest changed after `approve-evidence`)
- `409 DUPLICATE_SUBMISSION` (duplicate evidence submission for same `(dispute_id, seller_id)`)

---

## 3. PayPal Sandbox Integration Endpoints

| Method | Path | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v2/paypal/sync` | Pulls live captures, orders, webhook events, and disputes from `api-m.sandbox.paypal.com` |
| `GET` | `/api/v2/paypal/live-feed` | Live OAuth status, sample capture/order verification, and webhook count |
| `GET` | `/api/v2/paypal/live-order/{order_id}` | Direct `GET /v2/checkout/orders/{order_id}` query |
| `GET` | `/api/v2/paypal/live-capture/{capture_id}` | Direct `GET /v2/payments/captures/{capture_id}` query |
| `POST` | `/api/v2/paypal/generate-live-transaction` | Creates an authentic PayPal Sandbox order (`ORDER_CREATED`; `dispute_id` remains `null`) |
| `POST` | `/api/v2/paypal/orders/{order_id}/capture` | Captures an approved PayPal Sandbox order (rejects unapproved orders with HTTP `422`) |
| `POST` | `/api/v2/paypal/import-live` | Imports an existing PayPal Sandbox transaction into seller workspace |

---

## 4. Seller, Transactions & Audit Ledger Endpoints

- **Sellers**: `POST /api/v2/sellers/register`, `GET /api/v2/sellers/me`, `POST /api/v2/sellers/rotate-key`, `POST /api/v2/sellers/revoke`
- **Transactions**: `GET /api/v2/transactions`, `POST /api/v2/transactions`, `GET /api/v2/transactions/{order_id}`, `POST /api/v2/transactions/{order_id}/evidence`
- **Ledger & Events**: `GET /api/v2/overview`, `GET /api/v2/events`, `GET /api/v2/events/{event_id}/verify`, `GET /api/v2/ledger`, `GET /api/v2/ledger/validate`, `GET /api/v2/security`
