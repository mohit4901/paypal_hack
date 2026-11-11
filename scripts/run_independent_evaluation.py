#!/usr/bin/env python3
"""
Step 4: Run real production inference for Systems A-E across the frozen 600-pair
ProofLedger Independent Unseen Benchmark (ai/data/evaluation/proofledger_unseen_v1/dataset.jsonl).

Systems evaluated:
  A. Candidate fine-tuned DeBERTa-v3 (ai/artifacts/candidates/deberta_v3_inr_v1/best)
  B. Exact Pretrained NLI baseline (MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli)
  C. Legacy deployed checkpoint (ai/artifacts/best_model)
  D. Rules-only deterministic engine (DisputeVerificationService with neural model disabled)
  E. Current production Hybrid (DisputeVerificationService: Rules-first + Candidate)

Outputs raw per-example predictions to FINAL_RELEASE/INDEPENDENT_GENERALIZATION_AUDIT/*.jsonl
plus measured model load times and disk footprint to RUNTIME_BENCHMARKS.json.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ai"))
sys.path.insert(0, str(ROOT / "ai" / "src"))

from src.models.evidence_verifier import EvidenceVerifier
from src.models.input_format import EvidenceRecord
from backend.services.dispute_service import DisputeVerificationService

DATASET_PATH = ROOT / "ai" / "data" / "evaluation" / "proofledger_unseen_v1" / "dataset.jsonl"
OUT_DIR = ROOT / "FINAL_RELEASE" / "INDEPENDENT_GENERALIZATION_AUDIT"

CANDIDATE_PATH = str(ROOT / "ai" / "artifacts" / "candidates" / "deberta_v3_inr_v1" / "best")
PRETRAINED_ID = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
LEGACY_PATH = str(ROOT / "ai" / "artifacts" / "best_model")


def dir_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def load_dataset(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def run_verifier_system(
    system_name: str,
    model_path: str,
    rows: List[Dict[str, Any]],
    out_jsonl: Path,
) -> Dict[str, Any]:
    print(f"\n=== Running {system_name}: {model_path} ===")
    t_load0 = time.perf_counter()
    verifier = EvidenceVerifier(model_path=model_path)
    verifier.load()
    load_ms = (time.perf_counter() - t_load0) * 1000.0
    dev = getattr(verifier, "device", "cpu")
    print(f"Loaded in {load_ms:.1f} ms on device={dev}, id2label={verifier._model.config.id2label}")

    # Warmup 1 pass on dummy input so first-sample MPS kernel compilation doesn't skew latency stats cleanly
    # Wait: record warmup separately, keep per-sample timed inference exact.
    _ = verifier.predict(rows[0]["claim"], [EvidenceRecord("ev_w", "RECORD", None, rows[0]["evidence"])])

    records_written = 0
    trunc_count = 0
    abstain_count = 0
    latencies = []

    with out_jsonl.open("w", encoding="utf-8") as f:
        for idx, row in enumerate(rows):
            ev = [EvidenceRecord(evidence_id="ev_1", source_type="RECORD", timestamp=None, content=row["evidence"])]
            t0 = time.perf_counter()
            pred = verifier.predict(row["claim"], ev)
            dt_ms = (time.perf_counter() - t0) * 1000.0
            latencies.append(dt_ms)

            if pred.get("truncated"):
                trunc_count += 1
            if pred.get("is_abstained"):
                abstain_count += 1

            out_rec = {
                "sample_id": row["sample_id"],
                "scenario_family": row["scenario_family"],
                "gold_label": row["gold_label"],
                "pred_label": pred["label"],
                "operational_decision": pred["decision"],
                "is_abstained": bool(pred.get("is_abstained", False)),
                "scores": pred["scores"],
                "calibrated_scores": None,
                "confidence": pred["confidence"],
                "calibrated_confidence": None,
                "logits": pred.get("logits"),
                "truncated": bool(pred.get("truncated", False)),
                "latency_ms": round(dt_ms, 3),
                "verdict_engine": system_name,
                "deterministic_rule_triggered": False,
                "model_path": model_path,
            }
            f.write(json.dumps(out_rec, ensure_ascii=False) + "\n")
            records_written += 1

    resolved_dir = Path(model_path)
    if not resolved_dir.exists():
        hf_dir = Path.home() / ".cache" / "huggingface" / "hub" / f"models--{model_path.replace('/', '--')}" / "snapshots"
        if hf_dir.exists():
            snaps = sorted(hf_dir.iterdir())
            if snaps:
                resolved_dir = snaps[0]

    print(f"Completed {system_name}: N={records_written}, abstained={abstain_count}, truncated={trunc_count}, mean_ms={sum(latencies)/len(latencies):.2f}")
    return {
        "system": system_name,
        "model_path": model_path,
        "resolved_disk_path": str(resolved_dir),
        "model_size_bytes": dir_size_bytes(resolved_dir),
        "load_time_ms": round(load_ms, 2),
        "device": str(dev),
        "n_samples": records_written,
        "truncated_count": trunc_count,
        "abstained_count": abstain_count,
    }


def run_service_system(
    system_name: str,
    model_override: str,
    rows: List[Dict[str, Any]],
    out_jsonl: Path,
) -> Dict[str, Any]:
    print(f"\n=== Running Service System {system_name} (PROOFLEDGER_MODEL_PATH={model_override}) ===")
    os.environ["PROOFLEDGER_MODEL_PATH"] = model_override
    t_load0 = time.perf_counter()
    svc = DisputeVerificationService()
    load_ms = (time.perf_counter() - t_load0) * 1000.0
    print(f"Service initialized in {load_ms:.1f} ms | loaded_model_path={svc.loaded_model_path} | load_error={svc.model_load_error}")

    if system_name == "HYBRID_PRODUCTION" and not svc.loaded_model_path:
        raise RuntimeError(f"Hybrid system failed to load candidate checkpoint: {svc.model_load_error}")
    if system_name == "RULES_ONLY" and svc.loaded_model_path is not None:
        raise RuntimeError(f"Rules-only system unexpectedly loaded a neural model: {svc.loaded_model_path}")

    # Warmup if neural model loaded
    if svc.verifier and svc.verifier.is_loaded:
        _ = svc.verify_single_claim(
            rows[0]["claim"],
            [{"evidence_id": "ev_w", "source_type": "RECORD", "timestamp": None, "content": rows[0]["evidence"]}],
            transaction_reference="",
        )

    records_written = 0
    rule_triggers = 0
    abstain_count = 0
    latencies = []

    with out_jsonl.open("w", encoding="utf-8") as f:
        for row in rows:
            ev_list = [{"evidence_id": "ev_1", "source_type": "RECORD", "timestamp": None, "content": row["evidence"]}]
            t0 = time.perf_counter()
            res = svc.verify_single_claim(row["claim"], ev_list, transaction_reference="")
            dt_ms = (time.perf_counter() - t0) * 1000.0
            latencies.append(dt_ms)

            ai_info = res.get("ai_model", {})
            det_triggered = bool(res.get("deterministic_rule_triggered", False))
            if det_triggered:
                rule_triggers += 1
            if res.get("is_abstained") or res.get("verdict") == "NEEDS_HUMAN_REVIEW":
                abstain_count += 1

            # Strict 3-class pred_label:
            # - If Rules-Only: res["verdict"] (always one of SUPPORTED/CONTRADICTED/INSUFFICIENT_EVIDENCE)
            # - If Hybrid: deterministic override verdict if triggered, else underlying neural argmax ai_info["label"]
            if system_name == "RULES_ONLY":
                strict_label = res["verdict"]
                scores = None
                conf = None
                cal_scores = None
                cal_conf = None
            else:
                strict_label = res["verdict"] if det_triggered else (ai_info.get("label") or res["verdict"])
                scores = ai_info.get("raw_scores") or ai_info.get("scores")
                conf = ai_info.get("raw_confidence") or ai_info.get("confidence")
                cal_scores = ai_info.get("calibrated_scores")
                cal_conf = ai_info.get("calibrated_confidence")

            out_rec = {
                "sample_id": row["sample_id"],
                "scenario_family": row["scenario_family"],
                "gold_label": row["gold_label"],
                "pred_label": strict_label,
                "operational_decision": res["verdict"],
                "is_abstained": bool(res.get("is_abstained", False) or res.get("verdict") == "NEEDS_HUMAN_REVIEW"),
                "scores": scores,
                "calibrated_scores": cal_scores,
                "confidence": conf,
                "calibrated_confidence": cal_conf,
                "logits": ai_info.get("raw_logits"),
                "truncated": bool(ai_info.get("truncated", False)) if isinstance(ai_info, dict) else False,
                "latency_ms": round(dt_ms, 3),
                "verdict_engine": res.get("verdict_engine"),
                "deterministic_rule_triggered": det_triggered,
                "deterministic_rule_verdict": res.get("deterministic_rule_verdict"),
                "model_path": svc.loaded_model_path,
            }
            f.write(json.dumps(out_rec, ensure_ascii=False) + "\n")
            records_written += 1

    os.environ.pop("PROOFLEDGER_MODEL_PATH", None)
    size_bytes = dir_size_bytes(Path(svc.loaded_model_path)) if svc.loaded_model_path else 0
    print(f"Completed {system_name}: N={records_written}, rule_triggers={rule_triggers}, abstained={abstain_count}, mean_ms={sum(latencies)/len(latencies):.2f}")
    return {
        "system": system_name,
        "model_path": svc.loaded_model_path,
        "model_size_bytes": size_bytes,
        "load_time_ms": round(load_ms, 2),
        "device": str(getattr(svc.verifier, "device", "cpu")) if svc.verifier else "cpu",
        "n_samples": records_written,
        "rule_triggers": rule_triggers,
        "abstained_count": abstain_count,
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_dataset(DATASET_PATH)
    assert len(rows) == 600, f"Expected 600 unseen rows, found {len(rows)}"

    only_service = "--only-service" in sys.argv
    rb_path = OUT_DIR / "RUNTIME_BENCHMARKS.json"
    benchmarks = json.loads(rb_path.read_text(encoding="utf-8")) if (only_service and rb_path.exists()) else {}

    if not only_service:
        benchmarks["A_candidate"] = run_verifier_system(
            "CANDIDATE_DEBERTA_V3_INR_V1",
            CANDIDATE_PATH,
            rows,
            OUT_DIR / "CANDIDATE_PREDICTIONS.jsonl",
        )
        benchmarks["B_pretrained"] = run_verifier_system(
            "PRETRAINED_DEBERTA_V3_MNLI_FEVER_ANLI",
            PRETRAINED_ID,
            rows,
            OUT_DIR / "PRETRAINED_PREDICTIONS.jsonl",
        )
        benchmarks["C_legacy"] = run_verifier_system(
            "LEGACY_BEST_MODEL",
            LEGACY_PATH,
            rows,
            OUT_DIR / "LEGACY_PREDICTIONS.jsonl",
        )
    benchmarks["D_rules_only"] = run_service_system(
        "RULES_ONLY",
        "/tmp/proofledger_rules_only_no_model",
        rows,
        OUT_DIR / "RULES_ONLY_PREDICTIONS.jsonl",
    )
    benchmarks["E_hybrid"] = run_service_system(
        "HYBRID_PRODUCTION",
        CANDIDATE_PATH,
        rows,
        OUT_DIR / "HYBRID_PREDICTIONS.jsonl",
    )

    with rb_path.open("w", encoding="utf-8") as f:
        json.dump(benchmarks, f, indent=2)
    print("\nSaved prediction files and RUNTIME_BENCHMARKS.json.")


if __name__ == "__main__":
    main()
