"""
ProofLedger Cryptographic Evidence Platform — Dedicated Backend Service.

Run:
    cd /Users/mohitmudgil/Desktop/paypal/backend
    uvicorn main:app --reload --port 8000
"""
import os
import sys
from pathlib import Path

# Add project root, backend dir, and ai dir to sys.path so it runs from anywhere
_BACKEND_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _BACKEND_DIR.parent
_AI_DIR = _ROOT_DIR / "ai"
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
if str(_AI_DIR) not in sys.path:
    sys.path.insert(0, str(_AI_DIR))

import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.config import ROOT_DIR
from backend.routes import api_router
from backend.services.forensic_engine import ForensicEngine
from backend.services.db_schema import init_saas_schema
from backend.services.paypal_mcp import paypal_mcp

# Initialize persistent SQLite tables on startup
init_saas_schema()

app = FastAPI(
    title="ProofLedger Cryptographic Verification Platform API",
    version="2.0.0",
    description=(
        "Forensic evidence verification, tamper-evident hash-chain audits, "
        "and dispute lifecycle intelligence for PayPal Sandbox & Production."
    ),
)

# Enable CORS for frontend applications (Vite, Next.js, React)
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Mount all V2 forensic REST API routes
app.include_router(api_router)


@app.post("/api/v2/mcp")
@app.post("/mcp")
def handle_mcp_jsonrpc(req: dict):
    """
    Official PayPal Model Context Protocol (MCP) Server Endpoint.
    Handles JSON-RPC 2.0 messages: 'initialize', 'tools/list', 'tools/call'.
    Enforces read-only safety restrictions.
    """
    return paypal_mcp.handle_jsonrpc(req)

# Mount production frontend build and static document exhibits
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
FRONTEND_PUBLIC = ROOT_DIR / "frontend" / "public"

# Mount /documents directory for official certified visual exhibits
DOCUMENTS_DIR = FRONTEND_DIST / "documents" if (FRONTEND_DIST / "documents").exists() else FRONTEND_PUBLIC / "documents"
if DOCUMENTS_DIR.exists():
    app.mount("/documents", StaticFiles(directory=str(DOCUMENTS_DIR)), name="documents")

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="frontend_assets")
    app.mount("/dashboard", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend_dashboard")

@app.get("/logo-icon.png")
def get_logo_icon():
    from fastapi.responses import FileResponse
    p = FRONTEND_PUBLIC / "logo-icon.png"
    if not p.exists():
        p = FRONTEND_DIST / "logo-icon.png"
    if p.exists():
        return FileResponse(str(p))
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="logo-icon.png not found")

@app.get("/logo.png")
def get_logo():
    from fastapi.responses import FileResponse
    p = FRONTEND_PUBLIC / "logo.png"
    if not p.exists():
        p = FRONTEND_DIST / "logo.png"
    if p.exists():
        return FileResponse(str(p))
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="logo.png not found")


@app.get("/health")
def health_check():
    """Service liveness and readiness probe."""
    stats = ForensicEngine.get_overview_stats()
    return {
        "status": "HEALTHY",
        "timestamp": time.time(),
        "ledger_valid": stats["ledger"]["chain_valid"],
        "total_events": stats["ledger"]["total_events"],
    }


@app.get("/")
def root():
    """Redirect root to dashboard if built, otherwise to API docs."""
    if FRONTEND_DIST.exists():
        return RedirectResponse(url="/dashboard")
    return RedirectResponse(url="/docs")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
