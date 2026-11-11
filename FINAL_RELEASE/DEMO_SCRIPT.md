# ProofLedger Final Hackathon Demo Script (Live PayPal Buyer Dispute Flow)

## Video Overview
- **Duration**: ~2 minutes 45 seconds – 3 minutes 15 seconds
- **Format**: Screen capture showing PayPal Sandbox (`https://www.sandbox.paypal.com`) + ProofLedger (`http://127.0.0.1:5173` against live backend `:8000`) with spoken voiceover
- **Central Message**: *ProofLedger never guesses or fabricates dispute outcomes — it ingests a genuine PayPal dispute, separates verified records from unverified claims, binds merchant review via server-side SHA-256 approval, and submits grounded evidence straight back to PayPal.*
- **Pre-Recording Precaution**: Never claim or imply that ProofLedger OCR-reads inside uploaded PDFs/images. Always point directly to **`SHA-256 integrity verified`** and **`CONTENT_NOT_EXTRACTED`**.

---

## Pre-Recording Preparation (Do 2 Minutes Before Hitting Record)

1. Have a completed Sandbox payment sent from your **Personal (Buyer)** sandbox account to your **Business (Merchant)** sandbox account (`https://www.sandbox.paypal.com`) — do **not** use capture `10A71705XW788203L`.
2. Keep `https://www.sandbox.paypal.com` logged into the Buyer account on **Tab 1** (on that `COMPLETED` transaction details page, ready to click **Report a Problem** — or already filed if you prefer filing right at the start of the recording).
3. Keep ProofLedger open at `http://127.0.0.1:5173` on **Tab 2**, and have a sample tracking receipt PDF/PNG (`< 10 MB`) ready on your Desktop.

---

## Storyboard & Spoken Script

### Act 1: Real Buyer Files an Item Not Received Dispute on PayPal Sandbox (0:00 – 0:40)
- **Visual (Tab 1 — `sandbox.paypal.com`)**:
  - Show the `COMPLETED` buyer payment to the merchant store.
  - Click **Report a Problem** -> select **I haven't received my item (`MERCHANDISE_OR_SERVICE_NOT_RECEIVED`)** -> add brief note (*"Ordered item, never arrived"*), and submit -> PayPal Sandbox shows the real **`PP-D-...`** dispute ID.
- **Spoken**:
  > *"Let's start with a real buyer dispute on PayPal Sandbox, not a mocked JSON payload. As the buyer, I paid for an order, never received the item, and open an Item Not Received dispute right inside PayPal's Resolution Center — generating a genuine `PP-D-` case ID."*

---

### Act 2: Live PayPal Sync & Strict Local-vs-Live Separation (0:40 – 1:10)
- **Visual (Tab 2 — ProofLedger Dispute Inbox at `http://127.0.0.1:5173`)**:
  - Point briefly to the `LOCAL DEMO — NOT A PAYPAL DISPUTE` badges on sample rows, then click **`Sync PayPal Sandbox`** (or **`Refresh`**).
  - Click the **`Live PayPal`** filter pill and highlight the newly synced **`PP-D-...`** row (`PAYPAL SANDBOX LIVE`). Click **`Resolve ->`**.
- **Spoken**:
  > *"Switching over to the merchant's ProofLedger workspace: Notice how local test scenarios are strictly isolated and marked `LOCAL DEMO — NOT A PAYPAL DISPUTE`. When I click `Sync PayPal Sandbox`, ProofLedger calls PayPal's `/v1/customer/disputes` API and pulls in the exact live `PP-D-` dispute we just filed. Let's open it."*

---

### Act 3: 10-Stage SSE Analysis, Delivery Journey & Non-OCR Attachment Upload (1:10 – 2:10)
- **Visual (Resolve Dispute Page for `PP-D-...`)**:
  - Enter Carrier (`UPS`), Tracking Number (`1Z999AA10123456784`), attach your sample PDF/PNG (or pre-enter via New Analysis / Resolve uploader), and show the uploaded file card:
    - Point directly to **`SHA-256 integrity verified`** and **`CONTENT_NOT_EXTRACTED`** badge.
  - Click **`Analyze Evidence`** and watch the live **10-stage Server-Sent Events** progress (`01`–`10` -> `Analysis Complete`).
  - Scroll through the verification report and highlight:
    1. **Verification Summary**: `deberta_v3_inr_v1` active + **`AI-assisted assessment — merchant review required.`**
    2. **Delivery Verification Journey**:
       - Provenance strip separating **`Merchant Attestation & Uploads`** (`MERCHANT_ATTESTATION / FORMAT_VALID`) from **`Independent Carrier Verification`** (`LOOKUP_NOT_CONFIGURED`).
       - Step `01` tracking syntax = **`FORMAT_VALID`**.
       - Step `02` Carrier Pickup = **`NOT VERIFIED`**.
       - Step `06` never fakes green `Delivered` without a verified courier scan (shows **`Delivery Claimed by Merchant (Unverified)`** / **`Delivery Confirmation Pending`**).
    3. **How Your Evidence Supports the Claim**: Advisory DeBERTa-v3 NLI verdict (`SUPPORTED` / `CONTRADICTED` / `INSUFFICIENT_EVIDENCE` bounded beneath deterministic rules).
- **Spoken**:
  > *"As ProofLedger runs its 10-stage verification stream, notice two core guarantees. First, attached files are `SHA-256 integrity verified` and explicitly tagged `CONTENT_NOT_EXTRACTED` — our AI never pretends to OCR inside PDFs or turn an attachment into green delivery proof. Second, the Delivery Verification Journey keeps tracking format (`FORMAT_VALID`) and physical carrier pickup (`NOT VERIFIED`) strictly separate, while our fine-tuned DeBERTa-v3 candidate serves strictly as an advisory semantic check under deterministic rules."*

---

### Act 4: Server-Side SHA-256 Sealing, Tamper Invalidation & Live PayPal Submission (2:10 – 3:05)
- **Visual (Bottom of Resolve Dispute — `Prepare Your PayPal Response`)**:
  1. Show the grounded defense draft (plus **`SHA-256 verified`** & **`CONTENT_NOT_EXTRACTED`** on attachments).
  2. Tick **`#merchantApprovalCheck`** and click **`1. Approve Evidence Package`** -> confirm modal -> highlight **`Server Approval Sealed`** (`EAPPR-...` + SHA-256 digest).
  3. **Tamper Safety Moment**: Type 1 small edit inside the response textarea -> highlight the immediate **`Approval Invalidated`** warning.
  4. Re-seal approval (`1. Approve Evidence Package` -> Confirm) and click **`2. Submit Approved Evidence to PayPal`**!
  5. Show the live PayPal submission receipt (`submission_id`, `PayPal-Debug-Id`, updated state `UNDER_REVIEW`), and optionally switch back to Tab 1 (`sandbox.paypal.com`) / click **`Refresh`** to show PayPal received the merchant's fulfillment evidence!
- **Spoken**:
  > *"Before anything reaches PayPal, the merchant reviews the draft and seals a server-side SHA-256 digest. If even a single character is modified afterwards, approval invalidates immediately so stale evidence can never go out. Re-approving seals the exact package and submits `PROOF_OF_FULFILLMENT` directly to PayPal's `provide-evidence` REST API — completing a fully grounded, auditable live PayPal dispute response. Thank you."*
