"""
Overview and system health endpoint.
"""
from fastapi import APIRouter
from backend.services.forensic_engine import ForensicEngine

router = APIRouter()

@router.get("")
def get_overview():
    """Retrieve full system cryptographic status, ledger metrics, and sandbox state."""
    return ForensicEngine.get_overview_stats()

