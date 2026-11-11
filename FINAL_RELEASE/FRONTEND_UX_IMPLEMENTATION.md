# ProofLedger Frontend UX Architecture & Implementation

## 1. Design Philosophy: Transparent Two-Column Merchant Workflow

ProofLedger turns PayPal disputes into verifiable, source-grounded defense packages without hiding behind opaque AI text generation.

### Primary Navigation (`Sidebar.jsx`)
1. **Dispute Inbox** (`DisputeInboxTab.jsx`)
2. **Resolve Dispute** (`ResolveDisputeView.jsx`)
3. **Orders & Evidence** (`TransactionsTab.jsx`)
4. **Store Overview** (`DashboardTab.jsx`)
5. **Integrations & Setup** (`SettingsTab.jsx`)

---

## 2. Dispute Inbox (`DisputeInboxTab.jsx`)

- Displays every case with explicit provenance badges:
  - `LIVE PAYPAL` (retrieved from `GET /v1/customer/disputes`)
  - `LOCAL DEMO — NOT A PAYPAL DISPUTE` (local store demonstration scenario)
- When zero active live disputes exist in PayPal Sandbox, renders an honest empty-state banner explaining that `GET /v1/customer/disputes` returned 0 items.
- Shows dynamically computed dispute volume, active count, response deadlines, and requested evidence (`PROOF_OF_FULFILLMENT`).

---

## 3. Two-Column Resolve Dispute Workspace (`ResolveDisputeView.jsx`)

Responsive across **1440×900 desktop**, **1280×800 laptop**, and **390×844 mobile** with zero horizontal overflow.

### Left Column — Dispute Facts & Fulfillment Input
- **Dispute Facts & Requested Evidence**: Customer claim, reason (`MERCHANDISE_OR_SERVICE_NOT_RECEIVED`), deadline, and PayPal policy requirement (`PROOF_OF_FULFILLMENT`).
- **Linked Store Order & PayPal Payment**: Order ID, Capture ID, and exact captured amount.
- **Fulfillment Evidence Form**: Shipping carrier selector, tracking number input, multipart file upload (`POST /upload-evidence` with SHA-256 digest), merchant fulfillment notes, and **Analyze Evidence** button.

### Right Column — Real-Time 10-Stage SSE Analysis, Evidence Output, Citations & Approval
1. **Live 10-Stage Backend SSE Timeline** (`POST /analyze-stream`):
   1. Retrieving PayPal dispute
   2. Reading requested evidence
   3. Linking payment and order
   4. Validating amount/currency
   5. Validating tracking
   6. Checking delivery evidence
   7. Running semantic NLI analysis
   8. Identifying evidence gaps
   9. Preparing grounded response
   10. Ready for merchant review
2. **Strict Evidence Verification Taxonomy**:
   Distinguishes `VERIFIED_ON_PAYPAL`, `VERIFIED_ON_MERCHANT_RECORD`, `FORMAT_VALID`, `DELIVERY_CONFIRMED`, `LOOKUP_NOT_CONFIGURED`, `MERCHANT_ATTESTATION`, `NOT_PROVIDED`, and `NOT_INDEPENDENTLY_VERIFIED`. Never labels unconfigured carrier lookups as `"Not found"`.
3. **Editable Grounded Draft & Sentence Citations**:
   Displays every factual claim alongside its supporting source and verification status.
4. **Server-Side Approval & Post-Edit Invalidation**:
   - **Approve Evidence Package** creates a server-side SHA-256 `approval_id` + `evidence_digest`.
   - Editing the carrier, tracking number, uploaded file, notes, or draft response immediately invalidates the prior approval and requires explicit re-approval.
   - Live PayPal submission is disabled for local demo scenarios (`LOCAL DEMO — NOT A PAYPAL DISPUTE`).
