import asyncio
import json
import logging
from typing import Dict, Set, Optional, Any
from datetime import datetime, timedelta
from websockets import WebSocketServerProtocol
from collections import defaultdict
import redis
from app.config import settings

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages WebSocket connections and user sessions"""
    
    def __init__(self):
        # Active connections: {user_id: {session_id: websocket}}
        self.active_connections: Dict[str, Dict[str, WebSocketServerProtocol]] = defaultdict(dict)
        
        # Connection metadata: {user_id: {session_id: metadata}}
        self.connection_metadata: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
        
        # Redis for distributed connection tracking
        self.redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        
        # Heartbeat tracking
        self.heartbeats: Dict[str, datetime] = {}
        
        # Rate limiting per connection
        self.rate_limits: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'messages': 0,
            'last_reset': datetime.utcnow(),
            'blocked_until': None
        })
    
    async def connect(self, websocket: WebSocketServerProtocol, user_id: str, session_id: str, metadata: Dict[str, Any] = None):
        """Add a new WebSocket connection"""
        try:
            # Check if user has too many active sessions
            if len(self.active_connections[user_id]) >= settings.MAX_SESSIONS_PER_USER:
                # Disconnect oldest session
                oldest_session = min(
                    self.active_connections[user_id].keys(),
                    key=lambda s: self.connection_metadata[user_id].get(s, {}).get('connected_at', datetime.min)
                )
                await self.disconnect(user_id, oldest_session, "Too many active sessions")
            
            # Add connection
            self.active_connections[user_id][session_id] = websocket
            self.connection_metadata[user_id][session_id] = {
                'connected_at': datetime.utcnow(),
                'last_activity': datetime.utcnow(),
                'ip_address': metadata.get('ip_address'),
                'user_agent': metadata.get('user_agent'),
                'device_info': metadata.get('device_info'),
                **metadata
            }
            
            # Update Redis
            await self._update_redis_presence(user_id, session_id, 'online')
            
            logger.info(f"User {user_id} connected with session {session_id}")
            
            # Send connection confirmation
            await self.send_to_user(user_id, {
                'type': 'connection_established',
                'session_id': session_id,
                'timestamp': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error connecting user {user_id}: {e}")
            raise
    
    async def disconnect(self, user_id: str, session_id: str, reason: str = "Disconnected"):
        """Remove a WebSocket connection"""
        try:
            if user_id in self.active_connections and session_id in self.active_connections[user_id]:
                # Close WebSocket if still open
                websocket = self.active_connections[user_id][session_id]
                if not websocket.closed:
                    await websocket.close(code=1000, reason=reason.encode())
                
                # Remove from tracking
                del self.active_connections[user_id][session_id]
                if session_id in self.connection_metadata[user_id]:
                    del self.connection_metadata[user_id][session_id]
                
                # Clean up empty user entries
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
                    del self.connection_metadata[user_id]
                
                # Update Redis
                await self._update_redis_presence(user_id, session_id, 'offline')
                
                logger.info(f"User {user_id} disconnected session {session_id}: {reason}")
                
        except Exception as e:
            logger.error(f"Error disconnecting user {user_id}: {e}")
    
    async def send_to_user(self, user_id: str, message: Dict[str, Any], exclude_session: Optional[str] = None):
        """Send message to all sessions of a user"""
        if user_id not in self.active_connections:
            return False
        
        sent_count = 0
        failed_sessions = []
        
        for session_id, websocket in self.active_connections[user_id].items():
            if exclude_session and session_id == exclude_session:
                continue
                
            try:
                if not websocket.closed:
                    await websocket.send(json.dumps(message))
                    sent_count += 1
                else:
                    failed_sessions.append(session_id)
            except Exception as e:
                logger.error(f"Error sending message to user {user_id} session {session_id}: {e}")
                failed_sessions.append(session_id)
        
        # Clean up failed sessions
        for session_id in failed_sessions:
            await self.disconnect(user_id, session_id, "Connection failed")
        
        return sent_count > 0
    
    async def send_to_conversation(self, conversation_id: str, message: Dict[str, Any], exclude_user: Optional[str] = None):
        """Send message to all users in a conversation"""
        # This would typically query the database for conversation participants
        # For now, we'll implement a basic version
        sent_count = 0
        
        for user_id in self.active_connections:
            if exclude_user and user_id == exclude_user:
                continue
                
            if await self.send_to_user(user_id, message):
                sent_count += 1
        
        return sent_count
    
    async def broadcast_to_all(self, message: Dict[str, Any], exclude_user: Optional[str] = None):
        """Broadcast message to all connected users"""
        sent_count = 0
        
        for user_id in self.active_connections:
            if exclude_user and user_id == exclude_user:
                continue
                
            if await self.send_to_user(user_id, message):
                sent_count += 1
        
        return sent_count
    
    def is_user_online(self, user_id: str) -> bool:
        """Check if user has any active connections"""
        return user_id in self.active_connections and len(self.active_connections[user_id]) > 0
    
    def get_user_sessions(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        """Get all sessions for a user"""
        return self.connection_metadata.get(user_id, {})
    
    def get_online_users(self) -> Set[str]:
        """Get set of all online user IDs"""
        return set(self.active_connections.keys())
    
    async def update_activity(self, user_id: str, session_id: str):
        """Update last activity timestamp for a connection"""
        if user_id in self.connection_metadata and session_id in self.connection_metadata[user_id]:
            self.connection_metadata[user_id][session_id]['last_activity'] = datetime.utcnow()
            self.heartbeats[f"{user_id}:{session_id}"] = datetime.utcnow()
    
    async def check_heartbeats(self):
        """Check for stale connections and clean them up"""
        now = datetime.utcnow()
        timeout = timedelta(seconds=settings.WS_CONNECTION_TIMEOUT)
        
        stale_connections = []
        
        for connection_key, last_heartbeat in self.heartbeats.items():
            if now - last_heartbeat > timeout:
                user_id, session_id = connection_key.split(':', 1)
                stale_connections.append((user_id, session_id))
        
        for user_id, session_id in stale_connections:
            await self.disconnect(user_id, session_id, "Connection timeout")
            if connection_key in self.heartbeats:
                del self.heartbeats[connection_key]
    
    async def rate_limit_check(self, user_id: str, session_id: str) -> bool:
        """Check if connection is rate limited"""
        now = datetime.utcnow()
        rate_limit = self.rate_limits[f"{user_id}:{session_id}"]
        
        # Reset counter if minute has passed
        if now - rate_limit['last_reset'] > timedelta(minutes=1):
            rate_limit['messages'] = 0
            rate_limit['last_reset'] = now
            rate_limit['blocked_until'] = None
        
        # Check if currently blocked
        if rate_limit['blocked_until'] and now < rate_limit['blocked_until']:
            return False
        
        # Check rate limit
        if rate_limit['messages'] >= settings.RATE_LIMIT_PER_MINUTE:
            rate_limit['blocked_until'] = now + timedelta(minutes=1)
            return False
        
        # Increment counter
        rate_limit['messages'] += 1
        return True
    
    async def _update_redis_presence(self, user_id: str, session_id: str, status: str):
        """Update user presence in Redis"""
        try:
            presence_key = f"presence:{user_id}"
            session_data = {
                'session_id': session_id,
                'status': status,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            if status == 'online':
                self.redis_client.hset(presence_key, session_id, json.dumps(session_data))
                self.redis_client.expire(presence_key, 3600)  # 1 hour TTL
            else:
                self.redis_client.hdel(presence_key, session_id)
                
        except Exception as e:
            logger.error(f"Error updating Redis presence for user {user_id}: {e}")
    
    async def get_user_presence(self, user_id: str) -> Dict[str, Any]:
        """Get user presence from Redis"""
        try:
            presence_key = f"presence:{user_id}"
            sessions = self.redis_client.hgetall(presence_key)
            
            if not sessions:
                return {'status': 'offline', 'sessions': []}
            
            online_sessions = []
            for session_id, session_data in sessions.items():
                session_info = json.loads(session_data)
                online_sessions.append(session_info)
            
            return {
                'status': 'online' if online_sessions else 'offline',
                'sessions': online_sessions
            }
            
        except Exception as e:
            logger.error(f"Error getting user presence for user {user_id}: {e}")
            return {'status': 'offline', 'sessions': []}

# Global connection manager instance
connection_manager = ConnectionManager()
