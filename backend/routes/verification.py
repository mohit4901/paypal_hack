"""
Forensic Verification routes.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.services.forensic_engine import ForensicEngine

router = APIRouter()

class VerifyRequest(BaseModel):
    target_id: str

@router.get("/{target_id}")
def verify_by_get(target_id: str):
    """Run full cryptographic & database verification for a target identifier."""
    result = ForensicEngine.verify_event(target_id)
    return result

@router.post("/check")
def verify_by_post(req: VerifyRequest):
    """Run full cryptographic & database verification via POST payload."""
    result = ForensicEngine.verify_event(req.target_id)
    return result

