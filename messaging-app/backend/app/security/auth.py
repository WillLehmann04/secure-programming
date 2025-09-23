from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.hash import bcrypt
import secrets
import hashlib

from app.config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt with salt"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create a JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
    """Verify and decode a JWT token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        # Check token type
        if payload.get("type") != token_type:
            return None
            
        # Check expiration
        if datetime.utcnow() > datetime.fromtimestamp(payload.get("exp", 0)):
            return None
            
        return payload
    except JWTError:
        return None

def generate_session_token() -> str:
    """Generate a secure session token"""
    return secrets.token_urlsafe(32)

def generate_salt() -> str:
    """Generate a random salt for additional security"""
    return secrets.token_hex(16)

def hash_with_salt(data: str, salt: str) -> str:
    """Hash data with a salt using SHA-256"""
    return hashlib.sha256((data + salt).encode()).hexdigest()

def verify_session_token(token: str, stored_hash: str, salt: str) -> bool:
    """Verify a session token against stored hash"""
    token_hash = hash_with_salt(token, salt)
    return token_hash == stored_hash

def create_session_hash(token: str, salt: str) -> str:
    """Create a hash of the session token with salt"""
    return hash_with_salt(token, salt)

def is_token_expired(exp: int) -> bool:
    """Check if a token is expired"""
    return datetime.utcnow() > datetime.fromtimestamp(exp)

def get_token_remaining_time(exp: int) -> int:
    """Get remaining time in seconds for a token"""
    remaining = datetime.fromtimestamp(exp) - datetime.utcnow()
    return max(0, int(remaining.total_seconds()))
