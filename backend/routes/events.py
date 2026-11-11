"""
Events Explorer routes.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from backend.services.forensic_engine import ForensicEngine

router = APIRouter()

@router.get("")
def list_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    source_type: Optional[str] = None,
    search: Optional[str] = None,
    transaction_ref: Optional[str] = None,
):
    """Retrieve paginated events from the active V2 ledger with optional filtering."""
    return ForensicEngine.get_ledger_events(
        page=page,
        page_size=page_size,
        source_type=source_type,
        search=search,
        transaction_ref=transaction_ref,
    )

@router.get("/{event_id}")
def get_event(event_id: str):
    """Retrieve raw event details by ID."""
    event = ForensicEngine.get_event_by_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found in V2 ledger.")
    return event

@router.get("/{event_id}/verify")
def verify_event_endpoint(event_id: str):
    """Execute 6-dimensional forensic verification on a specific event."""
    result = ForensicEngine.verify_event(event_id)
    if not result.get("found"):
        raise HTTPException(status_code=404, detail=result.get("summary", "Event not found."))
    return result

