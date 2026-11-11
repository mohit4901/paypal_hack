"""
Ledger Chain Explorer routes.
"""
from fastapi import APIRouter
from backend.config import V2_CHAIN_LOG_PATH
from src.models.evidence_compiler import EventLog

router = APIRouter()

@router.get("")
def get_ledger_summary():
    """Retrieve full chain structural summary and recent block sequence."""
    log = EventLog(log_path=str(V2_CHAIN_LOG_PATH))
    is_valid, errors = log.verify_chain()
    total = len(log.events)

    blocks_summary = []
    # Include first 3, around target, and last 5 blocks
    for idx, ev in enumerate(log.events):
        if idx < 3 or idx >= total - 5:
            blocks_summary.append({
                "index": idx,
                "event_id": ev.get("event_id"),
                "source_type": ev.get("source_type"),
                "transaction_ref": ev.get("transaction_ref"),
                "current_hash": ev.get("current_hash"),
                "previous_hash": ev.get("previous_hash"),
                "recorded_at": ev.get("recorded_at"),
                "is_migrated": bool(ev.get("v2_migration")),
            })

    return {
        "ledger_file": str(V2_CHAIN_LOG_PATH),
        "total_events": total,
        "is_valid": is_valid,
        "errors": errors,
        "genesis_hash": log.events[0]["current_hash"] if total > 0 else "genesis",
        "head_hash": log.events[-1]["current_hash"] if total > 0 else "genesis",
        "sampled_blocks": blocks_summary,
    }

@router.get("/validate")
def validate_entire_chain():
    """Trigger full end-to-end cryptographic link audit across all records."""
    log = EventLog(log_path=str(V2_CHAIN_LOG_PATH))
    is_valid, errors = log.verify_chain()
    return {
        "is_valid": is_valid,
        "error_count": len(errors),
        "errors": errors,
        "total_records_verified": len(log.events),
    }

