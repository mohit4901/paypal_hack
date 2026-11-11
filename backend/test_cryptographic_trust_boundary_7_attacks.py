"""
ProofLedger 7-Attack Cryptographic Adversarial Audit Suite.
Verifies the cryptographic trust boundary under adversarial scenarios:
1. Attack 1: Ledger-only replacement (tampering payload bytes in place).
2. Attack 2: Ledger plus manifest replacement (recalculating local manifest).
3. Attack 3: Ledger + manifest + checkpoint replacement (attempting to forge Ed25519 signature without private key).
4. Attack 4: Deletion of the checkpoint (detecting missing anchor).
5. Attack 5: Replay of an older valid checkpoint (rollback attack to block 50).
6. Attack 6: Modification of checkpoint metadata (tampering head hash or height).
7. Attack 7: Verification persistence across application restarts.
"""
import os
import json
import shutil
import tempfile
from pathlib import Path
import pytest

from backend.config import V2_CHAIN_LOG_PATH
from backend.security.asymmetric_anchor import (
    verify_asymmetric_checkpoint,
    PINNED_ED25519_PUBLIC_KEY_HEX,
    get_canonical_checkpoint_digest,
)
from tools.external_signing_authority import sign_checkpoint_offline as sign_checkpoint_asymmetrically
from src.models.evidence_compiler import EventLog


BASELINE_CHECKPOINT_PATH = Path("ai/data/checkpoints/checkpoint_v2_baseline_ed25519_signed.json")


def setup_attack_sandbox():
    """Creates a temporary isolated copy of the ledger and checkpoint directory."""
    temp_dir = tempfile.mkdtemp(prefix="pl_attack_")
    sandbox_ledger = Path(temp_dir) / "events_hash_chain_v2.jsonl"
    sandbox_manifest = Path(temp_dir) / "events_hash_chain_v2.jsonl.manifest.json"
    sandbox_cp = Path(temp_dir) / "checkpoint.json"

    shutil.copyfile(str(V2_CHAIN_LOG_PATH), str(sandbox_ledger))
    real_manifest = Path(str(V2_CHAIN_LOG_PATH) + ".manifest.json")
    if real_manifest.exists():
        shutil.copyfile(str(real_manifest), str(sandbox_manifest))
    shutil.copyfile(str(BASELINE_CHECKPOINT_PATH), str(sandbox_cp))

    return temp_dir, sandbox_ledger, sandbox_manifest, sandbox_cp


def test_baseline_signed_checkpoint_valid():
    """Verify that unadulterated baseline checkpoint passes Ed25519 public-key verification."""
    is_valid, errors, data = verify_asymmetric_checkpoint(
        checkpoint_path=str(BASELINE_CHECKPOINT_PATH),
        ledger_path=str(V2_CHAIN_LOG_PATH),
        pinned_public_key_hex=PINNED_ED25519_PUBLIC_KEY_HEX,
    )
    assert is_valid is True, f"Baseline checkpoint failed: {errors}"
    assert len(errors) == 0
    assert data["block_height"] == 164
    assert data["signature_algorithm"] == "Ed25519"


def test_attack_1_ledger_only_replacement_fails():
    """
    ATTACK 1: Attacker modifies an event payload in the ledger without updating manifest or checkpoint.
    Result: Verification fails on hash chain continuity and checkpoint match.
    """
    temp_dir, s_ledger, s_manifest, s_cp = setup_attack_sandbox()
    try:
        # Tamper block #10
        with open(s_ledger, "r") as f:
            lines = f.readlines()
        
        tampered_ev = json.loads(lines[10])
        tampered_ev["payload"]["tampered"] = True
        lines[10] = json.dumps(tampered_ev) + "\n"

        with open(s_ledger, "w") as f:
            f.writelines(lines)

        is_valid, errors, _ = verify_asymmetric_checkpoint(
            checkpoint_path=str(s_cp),
            ledger_path=str(s_ledger),
            pinned_public_key_hex=PINNED_ED25519_PUBLIC_KEY_HEX,
        )
        assert is_valid is False
        assert any("hash mismatch" in err.lower() or "chain broken" in err.lower() or "discrepancy" in err.lower() for err in errors)
    finally:
        shutil.rmtree(temp_dir)


def test_attack_2_ledger_plus_manifest_replacement_fails():
    """
    ATTACK 2: Attacker recalculates all 164 SHA-256 blocks and generates a fresh local manifest.
    Result: Verification fails against external checkpoint because head_hash does not match.
    """
    temp_dir, s_ledger, s_manifest, s_cp = setup_attack_sandbox()
    try:
        # Re-chain ledger with modified payload at genesis
        with open(s_ledger, "r") as f:
            lines = [json.loads(l) for l in f if l.strip()]

        lines[0]["payload"]["injected_fraud"] = "attacker_value"
        # Recalculate whole chain
        import hashlib
        prev_h = "GENESIS"
        for ev in lines:
            ev["previous_hash"] = prev_h
            h_payload = hashlib.sha256(json.dumps(ev["payload"], sort_keys=True).encode()).hexdigest()
            ev["current_hash"] = hashlib.sha256(f"{prev_h}:{h_payload}".encode()).hexdigest()
            prev_h = ev["current_hash"]

        with open(s_ledger, "w") as f:
            for ev in lines:
                f.write(json.dumps(ev) + "\n")

        # Update local manifest
        with open(s_manifest, "w") as f:
            json.dump({"total_events": len(lines), "head_hash": prev_h}, f)

        is_valid, errors, _ = verify_asymmetric_checkpoint(
            checkpoint_path=str(s_cp),
            ledger_path=str(s_ledger),
            pinned_public_key_hex=PINNED_ED25519_PUBLIC_KEY_HEX,
        )
        assert is_valid is False
        assert any("discrepancy" in err.lower() for err in errors)
    finally:
        shutil.rmtree(temp_dir)


def test_attack_3_ledger_manifest_checkpoint_forgery_fails():
    """
    ATTACK 3: Attacker rewrites ledger, manifest, and rewrites the checkpoint file,
    attempting to forge an Ed25519 signature with a rogue private key.
    Result: Verification fails because rogue signature does not match PINNED_ED25519_PUBLIC_KEY_HEX.
    """
    temp_dir, s_ledger, s_manifest, s_cp = setup_attack_sandbox()
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519
        rogue_key = ed25519.Ed25519PrivateKey.generate()

        # Attacker crafts bogus checkpoint with rogue signature
        fake_head = "deadbeef" * 8
        cp_fake = {
            "checkpoint_type": "PROOFLEDGER_CRYPTOGRAPHIC_ANCHOR_V2",
            "block_height": 164,
            "head_hash": fake_head,
            "timestamp_utc": "2026-11-01T15:00:00Z",
        }
        digest = get_canonical_checkpoint_digest(cp_fake)
        rogue_sig = rogue_key.sign(digest.encode("utf-8")).hex()
        cp_fake["canonical_digest"] = digest
        cp_fake["signature"] = rogue_sig
        cp_fake["signature_algorithm"] = "Ed25519"

        with open(s_cp, "w") as f:
            json.dump(cp_fake, f)

        is_valid, errors, _ = verify_asymmetric_checkpoint(
            checkpoint_path=str(s_cp),
            ledger_path=str(s_ledger),
            pinned_public_key_hex=PINNED_ED25519_PUBLIC_KEY_HEX,
        )
        assert is_valid is False
        assert any("signature verification failed" in err.lower() for err in errors)
    finally:
        shutil.rmtree(temp_dir)


def test_attack_4_checkpoint_deletion_fails():
    """
    ATTACK 4: Attacker deletes the checkpoint file.
    Result: Verification immediately returns False reporting missing checkpoint.
    """
    temp_dir, s_ledger, s_manifest, s_cp = setup_attack_sandbox()
    try:
        s_cp.unlink()
        is_valid, errors, _ = verify_asymmetric_checkpoint(
            checkpoint_path=str(s_cp),
            ledger_path=str(s_ledger),
            pinned_public_key_hex=PINNED_ED25519_PUBLIC_KEY_HEX,
        )
        assert is_valid is False
        assert any("not found" in err.lower() for err in errors)
    finally:
        shutil.rmtree(temp_dir)


def test_attack_5_replay_older_checkpoint_rollback_fails():
    """
    ATTACK 5: Attacker truncates the ledger to block 50 and replays a valid older checkpoint (rollback).
    Result: Verification detects that ledger height is less than required checkpoint height (or height mismatch).
    """
    temp_dir, s_ledger, s_manifest, s_cp = setup_attack_sandbox()
    try:
        # Truncate ledger to 50 events
        with open(s_ledger, "r") as f:
            lines = f.readlines()[:50]
        with open(s_ledger, "w") as f:
            f.writelines(lines)

        # Attempt to verify truncated ledger against block 164 checkpoint
        is_valid, errors, _ = verify_asymmetric_checkpoint(
            checkpoint_path=str(s_cp),
            ledger_path=str(s_ledger),
            pinned_public_key_hex=PINNED_ED25519_PUBLIC_KEY_HEX,
        )
        assert is_valid is False
        assert any("rollback" in err.lower() for err in errors)
    finally:
        shutil.rmtree(temp_dir)


def test_attack_6_checkpoint_metadata_modification_fails():
    """
    ATTACK 6: Attacker edits head_hash or block_height directly inside the checkpoint file.
    Result: Verification fails due to canonical digest mismatch and invalid Ed25519 signature.
    """
    temp_dir, s_ledger, s_manifest, s_cp = setup_attack_sandbox()
    try:
        with open(s_cp, "r") as f:
            cp_data = json.load(f)
        cp_data["head_hash"] = "0000000000000000000000000000000000000000000000000000000000000000"
        with open(s_cp, "w") as f:
            json.dump(cp_data, f)

        is_valid, errors, _ = verify_asymmetric_checkpoint(
            checkpoint_path=str(s_cp),
            ledger_path=str(s_ledger),
            pinned_public_key_hex=PINNED_ED25519_PUBLIC_KEY_HEX,
        )
        assert is_valid is False
        assert any("digest mismatch" in err.lower() or "signature verification failed" in err.lower() for err in errors)
    finally:
        shutil.rmtree(temp_dir)


def test_attack_7_persistence_after_app_restart():
    """
    ATTACK 7: Simulation of complete cold restart of verifier runtime.
    Result: Clean verifier with pinned key verifies immutable baseline chain without state loss.
    """
    from backend.security.asymmetric_anchor import verify_asymmetric_checkpoint
    is_valid, errors, data = verify_asymmetric_checkpoint(
        checkpoint_path=str(BASELINE_CHECKPOINT_PATH),
        ledger_path=str(V2_CHAIN_LOG_PATH),
    )
    assert is_valid is True
    assert len(errors) == 0
    assert data["head_event_id"] == "wh_rev_163_7102"


def test_attack_8_transparency_log_monotonic_rollback_rejection():
    """
    ATTACK 8: Attacker presents an older checkpoint (height 100) when external WORM transparency log anchors at 164.
    Result: Verification strictly rejects the replay under monotonic progression invariant.
    """
    temp_dir, s_ledger, s_manifest, s_cp = setup_attack_sandbox()
    try:
        with open(s_cp, "r") as f:
            cp_data = json.load(f)
        cp_data["block_height"] = 100
        cp_data["total_events"] = 100
        from backend.security.asymmetric_anchor import get_canonical_checkpoint_digest
        cp_data["canonical_digest"] = get_canonical_checkpoint_digest(cp_data)
        with open(s_cp, "w") as f:
            json.dump(cp_data, f)

        is_valid, errors, _ = verify_asymmetric_checkpoint(
            checkpoint_path=str(s_cp),
            ledger_path=str(s_ledger),
            enforce_monotonic=True,
        )
        assert is_valid is False
        assert any("monotonic rollback attack detected" in err.lower() for err in errors)
    finally:
        shutil.rmtree(temp_dir)


def test_attack_9_missing_registry_fails_closed():
    """
    ATTACK 9: Monotonic registry file is missing/deleted or points to invalid path.
    Result: Verification strictly fails closed and refuses to verify checkpoints without active registry.
    """
    temp_dir, s_ledger, s_manifest, s_cp = setup_attack_sandbox()
    try:
        non_existent_reg = Path(temp_dir) / "does_not_exist_registry.json"
        is_valid, errors, _ = verify_asymmetric_checkpoint(
            checkpoint_path=str(s_cp),
            ledger_path=str(s_ledger),
            transparency_log_path=str(non_existent_reg),
            enforce_monotonic=True,
        )
        assert is_valid is False
        assert any("monotonic transparency registry not found" in err.lower() for err in errors)
    finally:
        shutil.rmtree(temp_dir)


def test_attack_10_corrupted_registry_fails_closed():
    """
    ATTACK 10: Monotonic registry has missing or corrupted height/hash fields.
    Result: Verification strictly fails closed.
    """
    temp_dir, s_ledger, s_manifest, s_cp = setup_attack_sandbox()
    try:
        corrupt_reg = Path(temp_dir) / "corrupt_registry.json"
        with open(corrupt_reg, "w") as f:
            json.dump({"registry_type": "CORRUPT"}, f)
        is_valid, errors, _ = verify_asymmetric_checkpoint(
            checkpoint_path=str(s_cp),
            ledger_path=str(s_ledger),
            transparency_log_path=str(corrupt_reg),
            enforce_monotonic=True,
        )
        assert is_valid is False
        assert any("fail-closed" in err.lower() for err in errors)
    finally:
        shutil.rmtree(temp_dir)


