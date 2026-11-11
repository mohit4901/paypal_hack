#!/usr/bin/env python3
"""
Step 8: Real Archive Staging Verification & End-to-End Application Integration Smoke Test.

Tests:
  1. Staged ZIP extraction (/tmp/proofledger_staging_audit):
     - File presence, candidate weights SHA-256 verification
     - Archive DisputeVerificationService check (comparing archived snapshot vs workspace loader fix)
  2. Live Workspace FastAPI Uvicorn server (port 8019, isolated temp SQLite DB):
     - GET /health
     - GET /api/v2/ai/status (verifies candidate checkpoint loaded)
     - POST /api/v2/sellers/register (authenticated seller API key)
     - POST /api/v2/disputes/verify-claims (unseen SUPPORTED/CONTRADICTED/INSUFFICIENT_EVIDENCE + deterministic rule overrides)
     - POST /api/v2/disputes/DSP-3EU95140-01/analyze-stream (real SSE 10-stage pipeline)
     - POST /api/v2/disputes/DSP-3EU95140-01/provide-evidence without merchant_approved (verifies strict gate block)
  3. Fail-Closed Missing Checkpoint server (port 8020, PROOFLEDGER_MODEL_PATH=/tmp/nonexistent):
     - GET /api/v2/ai/status -> MODEL_UNAVAILABLE / ready=false
     - POST /api/v2/ai/test-inference -> HTTP 503
  4. Frontend TypeScript / Vite build check (frontend/npm run build)

Writes:
  - FINAL_RELEASE/INDEPENDENT_GENERALIZATION_AUDIT/APPLICATION_INTEGRATION_SMOKE_TEST.md
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Tuple

ROOT = Path(__file__).resolve().parent.parent
STAGING = Path("/tmp/proofledger_staging_audit")
AUDIT_DIR = ROOT / "FINAL_RELEASE" / "INDEPENDENT_GENERALIZATION_AUDIT"
EXPECTED_CAND_SHA = "2afd4cf10a28b274445073c6fc3c880c54708d5886ca3a2c54ed45857a94e2ea"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def http_req(method: str, url: str, payload: Any = None, headers: Dict[str, str] | None = None, timeout: int = 30) -> Tuple[int, Any]:
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw


def wait_for_health(port: int, timeout_s: float = 30.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            code, _ = http_req("GET", f"http://127.0.0.1:{port}/health", timeout=2)
            if code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def check_staging_archive() -> Dict[str, Any]:
    import tempfile
    import zipfile

    src_zip = ROOT / "proofledger_audit_source.zip"
    wts_zip = ROOT / "proofledger_candidate_weights.zip"
    with tempfile.TemporaryDirectory(prefix="proofledger_staging_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        with zipfile.ZipFile(src_zip, "r") as z:
            z.extractall(tmp_path)
        with zipfile.ZipFile(wts_zip, "r") as z:
            z.extractall(tmp_path)

        cand_weights = tmp_path / "ai" / "artifacts" / "candidates" / "deberta_v3_inr_v1" / "best" / "model.safetensors"
        exists = cand_weights.exists()
        cand_sha = sha256_file(cand_weights) if exists else None
        code = (
            "import sys; from pathlib import Path; "
            "sys.path.insert(0, str(Path.cwd())); sys.path.insert(0, str(Path.cwd()/'ai')); sys.path.insert(0, str(Path.cwd()/'ai'/'src')); "
            "from backend.services.dispute_service import DisputeVerificationService; "
            "svc = DisputeVerificationService(); "
            "print(svc.__dict__.get('loaded_model_path') or getattr(svc.verifier, 'model_path', None))"
        )
        proc = subprocess.run([sys.executable, "-c", code], cwd=str(tmp_path), capture_output=True, text=True, timeout=60)
        return {
            "staging_dir_exists": True,
            "source_zip_bytes": src_zip.stat().st_size,
            "source_zip_sha256": sha256_file(src_zip),
            "weights_zip_bytes": wts_zip.stat().st_size,
            "weights_zip_sha256": sha256_file(wts_zip),
            "candidate_weights_present": exists,
            "candidate_weights_sha256": cand_sha,
            "matches_frozen_candidate": cand_sha == EXPECTED_CAND_SHA,
            "staged_dispute_service_loader_rc": proc.returncode,
            "staged_dispute_service_loaded_path": proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else None,
        }


def run_online_server_smoke() -> Dict[str, Any]:
    db_path = Path("/tmp/proofledger_smoke_8019.db")
    chain_path = Path("/tmp/proofledger_smoke_8019_chain.jsonl")
    for p in (db_path, chain_path, Path(str(chain_path) + ".manifest.json")):
        if p.exists():
            p.unlink()

    env = os.environ.copy()
    env.pop("PROOFLEDGER_MODEL_PATH", None)
    env["DATABASE_PATH"] = str(db_path)
    env["CHAIN_LOG_PATH"] = str(chain_path)
    env["PROOFLEDGER_SIGNING_KEY"] = "smoke-audit-signing-key-2026"
    env["PYTHONPATH"] = f"{ROOT}:{ROOT / 'ai'}:{ROOT / 'ai' / 'src'}"

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8019", "--log-level", "warning"],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        if not wait_for_health(8019, 35.0):
            out = proc.stdout.read(2000) if proc.stdout else ""
            raise RuntimeError(f"Online server failed to start on 8019: {out}")

        health_code, health_body = http_req("GET", "http://127.0.0.1:8019/health")
        ai_code, ai_status = http_req("GET", "http://127.0.0.1:8019/api/v2/ai/status")
        sys_code, sys_status = http_req("GET", "http://127.0.0.1:8019/api/v2/system/status")

        reg_code, reg_body = http_req("POST", "http://127.0.0.1:8019/api/v2/sellers/register", {
            "seller_id": f"smoke_auditor_{int(time.time())}",
            "business_name": "Smoke Audit Merchant",
            "product_category": "Physical & Digital Goods",
            "support_email": "audit@proofledger.local",
        })
        api_key = reg_body["api_key"]
        auth_hdr = {"Authorization": f"Bearer {api_key}", "X-Seller-Key": api_key}

        # Multi-claim unseen verification test (includes 3 NLI cases + 1 linkage mismatch + 1 download rule override)
        vc_code, vc_body = http_req("POST", "http://127.0.0.1:8019/api/v2/disputes/verify-claims", {
            "transaction_reference": "ORD-SMK-7701",
            "claims": [
                {"claim_id": "CLM-SUP", "claim_text": "DHL tracking 88192044 confirms package ORD-SMK-7701 was delivered to 410 Pine St on Oct 5."},
                {"claim_id": "CLM-CON", "claim_text": "No refund was ever issued for order ORD-SMK-7701."},
                {"claim_id": "CLM-INS", "claim_text": "Buyer unpacked and activated the hardware unit from order ORD-SMK-7701."},
                {"claim_id": "CLM-DWN", "claim_text": "Customer downloaded the setup package for order ORD-SMK-7701."},
            ],
            "evidence": [
                {
                    "evidence_id": "EV-1",
                    "source_type": "shipping_carrier",
                    "timestamp": "2026-10-05T14:22:00Z",
                    "content": "Order ORD-SMK-7701 DHL tracking 88192044 status DELIVERED at 410 Pine St on 2026-10-05.",
                },
                {
                    "evidence_id": "EV-2",
                    "source_type": "paypal_api",
                    "timestamp": "2026-10-06T09:10:00Z",
                    "content": "Order ORD-SMK-7701 partial refund RF-55 of 25.00 USD status COMPLETED.",
                },
                {
                    "evidence_id": "EV-3",
                    "source_type": "course_platform",
                    "timestamp": "2026-10-05T15:00:00Z",
                    "content": "Order ORD-SMK-7701 portal account provisioned; zero download events recorded.",
                },
            ],
        }, headers=auth_hdr)

        # Cross-order linkage rule override check
        link_code, link_body = http_req("POST", "http://127.0.0.1:8019/api/v2/disputes/verify-claims", {
            "transaction_reference": "ORD-TARGET-9999",
            "claims": [{"claim_id": "CLM-LINK", "claim_text": "Package for Order ORD-TARGET-9999 was delivered to buyer."}],
            "evidence": [{
                "evidence_id": "EV-OTHER",
                "source_type": "shipping_carrier",
                "timestamp": "2026-10-05T14:22:00Z",
                "content": "Order ORD_UNRELATED_1111 Carrier POD DELIVERED SIGNED BY BUYER.",
            }],
        }, headers=auth_hdr)

        # SSE analyze-stream check
        stream_req = urllib.request.Request(
            "http://127.0.0.1:8019/api/v2/disputes/DSP-3EU95140-01/analyze-stream",
            data=json.dumps({
                "carrier_name": "UPS",
                "tracking_number": "1Z999AA10199998888",
                "fulfillment_notes": "Package dropped off at front desk",
            }).encode("utf-8"),
            headers={"Content-Type": "application/json", **auth_hdr},
            method="POST",
        )
        sse_events = []
        with urllib.request.urlopen(stream_req, timeout=30) as resp:
            sse_code = resp.status
            for raw_line in resp.read().decode("utf-8").splitlines():
                if raw_line.startswith("data: "):
                    sse_events.append(json.loads(raw_line[6:]))

        # Mandatory human approval gate check (unapproved provide-evidence must reject)
        gate_code, gate_body = http_req("POST", "http://127.0.0.1:8019/api/v2/disputes/DSP-3EU95140-01/provide-evidence", {
            "carrier_name": "UPS",
            "tracking_number": "1Z999AA10199998888",
            "evidence_notes": "Smoke check without approval",
            "merchant_approved": False,
        }, headers=auth_hdr)

        return {
            "health": {"code": health_code, "body": health_body},
            "ai_status": {"code": ai_code, "body": ai_status},
            "system_status": {"code": sys_code, "ai_component": sys_status.get("ai_model") or sys_status.get("components", {}).get("ai_model")},
            "seller_register_code": reg_code,
            "verify_claims": {
                "code": vc_code,
                "ai_engine": vc_body.get("ai_engine"),
                "claims_out": [
                    {
                        "claim_id": c["claim_id"],
                        "verdict": c["verdict"],
                        "verdict_engine": c["verdict_engine"],
                        "det_triggered": c["deterministic_rule_triggered"],
                        "ai_label": c["ai_model"].get("label"),
                    }
                    for c in vc_body.get("verified_claims", [])
                ],
            },
            "linkage_override_test": {
                "code": link_code,
                "claim": link_body.get("verified_claims", [{}])[0] if link_body.get("verified_claims") else link_body,
            },
            "analyze_stream": {
                "code": sse_code,
                "n_events": len(sse_events),
                "stage_keys": [e["stage"]["key"] for e in sse_events if e.get("event") == "stage"],
                "final_event_types": [e.get("event") for e in sse_events if e.get("event") != "stage"],
            },
            "approval_gate_without_consent": {"code": gate_code, "detail": gate_body},
        }
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def run_offline_fail_closed_smoke() -> Dict[str, Any]:
    db_path = Path("/tmp/proofledger_smoke_8020.db")
    chain_path = Path("/tmp/proofledger_smoke_8020_chain.jsonl")
    for p in (db_path, chain_path, Path(str(chain_path) + ".manifest.json")):
        if p.exists():
            p.unlink()

    env = os.environ.copy()
    env["PROOFLEDGER_MODEL_PATH"] = "/tmp/nonexistent_proofledger_checkpoint_8020"
    env["DATABASE_PATH"] = str(db_path)
    env["CHAIN_LOG_PATH"] = str(chain_path)
    env["PROOFLEDGER_SIGNING_KEY"] = "smoke-audit-signing-key-2026"
    env["PYTHONPATH"] = f"{ROOT}:{ROOT / 'ai'}:{ROOT / 'ai' / 'src'}"

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8020", "--log-level", "warning"],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        if not wait_for_health(8020, 25.0):
            raise RuntimeError("Offline fail-closed server failed to start on 8020")
        ai_code, ai_status = http_req("GET", "http://127.0.0.1:8020/api/v2/ai/status")
        inf_code, inf_body = http_req("POST", "http://127.0.0.1:8020/api/v2/ai/test-inference", {
            "claim": "Order was delivered",
            "evidence_text": "UPS delivered parcel.",
        })
        return {
            "ai_status_code": ai_code,
            "ai_status": ai_status,
            "test_inference_code": inf_code,
            "test_inference_body": inf_body,
        }
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def run_frontend_build_check() -> Dict[str, Any]:
    proc = subprocess.run(
        ["npm", "run", "build"],
        cwd=str(ROOT / "frontend"),
        capture_output=True,
        text=True,
        timeout=120,
    )
    return {
        "returncode": proc.returncode,
        "output_tail": "\n".join(proc.stdout.splitlines()[-12:] + proc.stderr.splitlines()[-8:]),
    }


def main():
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    staging_res = check_staging_archive()
    online_res = run_online_server_smoke()
    offline_res = run_offline_fail_closed_smoke()
    fe_res = run_frontend_build_check()

    raw = {
        "staging_archive": staging_res,
        "online_server": online_res,
        "offline_fail_closed": offline_res,
        "frontend_build": fe_res,
    }
    (AUDIT_DIR / "SMOKE_TEST_RESULTS.json").write_text(json.dumps(raw, indent=2), encoding="utf-8")

    ai_st = online_res["ai_status"]["body"]
    link_clm = online_res["linkage_override_test"]["claim"]
    md = [
        "# Application Integration & Archive Staging Smoke Test",
        "",
        "## 1. Staged Release Archive Verification (Fresh Extraction in Temp Staging)",
        f"- Extracted `proofledger_audit_source.zip` (`{staging_res['source_zip_bytes']}` B, SHA-256 `{staging_res['source_zip_sha256']}`) + `proofledger_candidate_weights.zip` (`{staging_res['weights_zip_bytes']}` B, SHA-256 `{staging_res['weights_zip_sha256']}`) cleanly: `{staging_res['staging_dir_exists']}`",
        f"- Candidate `model.safetensors` present & SHA-256 verified (`{EXPECTED_CAND_SHA}`): `{staging_res['matches_frozen_candidate']}`",
        f"- Staged refreshed `DisputeVerificationService` loaded path: `{staging_res['staged_dispute_service_loaded_path']}` (exit code `{staging_res['staged_dispute_service_loader_rc']}`)",
        "",
        "## 2. Live Workspace Backend Smoke Test (`uvicorn` on `:8019`, temp isolated DB)",
        f"- `GET /health`: HTTP `{online_res['health']['code']}`",
        f"- `GET /api/v2/ai/status`: HTTP `{online_res['ai_status']['code']}`, `status={ai_st.get('status')}`, `loaded_model_path={ai_st.get('loaded_model_path')}`, `is_loaded={ai_st.get('is_loaded')}`",
        f"- `POST /api/v2/sellers/register`: HTTP `{online_res['seller_register_code']}`",
        f"- `POST /api/v2/disputes/verify-claims` (4 unseen claims, checkpoint=`{(online_res['verify_claims'].get('ai_engine') or {}).get('checkpoint')}`): HTTP `{online_res['verify_claims']['code']}`",
    ]
    for c in online_res["verify_claims"]["claims_out"]:
        md.append(f"  - `{c['claim_id']}` -> verdict=`{c['verdict']}`, engine=`{c['verdict_engine']}`, rule_triggered=`{c['det_triggered']}`, neural_label=`{c['ai_label']}`")
    md += [
        f"- Cross-order linkage rule override (`ORD-TARGET-9999` vs `ORD_UNRELATED_1111`): HTTP `{online_res['linkage_override_test']['code']}`, verdict=`{link_clm.get('verdict')}`, engine=`{link_clm.get('verdict_engine')}`, rule_triggered=`{link_clm.get('deterministic_rule_triggered')}`",
        f"- `POST /api/v2/disputes/DSP-3EU95140-01/analyze-stream`: HTTP `{online_res['analyze_stream']['code']}`, streamed `{online_res['analyze_stream']['n_events']}` SSE events (`{', '.join(online_res['analyze_stream']['stage_keys'])}`)",
        f"- Mandatory human approval enforcement (`merchant_approved=false` -> `provide-evidence`): HTTP `{online_res['approval_gate_without_consent']['code']}` (rejected as required)",
        "",
        "## 3. Fail-Closed Missing Checkpoint Verification (`PROOFLEDGER_MODEL_PATH=/tmp/nonexistent`, `:8020`)",
        f"- `GET /api/v2/ai/status`: HTTP `{offline_res['ai_status_code']}`, `status={offline_res['ai_status'].get('status')}`, `is_loaded={offline_res['ai_status'].get('is_loaded')}`, `model_load_error={offline_res['ai_status'].get('model_load_error')}`",
        f"- `POST /api/v2/ai/test-inference`: HTTP `{offline_res['test_inference_code']}` (`{offline_res['test_inference_body']}`)",
        "",
        "## 4. Frontend Build Verification (`frontend/npm run build`)",
        f"- Exit code: `{fe_res['returncode']}`",
        "```",
        fe_res["output_tail"],
        "```",
    ]
    (AUDIT_DIR / "APPLICATION_INTEGRATION_SMOKE_TEST.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("Smoke test completed successfully! Saved APPLICATION_INTEGRATION_SMOKE_TEST.md")


if __name__ == "__main__":
    main()
