"""
ProofLedger Asymmetric Trust Anchor Module.
Implements Ed25519 Digital Signatures for Cryptographic Checkpoints.

Key Security Architecture:
1. Private Signing Key: Isolated in External Signing Authority (simulating AWS KMS / HSM).
   The application runtime does NOT store or need the private key.
2. Pinned Public Key: Hardened in application configuration for fail-closed verification.
3. Checkpoint Verification: Asymmetric signature verification using only the public key.
4. Monotonic Height & Rollback Protection: Verifies block height and prevents state reversion.
"""
import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature

from src.models.evidence_compiler import EventLog

# Active Authority Public Key (Hex Encoded)
# Isolated from private signing key; verified fail-closed
ACTIVE_ED25519_PUBLIC_KEY_HEX = "9599d3b3ed9fe4643de0482c1c4e51c6be72f926d7021b93c6a657ec384324dd"
ACTIVE_AUTHORITY_KEY_IDENTITY = "proofledger-authority-v3-isolated"

# Pinned Active Key
PINNED_ED25519_PUBLIC_KEY_HEX = ACTIVE_ED25519_PUBLIC_KEY_HEX
AUTHORITY_KEY_IDENTITY = ACTIVE_AUTHORITY_KEY_IDENTITY

# Compromised / Revoked Historical Keys registry
REVOKED_HISTORICAL_AUTHORITIES = {
    "dbd6f98003d24c1170bfe6e89ad1e367e4f2aa44d14c2aaede7edd1600c1fae0": {
        "key_identity": "proofledger-anchor-authority-2026",
        "status": "REVOKED_COMPROMISED",
        "revoked_at": "2026-11-02T12:00:00Z",
        "reason": "Hardcoded default seed exposure in repository source files.",
    }
}


def get_canonical_checkpoint_digest(checkpoint_data: Dict[str, Any]) -> str:
    """Computes SHA-256 digest over sorted, canonical checkpoint payload excluding signature and digest fields."""
    canonical_dict = {
        k: v for k, v in checkpoint_data.items()
        if k not in (
            "signature",
            "ed25519_signature",
            "hmac_signature",
            "canonical_digest",
            "checkpoint_digest",
        )
    }
    canonical_json = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_TRANSPARENCY_LOG_PATH = _PROJECT_ROOT / "ai" / "data" / "checkpoints" / "external_transparency_log.json"


def verify_asymmetric_checkpoint(
    checkpoint_path: str,
    ledger_path: str,
    pinned_public_key_hex: str = PINNED_ED25519_PUBLIC_KEY_HEX,
    transparency_log_path: Optional[str] = None,
    enforce_monotonic: bool = True,
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Verifies a cryptographic checkpoint against an event ledger using ONLY the public key.
    
    Verifies:
    1. Checkpoint file exists.
    2. Digest matches canonical payload.
    3. Ed25519 digital signature is valid under the pinned public key.
    4. Ledger hash chain is unbroken.
    5. Ledger event count >= checkpoint block height (Rollback protection).
    6. Hash at checkpoint height equals checkpoint head_hash.
    7. External monotonic progression against transparency log (replays of older checkpoints rejected).
    """
    errors = []
    cp_path = Path(checkpoint_path)
    if not cp_path.exists():
        return False, [f"Checkpoint file not found: {checkpoint_path}"], {}

    try:
        with open(cp_path, "r", encoding="utf-8") as f:
            cp_data = json.load(f)
    except Exception as e:
        return False, [f"Failed to read checkpoint JSON: {e}"], {}

    # 1. Verify Digest
    expected_digest = get_canonical_checkpoint_digest(cp_data)
    recorded_digest = cp_data.get("canonical_digest") or cp_data.get("checkpoint_digest")
    if recorded_digest != expected_digest:
        errors.append(f"Checkpoint digest mismatch: computed {expected_digest} != recorded {recorded_digest}")

    # 2. Verify Ed25519 Signature
    sig_hex = cp_data.get("signature") or cp_data.get("ed25519_signature")
    cp_pub_key = cp_data.get("public_key_hex") or pinned_public_key_hex

    if cp_pub_key in REVOKED_HISTORICAL_AUTHORITIES:
        rev_info = REVOKED_HISTORICAL_AUTHORITIES[cp_pub_key]
        errors.append(
            f"Signing authority '{cp_pub_key[:16]}...' is REVOKED_COMPROMISED "
            f"(Revoked at: {rev_info['revoked_at']}, Reason: {rev_info['reason']}). "
            f"Checkpoints created under revoked authorities are rejected for active verification."
        )

    if not sig_hex:
        errors.append("Checkpoint is unsigned: missing 'signature' field.")
    else:
        try:
            pub_bytes = bytes.fromhex(pinned_public_key_hex)
            pub_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
            pub_key.verify(bytes.fromhex(sig_hex), expected_digest.encode("utf-8"))
        except InvalidSignature:
            errors.append("Ed25519 signature verification FAILED: Signature is invalid for pinned authority public key.")
        except Exception as e:
            errors.append(f"Ed25519 verification error: {e}")

    # 3. Verify Ledger Chain
    led_path = Path(ledger_path)
    if not led_path.exists():
        errors.append(f"Ledger file not found: {ledger_path}")
        return False, errors, cp_data

    log = EventLog(log_path=str(led_path), allow_broken_chain=True)
    chain_valid, chain_errs = log.verify_chain()
    if not chain_valid:
        errors.extend(chain_errs)

    ledger_events = log.events

    # 4. Monotonic Height / Rollback Protection
    req_height = cp_data.get("block_height") or cp_data.get("total_events", 0)
    if len(ledger_events) < req_height:
        errors.append(
            f"Rollback attack detected: Current ledger height ({len(ledger_events)}) is less than checkpoint height ({req_height})."
        )
    elif req_height > 0:
        anchor_block = ledger_events[req_height - 1]
        actual_head_hash = anchor_block.get("current_hash")
        cp_head_hash = cp_data.get("head_hash")
        if actual_head_hash != cp_head_hash:
            errors.append(
                f"Ledger content discrepancy at height {req_height}: Ledger hash '{actual_head_hash}' != checkpoint head_hash '{cp_head_hash}'."
            )

    # 5. Monotonic Progression against Local Monotonic Transparency Registry (Fail-Closed)
    if enforce_monotonic:
        t_path = Path(transparency_log_path) if transparency_log_path else DEFAULT_TRANSPARENCY_LOG_PATH
        if not t_path.exists():
            errors.append(
                f"Fail-closed: Monotonic transparency registry not found at '{t_path}'. "
                "Checkpoints cannot be verified without an active monotonic anchor registry."
            )
        else:
            try:
                with open(t_path, "r", encoding="utf-8") as tf:
                    t_data = json.load(tf)
                highest_trusted_height = t_data.get("highest_trusted_height")
                highest_trusted_hash = t_data.get("highest_trusted_head_hash")

                if highest_trusted_height is None or not highest_trusted_hash:
                    errors.append(
                        "Fail-closed: Monotonic registry corrupted or missing required anchor metadata "
                        "('highest_trusted_height' or 'highest_trusted_head_hash')."
                    )
                else:
                    if req_height < highest_trusted_height:
                        errors.append(
                            f"Monotonic rollback attack detected: presented checkpoint height ({req_height}) is strictly less than "
                            f"highest verified monotonic anchor ({highest_trusted_height}). Replay of historical states is prohibited."
                        )
                    elif req_height == highest_trusted_height:
                        if cp_data.get("head_hash") != highest_trusted_hash:
                            errors.append(
                                f"Transparency anchor discrepancy at height {highest_trusted_height}: "
                                f"checkpoint head_hash '{cp_data.get('head_hash')}' != anchored hash '{highest_trusted_hash}'."
                            )
            except Exception as e:
                errors.append(f"Fail-closed: Failed to read monotonic transparency registry: {e}")

    return len(errors) == 0, errors, cp_data
