"""
Database <-> Ledger Reconciliation routes.
"""
from fastapi import APIRouter
from backend.services.reconciliation_service import ReconciliationService

router = APIRouter()

@router.get("")
def get_reconciliation_report():
    """Execute cross-check between SQLite persistence and V2 JSONL evidence ledger."""
    return ReconciliationService.run_reconciliation()

