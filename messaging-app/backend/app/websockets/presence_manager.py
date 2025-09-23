import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Set, Optional
import redis
from app.config import settings

logger = logging.getLogger(__name__)

class PresenceManager:
    """Manages user presence and status updates"""
    
    def __init__(self):
        self.redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        self.presence_ttl = 300  # 5 minutes
    
    async def update_presence(self, user_id: str, status: str, session_id: str = None):
        """Update user presence status"""
        try:
            presence_key = f"presence:{user_id}"
            presence_data = {
                'status': status,
                'last_seen': datetime.utcnow().isoformat(),
                'session_id': session_id or 'unknown'
            }
            
            # Store in Redis with TTL
            self.redis_client.hset(presence_key, mapping=presence_data)
            self.redis_client.expire(presence_key, self.presence_ttl)
            
            logger.info(f"Updated presence for user {user_id}: {status}")
            
        except Exception as e:
            logger.error(f"Error updating presence for user {user_id}: {e}")
    
    async def get_presence(self, user_id: str) -> Optional[Dict]:
        """Get user presence status"""
        try:
            presence_key = f"presence:{user_id}"
            presence_data = self.redis_client.hgetall(presence_key)
            
            if not presence_data:
                return None
            
            return {
                'user_id': user_id,
                'status': presence_data.get('status', 'offline'),
                'last_seen': presence_data.get('last_seen'),
                'session_id': presence_data.get('session_id')
            }
            
        except Exception as e:
            logger.error(f"Error getting presence for user {user_id}: {e}")
            return None
    
    async def get_online_users(self) -> Set[str]:
        """Get set of online user IDs"""
        try:
            pattern = "presence:*"
            keys = self.redis_client.keys(pattern)
            
            online_users = set()
            for key in keys:
                user_id = key.replace('presence:', '')
                presence_data = self.redis_client.hgetall(key)
                if presence_data.get('status') == 'online':
                    online_users.add(user_id)
            
            return online_users
            
        except Exception as e:
            logger.error(f"Error getting online users: {e}")
            return set()
    
    async def cleanup_stale_presence(self):
        """Clean up stale presence data"""
        try:
            pattern = "presence:*"
            keys = self.redis_client.keys(pattern)
            
            current_time = datetime.utcnow()
            stale_threshold = timedelta(minutes=10)
            
            for key in keys:
                presence_data = self.redis_client.hgetall(key)
                last_seen_str = presence_data.get('last_seen')
                
                if last_seen_str:
                    try:
                        last_seen = datetime.fromisoformat(last_seen_str)
                        if current_time - last_seen > stale_threshold:
                            self.redis_client.delete(key)
                            logger.info(f"Cleaned up stale presence for {key}")
                    except ValueError:
                        # Invalid date format, delete the key
                        self.redis_client.delete(key)
                        logger.info(f"Cleaned up invalid presence data for {key}")
            
        except Exception as e:
            logger.error(f"Error cleaning up stale presence: {e}")
    
    async def broadcast_presence_update(self, user_id: str, status: str, connection_manager):
        """Broadcast presence update to user's connections"""
        try:
            # Get user's conversations
            from app.models.conversation import ConversationParticipant
            
            participants = await ConversationParticipant.find({
                'user_id': user_id
            }).to_list()
            
            presence_message = {
                'type': 'presence_update',
                'user_id': user_id,
                'status': status,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Broadcast to all conversations where user is a participant
            for participant in participants:
                # Get other participants in the same conversation
                other_participants = await ConversationParticipant.find({
                    'conversation_id': participant.conversation_id,
                    'user_id': {'$ne': user_id}
                }).to_list()
                
                for other_participant in other_participants:
                    await connection_manager.send_to_user(
                        other_participant.user_id, 
                        presence_message
                    )
            
        except Exception as e:
            logger.error(f"Error broadcasting presence update: {e}")

# Global presence manager instance
presence_manager = PresenceManager()
