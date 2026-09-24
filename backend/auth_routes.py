"""
Authentication Router
Handles user signup, login, email verification, and password reset.
"""
import secrets
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, EmailStr, validator
from sqlalchemy.orm import Session
import structlog

from models import (
    DatabaseManager,
    Customer,
    User,
    create_customer,
    create_user,
    get_user_by_email,
    get_user_by_verification_token,
    get_user_by_reset_token,
    update_user_verification_status,
    update_user_password,
    update_last_login
)
from auth import (
    hash_password,
    verify_password,
    hash_api_key,
    create_user_access_token,
    get_current_user
)
from email_service import email_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])

from database import get_db


# Request/Response models
class SignupRequest(BaseModel):
    """User signup request"""
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    company_name: str
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one number')
        if not any(char.isupper() for char in v):
            raise ValueError('Password must contain at least one uppercase letter')
        return v


class LoginRequest(BaseModel):
    """User login request"""
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """User login response"""
    access_token: str
    token_type: str = "bearer"
    user: dict


class ForgotPasswordRequest(BaseModel):
    """Forgot password request"""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Reset password request"""
    token: str
    new_password: str
    
    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one number')
        if not any(char.isupper() for char in v):
            raise ValueError('Password must contain at least one uppercase letter')
        return v


class MessageResponse(BaseModel):
    """Generic message response"""
    message: str


@router.post("/signup", response_model=MessageResponse)
async def signup(
    request: SignupRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Register a new user and customer account.
    
    Creates:
    1. Customer account (company)
    2. User account (login credentials)
    3. API key for programmatic access
    4. Sends verification email
    """
    # Check if email already exists
    existing_user = get_user_by_email(db, request.email)
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    try:
        # Generate API key for the customer
        api_key = secrets.token_urlsafe(32)
        api_key_hash = hash_api_key(api_key)
        
        # Create customer account (default to free plan)
        customer = create_customer(
            session=db,
            company_name=request.company_name,
            email=request.email,
            api_key_hash=api_key_hash,
            plan_type="free",
            max_calls_per_month=100
        )
        
        # Hash password
        password_hash = hash_password(request.password)
        
        # Generate verification token
        verification_token = secrets.token_urlsafe(32)
        verification_expires = datetime.utcnow() + timedelta(hours=24)
        
        # Create user account
        user = create_user(
            session=db,
            customer_id=str(customer.customer_id),
            email=request.email,
            password_hash=password_hash,
            full_name=request.full_name,
            role="owner"
        )
        
        # Set verification token
        user.verification_token = verification_token
        user.verification_token_expires = verification_expires
        db.commit()
        
        # Send verification email in background
        background_tasks.add_task(
            email_service.send_verification_email,
            request.email,
            request.full_name or request.company_name,
            verification_token
        )
        
        logger.info(
            "user_signed_up",
            user_id=user.id,
            email=user.email,
            customer_id=str(customer.customer_id)
        )
        
        return MessageResponse(
            message="Account created! Please check your email to verify your account."
        )
    
    except Exception as e:
        logger.error("signup_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to create account. Please try again."
        )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Login with email and password.
    
    Returns JWT token for API authentication.
    """
    # Find user
    user = get_user_by_email(db, request.email)
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not verify_password(request.password, user.password_hash):
        logger.warning("login_failed_invalid_password", email=request.email)
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Account is inactive. Please contact support."
        )
    
    # Check if email is verified
    if not user.is_verified:
        raise HTTPException(
            status_code=403,
            detail="Please verify your email before logging in."
        )
    
    # Update last login
    update_last_login(db, user.id)
    
    # Create JWT token
    access_token = create_user_access_token(
        user_id=user.id,
        email=user.email,
        customer_id=str(user.customer_id)
    )
    
    logger.info(
        "user_logged_in",
        user_id=user.id,
        email=user.email
    )
    
    return LoginResponse(
        access_token=access_token,
        user={
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "customer_id": str(user.customer_id)
        }
    )


@router.get("/verify-email/{token}", response_model=MessageResponse)
async def verify_email(
    token: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Verify email address with token from email.
    
    After verification, sends welcome email with API key.
    """
    user = get_user_by_verification_token(db, token)
    
    if not user:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification token"
        )
    
    # Mark user as verified
    update_user_verification_status(db, user.id)
    
    # Generate new API key for welcome email
    # (The existing one is already stored, this is just for display)
    api_key = secrets.token_urlsafe(32)
    
    # Get customer to update API key hash
    customer = db.query(Customer).filter(Customer.customer_id == user.customer_id).first()
    if customer:
        customer.api_key_hash = hash_api_key(api_key)
        db.commit()
    
    # Send welcome email with API key
    background_tasks.add_task(
        email_service.send_welcome_email,
        user.email,
        user.full_name or "",
        api_key
    )
    
    logger.info(
        "email_verified",
        user_id=user.id,
        email=user.email
    )
    
    return MessageResponse(
        message="Email verified successfully! Check your email for your API key."
    )


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    request: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Request password reset email.
    
    Sends email with reset token (1-hour expiration).
    """
    user = get_user_by_email(db, request.email)
    
    # Always return success to prevent email enumeration
    if not user:
        logger.warning("forgot_password_unknown_email", email=request.email)
        return MessageResponse(
            message="If that email exists, a password reset link has been sent."
        )
    
    # Generate reset token
    reset_token = secrets.token_urlsafe(32)
    reset_expires = datetime.utcnow() + timedelta(hours=1)
    
    # Update user with reset token
    user.reset_token = reset_token
    user.reset_token_expires = reset_expires
    db.commit()
    
    # Send reset email
    background_tasks.add_task(
        email_service.send_password_reset_email,
        user.email,
        user.full_name or "",
        reset_token
    )
    
    logger.info(
        "password_reset_requested",
        user_id=user.id,
        email=user.email
    )
    
    return MessageResponse(
        message="If that email exists, a password reset link has been sent."
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Reset password with token from email.
    """
    user = get_user_by_reset_token(db, request.token)
    
    if not user:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired reset token"
        )
    
    # Hash new password
    new_password_hash = hash_password(request.new_password)
    
    # Update password and clear reset token
    update_user_password(db, user.id, new_password_hash)
    
    logger.info(
        "password_reset_completed",
        user_id=user.id,
        email=user.email
    )
    
    return MessageResponse(
        message="Password reset successfully! You can now log in."
    )


@router.get("/me")
async def get_current_user_info(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current authenticated user's information.
    
    Requires: Bearer token in Authorization header
    """
    # Get customer details
    customer = db.query(Customer).filter(Customer.customer_id == user.customer_id).first()
    
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "is_verified": user.is_verified,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "created_at": user.created_at.isoformat()
        },
        "customer": {
            "customer_id": str(customer.customer_id),
            "company_name": customer.company_name,
            "plan_type": customer.plan_type,
            "max_calls_per_month": customer.max_calls_per_month,
            "calls_this_month": customer.calls_this_month,
            "status": customer.status
        } if customer else None
    }
