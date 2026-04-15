import uuid
from sqlalchemy import Column, String, Boolean, Float, ForeignKey, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, DeclarativeBase
from datetime import datetime

class Base(DeclarativeBase):
    pass

class Role(Base):
    __tablename__ = "roles"

    role_id = Column(Integer, primary_key=True, index=True)
    role_name = Column(String, unique=True, index=True)  # 'Supervisor'/'Manager'/'Staff'
    can_bill = Column(Boolean, default=False)
    can_cancel_bill = Column(Boolean, default=False)
    can_view_purchase = Column(Boolean, default=False)
    can_manage_system = Column(Boolean, default=False)
    can_approve_override = Column(Boolean, default=False)
    max_discount_pct = Column(Float, default=8.00)
    is_active = Column(Boolean, default=True)

    users = relationship("User", back_populates="role")

class User(Base):
    __tablename__ = "users"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role_id = Column(Integer, ForeignKey("roles.role_id"))
    salesman_id = Column(String, nullable=True)
    machine_code = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

    role = relationship("Role", back_populates="users")
    face_encodings = relationship("FaceEncoding", back_populates="user")

class FaceEncoding(Base):
    __tablename__ = "face_encodings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"))
    encoding = Column(JSONB)  # Store face encoding as a JSON list of floats
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="face_encodings")
