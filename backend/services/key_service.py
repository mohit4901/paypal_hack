"""
Cryptographic Key Lifecycle Registry Service (Finding F-04).
Manages Active, Retired, and Revoked keys with tamper-evident auditing.
Never exposes raw private secrets over API endpoints.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.config import DEFAULT_SIGNING_KEY, DEFAULT_SIGNING_KEY_ID
from src.models.evidence_compiler import KeyStatus, KeyRegistryEntry


class KeyRegistryService:
    """Manages system signing keys and their cryptographic governance state."""

    def __init__(self):
        # Initialize governed key entries (Zero raw secrets stored in source code)
        self._keys: Dict[str, KeyRegistryEntry] = {
            "proofledger-authority-v3-isolated": KeyRegistryEntry(
                key_id="proofledger-authority-v3-isolated",
                secret="[ISOLATED_ENVIRONMENT_SECRET]",
                status=KeyStatus.ACTIVE,
                activated_at="2026-11-02T12:00:00Z",
                description="Active Asymmetric Ed25519 Signing Authority Simulation (Pinned Public Key)",
            ),
            "proofledger-anchor-authority-2026": KeyRegistryEntry(
                key_id="proofledger-anchor-authority-2026",
                secret="[EXPOSED_HISTORICAL_MATERIAL]",
                status=KeyStatus.REVOKED,
                activated_at="2026-10-01T00:00:00Z",
                revoked_at="2026-11-02T12:00:00Z",
                revocation_reason="Authority private seed was exposed in source code repository; revoked immediately.",
                description="Revoked Ed25519 Authority Key — Historical Forensic Inspection Only",
            ),
            DEFAULT_SIGNING_KEY_ID or "v1-sandbox-202610": KeyRegistryEntry(
                key_id=DEFAULT_SIGNING_KEY_ID or "v1-sandbox-202610",
                secret=DEFAULT_SIGNING_KEY or "[REDACTED_EXTERNAL_SECRET]",
                status=KeyStatus.RETIRED,
                activated_at="2026-10-01T00:00:00Z",
                retired_at="2026-11-02T12:00:00Z",
                description="Legacy V2 Sandbox HMAC-SHA256 Key — Retired (Runtime HMAC creation disabled)",
            ),
            "v0-legacy-2025": KeyRegistryEntry(
                key_id="v0-legacy-2025",
                secret="[REDACTED_HISTORICAL_SECRET]",
                status=KeyStatus.RETIRED,
                activated_at="2025-01-01T00:00:00Z",
                retired_at="2026-09-30T23:59:59Z",
                description="Legacy V1 Manifest Signing Key — Historical Verification Only",
            ),
        }

    def list_keys(self) -> List[Dict[str, Any]]:
        """List all keys with lifecycle state, redacting the raw cryptographic secret."""
        return [entry.to_dict(include_secret=False) for entry in self._keys.values()]

    def get_key_entry(self, key_id: str) -> Optional[KeyRegistryEntry]:
        """Fetch internal KeyRegistryEntry with secret for cryptographic verification."""
        return self._keys.get(key_id)

    def get_signing_ring(self) -> Dict[str, KeyRegistryEntry]:
        """Return the dictionary of key entries for multi-key verification."""
        return dict(self._keys)


key_registry_service = KeyRegistryService()

