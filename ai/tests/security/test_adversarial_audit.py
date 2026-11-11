"""
ProofLedger v2 — Adversarial Cryptographic Security Audit Suite.

Subjecting the ProofLedger integrity architecture to deliberate adversarial attacks:
1. Crash recovery atomicity and rejection of non-trailing corruption.
2. Manifest tampering, digest verification, and HMAC signature forgery detection.
3. Migration record reordering, substitution, deletion, and duplicate ID attacks.
4. OS-level multiprocess lock contention and race prevention.
5. Fail-closed bootstrap posture and silent fallback prohibition.
6. SQLite / JSONL ledger disagreement and cross-correlation rejection.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import multiprocessing
import os
from pathlib import Path
import pytest

from src.integrations.run_live_sandbox_lifecycle import verify_event_in_hash_chain
from src.models.evidence_compiler import (
    ChainIntegrityError,
    EventLog,
    MalformedEventError,
)
from src.storage.db import (
    SilentFallbackProhibitedError,
    get_chain_log_path,
)


# ===========================================================================
# 1. Crash Recovery Atomicity & Scope Tests
# ===========================================================================

def test_adversarial_crash_recovery_atomic_replace(tmp_path):
    """
    Adversarial Scenario:
    Process crashes mid-write leaving a truncated, incomplete trailing line.
    Verification must prove:
    1. Recovery atomically truncates only the trailing corrupt fragment.
    2. Valid prior records remain completely intact and valid.
    3. Trailing corrupt bytes are backed up to a forensic .bak file.
    4. New appends immediately succeed and link to the last valid record.
    """
    chain_file = tmp_path / "chain_atomic_crash.jsonl"
    log = EventLog(log_path=str(chain_file))
    ev0 = log.append("ORD-1", "src", "EV-0", "2026-10-31T00:00:00Z", {"action": "create"})
    ev1 = log.append("ORD-1", "src", "EV-1", "2026-10-31T00:01:00Z", {"action": "approve"})

    # Simulate crash mid-write: half-written JSON line at EOF
    with open(chain_file, "a", encoding="utf-8") as f:
        f.write('{"event_id": "crashed-mid-write-uuid", "schema_version": "1.0", "transact')

    recovered, msg, valid_count = EventLog.recover_interrupted_write(str(chain_file), backup_corrupt=True)
    assert recovered is True
    assert valid_count == 2

    # Check that forensic backup was preserved
    bak_files = list(tmp_path.glob("*.bak"))
    assert len(bak_files) == 1
    assert "crashed-mid-write-uuid" in bak_files[0].read_text()

    # Reopen and continue appending
    clean_log = EventLog(log_path=str(chain_file))
    assert len(clean_log.events) == 2
    ev2 = clean_log.append("ORD-1", "src", "EV-2", "2026-10-31T00:02:00Z", {"action": "capture"})

    # Verify link: ev2 must link to ev1
    assert ev2["previous_hash"] == ev1["current_hash"]
    valid, errors = clean_log.verify_chain()
    assert valid is True
    assert len(errors) == 0


def test_adversarial_recovery_rejects_internal_line_corruption(tmp_path):
    """
    Adversarial Scenario:
    An attacker tampers with an internal record (line 1 of 3) rather than a trailing write.
    Crash recovery MUST REFUSE to truncate or auto-delete internal lines to prevent
    evidence destruction. It must require an explicit manual audit.
    """
    chain_file = tmp_path / "chain_internal_tamper.jsonl"
    log = EventLog(log_path=str(chain_file))
    log.append("ORD-1", "src", "EV-0", "2026-10-31T00:00:00Z", {"step": 0})
    log.append("ORD-1", "src", "EV-1", "2026-10-31T00:01:00Z", {"step": 1})
    log.append("ORD-1", "src", "EV-2", "2026-10-31T00:02:00Z", {"step": 2})

    # Tamper with internal line 1 (the middle record)
    with open(chain_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    lines[1] = "INTERNAL_CORRUPTED_LINE_ATTACK\n"
    with open(chain_file, "w", encoding="utf-8") as f:
        f.writelines(lines)

    recovered, msg, count = EventLog.recover_interrupted_write(str(chain_file))
    assert recovered is False
    assert "Internal corruption" in msg
    assert "Manual audit required" in msg


# ===========================================================================
# 2. Manifest Authenticity, Tampering & Signature Forgery Tests
# ===========================================================================

def test_adversarial_manifest_tampering_head_hash_rejected(tmp_path):
    """Adversarial Scenario: Attacker alters head_hash in manifest to hide later appends."""
    source_file = tmp_path / "source.jsonl"
    target_file = tmp_path / "v2.jsonl"

    log = EventLog(log_path=str(source_file))
    log.append("ORD-1", "src", "EV-0", "2026-10-31T00:00:00Z", {"val": 1})

    v2_log, meta = EventLog.reconstruct_v2_ledger(str(source_file), str(target_file))
    manifest_path = target_file.with_name(f"{target_file.name}.manifest.json")

    # Attacker alters head_hash
    with open(manifest_path, "r", encoding="utf-8") as mf:
        manifest_data = json.load(mf)
    manifest_data["head_hash"] = "forged_head_hash_00000000000000000000000000000000000000000"
    with open(manifest_path, "w", encoding="utf-8") as mf:
        json.dump(manifest_data, mf)

    is_valid, errors, report = EventLog.verify_v2_manifest(str(target_file))
    assert is_valid is False
    assert any("Head hash mismatch" in err or "Manifest digest mismatch" in err for err in errors)


def test_adversarial_manifest_tampering_event_count_rejected(tmp_path):
    """Adversarial Scenario: Attacker decrements total_events_migrated to hide historical events."""
    source_file = tmp_path / "source2.jsonl"
    target_file = tmp_path / "v2_2.jsonl"

    log = EventLog(log_path=str(source_file))
    log.append("ORD-1", "src", "EV-0", "2026-10-31T00:00:00Z", {"val": 1})
    log.append("ORD-1", "src", "EV-1", "2026-10-31T00:01:00Z", {"val": 2})

    v2_log, meta = EventLog.reconstruct_v2_ledger(str(source_file), str(target_file))
    manifest_path = target_file.with_name(f"{target_file.name}.manifest.json")

    # Attacker claims only 1 event was migrated
    with open(manifest_path, "r", encoding="utf-8") as mf:
        manifest_data = json.load(mf)
    manifest_data["total_events_migrated"] = 1
    with open(manifest_path, "w", encoding="utf-8") as mf:
        json.dump(manifest_data, mf)

    is_valid, errors, report = EventLog.verify_v2_manifest(str(target_file))
    assert is_valid is False
    assert any("Event count mismatch" in err or "Manifest digest mismatch" in err for err in errors)


def test_adversarial_manifest_hmac_signature_forgery_rejected(tmp_path, monkeypatch):
    """
    Adversarial Scenario:
    Manifest is signed with official key. Attacker tampers with manifest and
    either keeps old signature or tries to forge a signature with wrong key.
    """
    signing_key = "official_super_secret_signing_key_12345"
    monkeypatch.setenv("PROOFLEDGER_SIGNING_KEY", signing_key)

    source_file = tmp_path / "source_signed.jsonl"
    target_file = tmp_path / "v2_signed.jsonl"

    log = EventLog(log_path=str(source_file))
    log.append("ORD-1", "src", "EV-0", "2026-10-31T00:00:00Z", {"val": 1})

    v2_log, meta = EventLog.reconstruct_v2_ledger(str(source_file), str(target_file))
    manifest_path = target_file.with_name(f"{target_file.name}.manifest.json")

    # 1. Clean verification with authentic key MUST succeed
    is_valid, errors, report = EventLog.verify_v2_manifest(str(target_file), signing_key=signing_key)
    assert is_valid is True
    assert len(errors) == 0

    # 2. Attacker modifies disclaimer text
    with open(manifest_path, "r", encoding="utf-8") as mf:
        manifest_data = json.load(mf)
    manifest_data["provenance_disclaimer"] = "Tampered disclaimer without authorized key."
    with open(manifest_path, "w", encoding="utf-8") as mf:
        json.dump(manifest_data, mf)

    # Verification MUST fail due to HMAC signature failure
    is_valid_attack, errors_attack, _ = EventLog.verify_v2_manifest(str(target_file), signing_key=signing_key)
    assert is_valid_attack is False
    assert any("HMAC cryptographic signature verification failed" in err or "Manifest digest mismatch" in err for err in errors_attack)


# ===========================================================================
# 3. Migration Replay, Reordering & Substitution Attacks
# ===========================================================================

def test_adversarial_migration_rejects_duplicate_event_ids(tmp_path):
    """Adversarial Scenario: Source ledger contains duplicate event_id (replay attack)."""
    source_file = tmp_path / "source_dupe.jsonl"
    target_file = tmp_path / "v2_dupe.jsonl"

    rec1 = {
        "event_id": "DUPLICATE-UUID-123",
        "schema_version": "1.0",
        "transaction_ref": "ORD-1",
        "source_type": "src",
        "source_event_id": "EV-1",
        "event_timestamp": "2026-10-31T00:00:00Z",
        "recorded_at": "2026-10-31T00:00:00Z",
        "previous_hash": "genesis",
        "payload": {"val": 1},
        "current_hash": "a" * 64,
    }
    rec2 = dict(rec1)  # Exact duplicate event_id
    rec2["transaction_ref"] = "ORD-2"

    with open(source_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(rec1) + "\n")
        f.write(json.dumps(rec2) + "\n")

    with pytest.raises(MalformedEventError) as exc:
        EventLog.reconstruct_v2_ledger(str(source_file), str(target_file))
    assert "Duplicate event_id 'DUPLICATE-UUID-123'" in str(exc.value)


def test_adversarial_migration_detects_reordered_records(tmp_path):
    """Adversarial Scenario: V2 records were reordered after migration."""
    source_file = tmp_path / "source_reorder.jsonl"
    target_file = tmp_path / "v2_reorder.jsonl"

    log = EventLog(log_path=str(source_file))
    log.append("ORD-1", "src", "EV-A", "2026-10-31T00:00:00Z", {"val": "A"})
    log.append("ORD-1", "src", "EV-B", "2026-10-31T00:01:00Z", {"val": "B"})

    v2_log, meta = EventLog.reconstruct_v2_ledger(str(source_file), str(target_file))

    # Attacker reorders records in V2
    with open(target_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    with open(target_file, "w", encoding="utf-8") as f:
        f.writelines([lines[1], lines[0]])  # Swap records

    is_valid, errors, report = EventLog.verify_v2_manifest(
        v2_log_path=str(target_file),
        source_legacy_path=str(source_file),
    )
    assert is_valid is False
    assert any("positional order violation" in err or "broken hash chain link" in err for err in errors)


def test_adversarial_migration_detects_substituted_payload(tmp_path):
    """Adversarial Scenario: Attacker substitutes payload content in V2 record."""
    source_file = tmp_path / "source_sub.jsonl"
    target_file = tmp_path / "v2_sub.jsonl"

    log = EventLog(log_path=str(source_file))
    log.append("ORD-1", "src", "EV-1", "2026-10-31T00:00:00Z", {"amount": "5.00"})

    v2_log, meta = EventLog.reconstruct_v2_ledger(str(source_file), str(target_file))

    # Attacker substitutes amount to 5000.00
    with open(target_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    data = json.loads(lines[0])
    data["payload"]["amount"] = "5000.00"
    with open(target_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(data) + "\n")

    is_valid, errors, report = EventLog.verify_v2_manifest(
        v2_log_path=str(target_file),
        source_legacy_path=str(source_file),
    )
    assert is_valid is False
    assert any("hash mismatch" in err or "payload mismatch" in err for err in errors)


# ===========================================================================
# 4. Multiprocess Lock Contention & Heavy Concurrency
# ===========================================================================

def _adversarial_proc_writer(chain_path: str, proc_id: int, num_events: int) -> None:
    log = EventLog(log_path=chain_path)
    for i in range(num_events):
        log.append(
            transaction_ref=f"ORD-ADV-{proc_id}",
            source_type="adversarial_test",
            source_event_id=f"EV-A{proc_id}-{i}",
            event_timestamp=f"2026-10-31T00:{proc_id:02d}:{i:02d}Z",
            payload={"proc": proc_id, "seq": i, "padding": "x" * 200},
        )


def test_adversarial_multiprocess_high_contention(tmp_path):
    """
    Adversarial Scenario:
    6 separate OS processes hammering the same hash chain simultaneously
    with large payloads under extreme contention.
    Must verify:
    1. Zero deadlocks.
    2. Zero corrupted lines.
    3. Exactly 6 * 10 = 60 events persisted.
    4. Cryptographic verify_chain() is 100% unbroken.
    """
    chain_file = str(tmp_path / "chain_heavy_contention.jsonl")
    num_procs = 6
    events_per_proc = 10

    ctx = multiprocessing.get_context("spawn")
    procs = [
        ctx.Process(target=_adversarial_proc_writer, args=(chain_file, p_id, events_per_proc))
        for p_id in range(num_procs)
    ]

    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=15.0)
        assert p.exitcode == 0

    final_log = EventLog(log_path=chain_file)
    assert len(final_log.events) == num_procs * events_per_proc

    valid, errors = final_log.verify_chain()
    assert valid is True
    assert len(errors) == 0


# ===========================================================================
# 5. Fail-Closed Posture & Bootstrap Edge Cases
# ===========================================================================

def test_adversarial_silent_fallback_to_legacy_prevented(tmp_path, monkeypatch):
    """
    Adversarial Scenario:
    V2 ledger file was deleted or corrupted. The system MUST fail closed
    and NEVER silently fall back to reading or writing the legacy ledger.
    """
    legacy_file = tmp_path / "legacy_ledger.jsonl"
    legacy_file.write_text('{"event_id": "leg"}\n')

    missing_v2 = tmp_path / "missing_v2_ledger.jsonl"
    assert not missing_v2.exists()

    monkeypatch.setattr("src.storage.db.LEGACY_CHAIN_LOG_PATH", str(legacy_file))
    monkeypatch.setattr("src.storage.db.V2_CHAIN_LOG_PATH", str(missing_v2))
    monkeypatch.delenv("CHAIN_LOG_PATH", raising=False)

    with pytest.raises(SilentFallbackProhibitedError) as exc:
        get_chain_log_path()
    assert "Silent fallback to legacy ledger" in str(exc.value)


# ===========================================================================
# 6. SQLite vs JSONL Ledger Disagreement Detection
# ===========================================================================

def test_adversarial_sqlite_capture_id_disagreement_rejected(tmp_path):
    """
    Adversarial Scenario:
    Attacker creates a fake target event in the hash chain pointing to CAP-FORGED,
    while durable SQLite ledger records CAP-GENUINE.
    Independent verification MUST reject target validity.
    """
    chain_file = tmp_path / "chain_sqlite_disagree.jsonl"
    log = EventLog(log_path=str(chain_file))
    log.append(
        transaction_ref="CAP-FORGED-999",  # FORGED
        source_type="paypal_webhook",
        source_event_id="WH-CORRELATION-TEST",
        event_timestamp="2026-10-31T12:00:00Z",
        payload={"event_type": "PAYMENT.CAPTURE.COMPLETED", "summary": "Payment capture"},
    )

    sqlite_record = {
        "event_id": "WH-CORRELATION-TEST",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource_id": "CAP-GENUINE-111",  # GENUINE (mismatch)
        "transaction_reference": "ORD-123",
    }

    res = verify_event_in_hash_chain(
        chain_log_path=str(chain_file),
        expected_event_id="WH-CORRELATION-TEST",
        expected_event_type="PAYMENT.CAPTURE.COMPLETED",
        expected_capture_id="CAP-GENUINE-111",
        sqlite_event_record=sqlite_record,
    )

    assert res.target_valid is False
    assert "SQLite resource_id 'CAP-GENUINE-111'" in res.message
    assert res.forensic_verdict == "FAILED_VERIFICATION"
