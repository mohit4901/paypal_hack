"""
Key Lifecycle Management routes (Finding F-04).
"""
from fastapi import APIRouter
from backend.services.key_service import key_registry_service

router = APIRouter()

@router.get("")
def list_key_registry():
    """Retrieve key registry entries with lifecycle statuses (ACTIVE, RETIRED, REVOKED)."""
    keys = key_registry_service.list_keys()
    return {
        "total_keys": len(keys),
        "keys": keys,
        "governance_policy": {
            "ACTIVE": "Allowed to sign new manifests and verify signatures.",
            "RETIRED": "Cannot sign new manifests. Strictly allowed to verify historical signatures.",
            "REVOKED": "Compromised. All signatures are immediately rejected as UNTRUSTED/COMPROMISED.",
        },
    }

