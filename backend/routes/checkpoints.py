"""
External Integrity Checkpoints routes.
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth import get_current_seller
from backend.config import (
    CHECKPOINTS_DIR,
    V2_CHAIN_LOG_PATH,
    DEFAULT_SIGNING_KEY,
    DEFAULT_SIGNING_KEY_ID,
)
from src.models.evidence_compiler import EventLog, strict_json_pairs_hook

router = APIRouter()

class CreateCheckpointRequest(BaseModel):
    key_id: Optional[str] = DEFAULT_SIGNING_KEY_ID

@router.get("")
def list_checkpoints():
    """List all available external cryptographic checkpoints and verify their integrity."""
    checkpoints = []
    p = Path(CHECKPOINTS_DIR)
    if p.exists():
        for cp_file in sorted(p.glob("*.json")):
            try:
                with open(cp_file, "r", encoding="utf-8") as f:
                    data = json.load(f, object_pairs_hook=strict_json_pairs_hook)
                
                # Verify checkpoint against ledger (supports Ed25519 Asymmetric and HMAC-SHA256)
                if data.get("signature_algorithm") == "Ed25519":
                    from backend.security.asymmetric_anchor import verify_asymmetric_checkpoint
                    is_valid, errors, _ = verify_asymmetric_checkpoint(
                        checkpoint_path=str(cp_file),
                        ledger_path=str(V2_CHAIN_LOG_PATH),
                    )
                else:
                    is_valid, errors, _ = EventLog.verify_external_checkpoint(
                        ledger_path=str(V2_CHAIN_LOG_PATH),
                        checkpoint_path=str(cp_file),
                        signing_key=DEFAULT_SIGNING_KEY,
                    )
                data["_is_valid"] = is_valid
                data["_errors"] = errors
                data["_filename"] = cp_file.name
                checkpoints.append(data)
            except Exception as ex:
                checkpoints.append({
                    "_filename": cp_file.name,
                    "_is_valid": False,
                    "_errors": [str(ex)],
                })

    return {
        "total_checkpoints": len(checkpoints),
        "checkpoints": checkpoints,
    }

@router.post("/create")
def create_checkpoint(
    req: CreateCheckpointRequest,
    current_seller: Dict[str, Any] = Depends(get_current_seller),
):
    """
    Disabled in ProofLedger v2.6.
    Runtime checkpoint signing is strictly prohibited. ProofLedger enforces public-key-only asymmetric verification.
    All checkpoints must be generated via the isolated offline signing authority using Ed25519 digital signatures.
    """
    raise HTTPException(
        status_code=405,
        detail=(
            "Runtime checkpoint signing is prohibited in ProofLedger v2.6. "
            "Application runtime operates strictly as a read-only verifier under asymmetric Ed25519 digital signatures. "
            "Checkpoints must be anchored offline via tools/external_signing_authority.py with isolated authority keys."
        ),
    )

