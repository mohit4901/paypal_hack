# ProofLedger Canonical Backend Architecture

## 1. System Overview

The ProofLedger backend is a high-reliability, multi-tenant FastAPI service built to integrate merchant e-commerce platforms with the official PayPal REST Disputes API and the Model Context Protocol (MCP).

```
┌────────────────────────────────────────────────────────┐
│                   React 18 Frontend                    │
└───────────────────────────┬────────────────────────────┘
                            │ REST / JSON
                            ▼
┌────────────────────────────────────────────────────────┐
│                 FastAPI Gateway (Port 8000)             │
│  ├── /api/v2/disputes/         (Dispute Lifecycle)     │
│  ├── /api/v2/paypal/           (OAuth & Sandbox Sync)  │
│  ├── /api/v2/ai/               (Verification & Draft)  │
│  ├── /api/v2/sellers/          (Tenant Management)     │
│  └── /mcp/                     (JSON-RPC MCP Server)   │
└─────────────┬────────────────────────────┬─────────────┘
              │                            │
              ▼                            ▼
┌───────────────────────────┐ ┌──────────────────────────┐
│   DisputeRescueAIEngine   │ │  PayPal REST Client      │
│  ├── Deterministic Rules  │ │  ├── OAuth 2.0 Token     │
│  ├── Sentence Grounding   │ │  ├── GET /v1/customer/...│
│  └── DeBERTa-v3 Semantic  │ │  └── POST /provide-ev... │
└─────────────┬─────────────┘ └────────────┬─────────────┘
              │                            │
              └─────────────┬──────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│           SQLite Isolated Multi-Tenant Store           │
│   ├── seller_accounts      ├── dispute_submissions    │
│   ├── seller_transactions  ├── ledger_blocks (SHA256) │
└────────────────────────────────────────────────────────┘
```

---

## 2. Core Subsystems

### 2.1 Multi-Tenant Isolation
- Authentication via bearer tokens mapped to seller identities (`seller_alpha`, `seller_beta`).
- Every SQL query enforces strict `WHERE seller_id = ?` predicate isolation.
- Cross-tenant data leakage is prevented at both the database and routing levels.

### 2.2 Dispute Rescue AI Engine
- **Scope Restriction**: Only `MERCHANDISE_OR_SERVICE_NOT_RECEIVED` disputes are processed in this release.
- **Deterministic Pre-flight Rules**:
  - Links PayPal transaction ID to merchant store order.
  - Verifies currency and exact payment amount match.
  - Checks tracking number regex format (`FORMAT_VALID`).
- **Grounding Citations**: Every sentence in the generated draft defense links directly to a verifiable ledger source (PayPal API capture ID, order database, or merchant attestation).
- **10-Stage Real-Time SSE Orchestration**: `POST /api/v2/disputes/{dispute_id}/analyze-stream` streams each verification stage sequentially as it executes.
- **Server-Side Approval Digest Binding**: `POST /api/v2/disputes/{dispute_id}/approve-evidence` binds `(approval_id, seller_id, dispute_id, evidence_digest)` in `evidence_approvals`. Submitting modified or stale evidence returns `HTTP 409 STALE_OR_MODIFIED_APPROVAL`, and `provide-evidence` strictly requires `merchant_approved: true`.

### 2.3 PayPal REST & Agent Toolkit Integration
- **Direct REST Client**: Direct integration with `https://api-m.sandbox.paypal.com`.
- **OAuth 2.0 Client Credentials**: Automated token renewal and caching with thread-safe locking.
- **Disputes Endpoint**: Calls official `/v1/customer/disputes` endpoints for listing and evidence provision.
- **Official MCP Server**: JSON-RPC 2.0 compliant endpoint providing read-only financial tools (`list_disputes`, `get_dispute_details`) that disallow financial state modification.

