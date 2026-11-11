#!/usr/bin/env bash
# ==============================================================================
# ProofLedger Platform — Unified Dev Launcher
# ==============================================================================

echo "======================================================================"
echo "Starting ProofLedger Cryptographic Evidence Verification Platform"
echo "======================================================================"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "▶ [1/2] Launching Backend Service on http://localhost:8000..."
cd "$ROOT_DIR/backend" && python3 -m uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!

echo "▶ [2/2] Launching Frontend Dashboard on http://localhost:3000..."
cd "$ROOT_DIR/frontend" && npm run dev &
FRONTEND_PID=$!

echo "======================================================================"
echo "✔ Backend API:   http://localhost:8000 (API docs: /docs)"
echo "✔ Frontend UI:   http://localhost:3000"
echo "✔ Standalone UI: http://localhost:8000/dashboard"
echo "======================================================================"
echo "Press Ctrl+C to stop all services."

trap "echo 'Stopping ProofLedger services...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM EXIT
wait

