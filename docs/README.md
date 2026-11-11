# ProofLedger Documentation Index

Core engineering documentation is organized under `docs/`, while frozen evaluation artifacts, model cards, and release audit reports live under `FINAL_RELEASE/` and `ai/docs/`.

## Engineering & Integration Guides
- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — System architecture, deterministic-first rules gate, 10-stage SSE pipeline, attachment non-OCR integrity model, and approval binding.
- [`docs/API_REFERENCE.md`](API_REFERENCE.md) — Backend FastAPI v2 endpoints, SSE events, error contracts, and read-only MCP JSON-RPC interface.
- [`../SETUP.md`](../SETUP.md) — Local environment configuration, candidate weights placement, startup commands, and test suites.

## Release & Evaluation Reports (`FINAL_RELEASE/`)
- [`../FINAL_RELEASE/FINAL_MODEL_REPORT.md`](../FINAL_RELEASE/FINAL_MODEL_REPORT.md) — Locked candidate lineage, EvidenceBench-v2 confusion matrix, false-contradiction breakdown, and safety boundaries.
- [`../FINAL_RELEASE/INDEPENDENT_GENERALIZATION_AUDIT/INDEPENDENT_GENERALIZATION_REPORT.md`](../FINAL_RELEASE/INDEPENDENT_GENERALIZATION_AUDIT/INDEPENDENT_GENERALIZATION_REPORT.md) — 5-system unseen generalization audit (`proofledger_unseen_v1`, `N = 600`) and adversarial robustness (`N = 72`).
- [`../FINAL_RELEASE/SECURITY_RELEASE_CHECKLIST.md`](../FINAL_RELEASE/SECURITY_RELEASE_CHECKLIST.md) — Multi-tenant isolation, cryptographic approval checks, and credential hygiene.
- [`../FINAL_RELEASE/SHA256_CHECKSUMS.txt`](../FINAL_RELEASE/SHA256_CHECKSUMS.txt) — Authoritative SHA-256 digests for frozen model and tokenizer files.
- [`../FINAL_RELEASE/DEMO_SCRIPT.md`](../FINAL_RELEASE/DEMO_SCRIPT.md) — Live product walkthrough storyboard and recording precautions.
