"""
Pydantic schemas for the ProofLedger API.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class EvidenceItem(BaseModel):
    evidence_id: str = Field(..., description="Unique evidence record identifier")
    source_type: str = Field(..., description="Source system type (e.g., paypal_api, delivery_service)")
    timestamp: Optional[str] = Field(None, description="ISO 8601 timestamp")
    content: str = Field(..., description="Evidence record content")

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Evidence content must not be empty.")
        return v.strip()


class PredictRequest(BaseModel):
    claim_id: Optional[str] = Field(None, description="Caller-supplied claim identifier")
    transaction_reference: Optional[str] = Field(None, description="Order or transaction ID")
    claim: str = Field(..., description="Factual claim to verify", min_length=5, max_length=2000)
    evidence: List[EvidenceItem] = Field(default_factory=list, description="Source evidence records")
    dispute_reason: Optional[str] = Field(None, description="PayPal dispute reason, if applicable")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    @field_validator("evidence")
    @classmethod
    def check_evidence_ids_unique(cls, evs: List[EvidenceItem]) -> List[EvidenceItem]:
        ids = [e.evidence_id for e in evs]
        if len(ids) != len(set(ids)):
            raise ValueError("Evidence IDs must be unique within a request.")
        return evs


class PredictResponse(BaseModel):
    claim_id: str
    label: str = Field(..., description="SUPPORTED | CONTRADICTED | INSUFFICIENT_EVIDENCE")
    confidence: float = Field(..., description="Raw model score (not a calibrated probability)")
    note_confidence: str
    evidence_ids: List[str]
    supporting_evidence_ids: List[str]
    contradicting_evidence_ids: List[str]
    missing_information: List[str]
    deterministic_checks: List[Dict[str, Any]]
    deterministic_label: str
    model_label: str
    rule_model_disagreement: bool
    model_version: str
    dataset_version: str
    limitations: List[str]
    human_review_required: bool


class BatchPredictItem(PredictRequest):
    pass


class BatchPredictRequest(BaseModel):
    items: List[BatchPredictItem] = Field(..., max_length=50)


class BatchPredictResponse(BaseModel):
    results: List[PredictResponse]
    count: int


class ValidateEvidenceRequest(BaseModel):
    transaction_reference: Optional[str] = None
    claim: str = Field(..., min_length=5, max_length=2000)
    evidence: List[EvidenceItem] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None


class ValidateEvidenceResponse(BaseModel):
    label: str
    deterministic_checks: List[Dict[str, Any]]
    checks_passed: int
    checks_total: int
    human_review_required: bool


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    uptime_s: float


class DisputeEvidenceSubmissionRequest(BaseModel):
    dispute_id: str = Field(..., description="PayPal dispute identifier")
    evidence_type: str = Field(default="PROOF_OF_DELIVERY", description="PROOF_OF_DELIVERY | PROOF_OF_REFUND | OTHER")
    evidence_info: Dict[str, Any] = Field(default_factory=dict, description="Structured evidence payload (tracking, URLs, logs)")
    notes: str = Field(..., description="Summary explanation of the evidence dossier")
    seller_human_approved: bool = Field(..., description="Mandatory confirmation that human seller reviewed evidence before submission")

    @field_validator("seller_human_approved")
    @classmethod
    def validate_human_approval(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Submission rejected: seller_human_approved must be True. ProofLedger forbids automated submissions.")
        return v


class DisputeEvidenceSubmissionResponse(BaseModel):
    dispute_id: str
    status: str
    submission_timestamp: str
    seller_human_approved: bool
    details: Dict[str, Any]


class ModelInfoResponse(BaseModel):
    model_path: str
    architecture: str
    num_labels: int
    id2label: Dict[str, str]
    nli_to_app: Dict[str, str]
    device: str
    model_version: str
    dataset_version: str
    disclaimer: str


class WebhookProcessingResponse(BaseModel):
    status: str = Field(..., description="PROCESSED | DUPLICATE | FLAGGED_MANUAL_RECONCILIATION | SKIPPED")
    event_id: str
    event_type: str
    resource_id: Optional[str] = None
    transaction_reference: Optional[str] = None
    detail: Optional[str] = None
    evidence_compilation_id: Optional[str] = None


