from pydantic import Field
from datetime import datetime
from typing import Optional, List
from enum import Enum
from .base import BaseModel

class ConversationType(str, Enum):
    DM = "dm"  # Direct Message
    GROUP = "group"
    CHANNEL = "channel"

class Conversation(BaseModel):
    """Conversation model for MongoDB"""
    
    # Basic info
    name: Optional[str] = Field(None, max_length=100)  # Null for DMs
    description: Optional[str] = Field(None, max_length=1000)
    avatar_url: Optional[str] = Field(None, max_length=500)
    conversation_type: ConversationType = Field(...)
    
    # Settings
    is_public: bool = Field(default=False)
    is_archived: bool = Field(default=False)
    is_muted: bool = Field(default=False)
    
    # Encryption
    encryption_key: Optional[str] = Field(None)  # For group/channel encryption
    
    # Metadata
    last_message_id: Optional[str] = Field(None)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    message_count: int = Field(default=0)
    
    # Participants (embedded for better performance)
    participant_ids: List[str] = Field(default_factory=list, index=True)
    
    class Settings:
        name = "conversations"
        indexes = [
            "conversation_type",
            "participant_ids",
            "last_activity",
            "is_archived"
        ]
    
    def __repr__(self):
        return f"<Conversation(name='{self.name}', type='{self.conversation_type}')>"

class ConversationParticipant(BaseModel):
    """Conversation participant model for MongoDB"""
    
    conversation_id: str = Field(..., index=True)
    user_id: str = Field(..., index=True)
    
    # Permissions
    is_admin: bool = Field(default=False)
    can_send_messages: bool = Field(default=True)
    can_add_participants: bool = Field(default=False)
    can_remove_participants: bool = Field(default=False)
    can_edit_conversation: bool = Field(default=False)
    
    # Status
    joined_at: datetime = Field(default_factory=datetime.utcnow)
    last_read_message_id: Optional[str] = Field(None)
    unread_count: int = Field(default=0)
    is_muted: bool = Field(default=False)
    is_pinned: bool = Field(default=False)
    
    class Settings:
        name = "conversation_participants"
        indexes = [
            "conversation_id",
            "user_id",
            ("conversation_id", "user_id"),  # Compound index
            "is_pinned",
            "is_muted"
        ]
    
    def __repr__(self):
        return f"<ConversationParticipant(conversation_id='{self.conversation_id}', user_id='{self.user_id}')>"
