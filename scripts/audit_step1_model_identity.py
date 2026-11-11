#!/usr/bin/env python3
"""
Step 1: Freeze models, establish exact identity, SHA-256 fingerprints, Safetensors
headers, label mappings, and verify production loader behavior.
"""
import hashlib
import json
import os
import struct
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ai"))

from transformers import AutoConfig
from src.models.evidence_verifier import EvidenceVerifier
from src.models.input_format import EvidenceRecord, build_nli_input
from backend.services.dispute_service import DisputeVerificationService

OUT_DIR = ROOT / "FINAL_RELEASE" / "INDEPENDENT_GENERALIZATION_AUDIT"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_safetensors_header(path: Path) -> dict:
    size = path.stat().st_size
    with open(path, "rb") as f:
        hlen = struct.unpack("<Q", f.read(8))[0]
        hdr = json.loads(f.read(hlen).decode("utf-8"))
    meta = hdr.get("__metadata__", {})
    tensors = {k: v for k, v in hdr.items() if k != "__metadata__"}
    dtypes = sorted({v.get("dtype") for v in tensors.values()})
    max_end = max(v["data_offsets"][1] for v in tensors.values())
    return {
        "valid_structure": (8 + hlen + max_end) == size,
        "file_size_bytes": size,
        "header_bytes": hlen,
        "tensor_count": len(tensors),
        "dtypes": dtypes,
        "metadata": meta,
        "classifier_weight_shape": tensors.get("classifier.weight", {}).get("shape"),
        "classifier_bias_shape": tensors.get("classifier.bias", {}).get("shape"),
    }


def dir_inventory(d: Path) -> dict:
    files = {}
    for p in sorted(d.iterdir()):
        if p.is_file() and not p.name.startswith("."):
            entry = {
                "size_bytes": p.stat().st_size,
                "sha256": sha256_file(p),
            }
            if p.suffix == ".safetensors":
                entry["safetensors"] = parse_safetensors_header(p)
            files[p.name] = entry
    return files


def main():
    cand_dir = ROOT / "ai/artifacts/candidates/deberta_v3_inr_v1/best"
    legacy_dir = ROOT / "ai/artifacts/best_model"
    hf_cache = Path.home() / ".cache/huggingface/hub/models--MoritzLaurer--DeBERTa-v3-base-mnli-fever-anli/snapshots"
    pretrained_snap = sorted(hf_cache.iterdir())[0] if hf_cache.exists() else None

    # Production loader check
    os.environ.pop("PROOFLEDGER_MODEL_PATH", None)
    os.environ.pop("MODEL_PATH", None)
    svc = DisputeVerificationService()

    # Direct candidate loader check
    ev = EvidenceVerifier(model_path=str(cand_dir))
    ev.load()
    sample_inp = build_nli_input(
        "Package arrived at recipient porch.",
        [EvidenceRecord("EV-1", "carrier", "2026-11-10T00:00:00Z", "UPS delivered to porch.")],
    )
    probe = ev.predict("Package arrived at recipient porch.", [EvidenceRecord("EV-1", "carrier", "2026-11-10T00:00:00Z", "UPS delivered to porch.")])

    pretrained_cfg = AutoConfig.from_pretrained("MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli")

    # Missing-checkpoint fail-closed test (must NOT silently fall back)
    os.environ["PROOFLEDGER_MODEL_PATH"] = "/tmp/nonexistent_proofledger_ckpt_audit"
    svc_missing = DisputeVerificationService()
    os.environ.pop("PROOFLEDGER_MODEL_PATH", None)

    report = {
        "audit_timestamp": datetime.now(timezone.utc).isoformat(),
        "candidate_artifact": {
            "path": str(cand_dir.relative_to(ROOT)),
            "expected_model_safetensors_sha256": "2afd4cf10a28b274445073c6fc3c880c54708d5886ca3a2c54ed45857a94e2ea",
            "actual_model_safetensors_sha256": dir_inventory(cand_dir)["model.safetensors"]["sha256"],
            "matches_recorded_fingerprint": dir_inventory(cand_dir)["model.safetensors"]["sha256"] == "2afd4cf10a28b274445073c6fc3c880c54708d5886ca3a2c54ed45857a94e2ea",
            "files": dir_inventory(cand_dir),
            "loaded_verifier_info": ev.model_info,
            "tokenizer_class": type(ev._tokenizer).__name__,
            "vocab_size": ev._tokenizer.vocab_size,
            "max_length": ev.max_length,
            "input_order": "premise=formatted_evidence, hypothesis=claim",
            "sample_nli_input": {"premise": sample_inp.premise, "hypothesis": sample_inp.hypothesis},
            "sample_probe_output": probe,
        },
        "legacy_artifact": {
            "path": str(legacy_dir.relative_to(ROOT)),
            "expected_model_safetensors_sha256": "0e4d8903a24b7c8d45c63023a9d71425153f8919e6acbfa331337aaf088f4617",
            "actual_model_safetensors_sha256": dir_inventory(legacy_dir)["model.safetensors"]["sha256"],
            "matches_recorded_fingerprint": dir_inventory(legacy_dir)["model.safetensors"]["sha256"] == "0e4d8903a24b7c8d45c63023a9d71425153f8919e6acbfa331337aaf088f4617",
            "files": dir_inventory(legacy_dir),
        },
        "pretrained_baseline": {
            "model_id": "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
            "snapshot_path": str(pretrained_snap) if pretrained_snap else None,
            "id2label": {str(k): v for k, v in pretrained_cfg.id2label.items()},
            "architecture": pretrained_cfg.model_type,
            "files": dir_inventory(pretrained_snap) if pretrained_snap else {},
        },
        "production_loader_verification": {
            "default_loaded_model_path": svc.loaded_model_path,
            "default_matches_candidate": svc.loaded_model_path == str(cand_dir),
            "default_load_error": svc.model_load_error,
            "missing_override_verifier_is_none": svc_missing.verifier is None,
            "missing_override_loaded_model_path": svc_missing.loaded_model_path,
            "missing_override_error": svc_missing.model_load_error,
        },
    }

    out_path = OUT_DIR / "MODEL_IDENTITY_AND_HASHES.json"
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Wrote {out_path}")
    print("Candidate SHA match:", report["candidate_artifact"]["matches_recorded_fingerprint"])
    print("Legacy SHA match:", report["legacy_artifact"]["matches_recorded_fingerprint"])
    print("Production default loaded:", report["production_loader_verification"]["default_loaded_model_path"])
    print("Missing override fallback prevented:", report["production_loader_verification"]["missing_override_verifier_is_none"])


if __name__ == "__main__":
    main()

