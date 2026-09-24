"""
Authentication and Authorization Middleware
Handles API key validation, JWT tokens, and customer authentication
"""
import os
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, Security, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
import structlog

logger = structlog.get_logger(__name__)

# Security configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-secret-key-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
API_KEY_SALT = os.getenv("API_KEY_SALT", "change-this-salt-in-production")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


# Password hashing functions
def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


# API key functions
def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage"""
    return hashlib.pbkdf2_hmac(
        'sha256',
        api_key.encode('utf-8'),
        API_KEY_SALT.encode('utf-8'),
        100000
    ).hex()


def verify_api_key(api_key: str, hashed_key: str) -> bool:
    """Verify an API key against its hash"""
    return hmac.compare_digest(hash_api_key(api_key), hashed_key)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as e:
        logger.error("jwt_decode_error", error=str(e))
        raise HTTPException(status_code=401, detail="Invalid authentication token")


async def get_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    """Dependency to extract API key from header"""
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Provide X-API-Key header."
        )
    return x_api_key


from database import get_db

async def get_current_customer(
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """
    Validate API key and return customer information.
    This dependency should be used on all protected endpoints.
    """
    from models import Customer  # Import here to avoid circular dependency
    
    # Hash the provided API key
    api_key_hash = hash_api_key(api_key)
    
    # Look up customer by API key hash
    customer = db.query(Customer).filter(
        Customer.api_key_hash == api_key_hash,
        Customer.status == "active"
    ).first()
    
    if not customer:
        logger.warning("invalid_api_key_attempt")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key or inactive account"
        )
    
    # Check usage limits
    if customer.calls_this_month >= customer.max_calls_per_month:
        logger.warning(
            "rate_limit_exceeded",
            customer_id=str(customer.customer_id),
            calls_this_month=customer.calls_this_month,
            max_calls=customer.max_calls_per_month
        )
        raise HTTPException(
            status_code=429,
            detail=f"Monthly call limit reached ({customer.max_calls_per_month} calls). Please upgrade your plan."
        )
    
    logger.info(
        "customer_authenticated",
        customer_id=str(customer.customer_id),
        company_name=customer.company_name
    )
    
    return customer


async def get_optional_customer(
    x_api_key: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> Optional["Customer"]:  # type: ignore
    """
    Optional authentication - returns customer if API key is provided, None otherwise.
    Use for endpoints that work both authenticated and unauthenticated.
    """
    if not x_api_key:
        return None
    
    try:
        return await get_current_customer(x_api_key, db)
    except HTTPException:
        return None


async def require_jwt_token(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> dict:
    """
    Validate JWT token from Authorization header.
    Use for admin endpoints or service-to-service communication.
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    return payload


def check_permission(customer, required_permission: str) -> bool:
    """
    Check if customer has specific permission based on plan.
    """
    plan_permissions = {
        "free": ["basic_calls"],
        "starter": ["basic_calls", "appointment_booking"],
        "pro": ["basic_calls", "appointment_booking", "analytics", "webhooks"],
        "enterprise": ["basic_calls", "appointment_booking", "analytics", "webhooks", "custom_models", "priority_support"]
    }
    
    customer_permissions = plan_permissions.get(customer.plan_type, [])
    return required_permission in customer_permissions


def require_permission(permission: str):
    """
    Decorator/dependency to require specific permission.
    Usage: customer = Depends(require_permission("analytics"))
    """
    async def permission_checker(customer = Depends(get_current_customer)):
        if not check_permission(customer, permission):
            raise HTTPException(
                status_code=403,
                detail=f"This feature requires {permission} permission. Please upgrade your plan."
            )
        return customer
    return permission_checker


# User authentication (email/password + JWT)
def create_user_access_token(user_id: int, email: str, customer_id: str) -> str:
    """
    Create JWT access token for user authentication.
    
    Args:
        user_id: User's database ID
        email: User's email
        customer_id: Associated customer UUID
    
    Returns:
        JWT token string
    """
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    
    payload = {
        "sub": str(user_id),
        "email": email,
        "customer_id": str(customer_id),
        "exp": expire,
        "iat": datetime.utcnow()
    }
    
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token


def decode_user_token(token: str) -> Optional[dict]:
    """
    Decode and validate JWT token.
    
    Returns:
        Token payload dict or None if invalid
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db)
):
    """
    Get current authenticated user from JWT token.
    
    Args:
        credentials: Bearer token from Authorization header
        db: Database session
    
    Returns:
        User object if authenticated
    
    Raises:
        HTTPException: 401 if token invalid
    """
    from models import get_user_by_id
    
    token = credentials.credentials
    payload = decode_user_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid token payload"
        )
    
    user = get_user_by_id(db, int(user_id))
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="User not found or inactive"
        )
    
    logger.info(
        "user_authenticated",
        user_id=user.id,
        email=user.email
    )
    
    return user
