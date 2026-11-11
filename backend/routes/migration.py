"""
Migration Audit & Provenance Manifest routes.
"""
from pathlib import Path
from fastapi import APIRouter, HTTPException
from backend.config import (
    V2_CHAIN_LOG_PATH,
    V2_MANIFEST_PATH,
    LEGACY_ARCHIVE_PATH,
    DEFAULT_SIGNING_KEY,
)
from src.models.evidence_compiler import EventLog

router = APIRouter()

@router.get("")
def get_migration_audit():
    """Retrieve full V2 migration audit, manifest digest check, and HMAC verification."""
    if not Path(V2_MANIFEST_PATH).exists():
        raise HTTPException(status_code=404, detail="Migration manifest file not found.")

    has_signature = False
    try:
        with open(V2_MANIFEST_PATH, "r", encoding="utf-8") as mf:
            raw_m = json.load(mf)
            has_signature = "hmac_signature" in raw_m
    except Exception:
        pass

    is_valid, errors, report = EventLog.verify_v2_manifest(
        v2_log_path=str(V2_CHAIN_LOG_PATH),
        manifest_path=str(V2_MANIFEST_PATH),
        source_legacy_path=str(LEGACY_ARCHIVE_PATH) if Path(LEGACY_ARCHIVE_PATH).exists() else None,
        signing_key=DEFAULT_SIGNING_KEY if has_signature else None,
    )

    return {
        "manifest_valid": is_valid,
        "errors": errors,
        "audit_report": report,
        "legacy_archive_available": Path(LEGACY_ARCHIVE_PATH).exists(),
    }
