"""
Evidence Compiler — auditable claim verification pipeline.

Implements the full compilation flow:
1. Validate evidence record structure
2. Run deterministic checks
3. Run ML model
4. Compare and flag disagreements
5. Produce an evidence-readiness report

Includes an append-only hash-chain event log.
"""
from __future__ import annotations

from contextlib import contextmanager
from enum import Enum
import fcntl
import hashlib
import hmac
import json
import os
import time
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from src.models.deterministic_validator import DeterministicValidator
from src.models.evidence_verifier import EvidenceVerifier
from src.models.input_format import EvidenceRecord
from src.models.labels import AppLabel
from src.utils.logging_config import setup_logging

logger = setup_logging(name="evidence_compiler")


def fsync_dir(dir_path: Path) -> None:
    """
    Flush directory entry changes to physical durable storage (POSIX).
    Required by POSIX filesystems to guarantee that creating, unlinking, or
    renaming file entries persists across system crashes or power losses.
    """
    try:
        dir_fd = os.open(str(dir_path), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass


@contextmanager
def persistent_ledger_lock(lock_path: str, shared: bool = False, timeout_s: float = 30.0):
    """
    Acquire a kernel-enforced flock on a persistent, dedicated lock file.
    The lock file is NEVER unlinked, deleted, or replaced by os.replace,
    guaranteeing that all processes (concurrent appenders, crash recovery,
    migration, and snapshot verifiers) synchronize on the exact same inode.
    """
    lock_p = Path(lock_path)
    lock_p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_p), os.O_RDWR | os.O_CREAT, 0o644)
    lock_flags = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
    start_time = time.time()
    acquired = False
    try:
        while True:
            try:
                fcntl.flock(fd, lock_flags | fcntl.LOCK_NB)
                acquired = True
                break
            except (BlockingIOError, OSError):
                if time.time() - start_time > timeout_s:
                    raise TimeoutError(f"Timed out after {timeout_s}s waiting for lock on '{lock_path}'")
                time.sleep(0.01)
        yield
    finally:
        if acquired:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
        try:
            os.close(fd)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Hash-chain exceptions & constants
# ---------------------------------------------------------------------------

class HashChainError(Exception):
    """Base exception for ProofLedger hash-chain operations."""
    pass


class MalformedEventError(HashChainError):
    """Raised when an event log entry is structurally invalid or unparseable JSON."""
    pass


class ChainIntegrityError(HashChainError):
    """Raised when an append operation is rejected due to a broken or tampered hash chain."""
    pass


REQUIRED_EVENT_FIELDS = (
    "event_id",
    "schema_version",
    "transaction_ref",
    "source_type",
    "source_event_id",
    "event_timestamp",
    "recorded_at",
    "previous_hash",
    "payload",
    "current_hash",
)

CANONICAL_VERSION_1_0 = "1.0"
CANONICAL_VERSION_2_0 = "2.0"

FINANCIAL_KEYS = {
    "amount",
    "fee",
    "gross_amount",
    "net_amount",
    "dispute_amount",
    "shipping_discount",
    "insurance",
    "tax_total",
    "refund_amount",
    "disputed_amount",
    "total_amount",
    "custom_amount",
}


def strict_json_pairs_hook(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    """
    object_pairs_hook for json.loads that strictly rejects duplicate keys at any nesting level.
    Prevents JSON parser divergence attacks and silent overwrite vulnerabilities (Finding F-02).
    """
    res: Dict[str, Any] = {}
    for k, v in pairs:
        if k in res:
            raise MalformedEventError(f"Duplicate JSON key detected in payload or event: '{k}'")
        res[k] = v
    return res


def strict_json_loads(s: str) -> Any:
    """Parse JSON strictly, rejecting duplicate keys and malformed syntax."""
    try:
        return json.loads(s, object_pairs_hook=strict_json_pairs_hook)
    except MalformedEventError:
        raise
    except Exception as ex:
        raise MalformedEventError(f"Failed to parse JSON: {ex}") from ex


def normalize_canonical_data(data: Any, detect_collisions: bool = True) -> Any:
    """
    Recursively normalize dictionary keys and string values into Unicode NFC format.
    Detects collisions where two distinct Unicode key strings (e.g., precomposed vs decomposed)
    normalize to the exact same NFC representation (Finding F-01).
    """
    if isinstance(data, str):
        return unicodedata.normalize("NFC", data)
    elif isinstance(data, dict):
        normalized_dict: Dict[str, Any] = {}
        seen_raw_keys: Dict[str, str] = {}
        for k, v in data.items():
            k_str = str(k)
            norm_k = unicodedata.normalize("NFC", k_str)
            if detect_collisions and norm_k in normalized_dict:
                orig_k = seen_raw_keys[norm_k]
                if orig_k != k_str:
                    raise MalformedEventError(
                        f"Unicode collision detected in keys: '{orig_k}' and '{k_str}' normalize to identical NFC form '{norm_k}'"
                    )
            seen_raw_keys[norm_k] = k_str
            normalized_dict[norm_k] = normalize_canonical_data(v, detect_collisions=detect_collisions)
        return normalized_dict
    elif isinstance(data, list):
        return [normalize_canonical_data(item, detect_collisions=detect_collisions) for item in data]
    elif isinstance(data, tuple):
        return [normalize_canonical_data(item, detect_collisions=detect_collisions) for item in data]
    return data


def validate_financial_precision(data: Any, path: str = "") -> None:
    """
    Recursively check that financial monetary fields are represented as exact decimal strings
    (e.g., '5.00') or integer cents, NEVER IEEE-754 binary floating-point numbers (Finding F-03).
    """
    if isinstance(data, dict):
        for k, v in data.items():
            curr_path = f"{path}.{k}" if path else str(k)
            k_lower = str(k).lower()
            if k_lower in FINANCIAL_KEYS or "amount" in k_lower or "fee" in k_lower:
                if isinstance(v, float):
                    raise MalformedEventError(
                        f"Financial field '{curr_path}' uses floating-point ({v}). "
                        "Must be represented as an exact decimal string (e.g. '5.00') or integer cents."
                    )
            validate_financial_precision(v, curr_path)
    elif isinstance(data, (list, tuple)):
        for idx, item in enumerate(data):
            validate_financial_precision(item, f"{path}[{idx}]")


class KeyStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"
    REVOKED = "REVOKED"


class KeyRegistryEntry:
    """Represents a cryptographic signing key and its security lifecycle state (Finding F-04)."""
    def __init__(
        self,
        key_id: str,
        secret: str,
        status: Union[KeyStatus, str] = KeyStatus.ACTIVE,
        activated_at: Optional[str] = None,
        retired_at: Optional[str] = None,
        revoked_at: Optional[str] = None,
        revocation_reason: Optional[str] = None,
        description: Optional[str] = None,
    ):
        self.key_id = key_id
        self.secret = secret
        self.status = status if isinstance(status, KeyStatus) else KeyStatus(status)
        self.activated_at = activated_at or datetime.now(timezone.utc).isoformat()
        self.retired_at = retired_at
        self.revoked_at = revoked_at
        self.revocation_reason = revocation_reason
        self.description = description or ""

    def to_dict(self, include_secret: bool = False) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "key_id": self.key_id,
            "status": self.status.value,
            "activated_at": self.activated_at,
            "retired_at": self.retired_at,
            "revoked_at": self.revoked_at,
            "revocation_reason": self.revocation_reason,
            "description": self.description,
        }
        if include_secret:
            d["secret"] = self.secret
        return d


# ---------------------------------------------------------------------------
# Hash-chain event log
# ---------------------------------------------------------------------------

class EventLog:
    """
    Append-only tamper-evident event log with a SHA-256 hash chain.

    LIMITATION: The hash chain reveals later modification of recorded events
    but does NOT by itself prove the truth of the original event.
    """

    SCHEMA_VERSION = "1.0"

    def __init__(
        self,
        log_path: Optional[str] = None,
        lock_path: Optional[str] = None,
        allow_broken_chain: bool = False,
        auto_recover_interrupted_write: bool = False,
    ):
        self._events: List[Dict[str, Any]] = []
        self._log_path = log_path
        self._lock_path = lock_path or (f"{log_path}.lock" if log_path else None)
        self._allow_broken_chain = allow_broken_chain
        self._auto_recover = auto_recover_interrupted_write
        self._chain_valid: bool = True
        self._chain_errors: List[str] = []

        if log_path:
            p = Path(log_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            if p.exists():
                if self._auto_recover:
                    self.recover_interrupted_write(str(p), lock_path=self._lock_path)
                self._load_from_disk(p)

    def _load_from_disk(self, path: Path) -> None:
        """Load existing JSONL records from disk, validate structure, and evaluate chain integrity."""
        self._events = []
        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    event = json.loads(line_str, object_pairs_hook=strict_json_pairs_hook)
                except MalformedEventError:
                    raise
                except Exception as e:
                    raise MalformedEventError(
                        f"Line {line_no} in '{path}' is not valid JSON: {e}"
                    ) from e

                if not isinstance(event, dict):
                    raise MalformedEventError(
                        f"Line {line_no} in '{path}' is not a JSON object."
                    )

                missing_fields = [fld for fld in REQUIRED_EVENT_FIELDS if fld not in event]
                if missing_fields:
                    raise MalformedEventError(
                        f"Line {line_no} in '{path}' is missing required fields: {missing_fields}"
                    )

                self._events.append(event)

        # Evaluate chain integrity of loaded records
        self._chain_valid, self._chain_errors = self.verify_chain()
        if not self._chain_valid:
            logger.warning(
                f"EventLog loaded '{path}' with {len(self._chain_errors)} integrity errors. "
                "Normal append operations will be rejected."
            )

    @classmethod
    def from_file(cls, log_path: str, allow_broken_chain: bool = False) -> EventLog:
        """Load an event log from disk for chain verification and inspection."""
        return cls(log_path=log_path, allow_broken_chain=allow_broken_chain)

    def _hash_event(self, event: Dict[str, Any], canonical_version: Optional[str] = None) -> str:
        ver = canonical_version or event.get("canonical_version") or CANONICAL_VERSION_1_0
        if ver == CANONICAL_VERSION_2_0:
            norm_event = normalize_canonical_data(event)
            blob = json.dumps(norm_event, sort_keys=True, default=str).encode("utf-8")
        else:
            blob = json.dumps(event, sort_keys=True, default=str).encode()
        return hashlib.sha256(blob).hexdigest()

    def append(
        self,
        transaction_ref: str,
        source_type: str,
        source_event_id: str,
        event_timestamp: str,
        payload: Dict[str, Any],
        canonical_version: str = CANONICAL_VERSION_1_0,
    ) -> Dict[str, Any]:
        """
        Append a new event to the tamper-evident hash chain.
        - Enforces decimal precision over floating-point financial values (Finding F-03).
        - Normalizes Unicode keys/strings to NFC when canonical_version is '2.0' (Finding F-01).
        - Validates that the existing chain is valid before appending.
        - Uses fcntl.flock to guarantee thread/process concurrency safety.
        - Links to the actual last current_hash on disk.
        """
        validate_financial_precision(payload)

        if not self._chain_valid and not self._allow_broken_chain:
            raise ChainIntegrityError(
                f"Cannot append to broken hash chain in '{self._log_path}': "
                f"{len(self._chain_errors)} integrity error(s) detected. "
                f"First error: {self._chain_errors[0] if self._chain_errors else 'integrity compromised'}."
            )

        if self._log_path:
            lock_target = self._lock_path or f"{self._log_path}.lock"
            with persistent_ledger_lock(lock_target, shared=False):
                with open(self._log_path, "a+", encoding="utf-8") as f:
                    f.seek(0)
                    disk_lines = [l.strip() for l in f if l.strip()]
                    if disk_lines:
                        try:
                            last_event = json.loads(disk_lines[-1], object_pairs_hook=strict_json_pairs_hook)
                            prev_hash = last_event.get("current_hash", "genesis")
                        except Exception as ex:
                            raise MalformedEventError(f"Trailing line in '{self._log_path}' is corrupted: {ex}") from ex
                        # Synchronize memory representation if concurrent writers added events
                        if len(disk_lines) > len(self._events):
                            self._events = [json.loads(l, object_pairs_hook=strict_json_pairs_hook) for l in disk_lines]
                    else:
                        prev_hash = "genesis"

                    event = {
                        "event_id": str(uuid.uuid4()),
                        "schema_version": self.SCHEMA_VERSION,
                        "canonical_version": canonical_version,
                        "transaction_ref": transaction_ref,
                        "source_type": source_type,
                        "source_event_id": source_event_id,
                        "event_timestamp": event_timestamp,
                        "recorded_at": datetime.now(timezone.utc).isoformat(),
                        "previous_hash": prev_hash,
                        "payload": payload,
                    }
                    if canonical_version == CANONICAL_VERSION_2_0:
                        event = normalize_canonical_data(event)
                    event["current_hash"] = self._hash_event(event, canonical_version=canonical_version)

                    self._events.append(event)
                    f.seek(0, 2)
                    f.write(json.dumps(event) + "\n")
                    f.flush()
                    os.fsync(f.fileno())
        else:
            prev_hash = self._events[-1]["current_hash"] if self._events else "genesis"
            event = {
                "event_id": str(uuid.uuid4()),
                "schema_version": self.SCHEMA_VERSION,
                "canonical_version": canonical_version,
                "transaction_ref": transaction_ref,
                "source_type": source_type,
                "source_event_id": source_event_id,
                "event_timestamp": event_timestamp,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "previous_hash": prev_hash,
                "payload": payload,
            }
            if canonical_version == CANONICAL_VERSION_2_0:
                event = normalize_canonical_data(event)
            event["current_hash"] = self._hash_event(event, canonical_version=canonical_version)
            self._events.append(event)

        return event

    def verify_chain(self) -> Tuple[bool, List[str]]:
        """
        Verify the SHA-256 hash chain:
        1. Every record's self-hash must match its canonical serialization.
        2. Event 0 must have previous_hash == 'genesis'.
        3. Every subsequent event i must have previous_hash == events[i-1]['current_hash'].
        """
        errors = []
        for i, event in enumerate(self._events):
            current_hash = event.get("current_hash")
            event_without_hash = {k: v for k, v in event.items() if k != "current_hash"}
            computed = self._hash_event(event_without_hash, canonical_version=event.get("canonical_version"))
            if computed != current_hash:
                errors.append(
                    f"Event {i} ({event.get('event_id')}): hash mismatch — record may have been altered."
                )
            if i == 0:
                if event.get("previous_hash") != "genesis":
                    errors.append(
                        f"Event 0 ({event.get('event_id')}): genesis record previous_hash is '{event.get('previous_hash')}', expected 'genesis'."
                    )
            else:
                expected_prev = self._events[i - 1].get("current_hash")
                if event.get("previous_hash") != expected_prev:
                    errors.append(
                        f"Event {i} ({event.get('event_id')}): broken hash chain link (points to '{event.get('previous_hash')}', expected '{expected_prev}')."
                    )

        is_valid = len(errors) == 0
        self._chain_valid = is_valid
        self._chain_errors = errors
        return is_valid, errors

    @classmethod
    def reconstruct_v2_ledger(
        cls,
        source_log_path: str,
        target_log_path: str,
        provenance_note: Optional[str] = None,
        key_id: Optional[str] = None,
        signing_key: Optional[str] = None,
    ) -> Tuple[EventLog, Dict[str, Any]]:
        """
        Explicit recovery mechanism:
        Re-chains historical records from a legacy or broken chain into a clean,
        continuous V2 hash chain artifact without modifying the source file.

        CRITICAL PROVENANCE LIMITATION:
        Re-chaining establishes a continuous cryptographic chain going forward,
        but does NOT cryptographically prove the historical ordering or original
        linkage of events prior to reconstruction.
        """
        source_p = Path(source_log_path)
        if not source_p.exists():
            raise FileNotFoundError(f"Source hash chain log '{source_log_path}' not found.")

        target_p = Path(target_log_path)
        target_p.parent.mkdir(parents=True, exist_ok=True)
        if target_p.exists():
            raise FileExistsError(
                f"Target V2 log '{target_log_path}' already exists. Overwrite prohibited to preserve evidence."
            )

        target_lock = f"{target_log_path}.lock"
        with persistent_ledger_lock(target_lock, shared=False):
            raw_events: List[Dict[str, Any]] = []
            with open(source_p, "r", encoding="utf-8") as f:
                for line_no, line in enumerate(f, start=1):
                    s = line.strip()
                    if not s:
                        continue
                    try:
                        evt = json.loads(s, object_pairs_hook=strict_json_pairs_hook)
                    except MalformedEventError:
                        raise
                    except Exception as e:
                        raise MalformedEventError(f"Line {line_no} in '{source_log_path}' is invalid JSON: {e}") from e
                    raw_events.append(evt)

            if not raw_events:
                raise ValueError(f"Source log '{source_log_path}' contains no events.")

            v2_events: List[Dict[str, Any]] = []
            reconstruction_ts = datetime.now(timezone.utc).isoformat()
            seen_event_ids = set()

            for idx, orig in enumerate(raw_events):
                eid = orig.get("event_id")
                if eid in seen_event_ids:
                    raise MalformedEventError(
                        f"Duplicate event_id '{eid}' detected in source ledger at record {idx}. "
                        "Migration aborted to prevent replay corruption."
                    )
                seen_event_ids.add(eid)

                prev_hash = "genesis" if idx == 0 else v2_events[idx - 1]["current_hash"]
                v2_evt = {
                    "event_id": eid or str(uuid.uuid4()),
                    "schema_version": "2.0",
                    "transaction_ref": orig.get("transaction_ref", "unknown"),
                    "source_type": orig.get("source_type", "unknown"),
                    "source_event_id": orig.get("source_event_id", "unknown"),
                    "event_timestamp": orig.get("event_timestamp", reconstruction_ts),
                    "recorded_at": orig.get("recorded_at", reconstruction_ts),
                    "previous_hash": prev_hash,
                    "payload": orig.get("payload", {}),
                    "v2_migration": {
                        "original_hash": orig.get("current_hash"),
                        "original_previous_hash": orig.get("previous_hash"),
                        "migrated_at": reconstruction_ts,
                        "original_index": idx,
                        "provenance_note": provenance_note or "Automated V2 cryptographic re-chaining.",
                    },
                }
                blob = json.dumps(v2_evt, sort_keys=True, default=str).encode()
                v2_evt["current_hash"] = hashlib.sha256(blob).hexdigest()
                v2_events.append(v2_evt)

            with open(target_p, "w", encoding="utf-8") as f:
                for evt in v2_events:
                    f.write(json.dumps(evt) + "\n")
                f.flush()
                os.fsync(f.fileno())
            fsync_dir(target_p.parent)

            v2_log = cls(log_path=str(target_p))
            is_valid, errors = v2_log.verify_chain()

            metadata = {
                "source_log_path": str(source_p.resolve()),
                "target_log_path": str(target_p.resolve()),
                "total_events_migrated": len(v2_events),
                "migration_timestamp": reconstruction_ts,
                "v2_chain_valid": is_valid,
                "v2_errors": errors,
                "genesis_hash": v2_events[0]["current_hash"],
                "head_hash": v2_events[-1]["current_hash"],
                "provenance_disclaimer": (
                    "Reconstructed V2 chain creates sequential SHA-256 links from historical appearance order. "
                    "It establishes a verified continuous chain from this point forward, but cannot retroactively "
                    "guarantee the timing or absence of omitted events prior to reconstruction."
                ),
            }

            key = signing_key or os.getenv("PROOFLEDGER_SIGNING_KEY")
            effective_key_id = key_id or os.getenv("PROOFLEDGER_KEY_ID") or "v1-sandbox-202610"
            if key:
                metadata["signing"] = {
                    "key_id": effective_key_id,
                    "algorithm": "HMAC-SHA256",
                    "canonical_version": "1.0",
                    "signed_at": reconstruction_ts,
                }

            # Calculate immutable manifest digest and optional HMAC signature
            manifest_digest = hashlib.sha256(
                json.dumps(
                    {k: v for k, v in metadata.items() if k not in ("manifest_digest", "hmac_signature", "manifest_file")},
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            metadata["manifest_digest"] = manifest_digest

            if key:
                sig = hmac.new(
                    key.encode(),
                    manifest_digest.encode(),
                    hashlib.sha256,
                ).hexdigest()
                metadata["hmac_signature"] = sig

            # Persist migration provenance manifest alongside V2 artifact
            manifest_file = target_p.with_name(f"{target_p.name}.manifest.json")
            try:
                with open(manifest_file, "w", encoding="utf-8") as mf:
                    json.dump(metadata, mf, indent=2)
                    mf.flush()
                    os.fsync(mf.fileno())
                fsync_dir(manifest_file.parent)
                metadata["manifest_file"] = str(manifest_file.resolve())
            except Exception as ex:
                logger.warning(f"Could not write manifest file '{manifest_file}': {ex}")

            return v2_log, metadata

    @classmethod
    def recover_interrupted_write(
        cls,
        log_path: str,
        backup_corrupt: bool = True,
        lock_path: Optional[str] = None,
    ) -> Tuple[bool, str, int]:
        """
        Crash-recovery mechanism for interrupted or truncated trailing writes:
        1. Acquires exclusive lock on persistent .lock file (preventing inode decoupling).
        2. Safely verifies line-by-line structure.
        3. If trailing write is corrupt, securely creates .bak file (O_EXCL | O_NOFOLLOW | 0o600).
        4. Flushes, fsyncs backup file, and fsyncs parent directory.
        5. Writes valid lines to temp file with 0o600 permissions, flushes, and fsyncs temp file.
        6. Atomically replaces primary file via os.replace.
        7. fsyncs parent directory entry so replacement is durable.
        """
        p = Path(log_path)
        if not p.exists() or p.stat().st_size == 0:
            return False, "File does not exist or is empty.", 0

        lock_target = lock_path or f"{log_path}.lock"
        with persistent_ledger_lock(lock_target, shared=False):
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()

            lines = content.splitlines(keepends=True)
            if not lines:
                return False, "No lines present.", 0

            valid_lines = []
            trailing_is_corrupt = False
            corrupt_fragment = ""

            for i, line in enumerate(lines):
                s = line.strip()
                if not s:
                    continue
                try:
                    obj = json.loads(s, object_pairs_hook=strict_json_pairs_hook)
                    if isinstance(obj, dict) and all(k in obj for k in REQUIRED_EVENT_FIELDS):
                        valid_lines.append(line if line.endswith("\n") else line + "\n")
                    else:
                        if i == len(lines) - 1:
                            trailing_is_corrupt = True
                            corrupt_fragment = line
                        else:
                            return False, f"Internal corruption at line {i+1} (not trailing). Manual audit required.", len(valid_lines)
                except Exception:
                    if i == len(lines) - 1:
                        trailing_is_corrupt = True
                        corrupt_fragment = line
                    else:
                        return False, f"Internal corruption at line {i+1} (not trailing). Manual audit required.", len(valid_lines)

            if not trailing_is_corrupt:
                return False, "No trailing write corruption detected.", len(valid_lines)

            # Trailing corruption confirmed. Securely create backup
            if backup_corrupt and corrupt_fragment:
                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                bak_path = p.with_name(f"{p.name}.crash_recovery_{ts}_{uuid.uuid4().hex[:8]}.bak")
                bak_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
                bak_fd = os.open(str(bak_path), bak_flags, 0o600)
                try:
                    with os.fdopen(bak_fd, "w", encoding="utf-8") as bf:
                        bf.write(corrupt_fragment)
                        bf.flush()
                        os.fsync(bf.fileno())
                except Exception:
                    os.close(bak_fd)
                    raise
                fsync_dir(p.parent)

            # Atomic rewrite via temp file in same directory
            tmp_path = p.with_name(f".{p.name}.recovery_{uuid.uuid4().hex}.tmp")
            tmp_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            tmp_fd = os.open(str(tmp_path), tmp_flags, 0o600)
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as tf:
                    tf.writelines(valid_lines)
                    tf.flush()
                    os.fsync(tf.fileno())

                # Atomic POSIX rename replaces primary file without window of truncation
                os.replace(tmp_path, p)
                fsync_dir(p.parent)
                return True, f"Successfully recovered from interrupted write. Preserved {len(valid_lines)} valid records.", len(valid_lines)
            except Exception as ex:
                if tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except Exception:
                        pass
                raise ex

    @classmethod
    def verify_v2_manifest(
        cls,
        v2_log_path: str,
        manifest_path: Optional[str] = None,
        source_legacy_path: Optional[str] = None,
        signing_key: Optional[str] = None,
        signing_keys: Optional[Dict[str, str]] = None,
        min_event_count: Optional[int] = None,
        use_shared_lock: bool = False,
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Independent verification of V2 ledger, genesis hash, head hash, and manifest metadata:
        1. V2 Ledger file exists and all SHA-256 links form a valid, unbroken chain.
        2. Manifest file exists, is valid JSON, and contains immutable migration provenance.
        3. Manifest self-digest is cryptographically verified against tampering.
        4. HMAC digital signature is authenticated supporting key rotation (signing_keys dict).
        5. V2 Genesis hash matches manifest genesis_hash exactly.
        6. V2 Head hash matches manifest head_hash exactly.
        7. Total event count matches manifest total_events_migrated.
        8. Rollback prevention: verifies min_event_count constraint if specified.
        9. If source_legacy_path is provided, strictly verifies:
           - 1-to-1 sequential positional ordering (no reordering)
           - original_hash matches legacy current_hash
           - payload, transaction_ref, and source_event_id exact correspondence
        """
        def _run_verification() -> Tuple[bool, List[str], Dict[str, Any]]:
            errors = []
            v2_p = Path(v2_log_path)
            if not v2_p.exists():
                return False, [f"V2 ledger file '{v2_log_path}' not found."], {}

            m_path = Path(manifest_path) if manifest_path else Path(v2_log_path + ".manifest.json")
            if not m_path.exists():
                return False, [f"V2 manifest file '{m_path}' not found."], {}

            try:
                with open(m_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
            except Exception as e:
                return False, [f"Failed to parse V2 manifest: {e}"], {}

            # 1. Manifest self-digest integrity check
            computed_digest = None
            if "manifest_digest" in manifest:
                expected_digest = manifest["manifest_digest"]
                computed_digest = hashlib.sha256(
                    json.dumps(
                        {k: v for k, v in manifest.items() if k not in ("manifest_digest", "hmac_signature", "manifest_file")},
                        sort_keys=True,
                    ).encode()
                ).hexdigest()
                if computed_digest != expected_digest:
                    errors.append(
                        f"Manifest digest mismatch: computed '{computed_digest}' != expected '{expected_digest}'. Manifest has been altered."
                    )

            # 2. HMAC signature verification with key rotation support
            key_id = manifest.get("signing", {}).get("key_id")
            key = None
            if signing_keys and key_id and key_id in signing_keys:
                key = signing_keys[key_id]
            elif signing_key:
                key = signing_key
            else:
                key = (
                    (os.getenv(f"PROOFLEDGER_SIGNING_KEY_{key_id}") if key_id else None)
                    or os.getenv("PROOFLEDGER_SIGNING_KEY")
                )

            if "hmac_signature" in manifest:
                if not key and (signing_keys is not None or signing_key is not None):
                    errors.append(f"Key ID '{key_id}' not found in key ring and no valid key provided.")
                elif key:
                    expected_sig = manifest["hmac_signature"]
                    target_digest = manifest.get("manifest_digest") or computed_digest or ""
                    computed_sig = hmac.new(
                        key.encode() if isinstance(key, str) else key,
                        target_digest.encode(),
                        hashlib.sha256,
                    ).hexdigest()
                    if not hmac.compare_digest(computed_sig, expected_sig):
                        errors.append("Manifest HMAC cryptographic signature verification failed. Untrusted manifest.")
            elif (signing_key or signing_keys) and "hmac_signature" not in manifest:
                errors.append("Signing key provided but manifest contains no HMAC signature.")

            # 3. V2 chain cryptographic verification
            v2_log = cls(log_path=str(v2_p))
            v2_valid, chain_errors = v2_log.verify_chain()
            if not v2_valid:
                errors.extend([f"V2 chain verification failed: {err}" for err in chain_errors])

            if not v2_log.events:
                errors.append("V2 ledger is empty.")
                return False, errors, manifest

            expected_count = manifest.get("total_events_migrated")
            if expected_count is not None and len(v2_log.events) != expected_count:
                errors.append(f"Event count mismatch: ledger has {len(v2_log.events)}, manifest expects {expected_count}")

            # Rollback check
            if min_event_count is not None and len(v2_log.events) < min_event_count:
                errors.append(
                    f"Manifest rollback detected: ledger event count ({len(v2_log.events)}) is less than required minimum ({min_event_count})"
                )

            expected_genesis = manifest.get("genesis_hash")
            actual_genesis = v2_log.events[0].get("current_hash")
            if expected_genesis and actual_genesis != expected_genesis:
                errors.append(f"Genesis hash mismatch: actual '{actual_genesis}' != manifest '{expected_genesis}'")

            expected_head = manifest.get("head_hash")
            actual_head = v2_log.events[-1].get("current_hash")
            if expected_head and actual_head != expected_head:
                errors.append(f"Head hash mismatch: actual '{actual_head}' != manifest '{expected_head}'")

            # 4. Strict sequential provenance cross-check against legacy source
            legacy_matched = False
            if source_legacy_path:
                leg_p = Path(source_legacy_path)
                if leg_p.exists():
                    legacy_events = []
                    with open(leg_p, "r", encoding="utf-8") as lf:
                        for line in lf:
                            if line.strip():
                                legacy_events.append(json.loads(line))
                    if len(legacy_events) != len(v2_log.events):
                        errors.append(f"Legacy record count ({len(legacy_events)}) != V2 count ({len(v2_log.events)})")
                    else:
                        legacy_matched = True
                        for idx, (leg_ev, v2_ev) in enumerate(zip(legacy_events, v2_log.events)):
                            v2_mig = v2_ev.get("v2_migration", {})
                            if v2_mig.get("original_index") != idx:
                                errors.append(
                                    f"Record {idx} positional order violation: V2 original_index '{v2_mig.get('original_index')}' != {idx}"
                                )
                                legacy_matched = False
                            if v2_mig.get("original_hash") != leg_ev.get("current_hash"):
                                errors.append(
                                    f"Record {idx} migration hash mismatch: V2 original_hash '{v2_mig.get('original_hash')}' != legacy '{leg_ev.get('current_hash')}'"
                                )
                                legacy_matched = False
                            if v2_ev.get("source_event_id") != leg_ev.get("source_event_id"):
                                errors.append(
                                    f"Record {idx} source_event_id mismatch: '{v2_ev.get('source_event_id')}' != legacy '{leg_ev.get('source_event_id')}'"
                                )
                                legacy_matched = False
                            if v2_ev.get("transaction_ref") != leg_ev.get("transaction_ref"):
                                errors.append(
                                    f"Record {idx} transaction_ref mismatch: '{v2_ev.get('transaction_ref')}' != legacy '{leg_ev.get('transaction_ref')}'"
                                )
                                legacy_matched = False
                            if v2_ev.get("payload") != leg_ev.get("payload"):
                                errors.append(
                                    f"Record {idx} payload mismatch: '{v2_ev.get('payload')}' != legacy '{leg_ev.get('payload')}'"
                                )
                                legacy_matched = False

            audit_report = {
                "v2_log_path": str(v2_p.resolve()),
                "manifest_path": str(m_path.resolve()),
                "manifest_total_events": expected_count,
                "actual_total_events": len(v2_log.events),
                "manifest_genesis_hash": expected_genesis,
                "actual_genesis_hash": actual_genesis,
                "manifest_head_hash": expected_head,
                "actual_head_hash": actual_head,
                "v2_chain_valid": v2_valid,
                "legacy_source_crosschecked": bool(source_legacy_path),
                "legacy_records_matched": legacy_matched,
                "provenance_disclaimer": manifest.get("provenance_disclaimer"),
            }
            return len(errors) == 0, errors, audit_report

        if use_shared_lock:
            with persistent_ledger_lock(f"{v2_log_path}.lock", shared=True):
                return _run_verification()
        return _run_verification()

    @classmethod
    def create_external_checkpoint(
        cls,
        ledger_path: str,
        checkpoint_path: str,
        signing_key: Optional[str] = None,
        key_id: Optional[str] = "checkpoint-key-v1",
    ) -> Dict[str, Any]:
        """
        Export an external integrity checkpoint anchored outside the ledger directory.
        Protects against coordinated replacement of both ledger and local manifest.
        """
        p = Path(ledger_path)
        log = cls(log_path=str(p))
        is_valid, errors = log.verify_chain()
        if not is_valid:
            raise ChainIntegrityError(f"Cannot checkpoint invalid chain: {errors}")

        total_events = len(log.events)
        head_hash = log.events[-1]["current_hash"] if total_events > 0 else "genesis"
        genesis_hash = log.events[0]["current_hash"] if total_events > 0 else "genesis"

        checkpoint_data = {
            "ledger_path": str(p.resolve()),
            "total_events": total_events,
            "head_hash": head_hash,
            "genesis_hash": genesis_hash,
            "checkpoint_timestamp": datetime.now(timezone.utc).isoformat(),
            "signing": {
                "key_id": key_id,
                "algorithm": "HMAC-SHA256",
            },
        }
        digest = hashlib.sha256(
            json.dumps({k: v for k, v in checkpoint_data.items() if k != "hmac_signature"}, sort_keys=True).encode()
        ).hexdigest()
        checkpoint_data["checkpoint_digest"] = digest

        key = signing_key or os.getenv("PROOFLEDGER_SIGNING_KEY")
        if key:
            checkpoint_data["hmac_signature"] = hmac.new(key.encode(), digest.encode(), hashlib.sha256).hexdigest()

        cp_p = Path(checkpoint_path)
        cp_p.parent.mkdir(parents=True, exist_ok=True)
        with open(cp_p, "w", encoding="utf-8") as f:
            json.dump(checkpoint_data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        fsync_dir(cp_p.parent)
        return checkpoint_data

    @classmethod
    def verify_external_checkpoint(
        cls,
        ledger_path: str,
        checkpoint_path: str,
        signing_key: Optional[str] = None,
        signing_keys: Optional[Dict[str, str]] = None,
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Verify ledger against independently anchored external checkpoint.
        Detects coordinated replacement or rollback of the ledger.
        """
        errors = []
        cp_p = Path(checkpoint_path)
        if not cp_p.exists():
            return False, [f"Checkpoint file '{checkpoint_path}' not found."], {}

        with open(cp_p, "r", encoding="utf-8") as f:
            cp = json.load(f)

        # 1. Verify checkpoint digest
        digest = hashlib.sha256(
            json.dumps({k: v for k, v in cp.items() if k not in ("checkpoint_digest", "hmac_signature")}, sort_keys=True).encode()
        ).hexdigest()
        if digest != cp.get("checkpoint_digest"):
            errors.append(f"Checkpoint digest mismatch: checkpoint file '{checkpoint_path}' has been tampered with.")

        # 2. Verify signature if present
        key_id = cp.get("signing", {}).get("key_id")
        key = None
        if signing_keys and key_id and key_id in signing_keys:
            key = signing_keys[key_id]
        elif signing_key:
            key = signing_key
        else:
            key = os.getenv("PROOFLEDGER_SIGNING_KEY")

        if "hmac_signature" in cp:
            if not key:
                errors.append("Checkpoint HMAC signature verification failed: no HMAC verification key provided.")
            else:
                expected_sig = hmac.new(key.encode(), digest.encode(), hashlib.sha256).hexdigest()
                if not hmac.compare_digest(expected_sig, cp["hmac_signature"]):
                    errors.append("Checkpoint HMAC signature verification failed.")

        # 3. Check against current ledger
        log = cls(log_path=ledger_path)
        is_valid, chain_errs = log.verify_chain()
        if not is_valid:
            errors.extend(chain_errs)

        if len(log.events) < cp.get("total_events", 0):
            errors.append(
                f"Ledger rollback detected: ledger has {len(log.events)} events, but checkpoint requires at least {cp.get('total_events')}."
            )
        elif cp.get("total_events", 0) > 0:
            target_idx = cp["total_events"] - 1
            if target_idx < len(log.events):
                actual_hash_at_checkpoint = log.events[target_idx]["current_hash"]
                if actual_hash_at_checkpoint != cp.get("head_hash"):
                    errors.append(
                        f"Ledger content discrepancy at checkpoint height {cp['total_events']}: "
                        f"ledger hash '{actual_hash_at_checkpoint}' != checkpoint head_hash '{cp.get('head_hash')}'."
                    )

        return len(errors) == 0, errors, cp

    @property
    def is_valid(self) -> bool:
        return self._chain_valid

    @property
    def chain_errors(self) -> List[str]:
        return list(self._chain_errors)

    @property
    def events(self) -> List[Dict[str, Any]]:
        return list(self._events)


# ---------------------------------------------------------------------------
# Evidence Compiler
# ---------------------------------------------------------------------------

class EvidenceCompiler:
    """
    Orchestrates the full claim verification pipeline.

    The compiler never asserts that a source record exists unless it
    actually exists in the provided evidence. It never generates evidence IDs
    not present in the input.
    """

    def __init__(
        self,
        verifier: Optional[EvidenceVerifier] = None,
        log_path: Optional[str] = None,
        allow_broken_chain: bool = False,
    ):
        self._verifier = verifier
        self._validator = DeterministicValidator()
        self._log = EventLog(log_path=log_path, allow_broken_chain=allow_broken_chain)

    def compile(
        self,
        claim: str,
        evidence: List[Dict[str, Any]],
        transaction_reference: Optional[str] = None,
        claimed_recipient: Optional[str] = None,
        require_human_review: bool = True,
    ) -> Dict[str, Any]:
        """
        Run the complete evidence compilation flow.

        Returns a structured evidence-readiness report.
        Does NOT automatically approve or submit anything.
        """
        compilation_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc).isoformat()

        # Step 1: Validate evidence structure
        structure_errors = self._validate_structure(evidence)

        # Step 2: Log evidence events
        for ev in evidence:
            self._log.append(
                transaction_ref=transaction_reference or "unknown",
                source_type=ev.get("source_type", "unknown"),
                source_event_id=ev.get("evidence_id", "unknown"),
                event_timestamp=ev.get("timestamp") or started_at,
                payload={"content_length": len(ev.get("content", ""))},
            )

        # Step 3: Deterministic checks
        det_label, det_checks = self._validator.run_all(
            claim=claim,
            evidence=evidence,
            order_id=transaction_reference,
            claimed_recipient=claimed_recipient,
        )

        # Step 4: ML model prediction (if available)
        ml_result = None
        ml_label = None
        ml_available = self._verifier is not None and self._verifier.is_loaded

        if ml_available:
            ev_records = [
                EvidenceRecord(
                    evidence_id=ev.get("evidence_id", f"ev_{i}"),
                    source_type=ev.get("source_type", "unknown"),
                    timestamp=ev.get("timestamp"),
                    content=ev.get("content", ""),
                )
                for i, ev in enumerate(evidence)
            ]
            try:
                ml_result = self._verifier.predict(claim, ev_records)
                ml_label = ml_result["label"]
            except Exception as e:
                logger.error(f"Model prediction failed: {e}")
                ml_result = {"error": str(e)}

        # Step 5: Compare rule vs. model
        disagreement = (ml_label is not None) and (ml_label != det_label.value)
        if disagreement:
            logger.warning(
                f"Rule ({det_label.value}) ≠ Model ({ml_label}) for claim: {claim[:80]}..."
            )

        # Step 6: Determine overall label and readiness
        # Guard: If deterministic validator detected source linkage failure, override model contradiction to INSUFFICIENT_EVIDENCE
        has_source_mismatch = any(c.get("check") == "source_mismatch_detected" and c.get("passed") is True for c in det_checks)
        if has_source_mismatch:
            final_label = AppLabel.INSUFFICIENT_EVIDENCE.value
        elif ml_label:
            final_label = ml_label
        else:
            final_label = det_label.value

        # Evidence readiness assessment
        readiness_issues = []
        if not evidence:
            readiness_issues.append("No evidence records provided.")
        if structure_errors:
            readiness_issues.extend(structure_errors)
        if has_source_mismatch:
            readiness_issues.append("Evidence transaction linkage failure: records belong to an unrelated transaction.")
        elif final_label == AppLabel.CONTRADICTED.value:
            readiness_issues.append("Evidence contradicts the claim — do not submit as-is.")
        if final_label == AppLabel.INSUFFICIENT_EVIDENCE.value and not has_source_mismatch:
            readiness_issues.append("Insufficient evidence to support the claim.")
        if disagreement:
            readiness_issues.append(
                f"Rule-based and ML predictions disagree ({det_label.value} vs {ml_label}). "
                "Requires human review."
            )
        if ml_result and ml_result.get("truncated"):
            readiness_issues.append(ml_result.get("truncation_warning", "Evidence was truncated."))

        # Recommendation
        if final_label == AppLabel.SUPPORTED.value and not readiness_issues:
            recommendation = "Claim appears supported. Proceed to human review before submission."
        elif final_label == AppLabel.CONTRADICTED.value:
            recommendation = "Remove or correct the contradicted claim. Do not submit."
        else:
            recommendation = "Obtain additional evidence before submission. Claim is not sufficiently supported."

        # Chain integrity check
        chain_valid, chain_errors = self._log.verify_chain()

        report = {
            "compilation_id": compilation_id,
            "compiled_at": started_at,
            "transaction_reference": transaction_reference,
            "claim": claim,
            "final_label": final_label,
            "deterministic_label": det_label.value,
            "model_label": ml_label,
            "model_available": ml_available,
            "rule_model_disagreement": disagreement,
            "deterministic_checks": det_checks,
            "model_result": {
                k: v for k, v in (ml_result or {}).items()
                if k not in ("nli_scores",)  # omit internal details
            } if ml_result else None,
            "evidence_count": len(evidence),
            "structure_errors": structure_errors,
            "readiness_issues": readiness_issues,
            "evidence_readiness": "READY" if (not readiness_issues and final_label == AppLabel.SUPPORTED.value) else "NOT_READY",
            "recommendation": recommendation,
            "human_review_required": True,  # Always required
            "human_approved": False,  # Never auto-approved
            "event_log_entries": len(self._log.events),
            "event_chain_valid": chain_valid,
            "event_chain_errors": chain_errors,
            "limitations": [
                "AI predictions are based on synthetic training data.",
                "System does not determine PayPal Seller Protection eligibility.",
                "Human approval required before any submission.",
                "Hash chain reveals tampering but does not prove original event truth.",
            ],
        }
        return report

    def _validate_structure(self, evidence: List[Dict[str, Any]]) -> List[str]:
        errors = []
        seen_ids = set()
        for i, ev in enumerate(evidence):
            if "evidence_id" not in ev:
                errors.append(f"Record {i}: missing evidence_id.")
            else:
                if ev["evidence_id"] in seen_ids:
                    errors.append(f"Record {i}: duplicate evidence_id '{ev['evidence_id']}'.")
                seen_ids.add(ev["evidence_id"])
            if not ev.get("content", "").strip():
                errors.append(f"Record {i}: empty content.")
            if "source_type" not in ev:
                errors.append(f"Record {i}: missing source_type.")
        return errors

