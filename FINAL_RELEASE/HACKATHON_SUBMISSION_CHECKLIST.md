# PayPal AI Hackathon Submission Checklist

## 1. Submission Metadata
- **Project Name**: ProofLedger — PayPal Dispute Rescue
- **Tagline**: Source-grounded evidence verification and merchant-approved dispute rescue for PayPal merchants.
- **Repository**: Public GitHub Repository
- **License**: MIT Open Source License (`LICENSE` file at root)
- **Target Track**: Agentic Commerce / Developer & Merchant Tooling

---

## 2. Technical Deliverables

- [x] **Working Full-Stack Application**:
  - FastAPI backend serving on port 8000
  - React 18 / Vite frontend serving on port 5173
  - SQLite database with multi-tenant isolation and cryptographic audit ledger
- [x] **PayPal Sandbox Integration & Disclosures**:
  - Genuine OAuth 2.0 Client Credentials flow (`https://api-m.sandbox.paypal.com`)
  - Live PayPal Disputes list endpoint (`GET /v1/customer/disputes` returns HTTP 200, `items: []`)
  - Integration with `@paypal/agent-toolkit` (v1.11.0) read-only MCP bridge
  - **Outstanding / Unverified**: Live `POST /provide-evidence` against a real PayPal dispute ID remains **UNVERIFIED** (0 live buyer disputes in Sandbox); automated carrier scan API is **NOT CONFIGURED** (`LOOKUP_NOT_CONFIGURED`).
- [x] **Applied AI / Machine Learning**:
  - Fail-closed deterministic rules engine (0/10 false contradictions on diagnostic $N=30$)
  - Sentence-level source grounding citations for every generated statement
  - Fine-tuned candidate `ai/artifacts/candidates/deberta_v3_inr_v1/best/` (Seed 42, `C_top4_unfreeze`: 86.00% test accuracy on EvidenceBench-v2 $N=450$; see `DATASET_FINAL_AUDIT.md` for Tier-3 FEVEROUS placeholder findings)
- [x] **Verified Test Coverage**:
  - **324 unique automated pytest tests passed** (`ai/tests/`: 156, `backend/`: 168) + live headless Chrome CDP E2E workflow passed
- [ ] **Demo Video Recording (OUTSTANDING)**:
  - Demo storyboard & script ready in `FINAL_RELEASE/DEMO_SCRIPT.md`; actual screen recording video has **not** yet been recorded.
- [x] **Complete Documentation**:
  - Full reconciled release documents in `FINAL_RELEASE/` and `audit_output/`

