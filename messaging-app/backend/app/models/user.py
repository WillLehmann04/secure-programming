from pydantic import Field, EmailStr
from datetime import datetime
from typing import Optional, List
from enum import Enum
from .base import BaseModel

class UserStatus(str, Enum):
    ONLINE = "online"
    AWAY = "away"
    OFFLINE = "offline"
    DND = "dnd"  # Do Not Disturb

class User(BaseModel):
    """User model for MongoDB"""
    
    # Basic info
    email: EmailStr = Field(..., unique=True, index=True)
    username: str = Field(..., min_length=3, max_length=50, unique=True, index=True)
    display_name: str = Field(..., min_length=1, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    avatar_url: Optional[str] = Field(None, max_length=500)
    
    # Security
    password_hash: str = Field(...)
    salt: str = Field(...)  # For additional security
    
    # Status
    status: UserStatus = Field(default=UserStatus.OFFLINE)
    last_seen: Optional[datetime] = Field(None)
    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=False)
    
    # Settings
    public_key: Optional[str] = Field(None)  # For E2E encryption
    private_key_encrypted: Optional[str] = Field(None)  # Encrypted private key
    
    # Preferences
    settings: dict = Field(default_factory=dict)
    
    class Settings:
        name = "users"
        indexes = [
            "email",
            "username", 
            "status",
            "last_seen"
        ]
    
    def __repr__(self):
        return f"<User(username='{self.username}', email='{self.email}')>"

class UserSession(BaseModel):
    """User session model for MongoDB"""
    
    user_id: str = Field(..., index=True)
    session_token: str = Field(..., unique=True, index=True)
    refresh_token: Optional[str] = Field(None, unique=True, index=True)
    device_info: Optional[dict] = Field(None)  # Device details as dict
    ip_address: Optional[str] = Field(None, max_length=45)  # IPv6 compatible
    user_agent: Optional[str] = Field(None)
    is_active: bool = Field(default=True)
    expires_at: datetime = Field(...)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "user_sessions"
        indexes = [
            "user_id",
            "session_token",
            "refresh_token",
            "expires_at",
            "is_active"
        ]
    
    def __repr__(self):
        return f"<UserSession(user_id='{self.user_id}', device='{self.device_info}')>"
