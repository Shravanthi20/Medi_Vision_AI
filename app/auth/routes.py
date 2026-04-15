from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import User, Role, FaceEncoding
from app.auth.schemas import LoginRequest, TokenResponse, RefreshRequest, FaceLoginRequest
from app.auth.utils import verify_password, create_access_token, create_refresh_token, decode_token
from app.auth.dependencies import require_active_user
import time

router = APIRouter(prefix="/auth", tags=["auth"])

# Simple in-memory rate limiting and blacklisting placeholders
# In production, use Redis
login_attempts = {}
token_blacklist = set()

@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    # Simple Rate Limiting (Prevent brute force)
    client_ip = "default"  # Replace with actual IP retrieval if needed
    now = time.time()
    if client_ip in login_attempts and now - login_attempts[client_ip] < 1:
        raise HTTPException(status_code=429, detail="Too many requests. Please wait.")
    login_attempts[client_ip] = now

    result = await db.execute(
        select(User, Role).join(Role, User.role_id == Role.role_id).where(User.username == data.username)
    )
    row = result.first()
    
    if not row or not verify_password(data.password, row[0].password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    
    user, role = row
    
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")
    
    # Payload as specified: user_id, role_id, role_name, can_bill, can_cancel_bill, 
    # can_view_purchase, can_manage_system, can_approve_override, max_discount_pct, machine_code, salesman_id
    token_data = {
        "user_id": str(user.user_id),
        "role_id": role.role_id,
        "role_name": role.role_name,
        "can_bill": role.can_bill,
        "can_cancel_bill": role.can_cancel_bill,
        "can_view_purchase": role.can_view_purchase,
        "can_manage_system": role.can_manage_system,
        "can_approve_override": role.can_approve_override,
        "max_discount_pct": role.max_discount_pct,
        "machine_code": user.machine_code,
        "salesman_id": user.salesman_id
    }
    
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(user_id=user.user_id)
    
    return {"access_token": access_token, "refresh_token": refresh_token}

@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    if data.refresh_token in token_blacklist:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")
        
    payload = decode_token(data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    
    user_id = payload.get("sub")
    result = await db.execute(
        select(User, Role).join(Role, User.role_id == Role.role_id).where(User.user_id == user_id)
    )
    row = result.first()
    
    if not row or not row[0].is_active:
         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    
    user, role = row
    
    token_data = {
        "user_id": str(user.user_id),
        "role_id": role.role_id,
        "role_name": role.role_name,
        "can_bill": role.can_bill,
        "can_cancel_bill": role.can_cancel_bill,
        "can_view_purchase": role.can_view_purchase,
        "can_manage_system": role.can_manage_system,
        "can_approve_override": role.can_approve_override,
        "max_discount_pct": role.max_discount_pct,
        "machine_code": user.machine_code,
        "salesman_id": user.salesman_id
    }
    
    access_token = create_access_token(data=token_data)
    # Rotating refresh token
    new_refresh_token = create_refresh_token(user_id=user.user_id)
    token_blacklist.add(data.refresh_token)
    
    return {"access_token": access_token, "refresh_token": new_refresh_token}

@router.post("/logout")
async def logout(data: RefreshRequest):
    token_blacklist.add(data.refresh_token)
    return {"message": "Successfully logged out"}

@router.post("/face-login", response_model=TokenResponse)
async def face_login(data: FaceLoginRequest, db: AsyncSession = Depends(get_db)):
    # Placeholder for matching logic
    # In production, use cosine similarity against all encodings in DB
    result = await db.execute(
        select(User, Role).join(Role, User.role_id == Role.role_id).limit(1) 
    )
    row = result.first()
    
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Face not recognized or no users found")
    
    user, role = row
    
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")

    token_data = {
        "user_id": str(user.user_id),
        "role_id": role.role_id,
        "role_name": role.role_name,
        "can_bill": role.can_bill,
        "can_cancel_bill": role.can_cancel_bill,
        "can_view_purchase": role.can_view_purchase,
        "can_manage_system": role.can_manage_system,
        "can_approve_override": role.can_approve_override,
        "max_discount_pct": role.max_discount_pct,
        "machine_code": user.machine_code,
        "salesman_id": user.salesman_id
    }
    
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(user_id=user.user_id)
    
    return {"access_token": access_token, "refresh_token": refresh_token}
