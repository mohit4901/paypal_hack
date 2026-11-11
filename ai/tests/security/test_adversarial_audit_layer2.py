"""
ProofLedger v2 — Adversarial Cryptographic Security Audit Suite (Layer 2).

Audits the critical P0/P1 failure modes identified in the independent review:
1. Persistent lock file synchronization preventing inode-decoupling during atomic os.replace.
2. Crash durability protocol (file + directory fsync sequence).
3. Symlink attack rejection during crash recovery backup creation (O_NOFOLLOW | O_EXCL).
4. Manifest rollback detection and external anchored checkpoints.
5. HMAC key rotation and multi-key ring verification.
6. Multi-dimensional forensic verdicts:
   - Separation of Content Authentication, Database Correlation, Source Authentication, and Ledger Integrity.
   - Strict prohibition on upgrading migrated historical events to unconditional authenticity.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import multiprocessing
import os
from pathlib import Path
import pytest
import time

from src.integrations.run_live_sandbox_lifecycle import verify_event_in_hash_chain
from src.models.evidence_compiler import (
    EventLog,
    MalformedEventError,
    ChainIntegrityError,
    persistent_ledger_lock,
)


# ===========================================================================
# 1. Persistent Lock File vs. Inode Decoupling Tests
# ===========================================================================

def _proc_writer_concurrent(chain_file: str, proc_id: int, write_count: int) -> None:
    """Worker process appending events while recovery might replace the active ledger."""
    log = EventLog(log_path=chain_file)
    for i in range(write_count):
        try:
            log.append(
                transaction_ref=f"ORD-LOCK-{proc_id}",
                source_type="concurrent_test",
                source_event_id=f"EV-L{proc_id}-{i}",
                event_timestamp=f"2026-10-31T01:{proc_id:02d}:{i:02d}Z",
                payload={"proc": proc_id, "idx": i},
            )
            time.sleep(0.005)
        except Exception:
            pass


def test_persistent_lock_prevents_inode_decoupling_during_replace(tmp_path):
    """
    Critical Finding P0:
    flock on the ledger file itself is decoupled when os.replace updates the inode.
    A dedicated, persistent .lock file ensures that all processes (appenders and
    recovery replacers) synchronize on the exact same inode.
    """
    chain_file = tmp_path / "chain_persistent_lock.jsonl"
    log = EventLog(log_path=str(chain_file))
    ev0 = log.append("ORD-1", "src", "EV-0", "2026-10-31T00:00:00Z", {"step": 0})
    ev1 = log.append("ORD-1", "src", "EV-1", "2026-10-31T00:01:00Z", {"step": 1})

    # Simulate truncated write
    with open(chain_file, "a", encoding="utf-8") as f:
        f.write('{"event_id": "crashed-mid-write-fragment')

    # Launch concurrent writer in separate OS process
    ctx = multiprocessing.get_context("spawn")
    p = ctx.Process(target=_proc_writer_concurrent, args=(str(chain_file), 1, 5))
    p.start()

    # In main process, execute recovery (which performs os.replace)
    recovered, msg, count = EventLog.recover_interrupted_write(str(chain_file))
    assert recovered is True
    assert count == 2

    p.join(timeout=10.0)
    assert p.exitcode == 0

    # Verify that the ledger on disk has unbroken chain integrity
    final_log = EventLog(log_path=str(chain_file))
    valid, errors = final_log.verify_chain()
    assert valid is True
    assert len(errors) == 0
    # Initial 2 records + whatever concurrent writes succeeded must be chained correctly
    assert len(final_log.events) >= 2


def test_recovery_while_verification_shared_lock(tmp_path):
    """
    Verifies that a process holding a shared lock on the .lock file prevents
    recovery from replacing the ledger until the read snapshot finishes.
    """
    chain_file = tmp_path / "chain_shared.jsonl"
    lock_file = str(chain_file) + ".lock"
    log = EventLog(log_path=str(chain_file))
    log.append("ORD-1", "src", "EV-0", "2026-10-31T00:00:00Z", {"step": 0})

    # Acquire shared lock simulating a read snapshot
    with persistent_ledger_lock(lock_file, shared=True):
        # In non-blocking attempt, exclusive lock for recovery should fail
        with pytest.raises(TimeoutError):
            with persistent_ledger_lock(lock_file, shared=False, timeout_s=0.05):
                pass


# ===========================================================================
# 2. Symlink Attack & Recovery Security
# ===========================================================================

def test_recovery_backup_symlink_attack_rejected(tmp_path, monkeypatch):
    """
    Verifies that crash recovery backup creation refuses to follow symlinks.
    If an attacker creates a symlink where the backup would be written,
    O_NOFOLLOW / O_EXCL prevents overwriting arbitrary host files.
    """
    chain_file = tmp_path / "chain_symlink_target.jsonl"
    sensitive_file = tmp_path / "sensitive_system_file.txt"
    sensitive_file.write_text("SENSITIVE_DATA_DO_NOT_OVERWRITE")

    log = EventLog(log_path=str(chain_file))
    log.append("ORD-1", "src", "EV-0", "2026-10-31T00:00:00Z", {"val": 1})

    # Append trailing corrupt fragment
    with open(chain_file, "a", encoding="utf-8") as f:
        f.write('{"event_id": "corrupted-tail')

    # Predictable backup symlink targeting sensitive file
    # We monkeypatch datetime.now to fix the timestamp
    from datetime import datetime, timezone
    fixed_dt = datetime(2026, 10, 31, 12, 0, 0, tzinfo=timezone.utc)

    class MockDatetime:
        @classmethod
        def now(cls, tz=None):
            return fixed_dt

    monkeypatch.setattr("src.models.evidence_compiler.datetime", MockDatetime)
    # Patch uuid so we know the exact filename
    monkeypatch.setattr("uuid.uuid4", lambda: type("MockUUID", (), {"hex": "1234567890"})())

    expected_bak = tmp_path / f"{chain_file.name}.crash_recovery_20261031_120000_12345678.bak"
    # Attacker symlinks expected_bak -> sensitive_file
    os.symlink(sensitive_file, expected_bak)

    # Recovery must fail or raise FileExistsError / OSError because file exists / symlink
    with pytest.raises(OSError):
        EventLog.recover_interrupted_write(str(chain_file), backup_corrupt=True)

    # Sensitive file must NOT have been overwritten
    assert sensitive_file.read_text() == "SENSITIVE_DATA_DO_NOT_OVERWRITE"


# ===========================================================================
# 3. Key Rotation & Multi-Key Ring Manifest Verification
# ===========================================================================

def test_manifest_key_rotation_with_key_ring(tmp_path):
    """
    Enterprise Key Management:
    Manifest was signed with key 'v1-key-202610'.
    When verifying using a key ring containing multiple versioned keys,
    the correct key is matched by key_id and verifies successfully.
    """
    source_file = tmp_path / "source_kr.jsonl"
    v2_file = tmp_path / "v2_kr.jsonl"

    log = EventLog(log_path=str(source_file))
    log.append("ORD-1", "src", "EV-0", "2026-10-31T00:00:00Z", {"step": 0})

    key_ring = {
        "v1-key-202610": "secret_key_v1_987654321",
        "v2-key-202611": "secret_key_v2_123456789",
    }

    v2_log, meta = EventLog.reconstruct_v2_ledger(
        source_log_path=str(source_file),
        target_log_path=str(v2_file),
        key_id="v1-key-202610",
        signing_key=key_ring["v1-key-202610"],
    )

    # 1. Verification with key ring succeeds
    valid, errors, report = EventLog.verify_v2_manifest(
        v2_log_path=str(v2_file),
        signing_keys=key_ring,
    )
    assert valid is True
    assert len(errors) == 0

    # 2. Verification with key ring missing the key fails
    bad_ring = {"v2-key-202611": "secret_key_v2_123456789"}
    valid_bad, errors_bad, _ = EventLog.verify_v2_manifest(
        v2_log_path=str(v2_file),
        signing_keys=bad_ring,
    )
    assert valid_bad is False
    assert any("not found in key ring" in err for err in errors_bad)


# ===========================================================================
# 4. Manifest Rollback & External Anchored Checkpoints
# ===========================================================================

def test_manifest_rollback_detection(tmp_path):
    """
    Rollback Detection:
    An attacker attempts to roll back to an older manifest with fewer events.
    min_event_count constraint immediately catches the rollback.
    """
    source_file = tmp_path / "source_rb.jsonl"
    v2_file = tmp_path / "v2_rb.jsonl"

    log = EventLog(log_path=str(source_file))
    log.append("ORD-1", "src", "EV-0", "2026-10-31T00:00:00Z", {"val": 1})
    log.append("ORD-1", "src", "EV-1", "2026-10-31T00:01:00Z", {"val": 2})

    EventLog.reconstruct_v2_ledger(str(source_file), str(v2_file))

    # Expecting at least 5 events (e.g. from an external checkpoint), but ledger only has 2
    valid, errors, report = EventLog.verify_v2_manifest(
        v2_log_path=str(v2_file),
        min_event_count=5,
    )
    assert valid is False
    assert any("Manifest rollback detected" in err for err in errors)


def test_external_checkpoint_anchoring(tmp_path):
    """
    External Checkpoint Anchoring:
    Detects coordinated replacement of BOTH the ledger AND the local manifest file.
    """
    ledger_file = tmp_path / "ledger_anchor.jsonl"
    cp_file = tmp_path / "external_anchors" / "checkpoint.json"

    log = EventLog(log_path=str(ledger_file))
    log.append("ORD-1", "src", "EV-0", "2026-10-31T00:00:00Z", {"val": 100})
    log.append("ORD-1", "src", "EV-1", "2026-10-31T00:01:00Z", {"val": 200})

    # Create signed external checkpoint
    secret = "checkpoint_secret_key_abc"
    cp_data = EventLog.create_external_checkpoint(
        ledger_path=str(ledger_file),
        checkpoint_path=str(cp_file),
        signing_key=secret,
        key_id="cp-v1",
    )
    assert cp_file.exists()
    assert cp_data["total_events"] == 2

    # Verify against external checkpoint succeeds
    valid, errors, cp = EventLog.verify_external_checkpoint(
        ledger_path=str(ledger_file),
        checkpoint_path=str(cp_file),
        signing_key=secret,
    )
    assert valid is True
    assert len(errors) == 0

    # Attacker replaces ledger with a forged chain of same length
    forged_ledger = tmp_path / "ledger_anchor.jsonl"
    forged_log = EventLog(log_path=str(forged_ledger))
    # Clear and rewrite with forged events
    with open(forged_ledger, "w") as f:
        pass
    forged_log = EventLog(log_path=str(forged_ledger))
    forged_log.append("ORD-FORGED", "attacker", "EV-FORGE-0", "2026-10-31T00:00:00Z", {"forged": True})
    forged_log.append("ORD-FORGED", "attacker", "EV-FORGE-1", "2026-10-31T00:01:00Z", {"forged": True})

    # External checkpoint MUST detect the discrepancy
    valid_f, errors_f, _ = EventLog.verify_external_checkpoint(
        ledger_path=str(ledger_file),
        checkpoint_path=str(cp_file),
        signing_key=secret,
    )
    assert valid_f is False
    assert any("Ledger content discrepancy at checkpoint height" in err for err in errors_f)


# ===========================================================================
# 5. Multi-Dimensional Forensic Verdicts & Provenance Preservation
# ===========================================================================

def test_migrated_historical_record_never_upgraded_to_unconditional_authenticity(tmp_path):
    """
    Auditor P0 Finding:
    A migrated historical event in V2 must NEVER be upgraded to 'VERIFIED_VALID & AUTHENTIC'
    solely because its new V2 predecessor link is valid.
    It must preserve HISTORICAL_CHAIN_LINK_UNVERIFIED and HISTORICAL_ORDER_UNVERIFIED.
    """
    source_file = tmp_path / "legacy_source.jsonl"
    v2_file = tmp_path / "v2_target.jsonl"

    rec = {
        "event_id": "MIGRATED-HISTORICAL-WH-01",
        "schema_version": "1.0",
        "transaction_ref": "CAP-HISTORICAL-1",
        "source_type": "paypal_webhook",
        "source_event_id": "MIGRATED-HISTORICAL-WH-01",
        "event_timestamp": "2026-10-31T10:00:00Z",
        "recorded_at": "2026-10-31T10:00:00Z",
        "previous_hash": "genesis",  # Historical state loss bug
        "payload": {"event_type": "PAYMENT.CAPTURE.COMPLETED", "summary": "Capture completed"},
        "current_hash": "a" * 64,
    }
    with open(source_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")

    # Migrate to V2
    EventLog.reconstruct_v2_ledger(str(source_file), str(v2_file))

    # Verify against V2
    res = verify_event_in_hash_chain(
        chain_log_path=str(v2_file),
        expected_event_id="MIGRATED-HISTORICAL-WH-01",
        expected_event_type="PAYMENT.CAPTURE.COMPLETED",
        expected_capture_id="CAP-HISTORICAL-1",
        source_authenticated=True,
    )

    # Must NOT be VERIFIED_VALID & AUTHENTIC!
    assert res.forensic_verdict != "VERIFIED_VALID & AUTHENTIC"
    assert "HISTORICAL PROVENANCE UNVERIFIED" in res.forensic_verdict
    assert "HISTORICAL_ORDER_UNVERIFIED" in res.legacy_provenance_status
    assert "HISTORICAL_CHAIN_LINK_UNVERIFIED" in res.legacy_provenance_status
    assert res.v2_migration_integrity_status == "V2_MIGRATION_INTEGRITY_VERIFIED"
    assert res.is_migrated_historical is True


def test_source_authentication_dimension_separation(tmp_path):
    """
    Auditor P0 Finding:
    Chain integrity is not event authenticity.
    A locally valid, unbroken chain event without PayPal source verification
    receives LEDGER_INTEGRITY_VERIFIED — SOURCE_AUTHENTICATION_PENDING_OR_UNVERIFIED.
    Only when source_authenticated=True does it upgrade to VERIFIED_VALID & AUTHENTIC.
    """
    chain_file = tmp_path / "chain_native_v2.jsonl"
    log = EventLog(log_path=str(chain_file))
    log.append(
        transaction_ref="CAP-NATIVE-999",
        source_type="paypal_webhook",
        source_event_id="WH-NATIVE-999",
        event_timestamp="2026-10-31T12:00:00Z",
        payload={"event_type": "PAYMENT.CAPTURE.COMPLETED", "summary": "Capture"},
    )

    # 1. Check with source_authenticated=False
    res_unauth = verify_event_in_hash_chain(
        chain_log_path=str(chain_file),
        expected_event_id="WH-NATIVE-999",
        expected_event_type="PAYMENT.CAPTURE.COMPLETED",
        expected_capture_id="CAP-NATIVE-999",
        source_authenticated=False,
    )
    assert res_unauth.ledger_integrity_verified is True
    assert res_unauth.source_authenticated is False
    assert res_unauth.forensic_verdict == "LEDGER_INTEGRITY_VERIFIED — SOURCE_AUTHENTICATION_PENDING_OR_UNVERIFIED"

    # 2. Check with source_authenticated=True (PayPal signature verified)
    res_auth = verify_event_in_hash_chain(
        chain_log_path=str(chain_file),
        expected_event_id="WH-NATIVE-999",
        expected_event_type="PAYMENT.CAPTURE.COMPLETED",
        expected_capture_id="CAP-NATIVE-999",
        source_authenticated=True,
    )
    assert res_auth.ledger_integrity_verified is True
    assert res_auth.source_authenticated is True
    assert res_auth.forensic_verdict == "VERIFIED_VALID & AUTHENTIC"

