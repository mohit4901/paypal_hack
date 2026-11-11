"""
Seller Account Management and Profile Routes.
Supports registration, profile lookup, key rotation, and revocation.
Never exposes raw secrets or hashes in standard profile endpoints.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from backend.auth import (
    Seller,
    get_current_seller,
    register_new_seller,
    rotate_seller_key,
    revoke_seller_access,
)

router = APIRouter()


class SellerRegisterRequest(BaseModel):
    seller_id: str
    business_name: str
    product_category: Optional[str] = "Digital Products"
    support_email: Optional[str] = "contact@example.com"


@router.get("/me")
def get_me(current_seller: Seller = Depends(get_current_seller)):
    """Retrieve currently authenticated seller profile."""
    return {
        "seller_id": current_seller.seller_id,
        "business_name": current_seller.business_name,
        "product_category": current_seller.product_category,
        "support_email": current_seller.support_email,
        "key_prefix": current_seller.api_key_prefix,
        "is_active": current_seller.is_active,
    }


@router.post("/register")
def register_seller(req: SellerRegisterRequest):
    """
    Register a new independent seller account with persistent storage in SQLite.
    Returns the newly generated high-entropy raw API key ONCE.
    """
    try:
        seller, raw_api_key = register_new_seller(
            seller_id=req.seller_id.strip(),
            business_name=req.business_name.strip(),
            product_category=req.product_category.strip(),
            support_email=req.support_email.strip(),
        )
        return {
            "status": "REGISTERED",
            "seller_id": seller.seller_id,
            "business_name": seller.business_name,
            "api_key": raw_api_key,
            "raw_api_key": raw_api_key,
            "note": "Store this API key securely. ProofLedger stores only salted cryptographic hashes and cannot retrieve the raw key.",
        }
    except ValueError as ve:
        raise HTTPException(status_code=409, detail=str(ve))
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Registration failed: {ex}")


@router.post("/rotate-key")
def rotate_key(current_seller: Seller = Depends(get_current_seller)):
    """
    Rotate API key for the authenticated seller.
    Invalidates previous key immediately and returns new key ONCE.
    """
    try:
        new_key = rotate_seller_key(current_seller.seller_id)
        return {
            "status": "KEY_ROTATED",
            "seller_id": current_seller.seller_id,
            "api_key": new_key,
            "new_api_key": new_key,
            "raw_api_key": new_key,
            "note": "Previous API key has been revoked. Update your authorization header with this new key.",
        }
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Key rotation failed: {ex}")


@router.post("/revoke")
def revoke_credentials(current_seller: Seller = Depends(get_current_seller)):
    """Deactivate and revoke credentials for this seller immediately."""
    revoke_seller_access(current_seller.seller_id)
    return {
        "status": "REVOKED",
        "seller_id": current_seller.seller_id,
        "detail": "Seller credentials have been revoked. Future requests will be rejected.",
    }
