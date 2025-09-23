import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from websockets import WebSocketServerProtocol

from app.models.message import Message, MessageType, MessageStatus
from app.models.conversation import Conversation, ConversationParticipant
from app.models.user import User
from app.websockets.connection_manager import connection_manager
from app.websockets.encryption_handler import encryption_handler
from app.security.validation import validate_message

logger = logging.getLogger(__name__)

class MessageHandler:
    """Handles WebSocket message processing and routing"""
    
    def __init__(self):
        self.typing_users: Dict[str, Dict[str, datetime]] = {}  # {conversation_id: {user_id: timestamp}}
        self.message_acks: Dict[str, Dict[str, bool]] = {}  # {message_id: {user_id: acked}}
    
    def get_current_time(self) -> str:
        """Get current timestamp in ISO format"""
        return datetime.utcnow().isoformat()
    
    async def handle_message(self, user_id: str, session_id: str, message_data: Dict[str, Any], websocket: WebSocketServerProtocol) -> Optional[Dict[str, Any]]:
        """Handle incoming WebSocket message"""
        try:
            message_type = message_data.get('type')
            
            if message_type == 'ping':
                return await self.handle_ping(user_id, session_id, message_data)
            elif message_type == 'message':
                return await self.handle_send_message(user_id, session_id, message_data)
            elif message_type == 'typing_start':
                return await self.handle_typing_start(user_id, session_id, message_data)
            elif message_type == 'typing_stop':
                return await self.handle_typing_stop(user_id, session_id, message_data)
            elif message_type == 'message_ack':
                return await self.handle_message_ack(user_id, session_id, message_data)
            elif message_type == 'message_read':
                return await self.handle_message_read(user_id, session_id, message_data)
            elif message_type == 'reaction':
                return await self.handle_reaction(user_id, session_id, message_data)
            elif message_type == 'presence_update':
                return await self.handle_presence_update(user_id, session_id, message_data)
            elif message_type == 'key_exchange':
                return await self.handle_key_exchange(user_id, session_id, message_data)
            else:
                return {
                    'type': 'error',
                    'message': f'Unknown message type: {message_type}',
                    'timestamp': self.get_current_time()
                }
                
        except Exception as e:
            logger.error(f"Error handling message for user {user_id}: {e}")
            return {
                'type': 'error',
                'message': 'Failed to process message',
                'timestamp': self.get_current_time()
            }
    
    async def handle_ping(self, user_id: str, session_id: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ping message for connection keep-alive"""
        await connection_manager.update_activity(user_id, session_id)
        return {
            'type': 'pong',
            'timestamp': self.get_current_time()
        }
    
    async def handle_send_message(self, user_id: str, session_id: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle sending a new message"""
        try:
            conversation_id = message_data.get('conversation_id')
            content = message_data.get('content', '')
            message_type = message_data.get('message_type', 'text')
            reply_to_id = message_data.get('reply_to_id')
            thread_id = message_data.get('thread_id')
            
            if not conversation_id:
                return {
                    'type': 'error',
                    'message': 'conversation_id is required',
                    'timestamp': self.get_current_time()
                }
            
            # Validate message content
            validation_result = validate_message(content, message_type)
            if not validation_result['is_valid']:
                return {
                    'type': 'error',
                    'message': f"Message validation failed: {', '.join(validation_result['errors'])}",
                    'timestamp': self.get_current_time()
                }
            
            # Sanitize content
            sanitized_content = validation_result['sanitized_content']
            
            # Check if user is participant in conversation
            participant = await ConversationParticipant.find_one({
                'conversation_id': conversation_id,
                'user_id': user_id
            })
            
            if not participant:
                return {
                    'type': 'error',
                    'message': 'You are not a participant in this conversation',
                    'timestamp': self.get_current_time()
                }
            
            # Create message
            message = Message(
                conversation_id=conversation_id,
                sender_id=user_id,
                content=sanitized_content,
                message_type=MessageType(message_type),
                status=MessageStatus.SENDING,
                reply_to_id=reply_to_id,
                thread_id=thread_id
            )
            
            # Encrypt message if needed
            if message_data.get('encrypt', False):
                encrypted_data = encryption_handler.encrypt_message_for_conversation(
                    sanitized_content, conversation_id
                )
                message.encrypted_content = encrypted_data['encrypted_message']
                message.encryption_iv = encrypted_data['iv']
                message.content = None  # Clear plain text
            
            # Save message
            await message.save()
            
            # Update conversation
            conversation = await Conversation.get(conversation_id)
            if conversation:
                conversation.last_message_id = str(message.id)
                conversation.last_activity = datetime.utcnow()
                conversation.message_count += 1
                await conversation.save()
            
            # Broadcast message to all participants
            await self.broadcast_message_to_conversation(conversation_id, message, user_id)
            
            # Update message status to sent
            message.status = MessageStatus.SENT
            await message.save()
            
            return {
                'type': 'message_sent',
                'message_id': str(message.id),
                'conversation_id': conversation_id,
                'timestamp': self.get_current_time()
            }
            
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return {
                'type': 'error',
                'message': 'Failed to send message',
                'timestamp': self.get_current_time()
            }
    
    async def handle_typing_start(self, user_id: str, session_id: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle typing start indicator"""
        conversation_id = message_data.get('conversation_id')
        
        if not conversation_id:
            return {
                'type': 'error',
                'message': 'conversation_id is required',
                'timestamp': self.get_current_time()
            }
        
        # Update typing users
        if conversation_id not in self.typing_users:
            self.typing_users[conversation_id] = {}
        
        self.typing_users[conversation_id][user_id] = datetime.utcnow()
        
        # Broadcast typing indicator to other participants
        await self.broadcast_typing_indicator(conversation_id, user_id, True)
        
        return {
            'type': 'typing_started',
            'conversation_id': conversation_id,
            'timestamp': self.get_current_time()
        }
    
    async def handle_typing_stop(self, user_id: str, session_id: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle typing stop indicator"""
        conversation_id = message_data.get('conversation_id')
        
        if not conversation_id:
            return {
                'type': 'error',
                'message': 'conversation_id is required',
                'timestamp': self.get_current_time()
            }
        
        # Remove from typing users
        if conversation_id in self.typing_users and user_id in self.typing_users[conversation_id]:
            del self.typing_users[conversation_id][user_id]
        
        # Broadcast typing stop to other participants
        await self.broadcast_typing_indicator(conversation_id, user_id, False)
        
        return {
            'type': 'typing_stopped',
            'conversation_id': conversation_id,
            'timestamp': self.get_current_time()
        }
    
    async def handle_message_ack(self, user_id: str, session_id: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle message acknowledgment"""
        message_id = message_data.get('message_id')
        
        if not message_id:
            return {
                'type': 'error',
                'message': 'message_id is required',
                'timestamp': self.get_current_time()
            }
        
        # Update message ACK tracking
        if message_id not in self.message_acks:
            self.message_acks[message_id] = {}
        
        self.message_acks[message_id][user_id] = True
        
        # Update message status to delivered
        message = await Message.get(message_id)
        if message:
            message.status = MessageStatus.DELIVERED
            await message.save()
        
        return {
            'type': 'message_acked',
            'message_id': message_id,
            'timestamp': self.get_current_time()
        }
    
    async def handle_message_read(self, user_id: str, session_id: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle message read receipt"""
        message_id = message_data.get('message_id')
        conversation_id = message_data.get('conversation_id')
        
        if not message_id or not conversation_id:
            return {
                'type': 'error',
                'message': 'message_id and conversation_id are required',
                'timestamp': self.get_current_time()
            }
        
        # Update participant's last read message
        participant = await ConversationParticipant.find_one({
            'conversation_id': conversation_id,
            'user_id': user_id
        })
        
        if participant:
            participant.last_read_message_id = message_id
            participant.unread_count = 0
            await participant.save()
        
        # Update message status to read
        message = await Message.get(message_id)
        if message:
            message.status = MessageStatus.READ
            await message.save()
        
        return {
            'type': 'message_read',
            'message_id': message_id,
            'conversation_id': conversation_id,
            'timestamp': self.get_current_time()
        }
    
    async def handle_reaction(self, user_id: str, session_id: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle message reaction"""
        message_id = message_data.get('message_id')
        emoji = message_data.get('emoji')
        action = message_data.get('action', 'add')  # add or remove
        
        if not message_id or not emoji:
            return {
                'type': 'error',
                'message': 'message_id and emoji are required',
                'timestamp': self.get_current_time()
            }
        
        message = await Message.get(message_id)
        if not message:
            return {
                'type': 'error',
                'message': 'Message not found',
                'timestamp': self.get_current_time()
            }
        
        if action == 'add':
            # Add reaction
            reaction = {
                'user_id': user_id,
                'emoji': emoji,
                'timestamp': self.get_current_time()
            }
            
            # Remove existing reaction from same user
            message.reactions = [r for r in message.reactions if r.get('user_id') != user_id]
            message.reactions.append(reaction)
            
        elif action == 'remove':
            # Remove reaction
            message.reactions = [r for r in message.reactions if not (r.get('user_id') == user_id and r.get('emoji') == emoji)]
        
        await message.save()
        
        # Broadcast reaction to conversation
        await self.broadcast_reaction_to_conversation(message.conversation_id, message_id, reaction if action == 'add' else None, user_id)
        
        return {
            'type': 'reaction_updated',
            'message_id': message_id,
            'emoji': emoji,
            'action': action,
            'timestamp': self.get_current_time()
        }
    
    async def handle_presence_update(self, user_id: str, session_id: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle user presence update"""
        status = message_data.get('status')
        
        if not status:
            return {
                'type': 'error',
                'message': 'status is required',
                'timestamp': self.get_current_time()
            }
        
        # Update user status in database
        user = await User.get(user_id)
        if user:
            user.status = status
            user.last_seen = datetime.utcnow()
            await user.save()
        
        # Broadcast presence update to user's conversations
        await self.broadcast_presence_update(user_id, status)
        
        return {
            'type': 'presence_updated',
            'status': status,
            'timestamp': self.get_current_time()
        }
    
    async def handle_key_exchange(self, user_id: str, session_id: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle key exchange for E2E encryption"""
        action = message_data.get('action')
        
        if action == 'initiate':
            recipient_id = message_data.get('recipient_id')
            if not recipient_id:
                return {
                    'type': 'error',
                    'message': 'recipient_id is required',
                    'timestamp': self.get_current_time()
                }
            
            exchange_id = encryption_handler.initiate_key_exchange(user_id, recipient_id)
            
            return {
                'type': 'key_exchange_initiated',
                'exchange_id': exchange_id,
                'timestamp': self.get_current_time()
            }
        
        elif action == 'complete':
            exchange_id = message_data.get('exchange_id')
            public_key = message_data.get('public_key')
            
            if not exchange_id or not public_key:
                return {
                    'type': 'error',
                    'message': 'exchange_id and public_key are required',
                    'timestamp': self.get_current_time()
                }
            
            try:
                result = encryption_handler.complete_key_exchange(exchange_id, public_key)
                return {
                    'type': 'key_exchange_completed',
                    'exchange_id': exchange_id,
                    'encrypted_secret': result['encrypted_secret'],
                    'ephemeral_public': result['ephemeral_public'],
                    'timestamp': self.get_current_time()
                }
            except Exception as e:
                return {
                    'type': 'error',
                    'message': f'Key exchange failed: {str(e)}',
                    'timestamp': self.get_current_time()
                }
        
        else:
            return {
                'type': 'error',
                'message': 'Invalid key exchange action',
                'timestamp': self.get_current_time()
            }
    
    async def handle_public_message(self, channel: str, message_data: Dict[str, Any], websocket: WebSocketServerProtocol) -> Optional[Dict[str, Any]]:
        """Handle public channel messages"""
        message_type = message_data.get('type')
        
        if message_type == 'subscribe':
            # Handle channel subscription
            return {
                'type': 'subscribed',
                'channel': channel,
                'timestamp': self.get_current_time()
            }
        
        elif message_type == 'announcement':
            # Handle system announcements
            return {
                'type': 'announcement_received',
                'channel': channel,
                'message': message_data.get('message'),
                'timestamp': self.get_current_time()
            }
        
        return None
    
    async def broadcast_message_to_conversation(self, conversation_id: str, message: Message, sender_id: str):
        """Broadcast message to all participants in a conversation"""
        participants = await ConversationParticipant.find({
            'conversation_id': conversation_id
        }).to_list()
        
        message_data = {
            'type': 'new_message',
            'message': {
                'id': str(message.id),
                'conversation_id': conversation_id,
                'sender_id': message.sender_id,
                'content': message.content,
                'message_type': message.message_type,
                'status': message.status,
                'created_at': message.created_at.isoformat(),
                'reply_to_id': message.reply_to_id,
                'thread_id': message.thread_id,
                'attachments': message.attachments,
                'reactions': message.reactions
            },
            'timestamp': self.get_current_time()
        }
        
        for participant in participants:
            if participant.user_id != sender_id:
                await connection_manager.send_to_user(participant.user_id, message_data)
    
    async def broadcast_typing_indicator(self, conversation_id: str, user_id: str, is_typing: bool):
        """Broadcast typing indicator to conversation participants"""
        participants = await ConversationParticipant.find({
            'conversation_id': conversation_id
        }).to_list()
        
        message_data = {
            'type': 'typing_indicator',
            'conversation_id': conversation_id,
            'user_id': user_id,
            'is_typing': is_typing,
            'timestamp': self.get_current_time()
        }
        
        for participant in participants:
            if participant.user_id != user_id:
                await connection_manager.send_to_user(participant.user_id, message_data)
    
    async def broadcast_reaction_to_conversation(self, conversation_id: str, message_id: str, reaction: Optional[Dict], user_id: str):
        """Broadcast reaction update to conversation participants"""
        participants = await ConversationParticipant.find({
            'conversation_id': conversation_id
        }).to_list()
        
        message_data = {
            'type': 'reaction_update',
            'conversation_id': conversation_id,
            'message_id': message_id,
            'reaction': reaction,
            'user_id': user_id,
            'timestamp': self.get_current_time()
        }
        
        for participant in participants:
            await connection_manager.send_to_user(participant.user_id, message_data)
    
    async def broadcast_presence_update(self, user_id: str, status: str):
        """Broadcast presence update to user's conversations"""
        # Get all conversations where user is a participant
        participants = await ConversationParticipant.find({
            'user_id': user_id
        }).to_list()
        
        message_data = {
            'type': 'presence_update',
            'user_id': user_id,
            'status': status,
            'timestamp': self.get_current_time()
        }
        
        for participant in participants:
            # Get other participants in the same conversation
            other_participants = await ConversationParticipant.find({
                'conversation_id': participant.conversation_id,
                'user_id': {'$ne': user_id}
            }).to_list()
            
            for other_participant in other_participants:
                await connection_manager.send_to_user(other_participant.user_id, message_data)
