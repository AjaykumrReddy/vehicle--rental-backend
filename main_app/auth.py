from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
import random
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv
from .logging_config import get_logger

load_dotenv()
logger = get_logger(__name__)

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
OTP_EXPIRE_MINUTES = int(os.getenv("OTP_EXPIRE_MINUTES", "5"))
ACCESS_TOKEN_EXPIRE_DAYS = int(os.getenv("ACCESS_TOKEN_EXPIRE_DAYS", "30"))

def generate_otp() -> str:
    """Generate 6-digit OTP"""
    return str(random.randint(100000, 999999))

def is_otp_valid(otp_expires_at: datetime) -> bool:
    """Check if OTP is still valid"""
    return datetime.now(timezone.utc) < otp_expires_at

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create long-lived JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    logger.info(f"Access token created", extra={
        "user_id": data.get("sub"),
        "phone": data.get("phone"),
        "expires_at": expire.isoformat(),
        "token_type": "access_token"
    })
    
    return encoded_jwt

security = HTTPBearer()

def verify_token(token: str) -> dict:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        logger.debug(f"Token verified successfully", extra={
            "user_id": payload.get("sub"),
            "phone": payload.get("phone"),
            "token_exp": payload.get("exp")
        })
        
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning(f"Expired token verification attempt", extra={
            "token_prefix": token[:20] + "..." if len(token) > 20 else token,
            "error_type": "expired_token"
        })
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.JWTError as e:
        logger.warning(f"Invalid token verification attempt", extra={
            "token_prefix": token[:20] + "..." if len(token) > 20 else token,
            "error_type": "invalid_token",
            "jwt_error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user from JWT token"""
    payload = verify_token(credentials.credentials)
    user_id = payload.get("sub")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    return {"user_id": user_id, "phone": payload.get("phone")}