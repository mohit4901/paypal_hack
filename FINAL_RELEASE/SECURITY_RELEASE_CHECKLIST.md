# ProofLedger Security & Compliance Release Checklist

## 1. Security Architecture & Boundary Verification

- [x] **Zero Autonomous Financial Movement**: ProofLedger cannot move money, refund transactions, or submit dispute evidence without explicit merchant approval.
- [x] **Mandatory Merchant Sign-off & Digest Binding**: Submissions to `POST /api/v2/disputes/{id}/provide-evidence` strictly enforce `merchant_approved: true` (`HTTP 400`) and verify server-side SHA-256 `approval_id` + `approved_digest` (`HTTP 409 STALE_OR_MODIFIED_APPROVAL` if evidence or draft changes post-approval).
- [x] **Local Demo Live-Submission Guardrail**: `require_live_paypal: true` rejects local demo scenarios with `HTTP 400 LOCAL_DEMO_NOT_LIVE_PAYPAL`.
- [x] **Production Credential Isolation**: `APP_ENV=production` or `SEED_DEMO_CREDENTIALS=false` automatically deactivates demo sellers (`seller_alpha`, `seller_beta`) and rejects demo bearer keys with `HTTP 401`.
- [x] **Multi-Tenant Data Isolation**: All database queries enforce strict `seller_id` predicate binding. Verified across tenant boundary test suites.
- [x] **Idempotency & Duplicate Submission Defense**: Submissions are cryptographically sealed in the database; subsequent submission attempts return `HTTP 409 Conflict`.
- [x] **Read-Only Agent Toolkit Integration**: PayPal Agent Toolkit tools are constrained to read-only capabilities. No state-mutating agent actions.
- [x] **Cryptographic Ledger Integrity**: Ledger blocks are verified with SHA-256 hash chains and asymmetric Ed25519 signatures.

---

## 2. Privacy & Regulatory Compliance

- [x] **PCI DSS Non-Applicability**: ProofLedger does not collect, transmit, or store Primary Account Numbers (PAN) or Card Verification Values (CVV). All transaction references use PayPal Order IDs and Capture IDs.
- [x] **GDPR / Privacy Adherence**: Customer PII is limited to buyer email addresses associated with verified PayPal transactions and is scrubbed from public export logs.
- [x] **Secret Hygiene**: All sandbox client secrets and credentials are loaded exclusively from `.env` files and excluded from git version control.

