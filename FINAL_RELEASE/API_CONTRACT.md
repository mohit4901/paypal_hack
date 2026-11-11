# ProofLedger API Contract Specification

## Base URL & Authentication
- Base URL: `http://127.0.0.1:8000/api/v2`
- Auth Header: `Authorization: Bearer <SELLER_API_KEY>`

---

## 1. Dispute & Evidence Endpoints

### `GET /disputes` & `GET /disputes/{dispute_id}`
Retrieves disputes for the authenticated seller, separating live PayPal Sandbox disputes (`PAYPAL_SANDBOX_LIVE`) from local demo records (`LOCAL_DEMO_SCENARIO`).

### `POST /disputes/{dispute_id}/analyze-stream` (SSE)
Streams real-time Server-Sent Events (`text/event-stream`) across the 10 sequential backend analysis stages (`retrieve_dispute` through `ready_for_review`), ending with a `complete` payload containing `analysis_stages`, `evidence_items`, `grounding_sources`, `draft_response`, and canonical SHA-256 `evidence_digest`.

### `POST /disputes/{dispute_id}/prepare-response`
Synchronous JSON equivalent of the evidence validation, deterministic rules gate, and grounded draft generator.

### `POST /disputes/{dispute_id}/upload-evidence`
Accepts multipart file upload (`file`), persists filename, size, and SHA-256 hash in SQLite (`uploaded_evidence_files`), and returns `file_id`, `file_sha256`, and `proof_document_url`.

### `POST /disputes/{dispute_id}/approve-evidence`
Server-side cryptographic approval binding `seller_id`, `dispute_id`, timestamp, and canonical SHA-256 `evidence_digest` in `evidence_approvals`.

**Request Body:**
```json
{
  "carrier_name": "USPS",
  "tracking_number": "9400111899223192348571",
  "evidence_notes": "Approved defense draft text.",
  "proof_document_url": "https://proofledger.local/docs/FILE-123/receipt.pdf",
  "signature_confirmed": true
}
```

### `POST /disputes/{dispute_id}/provide-evidence`
Submits fulfillment evidence (`PROOF_OF_FULFILLMENT`).
- Requires `merchant_approved: true` (HTTP 400 otherwise).
- When `approval_id` / `approved_digest` are supplied, verifies seller ownership and digest match; returns HTTP 409 `STALE_OR_MODIFIED_APPROVAL` if evidence or draft changed after approval.
- Enforces idempotency per `(dispute_id, seller_id)` (HTTP 409 `DUPLICATE_SUBMISSION`).
- Rejects local demo scenarios with HTTP 400 `LOCAL_DEMO_NOT_LIVE_PAYPAL` when `require_live_paypal: true`.
