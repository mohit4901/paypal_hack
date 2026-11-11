"""
Routes package for ProofLedger backend API.
"""
from fastapi import APIRouter

from backend.routes.overview import router as overview_router
from backend.routes.events import router as events_router
from backend.routes.verification import router as verification_router
from backend.routes.ledger import router as ledger_router
from backend.routes.migration import router as migration_router
from backend.routes.checkpoints import router as checkpoints_router
from backend.routes.keys import router as keys_router
from backend.routes.security import router as security_router
from backend.routes.reconciliation import router as reconciliation_router
from backend.routes.disputes import router as disputes_router
from backend.routes.transactions import router as transactions_router
from backend.routes.ai import router as ai_router
from backend.routes.system import router as system_router
from backend.routes.sellers import router as sellers_router
from backend.routes.paypal import router as paypal_router

api_router = APIRouter(prefix="/api/v2")

api_router.include_router(system_router, prefix="/system", tags=["System Status"])
api_router.include_router(paypal_router, prefix="/paypal", tags=["PayPal Live Sandbox"])
api_router.include_router(sellers_router, prefix="/sellers", tags=["Sellers & Accounts"])
api_router.include_router(overview_router, prefix="/overview", tags=["Overview"])
api_router.include_router(events_router, prefix="/events", tags=["Events"])
api_router.include_router(verification_router, prefix="/verification", tags=["Verification"])
api_router.include_router(disputes_router, prefix="/disputes", tags=["Disputes & Claims"])
api_router.include_router(transactions_router, prefix="/transactions", tags=["Transactions"])
api_router.include_router(ai_router, prefix="/ai", tags=["AI Neural Model"])
api_router.include_router(ledger_router, prefix="/ledger", tags=["Ledger"])
api_router.include_router(migration_router, prefix="/migration", tags=["Migration"])
api_router.include_router(checkpoints_router, prefix="/checkpoints", tags=["Checkpoints"])
api_router.include_router(keys_router, prefix="/keys", tags=["Key Governance"])
api_router.include_router(security_router, prefix="/security", tags=["Security & Invariants"])
api_router.include_router(reconciliation_router, prefix="/reconciliation", tags=["Reconciliation"])

