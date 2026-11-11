# ProofLedger — November 11 Final Release Notes

## Release Status: CONDITIONAL SHIP (Engineering Freeze Verified; Live Dispute Submit & Demo Video Outstanding)

1. **AI Model & Safety Architecture**:
   - Primary Locked Candidate: [`ai/artifacts/candidates/deberta_v3_inr_v1/best/`](file:///Users/mohitmudgil/Desktop/paypal/ai/artifacts/candidates/deberta_v3_inr_v1/best/) (`C_top4_unfreeze`, Seed 42, exact copy of `C_top4_unfreeze/`).
   - Seed 42 Frozen Test Metrics ($N=450$: 151 `SUPPORTED` / 144 `CONTRADICTED` / 155 `INSUFFICIENT_EVIDENCE`): Accuracy **86.00%** (`387/450`), Macro F1 **0.8589**, ECE **0.0404**, Brier **0.1907**, `INSUF→CON` Rate **5.16%** (`8/155`), Overall Non-Contradicted False-Contradiction Rate **12.09%** (`37/306`).
   - Three-seed evaluations (`42, 1337, 2026`) on the frozen test split: `86.00%`, `85.78%`, `86.22%` (Mean ± Std: `86.00% ± 0.18%`, Macro F1 `0.8594 ± 0.0016`). Seed 42 selected strictly by validation Macro F1 (`0.8913`).
   - Production Authority: **Rules-first Deterministic Gatekeeper + Assistive Semantic Alignment**. Protected legacy `ai/artifacts/best_model/` verified untouched (`0e4d8903...f4617`).
2. **Canonical Backend & Frontend**:
   - 10-stage SSE analysis stream (`/analyze-stream`), multipart upload (`/upload-evidence`), server-side SHA-256 approval binding (`/approve-evidence`, `HTTP 409 STALE_OR_MODIFIED_APPROVAL`), and responsive two-column Resolve Dispute workspace.
3. **Verification & Known Unverified / Outstanding Items**:
   - **324 / 324 unique pytest tests passed** (`ai/tests/`: 156, `backend/`: 168).
   - **Live headless Chrome CDP E2E passed** across `1440x900`, `1280x800`, and `390x844`.
   - **UNVERIFIED**: Live `POST /provide-evidence` against a genuine PayPal Sandbox dispute ID (0 buyer disputes in Sandbox).
   - **NOT CONFIGURED**: Automated courier carrier delivery scan lookup (`LOOKUP_NOT_CONFIGURED`).
   - **OUTSTANDING**: Final recorded demo video (`DEMO_SCRIPT.md` ready; video recording not yet produced).
