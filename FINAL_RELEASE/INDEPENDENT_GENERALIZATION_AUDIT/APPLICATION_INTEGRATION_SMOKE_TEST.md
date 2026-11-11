# Application Integration & Archive Staging Smoke Test

## 1. Staged Release Archive Verification (Fresh Extraction in Temp Staging)
- Extracted `proofledger_audit_source.zip` (`384118106` B, SHA-256 `d3dc6b2135b910be08e568d7dbd9e524c4f1d1064e33f8f8630d5a60fe38d2eb`) + `proofledger_candidate_weights.zip` (`473017624` B, SHA-256 `f74a470ec3de1a640e8c17d619745c7ceeb16bd102d93b17bd530906d97ac46f`) cleanly: `True`
- Candidate `model.safetensors` present & SHA-256 verified (`2afd4cf10a28b274445073c6fc3c880c54708d5886ca3a2c54ed45857a94e2ea`): `True`
- Staged refreshed `DisputeVerificationService` loaded path: `/private/var/folders/7y/2lqt2mz55c51r0lpvdlqsz680000gn/T/proofledger_staging_q5he0d5o/ai/artifacts/candidates/deberta_v3_inr_v1/best` (exit code `0`)

## 2. Live Workspace Backend Smoke Test (`uvicorn` on `:8019`, temp isolated DB)
- `GET /health`: HTTP `200`
- `GET /api/v2/ai/status`: HTTP `200`, `status=ONLINE`, `loaded_model_path=/Users/mohitmudgil/Desktop/paypal/ai/artifacts/candidates/deberta_v3_inr_v1/best`, `is_loaded=True`
- `POST /api/v2/sellers/register`: HTTP `200`
- `POST /api/v2/disputes/verify-claims` (4 unseen claims, checkpoint=`ai/artifacts/candidates/deberta_v3_inr_v1/best`): HTTP `200`
  - `CLM-SUP` -> verdict=`SUPPORTED`, engine=`FINE_TUNED_DEBERTA_V3`, rule_triggered=`False`, neural_label=`SUPPORTED`
  - `CLM-CON` -> verdict=`CONTRADICTED`, engine=`FINE_TUNED_DEBERTA_V3`, rule_triggered=`False`, neural_label=`CONTRADICTED`
  - `CLM-INS` -> verdict=`INSUFFICIENT_EVIDENCE`, engine=`FINE_TUNED_DEBERTA_V3`, rule_triggered=`False`, neural_label=`INSUFFICIENT_EVIDENCE`
  - `CLM-DWN` -> verdict=`INSUFFICIENT_EVIDENCE`, engine=`DETERMINISTIC_SAFETY_RULE`, rule_triggered=`True`, neural_label=`SUPPORTED`
- Cross-order linkage rule override (`ORD-TARGET-9999` vs `ORD_UNRELATED_1111`): HTTP `200`, verdict=`INSUFFICIENT_EVIDENCE`, engine=`DETERMINISTIC_SAFETY_RULE`, rule_triggered=`True`
- `POST /api/v2/disputes/DSP-3EU95140-01/analyze-stream`: HTTP `200`, streamed `11` SSE events (`retrieve_dispute, read_requested_evidence, link_payment_order, validate_amount_currency, validate_tracking, check_delivery_evidence, semantic_nli, identify_gaps, prepare_grounded_response, ready_for_review`)
- Mandatory human approval enforcement (`merchant_approved=false` -> `provide-evidence`): HTTP `400` (rejected as required)

## 3. Fail-Closed Missing Checkpoint Verification (`PROOFLEDGER_MODEL_PATH=/tmp/nonexistent`, `:8020`)
- `GET /api/v2/ai/status`: HTTP `200`, `status=MODEL_UNAVAILABLE`, `is_loaded=False`, `model_load_error=Checkpoint not found at /tmp/nonexistent_proofledger_checkpoint_8020`
- `POST /api/v2/ai/test-inference`: HTTP `503` (`{'detail': 'AI Neural Model is currently unavailable.'}`)

## 4. Frontend Build Verification (`frontend/npm run build`)
- Exit code: `0`
```
> proofledger-frontend@2.0.0 build
> vite build

vite v5.4.21 building for production...
transforming...
✓ 1620 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.89 kB │ gzip:  0.51 kB
dist/assets/index-802Chpng.css   58.97 kB │ gzip: 10.06 kB
dist/assets/index-C08I6OZ-.js   367.83 kB │ gzip: 96.00 kB
✓ built in 1.45s
```
