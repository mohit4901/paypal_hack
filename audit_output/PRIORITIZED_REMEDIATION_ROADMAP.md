# PROOFLEDGER AUDIT — PRIORITIZED REMEDIATION ROADMAP

**Audit Date:** November 4, 2026  
**Auditor Personas:** Principal Fintech Backend Engineer, Application Security Auditor & Senior Hackathon Judge  
**Standard:** Actionable, File-Specific Technical Remediation  

---

## 1. Master Issue Matrix

| Rank | Issue ID | Severity | Subsystem | Target File Path | Primary Impact | Status |
|:---:|---|:---:|---|---|---|:---:|
| **1** | **REM-01** | `HIGH` | Packaging / Env | `pyproject.toml`, `requirements.txt` | 9 test failures when run on clean Python 3.11 due to missing data science packages. | `OPEN` |
| **2** | **REM-02** | `HIGH` | Live Demo | `scripts/test_live_paypal_sandbox_dispute_flow.py` | Live sandbox seller account has 0 disputes; live submission remains unproven against a real `PP-D-` ID. | `OPEN` |
| **3** | **REM-03** | `MEDIUM` | Product / UX | `frontend/src/components/Sidebar.jsx` | "Forensic Audit Ledger" and "Checkpoints" linger in sidebar, creating cognitive clutter for merchants. | `OPEN` |
| **4** | **REM-04** | `MEDIUM` | Architecture | `tools/paypal_agent_toolkit_bridge.js` | Spawning `node` subprocess per tool call incurs ~350ms process overhead. | `OPEN` |
| **5** | **REM-05** | `MEDIUM` | AI Scientific | `ai/artifacts/best_model`, `dispute_rescue_ai.py` | DeBERTa has low precision (20-25%) on contradiction; relies heavily on deterministic fallback. | `OPEN` |
| **6** | **REM-06** | `LOW` | Privacy / GDPR | `backend/services/forensic_engine.py` | Storing buyer email in hashed ledger payloads risks GDPR Art. 17 right-to-erasure non-compliance. | `OPEN` |
| **7** | **REM-07** | `LOW` | Frontend / UX | `frontend/src/components/ResolveDisputeView.jsx` | Fixed desktop column width causes horizontal scrolling on smaller laptop displays. | `OPEN` |

---

## 2. Detailed Technical Breakdown & Remediation Steps

### Issue REM-01: Runtime Environment Fragmentation
- **Severity:** `HIGH`
- **Component:** Python Build & Packaging
- **File Paths:** `requirements.txt`, `pyproject.toml`
- **Root Cause:** Dependencies like `torch`, `matplotlib`, and `hypothesis` are installed in the developer's macOS Command Line Tools Python 3.9 user environment, but are not pinned in `requirements.txt` or installed in standard Python 3.11 Homebrew environments. When an auditor runs `pytest` in Python 3.11, 9 import and NLI tests fail.
- **Merchant / Hackathon Impact:** Evaluators cloning the repository on Python 3.10+ will experience test failures.
- **Recommended Solution:**
  1. Pin exact dependencies in `pyproject.toml`:
     ```toml
     dependencies = [
       "fastapi>=0.115.0",
       "uvicorn>=0.30.0",
       "torch>=2.2.0",
       "transformers>=4.40.0",
       "pydantic>=2.7.0",
       "httpx>=0.27.0",
       "hypothesis>=6.100.0"
     ]
     ```
  2. Provide a standalone `setup_env.sh` script that automates virtual environment creation.

---

### Issue REM-02: Zero Genuine Disputes in Live PayPal Sandbox
- **Severity:** `HIGH`
- **Component:** Live Demonstration & External Verification
- **File Paths:** `scripts/test_live_paypal_sandbox_dispute_flow.py`, `ai/.env`
- **Root Cause:** The seller account authenticated in `ai/.env` (`sb-lgmd253645304@business.example.com`) has 0 disputes in its live queue (`items: []`). While API connectivity is verified, live evidence submission against an authentic `PP-D-` dispute ID cannot be recorded until a buyer files one.
- **Merchant / Hackathon Impact:** Prevents a live video demonstration of a completed PayPal dispute lifecycle; caps jury score at 88/100.
- **Recommended Solution:**
  1. Log into `https://www.sandbox.paypal.com` with personal buyer credentials (`sb-rcnwy53637793@personal.example.com`).
  2. Open captured transaction `10A71705XW788203L` and click "Report a Problem" -> "Item Not Received".
  3. Copy the authentic dispute ID (e.g. `PP-D-12345678`).
  4. Run `python3 scripts/test_live_paypal_sandbox_dispute_flow.py PP-D-12345678` to execute live evidence submission and capture PayPal's real `200 OK` / `UNDER_REVIEW` response.

---

### Issue REM-03: Vestigial Enterprise Tabs Diluting Merchant UX
- **Severity:** `MEDIUM`
- **Component:** Frontend Navigation
- **File Paths:** `frontend/src/components/Sidebar.jsx`, `frontend/src/App.jsx`
- **Root Cause:** Residue from ProofLedger's prior incarnation as an enterprise blockchain notary still appears in the sidebar: `AuditLedgerTab`, `CheckpointsTab`, and `VerificationTab`.
- **Merchant / Hackathon Impact:** Confuses small online sellers who just want a clean PayPal dispute rescue tool.
- **Recommended Solution:**
  1. In `Sidebar.jsx`, collapse or remove `Forensic Audit Ledger` from primary navigation.
  2. Keep the navigation strictly focused on:
     - **Dispute Inbox**
     - **Resolve Dispute**
     - **Orders & Evidence**
     - **Settings & PayPal Connection**

---

### Issue REM-04: Node.js Bridge Subprocess Spawning Overhead
- **Severity:** `MEDIUM`
- **Component:** MCP & Agent Toolkit Bridge
- **File Paths:** `tools/paypal_agent_toolkit_bridge.js`, `backend/services/paypal_dispute_service.py`
- **Root Cause:** Invoking the official `@paypal/agent-toolkit` currently spawns a new Node.js process (`subprocess.run(['node', ...])`) for each tool call, adding ~350ms of V8 VM startup time.
- **Merchant / Hackathon Impact:** Noticeable UI latency when fetching dispute lists or order details.
- **Recommended Solution:**
  1. Maintain a persistent long-lived background Node.js daemon using standard JSON-RPC 2.0 over standard I/O (stdin/stdout).
  2. Re-use the active process connection across requests to reduce latency to <15ms.

---

### Issue REM-05: DeBERTa-v3 Contradiction Precision Deficit
- **Severity:** `MEDIUM`
- **Component:** Applied AI / Natural Language Inference
- **File Paths:** `ai/src/models/evidence_verifier.py`, `backend/services/dispute_rescue_ai.py`
- **Root Cause:** DeBERTa-v3 was fine-tuned on a small synthetic corpus (850 pairs), leading to low precision (20-25%) when separating contradiction from insufficient evidence.
- **Merchant / Hackathon Impact:** The system currently relies on the deterministic validator to catch amount/currency/ID mismatches, rendering the neural model somewhat redundant.
- **Recommended Solution:**
  1. Augment training with 2,500 real e-commerce dispute scenarios with balanced contradiction/entailment pairs.
  2. Alternatively, deploy an instruction-tuned small language model (SLM) with structured JSON generation and strict schema constraints.

---

### Issue REM-06: Potential GDPR Art. 17 Conflict with Immutable Hashes
- **Severity:** `LOW`
- **Component:** Data Protection & Ledger Immutability
- **File Paths:** `backend/services/forensic_engine.py`, `backend/services/db_schema.py`
- **Root Cause:** If buyer PII (such as buyer email) is embedded in the SHA-256 payload of historical ledger events, fulfilling a GDPR deletion request without invalidating downstream hash pointers is problematic.
- **Merchant / Hackathon Impact:** Compliance blocker for large EU-based merchants.
- **Recommended Solution:**
  1. Store buyer PII in an off-chain table keyed by a cryptographic salt.
  2. Embed only the salted hash in the tamper-evident chain. To fulfill erasure, delete the salt, rendering the historical payload permanently unrecoverable.

---

### Issue REM-07: Fixed Column Layout on Laptop Screens
- **Severity:** `LOW`
- **Component:** Frontend Responsiveness
- **File Paths:** `frontend/src/components/ResolveDisputeView.jsx`
- **Root Cause:** The two-column view uses fixed minimum widths (`min-w-[480px]`) which causes horizontal scroll on 13-inch MacBook displays.
- **Merchant / Hackathon Impact:** Minor cosmetic friction.
- **Recommended Solution:**
  1. Add Tailwind responsive classes (`flex-col lg:flex-row`) to stack the evidence checklist above the drafted defense on smaller screens.

