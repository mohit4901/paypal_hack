# ProofLedger Final Hackathon Demo Script

## Video Overview
- **Duration**: ~2 minutes 45 seconds
- **Format**: Screen capture (`http://127.0.0.1:5173` against live backend `:8000`) with spoken voiceover
- **Central Message**: *ProofLedger's strength is not just that it uses AI — it is that it shows a merchant clearly what the available evidence establishes, what it does not establish, and what is still needed.*
- **Pre-Recording Precaution**: Never show or imply any PDF or image document being read by AI/OCR during the demo. Uploaded documents are explicitly **`CONTENT_NOT_EXTRACTED`** and **`SHA-256 integrity verified`** only.

---

## Storyboard & Narration

### Part 1: The Problem & Core Principle (0:00 – 0:25)
- **Visual**: Show **Dispute Inbox** (`Disputes — Review claims, verify evidence and prepare grounded responses`).
- **Spoken**:
  > "Merchants often lose PayPal Item Not Received disputes because submitting disorganized tracking info or overclaiming beyond what records prove backfires. Generic AI tools either guess delivery succeeded or hallucinate facts.
  > ProofLedger is built around one principle: show the merchant honestly what available evidence establishes, what it does NOT establish, and what is still needed."

### Part 2: Honest Dispute Inbox & Local-vs-Live Separation (0:25 – 0:50)
- **Visual**: Point to the backend summary cards, the explicit banner **`No live PayPal disputes found.`**, and the **`LOCAL DEMO — NOT A PAYPAL DISPUTE`** labels on `DSP-3EU95140-01`. Click **New Analysis**.
- **Spoken**:
  > "Here in the Dispute Inbox, ProofLedger queries PayPal Sandbox directly. Because this Sandbox account has zero open live buyer disputes right now, ProofLedger states that honestly and clearly labels local test cases as `LOCAL DEMO — NOT A PAYPAL DISPUTE`."

### Part 3: Structured Intake & Non-OCR Attachment Upload (0:50 – 1:25)
- **Visual**: On **Analyze a Dispute**, show Environment (`Local demo scenario` vs `Existing live PayPal dispute`), enter Order ID, Capture ID, Amount, Carrier, Tracking Number, upload a PDF/PNG file — point directly to **`SHA-256 integrity verified`** and **`CONTENT_NOT_EXTRACTED`** on the uploaded file card — and state the merchant factual claim to test. Click **Analyze Evidence**.
- **Spoken**:
  > "In New Analysis, the merchant enters order, payment, and carrier attestation details, states the factual claim they want tested, and uploads a supporting PDF or image. Notice ProofLedger's honesty: the file is `SHA-256 integrity verified`, and explicitly marked `CONTENT_NOT_EXTRACTED` — our AI does NOT claim to OCR or read inside uploaded PDFs, and attaching a file never marks the shipment Delivered.
  > Clicking Analyze Evidence launches a real 10-stage Server-Sent Events stream from our FastAPI backend."

### Part 4: Live Analysis -> Signature Delivery Verification Journey (1:25 – 2:10)
- **Visual**: Watch stages `01`–`10` complete cleanly, then scroll through **Verification Summary** (showing active checkpoint `deberta_v3_inr_v1/best`), **Order & Payment Verification**, and the **Delivery Verification Journey**:
  - Highlight `[FORMAT_VALID]` for tracking syntax
  - Highlight `[NOT VERIFIED]` for Carrier Pickup (*"Label generation or tracking syntax alone does not establish physical carrier possession"*)
  - Highlight `[LOOKUP_NOT_CONFIGURED]` (*"Independent carrier verification unavailable"*)
  - Show **How Your Evidence Supports the Claim** (edit the claim briefly and click **Re-verify Claim** if time allows, or point to `SUPPORTED`/`CONTRADICTED`/`INSUFFICIENT_EVIDENCE` advisory tags) and **Evidence Still Needed**.
- **Spoken**:
  > "Notice the Delivery Verification Journey: ProofLedger refuses to turn valid tracking syntax into a green 'Delivered' badge. It shows `FORMAT_VALID` on tracking syntax, warns that physical carrier pickup is `NOT VERIFIED`, discloses that automated carrier API lookup is not configured, and surfaces exactly what missing proof to attach next — alongside advisory DeBERTa-v3 claim alignment."

### Part 5: Merchant Review, SHA-256 Sealing & Edit Invalidation (2:10 – 2:45)
- **Visual**: Scroll to **Prepare Your PayPal Response**, check `#merchantApprovalCheck`, click **1. Approve Evidence Package** -> confirm modal -> show **`Server Approval Sealed`** (`EAPPR-...` + SHA-256 digest). Edit one line in the draft textarea to show immediate **`Approval Invalidated — Changes require re-approval`**, re-approve, and click **2. Record Local Simulated Submission** (`LOCAL_SIMULATED_SUBMISSION`).
- **Spoken**:
  > "Before anything is submitted, the merchant edits the grounded response and seals a server-side SHA-256 digest. Watch: modifying even a single character invalidates the approval immediately so stale evidence can never go out. And on local scenarios, ProofLedger only records a local simulation and never hits live PayPal. Transparent, deterministic-first, and merchant-controlled. Thank you."
