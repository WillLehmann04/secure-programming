from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from beanie import PydanticObjectId

from app.models.message import Message, MessageType, MessageStatus
from app.models.conversation import Conversation, ConversationParticipant
from app.models.user import User
from app.security.auth import verify_token

router = APIRouter()
security = HTTPBearer()

class SendMessageRequest(BaseModel):
    content: str
    message_type: MessageType = MessageType.TEXT
    reply_to_id: Optional[str] = None
    thread_id: Optional[str] = None
    encrypt: bool = False

class EditMessageRequest(BaseModel):
    content: str

class AddReactionRequest(BaseModel):
    emoji: str

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user from JWT token"""
    token = credentials.credentials
    payload = verify_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    user_id = payload.get('user_id')
    user = await User.get(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user

@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    before: Optional[str] = Query(None)
):
    """Get messages from a conversation"""
    try:
        # Check if user is participant
        participant = await ConversationParticipant.find_one({
            'conversation_id': conversation_id,
            'user_id': str(current_user.id)
        })
        
        if not participant:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a participant in this conversation"
            )
        
        # Build query
        query = {'conversation_id': conversation_id}
        
        if before:
            try:
                before_date = datetime.fromisoformat(before.replace('Z', '+00:00'))
                query['created_at'] = {'$lt': before_date}
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid before date format"
                )
        
        # Get messages
        messages = await Message.find(query).sort('-created_at').skip(offset).limit(limit).to_list()
        
        # Get sender information
        sender_ids = list(set(msg.sender_id for msg in messages))
        senders = await User.find({
            '_id': {'$in': [PydanticObjectId(sid) for sid in sender_ids]}
        }).to_list()
        
        sender_map = {str(sender.id): sender for sender in senders}
        
        # Format messages
        result = []
        for message in messages:
            sender = sender_map.get(message.sender_id)
            
            result.append({
                'id': str(message.id),
                'conversation_id': message.conversation_id,
                'sender': {
                    'id': message.sender_id,
                    'username': sender.username if sender else 'Unknown',
                    'display_name': sender.display_name if sender else 'Unknown User',
                    'avatar_url': sender.avatar_url if sender else None
                },
                'content': message.content,
                'message_type': message.message_type,
                'status': message.status,
                'is_edited': message.is_edited,
                'edited_at': message.edited_at.isoformat() if message.edited_at else None,
                'is_pinned': message.is_pinned,
                'is_starred': message.is_starred,
                'reply_to_id': message.reply_to_id,
                'thread_id': message.thread_id,
                'attachments': message.attachments,
                'reactions': message.reactions,
                'created_at': message.created_at.isoformat(),
                'updated_at': message.updated_at.isoformat()
            })
        
        return {
            'success': True,
            'messages': result,
            'has_more': len(messages) == limit
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get messages: {str(e)}"
        )

@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    request: SendMessageRequest,
    current_user: User = Depends(get_current_user)
):
    """Send a message to a conversation"""
    try:
        # Check if user is participant
        participant = await ConversationParticipant.find_one({
            'conversation_id': conversation_id,
            'user_id': str(current_user.id)
        })
        
        if not participant:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a participant in this conversation"
            )
        
        if not participant.can_send_messages:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to send messages"
            )
        
        # Create message
        message = Message(
            conversation_id=conversation_id,
            sender_id=str(current_user.id),
            content=request.content,
            message_type=request.message_type,
            status=MessageStatus.SENDING,
            reply_to_id=request.reply_to_id,
            thread_id=request.thread_id
        )
        
        await message.save()
        
        # Update conversation
        conversation = await Conversation.get(conversation_id)
        if conversation:
            conversation.last_message_id = str(message.id)
            conversation.last_activity = datetime.utcnow()
            conversation.message_count += 1
            await conversation.save()
        
        # Update unread counts for other participants
        other_participants = await ConversationParticipant.find({
            'conversation_id': conversation_id,
            'user_id': {'$ne': str(current_user.id)}
        }).to_list()
        
        for participant in other_participants:
            participant.unread_count += 1
            await participant.save()
        
        return {
            'success': True,
            'message': {
                'id': str(message.id),
                'conversation_id': message.conversation_id,
                'sender_id': message.sender_id,
                'content': message.content,
                'message_type': message.message_type,
                'status': message.status,
                'created_at': message.created_at.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {str(e)}"
        )

@router.put("/{message_id}")
async def edit_message(
    message_id: str,
    request: EditMessageRequest,
    current_user: User = Depends(get_current_user)
):
    """Edit a message"""
    try:
        # Get message
        message = await Message.get(message_id)
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found"
            )
        
        # Check if user is the sender
        if message.sender_id != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only edit your own messages"
            )
        
        # Update message
        message.content = request.content
        message.is_edited = True
        message.edited_at = datetime.utcnow()
        message.updated_at = datetime.utcnow()
        
        await message.save()
        
        return {
            'success': True,
            'message': {
                'id': str(message.id),
                'content': message.content,
                'is_edited': message.is_edited,
                'edited_at': message.edited_at.isoformat(),
                'updated_at': message.updated_at.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to edit message: {str(e)}"
        )

@router.delete("/{message_id}")
async def delete_message(
    message_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a message"""
    try:
        # Get message
        message = await Message.get(message_id)
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found"
            )
        
        # Check if user is the sender or has admin permissions
        participant = await ConversationParticipant.find_one({
            'conversation_id': message.conversation_id,
            'user_id': str(current_user.id)
        })
        
        if message.sender_id != str(current_user.id) and (not participant or not participant.is_admin):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to delete this message"
            )
        
        # Soft delete - mark as deleted
        message.status = MessageStatus.DELETED
        message.content = "[Message deleted]"
        message.updated_at = datetime.utcnow()
        
        await message.save()
        
        return {
            'success': True,
            'message': 'Message deleted successfully'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete message: {str(e)}"
        )

@router.post("/{message_id}/reactions")
async def add_reaction(
    message_id: str,
    request: AddReactionRequest,
    current_user: User = Depends(get_current_user)
):
    """Add reaction to a message"""
    try:
        # Get message
        message = await Message.get(message_id)
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found"
            )
        
        # Check if user is participant in conversation
        participant = await ConversationParticipant.find_one({
            'conversation_id': message.conversation_id,
            'user_id': str(current_user.id)
        })
        
        if not participant:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a participant in this conversation"
            )
        
        # Remove existing reaction from same user
        message.reactions = [r for r in message.reactions if r.get('user_id') != str(current_user.id)]
        
        # Add new reaction
        reaction = {
            'user_id': str(current_user.id),
            'emoji': request.emoji,
            'timestamp': datetime.utcnow().isoformat()
        }
        message.reactions.append(reaction)
        
        await message.save()
        
        return {
            'success': True,
            'reaction': reaction
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add reaction: {str(e)}"
        )

@router.delete("/{message_id}/reactions/{emoji}")
async def remove_reaction(
    message_id: str,
    emoji: str,
    current_user: User = Depends(get_current_user)
):
    """Remove reaction from a message"""
    try:
        # Get message
        message = await Message.get(message_id)
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found"
            )
        
        # Check if user is participant in conversation
        participant = await ConversationParticipant.find_one({
            'conversation_id': message.conversation_id,
            'user_id': str(current_user.id)
        })
        
        if not participant:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a participant in this conversation"
            )
        
        # Remove reaction
        message.reactions = [r for r in message.reactions if not (r.get('user_id') == str(current_user.id) and r.get('emoji') == emoji)]
        
        await message.save()
        
        return {
            'success': True,
            'message': 'Reaction removed successfully'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove reaction: {str(e)}"
        )

@router.post("/{message_id}/read")
async def mark_message_read(
    message_id: str,
    current_user: User = Depends(get_current_user)
):
    """Mark a message as read"""
    try:
        # Get message
        message = await Message.get(message_id)
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found"
            )
        
        # Check if user is participant in conversation
        participant = await ConversationParticipant.find_one({
            'conversation_id': message.conversation_id,
            'user_id': str(current_user.id)
        })
        
        if not participant:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a participant in this conversation"
            )
        
        # Update participant's last read message
        participant.last_read_message_id = message_id
        participant.unread_count = 0
        await participant.save()
        
        # Update message status
        message.status = MessageStatus.READ
        await message.save()
        
        return {
            'success': True,
            'message': 'Message marked as read'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark message as read: {str(e)}"
        )
