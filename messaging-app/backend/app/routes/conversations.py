from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from beanie import PydanticObjectId

from app.models.conversation import Conversation, ConversationParticipant, ConversationType
from app.models.user import User
from app.models.message import Message
from app.security.auth import verify_token

router = APIRouter()
security = HTTPBearer()

class CreateConversationRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    conversation_type: ConversationType
    participant_ids: List[str]

class UpdateConversationRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    avatar_url: Optional[str] = None

class AddParticipantRequest(BaseModel):
    user_id: str

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

@router.get("/")
async def get_conversations(
    current_user: User = Depends(get_current_user),
    search: Optional[str] = Query(None),
    conversation_type: Optional[ConversationType] = Query(None),
    has_unread: Optional[bool] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0)
):
    """Get user's conversations with optional filtering"""
    try:
        # Build query
        query = {'participant_ids': str(current_user.id)}
        
        if conversation_type:
            query['conversation_type'] = conversation_type
        
        if search:
            query['$or'] = [
                {'name': {'$regex': search, '$options': 'i'}},
                {'description': {'$regex': search, '$options': 'i'}}
            ]
        
        # Get conversations
        conversations = await Conversation.find(query).skip(offset).limit(limit).to_list()
        
        # Get participant details and unread counts
        result = []
        for conv in conversations:
            # Get participants
            participants = await User.find({
                '_id': {'$in': [PydanticObjectId(pid) for pid in conv.participant_ids]}
            }).to_list()
            
            # Get unread count for current user
            participant = await ConversationParticipant.find_one({
                'conversation_id': str(conv.id),
                'user_id': str(current_user.id)
            })
            
            unread_count = participant.unread_count if participant else 0
            
            # Apply unread filter
            if has_unread is not None and (unread_count > 0) != has_unread:
                continue
            
            # Get last message
            last_message = None
            if conv.last_message_id:
                last_message = await Message.get(conv.last_message_id)
            
            result.append({
                'id': str(conv.id),
                'name': conv.name,
                'description': conv.description,
                'avatar_url': conv.avatar_url,
                'conversation_type': conv.conversation_type,
                'participants': [
                    {
                        'id': str(p.id),
                        'username': p.username,
                        'display_name': p.display_name,
                        'avatar_url': p.avatar_url,
                        'status': p.status
                    } for p in participants
                ],
                'unread_count': unread_count,
                'last_message': {
                    'id': str(last_message.id),
                    'content': last_message.content,
                    'sender_id': last_message.sender_id,
                    'created_at': last_message.created_at.isoformat()
                } if last_message else None,
                'last_activity': conv.last_activity.isoformat(),
                'message_count': conv.message_count,
                'created_at': conv.created_at.isoformat()
            })
        
        return {
            'success': True,
            'conversations': result,
            'total': len(result)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get conversations: {str(e)}"
        )

@router.post("/")
async def create_conversation(
    request: CreateConversationRequest,
    current_user: User = Depends(get_current_user)
):
    """Create a new conversation"""
    try:
        # Validate participants exist
        participant_users = await User.find({
            '_id': {'$in': [PydanticObjectId(pid) for pid in request.participant_ids]}
        }).to_list()
        
        if len(participant_users) != len(request.participant_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more participants not found"
            )
        
        # Add current user to participants
        all_participant_ids = [str(current_user.id)] + request.participant_ids
        
        # Create conversation
        conversation = Conversation(
            name=request.name,
            description=request.description,
            conversation_type=request.conversation_type,
            participant_ids=all_participant_ids
        )
        
        await conversation.save()
        
        # Create participant records
        for user_id in all_participant_ids:
            is_admin = user_id == str(current_user.id)
            participant = ConversationParticipant(
                conversation_id=str(conversation.id),
                user_id=user_id,
                is_admin=is_admin,
                can_send_messages=True,
                can_add_participants=is_admin,
                can_remove_participants=is_admin,
                can_edit_conversation=is_admin
            )
            await participant.save()
        
        return {
            'success': True,
            'conversation': {
                'id': str(conversation.id),
                'name': conversation.name,
                'description': conversation.description,
                'conversation_type': conversation.conversation_type,
                'participant_ids': conversation.participant_ids,
                'created_at': conversation.created_at.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create conversation: {str(e)}"
        )

@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get conversation details"""
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
        
        # Get conversation
        conversation = await Conversation.get(conversation_id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        # Get participants
        participants = await User.find({
            '_id': {'$in': [PydanticObjectId(pid) for pid in conversation.participant_ids]}
        }).to_list()
        
        # Get participant details with permissions
        participant_details = []
        for user in participants:
            user_participant = await ConversationParticipant.find_one({
                'conversation_id': conversation_id,
                'user_id': str(user.id)
            })
            
            participant_details.append({
                'id': str(user.id),
                'username': user.username,
                'display_name': user.display_name,
                'avatar_url': user.avatar_url,
                'status': user.status,
                'is_admin': user_participant.is_admin if user_participant else False,
                'joined_at': user_participant.joined_at.isoformat() if user_participant else None
            })
        
        return {
            'success': True,
            'conversation': {
                'id': str(conversation.id),
                'name': conversation.name,
                'description': conversation.description,
                'avatar_url': conversation.avatar_url,
                'conversation_type': conversation.conversation_type,
                'participants': participant_details,
                'last_activity': conversation.last_activity.isoformat(),
                'message_count': conversation.message_count,
                'created_at': conversation.created_at.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get conversation: {str(e)}"
        )

@router.put("/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    request: UpdateConversationRequest,
    current_user: User = Depends(get_current_user)
):
    """Update conversation details"""
    try:
        # Check if user is participant and has edit permissions
        participant = await ConversationParticipant.find_one({
            'conversation_id': conversation_id,
            'user_id': str(current_user.id)
        })
        
        if not participant:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a participant in this conversation"
            )
        
        if not participant.can_edit_conversation:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to edit this conversation"
            )
        
        # Get conversation
        conversation = await Conversation.get(conversation_id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        # Update fields
        if request.name is not None:
            conversation.name = request.name
        if request.description is not None:
            conversation.description = request.description
        if request.avatar_url is not None:
            conversation.avatar_url = request.avatar_url
        
        conversation.updated_at = datetime.utcnow()
        await conversation.save()
        
        return {
            'success': True,
            'conversation': {
                'id': str(conversation.id),
                'name': conversation.name,
                'description': conversation.description,
                'avatar_url': conversation.avatar_url,
                'updated_at': conversation.updated_at.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update conversation: {str(e)}"
        )

@router.post("/{conversation_id}/participants")
async def add_participant(
    conversation_id: str,
    request: AddParticipantRequest,
    current_user: User = Depends(get_current_user)
):
    """Add participant to conversation"""
    try:
        # Check if user has permission to add participants
        participant = await ConversationParticipant.find_one({
            'conversation_id': conversation_id,
            'user_id': str(current_user.id)
        })
        
        if not participant or not participant.can_add_participants:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to add participants"
            )
        
        # Check if user to add exists
        user_to_add = await User.get(request.user_id)
        if not user_to_add:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check if user is already a participant
        existing_participant = await ConversationParticipant.find_one({
            'conversation_id': conversation_id,
            'user_id': request.user_id
        })
        
        if existing_participant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a participant"
            )
        
        # Add participant
        new_participant = ConversationParticipant(
            conversation_id=conversation_id,
            user_id=request.user_id,
            is_admin=False,
            can_send_messages=True,
            can_add_participants=False,
            can_remove_participants=False,
            can_edit_conversation=False
        )
        await new_participant.save()
        
        # Update conversation participant list
        conversation = await Conversation.get(conversation_id)
        if conversation and request.user_id not in conversation.participant_ids:
            conversation.participant_ids.append(request.user_id)
            await conversation.save()
        
        return {
            'success': True,
            'message': 'Participant added successfully',
            'participant': {
                'id': str(user_to_add.id),
                'username': user_to_add.username,
                'display_name': user_to_add.display_name
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add participant: {str(e)}"
        )

@router.delete("/{conversation_id}/participants/{user_id}")
async def remove_participant(
    conversation_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    """Remove participant from conversation"""
    try:
        # Check if user has permission to remove participants
        participant = await ConversationParticipant.find_one({
            'conversation_id': conversation_id,
            'user_id': str(current_user.id)
        })
        
        if not participant or not participant.can_remove_participants:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to remove participants"
            )
        
        # Check if user to remove is a participant
        participant_to_remove = await ConversationParticipant.find_one({
            'conversation_id': conversation_id,
            'user_id': user_id
        })
        
        if not participant_to_remove:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User is not a participant in this conversation"
            )
        
        # Remove participant
        await participant_to_remove.delete()
        
        # Update conversation participant list
        conversation = await Conversation.get(conversation_id)
        if conversation and user_id in conversation.participant_ids:
            conversation.participant_ids.remove(user_id)
            await conversation.save()
        
        return {
            'success': True,
            'message': 'Participant removed successfully'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove participant: {str(e)}"
        )

@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete conversation"""
    try:
        # Check if user is admin
        participant = await ConversationParticipant.find_one({
            'conversation_id': conversation_id,
            'user_id': str(current_user.id)
        })
        
        if not participant or not participant.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to delete this conversation"
            )
        
        # Delete conversation and all related data
        conversation = await Conversation.get(conversation_id)
        if conversation:
            await conversation.delete()
        
        # Delete all participants
        await ConversationParticipant.find({
            'conversation_id': conversation_id
        }).delete()
        
        # Delete all messages
        await Message.find({
            'conversation_id': conversation_id
        }).delete()
        
        return {
            'success': True,
            'message': 'Conversation deleted successfully'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete conversation: {str(e)}"
        )
