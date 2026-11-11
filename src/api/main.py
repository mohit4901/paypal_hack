"""
FastAPI inference service for ProofLedger AI.

Run:
    uvicorn src.api.main:app --reload --port 8000
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

load_dotenv()
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.schemas import (
    BatchPredictRequest,
    BatchPredictResponse,
    DisputeEvidenceSubmissionRequest,
    DisputeEvidenceSubmissionResponse,
    EvidenceItem,
    HealthResponse,
    ModelInfoResponse,
    PredictRequest,
    PredictResponse,
    ValidateEvidenceRequest,
    ValidateEvidenceResponse,
    WebhookProcessingResponse,
)
from src.integrations.paypal_client import PayPalClient, PayPalClientError
from src.integrations.paypal_webhook_processor import (
    compile_dispute_evidence_background,
    process_webhook_event,
)
from src.models.deterministic_validator import DeterministicValidator
from src.models.evidence_verifier import EvidenceVerifier
from src.models.input_format import EvidenceRecord
from src.storage.db import DatabaseError
from src.utils.logging_config import setup_logging

logger = setup_logging(name="api")

MODEL_PATH = os.getenv("MODEL_PATH", "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli")
MODEL_VERSION = os.getenv("MODEL_VERSION", "pretrained_baseline")
DATASET_VERSION = os.getenv("DATASET_VERSION", "evidencebench_v1.0")
MAX_REQUEST_BODY = 1 * 1024 * 1024  # 1 MB

_verifier: Optional[EvidenceVerifier] = None
_validator = DeterministicValidator()
_startup_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _verifier
    logger.info(f"Loading EvidenceVerifier from {MODEL_PATH}")
    _verifier = EvidenceVerifier(model_path=MODEL_PATH)
    try:
        _verifier.load()
        logger.info("Model loaded successfully.")
    except Exception as e:
        logger.error(f"Model load failed: {e}. /predict will return 503.")
        _verifier = None
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="ProofLedger AI — Evidence Verification Service",
    version="1.0.0",
    description=(
        "Source-grounded evidence verification for PayPal digital-goods sellers. "
        "AI predictions do NOT constitute PayPal Seller Protection determinations."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def _ev_records(evidence: List[EvidenceItem]) -> List[EvidenceRecord]:
    return [
        EvidenceRecord(
            evidence_id=e.evidence_id,
            source_type=e.source_type,
            timestamp=e.timestamp,
            content=e.content,
        )
        for e in evidence
    ]


def _ev_dicts(evidence: List[EvidenceItem]) -> List[Dict]:
    return [e.model_dump() for e in evidence]


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok" if _verifier and _verifier.is_loaded else "degraded",
        model_loaded=bool(_verifier and _verifier.is_loaded),
        uptime_s=round(time.time() - _startup_time, 1),
    )


@app.get("/model/info", response_model=ModelInfoResponse)
async def model_info():
    if not _verifier or not _verifier.is_loaded:
        raise HTTPException(status_code=503, detail="Model not loaded.")
    info = _verifier.model_info
    raw_id2label = info.get("id2label", {})
    str_id2label = {str(k): str(v) for k, v in raw_id2label.items()}
    return ModelInfoResponse(
        model_path=info.get("model_path", MODEL_PATH),
        architecture=info.get("architecture", "unknown"),
        num_labels=info.get("num_labels", 3),
        id2label=str_id2label,
        nli_to_app=info.get("nli_to_app", {}),
        device=info.get("device", "cpu"),
        model_version=MODEL_VERSION,
        dataset_version=DATASET_VERSION,
        disclaimer=(
            "Confidence scores are raw model outputs, not calibrated probabilities. "
            "This system does not determine PayPal dispute outcomes."
        ),
    )


@app.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest):
    if not _verifier or not _verifier.is_loaded:
        raise HTTPException(status_code=503, detail="Model not loaded.")

    ev_records = _ev_records(req.evidence)
    ev_dicts = _ev_dicts(req.evidence)

    # Deterministic checks first
    det_label, det_checks = _validator.run_all(
        claim=req.claim,
        evidence=ev_dicts,
        order_id=req.transaction_reference,
        claimed_recipient=req.metadata.get("recipient") if req.metadata else None,
    )

    # Model prediction
    try:
        model_result = _verifier.predict(req.claim, ev_records)
    except Exception as e:
        logger.error(f"Model inference error: {e}")
        raise HTTPException(status_code=500, detail=f"Model inference error: {e}")

    ml_label = model_result["label"]
    det_label_str = det_label.value

    # Flag disagreements
    disagreement = ml_label != det_label_str
    human_review = (
        disagreement
        or model_result.get("truncated", False)
        or ml_label == "INSUFFICIENT_EVIDENCE"
    )

    # Supporting / contradicting evidence IDs (from model result)
    all_evidence_ids = [e.evidence_id for e in req.evidence]
    supporting_ids = model_result["evidence_ids"] if ml_label == "SUPPORTED" else []
    contradicting_ids = model_result["evidence_ids"] if ml_label == "CONTRADICTED" else []

    # Guard: only return evidence IDs that exist in the request
    valid_ids = set(all_evidence_ids)
    supporting_ids = [eid for eid in supporting_ids if eid in valid_ids]
    contradicting_ids = [eid for eid in contradicting_ids if eid in valid_ids]

    missing_info = []
    if not req.evidence:
        missing_info.append("No evidence records provided.")
    if model_result.get("truncated"):
        missing_info.append(model_result.get("truncation_warning", "Evidence truncated."))

    return PredictResponse(
        claim_id=req.claim_id or f"claim_{int(time.time())}",
        label=ml_label,
        confidence=model_result["confidence"],
        note_confidence=model_result["note_confidence"],
        evidence_ids=all_evidence_ids,
        supporting_evidence_ids=supporting_ids,
        contradicting_evidence_ids=contradicting_ids,
        missing_information=missing_info,
        deterministic_checks=det_checks,
        deterministic_label=det_label_str,
        model_label=ml_label,
        rule_model_disagreement=disagreement,
        model_version=MODEL_VERSION,
        dataset_version=DATASET_VERSION,
        limitations=[
            "Synthetic training data only — real-world performance unvalidated.",
            "Confidence scores are uncalibrated model outputs.",
            "Does not determine PayPal Seller Protection eligibility.",
            "Human review required before submission.",
        ],
        human_review_required=human_review,
    )


@app.post("/batch-predict", response_model=BatchPredictResponse)
async def batch_predict(req: BatchPredictRequest):
    if not _verifier or not _verifier.is_loaded:
        raise HTTPException(status_code=503, detail="Model not loaded.")
    if len(req.items) > 50:
        raise HTTPException(status_code=400, detail="Batch size exceeds maximum of 50.")

    results = []
    for item in req.items:
        sub_req = PredictRequest(**item.model_dump())
        result = await predict(sub_req)
        results.append(result)

    return BatchPredictResponse(results=results, count=len(results))


@app.post("/validate-evidence", response_model=ValidateEvidenceResponse)
async def validate_evidence(req: ValidateEvidenceRequest):
    """Deterministic-only evidence validation — no ML model."""
    ev_dicts = _ev_dicts(req.evidence)
    det_label, det_checks = _validator.run_all(
        claim=req.claim,
        evidence=ev_dicts,
        order_id=req.transaction_reference,
        claimed_recipient=req.metadata.get("recipient") if req.metadata else None,
    )
    passed = sum(1 for c in det_checks if c["passed"])
    return ValidateEvidenceResponse(
        label=det_label.value,
        deterministic_checks=det_checks,
        checks_passed=passed,
        checks_total=len(det_checks),
        human_review_required=True,
    )


@app.post("/paypal/disputes/{dispute_id}/submit-evidence", response_model=DisputeEvidenceSubmissionResponse)
async def submit_dispute_evidence(dispute_id: str, req: DisputeEvidenceSubmissionRequest):
    """
    Submit evidence package to PayPal Customer Dispute API.
    Enforces mandatory seller human approval check and authentic sandbox API dispatch.
    """
    if req.dispute_id != dispute_id:
        raise HTTPException(status_code=400, detail="Mismatched dispute_id in URL path and request body.")
    if not req.seller_human_approved:
        raise HTTPException(
            status_code=400,
            detail="Forbidden: Automated submission disallowed. Seller must provide explicit human approval.",
        )

    client = PayPalClient(mode="sandbox")
    if not client.is_configured:
        raise HTTPException(
            status_code=503,
            detail=(
                "PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET not configured on backend. "
                "Set environment variables to connect to PayPal sandbox."
            ),
        )

    try:
        result = client.provide_dispute_evidence(
            dispute_id=dispute_id,
            evidence_type=req.evidence_type,
            evidence_info=req.evidence_info,
            notes=req.notes,
        )
    except PayPalClientError as e:
        logger.error(f"PayPal dispute evidence submission error: {e}")
        status_code = 403 if "403" in str(e) or "scope" in str(e).lower() else 502
        raise HTTPException(status_code=status_code, detail=str(e))

    return DisputeEvidenceSubmissionResponse(
        dispute_id=dispute_id,
        status="SUBMITTED",
        submission_timestamp=datetime.now(timezone.utc).isoformat(),
        seller_human_approved=True,
        details=result,
    )


@app.post("/paypal/webhook", response_model=WebhookProcessingResponse)
async def paypal_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    PayPal Sandbox Webhook Receiver.

    - Validates PayPal transmission signature using PayPalClient.verify_webhook_signature()
    - Enforces persistent idempotency at database level
    - Processes captures, orders, and disputes
    - Triggers non-blocking background evidence compilation for verified disputes
    - Forbids automatic evidence submission (human approval remains mandatory)
    """
    # 1. Read raw body and validate JSON
    raw_body = await request.body()
    if not raw_body:
        raise HTTPException(status_code=400, detail="Empty webhook payload.")

    try:
        import json
        event_data = json.loads(raw_body)
    except Exception as e:
        logger.warning(f"Malformed webhook JSON payload: {e}")
        raise HTTPException(status_code=400, detail="Malformed JSON payload.")

    # 2. Extract required PayPal transmission headers (case-insensitive in Starlette)
    transmission_id = request.headers.get("paypal-transmission-id")
    transmission_time = request.headers.get("paypal-transmission-time")
    transmission_sig = request.headers.get("paypal-transmission-sig")
    cert_url = request.headers.get("paypal-cert-url")
    auth_algo = request.headers.get("paypal-auth-algo")

    if not all([transmission_id, transmission_time, transmission_sig, cert_url, auth_algo]):
        missing = [
            h for h, val in [
                ("paypal-transmission-id", transmission_id),
                ("paypal-transmission-time", transmission_time),
                ("paypal-transmission-sig", transmission_sig),
                ("paypal-cert-url", cert_url),
                ("paypal-auth-algo", auth_algo),
            ] if not val
        ]
        logger.warning(f"Webhook request missing required PayPal transmission headers: {missing}")
        raise HTTPException(status_code=400, detail=f"Missing required PayPal transmission headers: {', '.join(missing)}")

    # 3. Retrieve webhook ID configuration
    webhook_id = os.getenv("PAYPAL_WEBHOOK_ID", "").strip()
    if not webhook_id:
        logger.error("PAYPAL_WEBHOOK_ID environment variable is not configured.")
        raise HTTPException(status_code=500, detail="PAYPAL_WEBHOOK_ID is not configured.")

    # 4. Verify signature using existing PayPalClient
    client = PayPalClient()
    try:
        is_valid = client.verify_webhook_signature(
            transmission_id=transmission_id,
            transmission_time=transmission_time,
            webhook_id=webhook_id,
            event_body=raw_body,
            cert_url=cert_url,
            auth_algo=auth_algo,
            actual_signature=transmission_sig,
        )
    except PayPalClientError as e:
        logger.error(f"PayPal signature verification client error: {e}")
        raise HTTPException(status_code=502, detail=f"PayPal client error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error verifying webhook signature: {e}")
        is_valid = False

    if not is_valid:
        logger.warning(f"Invalid webhook signature for transmission_id={transmission_id}")
        raise HTTPException(status_code=400, detail="Invalid webhook signature. Verification failed.")

    # 5. Process event and enforce persistent idempotency
    try:
        raw_payload_str = raw_body.decode("utf-8") if isinstance(raw_body, bytes) else str(raw_body)
        status, result = process_webhook_event(
            event_data=event_data,
            raw_payload=raw_payload_str,
            verifier_instance=_verifier,
        )
    except DatabaseError as e:
        logger.error(f"Durable database persistence failure during webhook processing: {e}")
        raise HTTPException(status_code=500, detail="Database persistence failure. Retryable error.")
    except Exception as e:
        logger.error(f"Unexpected error processing webhook event {event_data.get('id')}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal webhook processing error: {e}")

    # 6. For verified dispute creation, queue non-blocking background evidence compilation
    if (
        status == "PROCESSED"
        and event_data.get("event_type") == "CUSTOMER.DISPUTE.CREATED"
        and result.get("verified_linkage")
    ):
        background_tasks.add_task(
            compile_dispute_evidence_background,
            dispute_id=result.get("resource_id"),
            transaction_reference=result.get("transaction_reference"),
            reason=result.get("reason", "UNKNOWN"),
            verifier_instance=_verifier,
        )

    return WebhookProcessingResponse(
        status=status,
        event_id=result.get("event_id") or event_data.get("id", ""),
        event_type=result.get("event_type") or event_data.get("event_type", ""),
        resource_id=result.get("resource_id"),
        transaction_reference=result.get("transaction_reference"),
        detail=result.get("detail"),
        evidence_compilation_id=result.get("evidence_compilation_id"),
    )


@app.get("/metrics")
async def metrics():
    """Safe, precomputed evaluation summaries (loaded from report files)."""
    reports_dir = Path("artifacts/reports")
    summaries = []
    if reports_dir.exists():
        for f in sorted(reports_dir.glob("eval_*.json")):
            try:
                import json
                with open(f) as fh:
                    data = json.load(fh)
                summaries.append({
                    "file": f.name,
                    "split": data.get("split"),
                    "n_examples": data.get("n_examples"),
                    "accuracy": data.get("accuracy"),
                    "macro_f1": data.get("macro_f1"),
                    "contradiction_recall": data.get("contradiction_recall"),
                })
            except Exception:
                pass
    return {"evaluation_summaries": summaries, "note": "Precomputed evaluation results."}

