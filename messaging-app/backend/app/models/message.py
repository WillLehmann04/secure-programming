from pydantic import Field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from .base import BaseModel

class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    SYSTEM = "system"
    CALL = "call"
    POLL = "poll"

class MessageStatus(str, Enum):
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    EDITED = "edited"
    DELETED = "deleted"

class Message(BaseModel):
    """Message model for MongoDB"""
    
    # Basic info
    conversation_id: str = Field(..., index=True)
    sender_id: str = Field(..., index=True)
    content: Optional[str] = Field(None)  # Null for system messages
    message_type: MessageType = Field(default=MessageType.TEXT)
    
    # Status and metadata
    status: MessageStatus = Field(default=MessageStatus.SENDING)
    is_edited: bool = Field(default=False)
    edited_at: Optional[datetime] = Field(None)
    is_pinned: bool = Field(default=False)
    is_starred: bool = Field(default=False)
    
    # Threading
    reply_to_id: Optional[str] = Field(None, index=True)
    thread_id: Optional[str] = Field(None, index=True)  # For threaded conversations
    
    # Encryption
    encrypted_content: Optional[str] = Field(None)  # Encrypted message content
    encryption_iv: Optional[str] = Field(None)  # Initialization vector
    
    # Delivery tracking
    delivery_attempts: int = Field(default=0)
    last_delivery_attempt: Optional[datetime] = Field(None)
    delivery_failures: int = Field(default=0)
    
    # Metadata
    metadata: Optional[Dict[str, Any]] = Field(None)  # Additional message data
    
    # Attachments (embedded for better performance)
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Reactions (embedded for better performance)
    reactions: List[Dict[str, Any]] = Field(default_factory=list)
    
    class Settings:
        name = "messages"
        indexes = [
            "conversation_id",
            "sender_id",
            "created_at",
            "reply_to_id",
            "thread_id",
            "status",
            ("conversation_id", "created_at"),  # Compound index for conversation messages
            ("conversation_id", "status")  # Compound index for message status
        ]
    
    def __repr__(self):
        return f"<Message(id='{self.id}', content='{self.content[:50] if self.content else None}...')>"

class MessageAttachment(BaseModel):
    """Message attachment model for MongoDB"""
    
    message_id: str = Field(..., index=True)
    file_name: str = Field(..., max_length=255)
    file_size: int = Field(...)
    mime_type: str = Field(..., max_length=100)
    file_url: str = Field(..., max_length=500)
    thumbnail_url: Optional[str] = Field(None, max_length=500)
    
    # Encryption
    encrypted_file_url: Optional[str] = Field(None, max_length=500)
    file_hash: str = Field(..., max_length=64)  # SHA-256 hash for integrity
    
    # Metadata
    width: Optional[int] = Field(None)  # For images/videos
    height: Optional[int] = Field(None)  # For images/videos
    duration: Optional[int] = Field(None)  # For audio/video in seconds
    
    class Settings:
        name = "message_attachments"
        indexes = [
            "message_id",
            "file_hash",
            "mime_type"
        ]
    
    def __repr__(self):
        return f"<MessageAttachment(file_name='{self.file_name}', size={self.file_size})>"

class MessageReaction(BaseModel):
    """Message reaction model for MongoDB"""
    
    message_id: str = Field(..., index=True)
    user_id: str = Field(..., index=True)
    emoji: str = Field(..., max_length=10)  # Unicode emoji
    
    class Settings:
        name = "message_reactions"
        indexes = [
            "message_id",
            "user_id",
            ("message_id", "user_id"),  # Compound index
            ("message_id", "emoji")  # Compound index for emoji reactions
        ]
    
    def __repr__(self):
        return f"<MessageReaction(emoji='{self.emoji}', user_id='{self.user_id}')>"
