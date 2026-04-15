from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError
from app.auth.utils import decode_token
from app.database import get_db
from app.models import User
from typing import Optional

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

async def get_current_user_payload(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if not payload or not payload.get("user_id"):
        raise credentials_exception
    return payload

async def require_active_user(
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db)
) -> User:
    user_id = payload.get("user_id")
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )
    return user

def require_permission(permission_name: str):
    async def permission_checker(payload: dict = Depends(get_current_user_payload)):
        if not payload.get(permission_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Missing required permission '{permission_name}'"
            )
        return True
    return permission_checker

def require_max_discount(discount_pct: float):
    async def discount_checker(payload: dict = Depends(get_current_user_payload)):
        max_allowed = payload.get("max_discount_pct", 0)
        if discount_pct > max_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Discount {discount_pct}% exceeds maximum allowed {max_allowed}%"
            )
        return True
    return discount_checker
