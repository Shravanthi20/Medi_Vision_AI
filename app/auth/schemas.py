from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID

class LoginRequest(BaseModel):
    username: str
    password: str

class FaceLoginRequest(BaseModel):
    image_base64: str  # Base64 encoded image

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str

class UserAuthInToken(BaseModel):
    user_id: str
    role_id: int
    role_name: str
    can_bill: bool
    can_cancel_bill: bool
    can_view_purchase: bool
    can_manage_system: bool
    can_approve_override: bool
    max_discount_pct: float
    machine_code: str
    salesman_id: Optional[str] = None
