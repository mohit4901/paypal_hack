"""
AI Model & Neural Verification Routes.
Provides live status and interactive test inference directly from frontend.
"""
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.dispute_service import dispute_service
from src.models.input_format import EvidenceRecord

router = APIRouter()


class AITestRequest(BaseModel):
    claim: str
    evidence_text: str
    source_type: Optional[str] = "custom_log"


@router.get("/status")
def get_ai_status():
    """Retrieve live status of the DeBERTa-v3 Fine-Tuned NLI neural model."""
    verifier = dispute_service.verifier
    root_dir = Path(__file__).resolve().parent.parent.parent
    raw_path = dispute_service.loaded_model_path or dispute_service.configured_model_path
    model_dir = Path(raw_path) if raw_path else (root_dir / "ai" / "artifacts" / "best_model")
    model_file = model_dir / "model.safetensors"

    file_size_mb = round(model_file.stat().st_size / (1024 * 1024), 2) if model_file.exists() else 0
    try:
        rel_path = str(model_dir.relative_to(root_dir))
    except ValueError:
        rel_path = str(model_dir)

    return {
        "status": "ONLINE" if (verifier and verifier.is_loaded) else "MODEL_UNAVAILABLE",
        "model_name": "DeBERTa-v3-base-mnli-fever-anli (Fine-Tuned)",
        "model_path": rel_path,
        "loaded_model_path": dispute_service.loaded_model_path,
        "model_load_error": dispute_service.model_load_error,
        "weights_file": "model.safetensors",
        "weights_size_mb": file_size_mb,
        "is_loaded": verifier.is_loaded if verifier else False,
        "device": getattr(verifier, "device", getattr(verifier, "_device", "cpu")) if verifier else "offline",
        "supported_labels": ["SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"],
        "architecture": verifier.model_info.get("architecture", "DeBERTaV2ForSequenceClassification") if verifier else None,
        "fine_tuning": "Dispute Resolution NLI (Advisory Semantic Alignment)",
    }


@router.post("/test-inference")
def test_ai_inference(req: AITestRequest):
    """
    Execute real-time neural inference on custom claim and evidence text.
    Measures exact inference latency and returns class probabilities.
    """
    verifier = dispute_service.verifier
    if not verifier or not verifier.is_loaded:
        raise HTTPException(status_code=503, detail="AI Neural Model is currently unavailable.")

    t0 = time.time()
    record = EvidenceRecord(
        evidence_id="EV-TEST-01",
        source_type=req.source_type or "custom_log",
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        content=req.evidence_text,
    )

    try:
        pred = verifier.predict(req.claim, [record])
        latency_ms = round((time.time() - t0) * 1000, 2)
        return {
            "claim": req.claim,
            "evidence_text": req.evidence_text,
            "label": pred.get("label"),
            "confidence": pred.get("confidence"),
            "scores": pred.get("scores"),
            "latency_ms": latency_ms,
            "model_name": "DeBERTa-v3-base-mnli-fever-anli (Fine-Tuned)",
            "device": getattr(verifier, "_device", "mps"),
            "timestamp": time.time(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference error: {str(e)}")

