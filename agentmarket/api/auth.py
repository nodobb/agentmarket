"""
Authentication API Routes
"""

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, field_validator
from agentmarket.models import get_db_dependency
from agentmarket.models.database import User
from agentmarket.services.auth import (
    verify_password, get_password_hash, create_access_token,
    get_current_user
)
from agentmarket.utils.rate_limit import limiter, LOGIN_RATE_LIMIT


router = APIRouter()


# Pydantic models for requests/responses
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: str = "agent_owner"

    @field_validator("role")
    @classmethod
    def role_must_be_self_assignable(cls, v: str) -> str:
        # "admin" must never be self-assignable through public registration
        if v not in ("agent_owner", "vendor"):
            raise ValueError("role must be 'agent_owner' or 'vendor'")
        return v


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    
    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: Session = Depends(get_db_dependency)):
    """Register a new user account"""
    
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        role=user_data.role
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user


@router.post("/login", response_model=Token)
@limiter.limit(LOGIN_RATE_LIMIT)
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db_dependency)):
    """Login and get access token"""
    
    # Authenticate user
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user