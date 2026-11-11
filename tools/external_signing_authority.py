"""
ProofLedger External Signing Authority Tool (Offline / Isolated Boundary).
Offline Ed25519 Signing Authority Simulation:
- ZERO private keys or default seeds are stored in source code.
- Private signing key is loaded strictly from the external environment (PROOFLEDGER_AUTHORITY_OFFLINE_SECRET).
- Strictly decoupled from web application processes and database layers.
- Signs canonical checkpoint manifests with Ed25519 digital signatures.
- NOTE: This is an offline software simulation of an asymmetric signing authority;
  it does NOT connect to physical HSM hardware or live AWS KMS in this environment.
"""
import os
import json
import hashlib
from pathlib import Path
from typing import Any, Dict

from cryptography.hazmat.primitives.asymmetric import ed25519

AUTHORITY_KEY_IDENTITY = "proofledger-authority-v3-isolated"
AUTHORITY_PUBLIC_KEY_HEX = "9599d3b3ed9fe4643de0482c1c4e51c6be72f926d7021b93c6a657ec384324dd"


def _get_private_key() -> ed25519.Ed25519PrivateKey:
    """
    Loads Ed25519 private signing key strictly from an isolated external environment secret.
    Raises RuntimeError if no external secret is configured.
    """
    seed_hex = os.getenv("PROOFLEDGER_AUTHORITY_OFFLINE_SECRET")
    if not seed_hex:
        raise RuntimeError(
            "PROOFLEDGER_AUTHORITY_OFFLINE_SECRET environment variable is missing. "
            "Private signing keys are strictly isolated outside the source code repository. "
            "Zero private keys or default seeds are permitted in source code."
        )
    seed = bytes.fromhex(seed_hex.strip())
    if len(seed) != 32:
        raise ValueError(f"Authority seed must be exactly 32 bytes (64 hex characters), got {len(seed)} bytes.")
    return ed25519.Ed25519PrivateKey.from_private_bytes(seed)


def compute_canonical_digest(checkpoint_data: Dict[str, Any]) -> str:
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


def sign_checkpoint_offline(checkpoint_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Offline Authority Signing Function:
    Applies Ed25519 signature to canonical checkpoint manifest using the isolated authority private key.
    """
    private_key = _get_private_key()
    pub_key_hex = private_key.public_key().public_bytes_raw().hex()

    record_to_sign = dict(checkpoint_data)
    record_to_sign["signature_algorithm"] = "Ed25519"
    record_to_sign["key_identity"] = AUTHORITY_KEY_IDENTITY
    record_to_sign["public_key_hex"] = pub_key_hex
    record_to_sign["trust_boundary"] = "OFFLINE_SIGNING_AUTHORITY_SIMULATION"

    digest = compute_canonical_digest(record_to_sign)
    sig_bytes = private_key.sign(digest.encode("utf-8"))

    record_to_sign["canonical_digest"] = digest
    record_to_sign["signature"] = sig_bytes.hex()
    return record_to_sign


if __name__ == "__main__":
    print("External Signing Authority (Offline Simulation)")
    print(f"Key Identity: {AUTHORITY_KEY_IDENTITY}")
    print(f"Active Public Key Hex: {AUTHORITY_PUBLIC_KEY_HEX}")
    has_key = bool(os.getenv("PROOFLEDGER_AUTHORITY_OFFLINE_SECRET"))
    print(f"Private Key Available in Environment: {has_key}")
