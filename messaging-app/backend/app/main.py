from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
import json
import logging
from typing import Dict, Any

from app.config import settings
from app.database import init_database, close_database
from app.websockets.connection_manager import connection_manager
from app.websockets.message_handler import MessageHandler
from app.websockets.encryption_handler import encryption_handler
from app.security.auth import verify_token
from app.routes import auth, conversations, messages, users, files

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize message handler
message_handler = MessageHandler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting up messaging app backend...")
    await init_database()
    
    # Generate encryption keys for the system
    encryption_handler.generate_user_keypair("system")
    
    yield
    
    # Shutdown
    logger.info("Shutting down messaging app backend...")
    await close_database()

# Create FastAPI app
app = FastAPI(
    title="Secure Messaging App API",
    description="A secure real-time messaging application with end-to-end encryption",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["Conversations"])
app.include_router(messages.router, prefix="/api/messages", tags=["Messages"])
app.include_router(files.router, prefix="/api/files", tags=["Files"])

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user from JWT token"""
    token = credentials.credentials
    payload = verify_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return payload

@app.websocket("/ws/{user_id}/{session_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, session_id: str):
    """WebSocket endpoint for real-time communication"""
    await websocket.accept()
    
    try:
        # Verify user authentication
        # In a real implementation, you'd verify the session token here
        logger.info(f"WebSocket connection established for user {user_id}, session {session_id}")
        
        # Add connection to manager
        metadata = {
            'ip_address': websocket.client.host if websocket.client else None,
            'user_agent': websocket.headers.get('user-agent'),
            'connected_at': message_handler.get_current_time()
        }
        
        await connection_manager.connect(websocket, user_id, session_id, metadata)
        
        # Send welcome message
        await websocket.send_text(json.dumps({
            'type': 'connection_established',
            'user_id': user_id,
            'session_id': session_id,
            'timestamp': message_handler.get_current_time()
        }))
        
        # Main message loop
        while True:
            try:
                # Receive message
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # Update activity
                await connection_manager.update_activity(user_id, session_id)
                
                # Check rate limiting
                if not await connection_manager.rate_limit_check(user_id, session_id):
                    await websocket.send_text(json.dumps({
                        'type': 'error',
                        'message': 'Rate limit exceeded. Please slow down.',
                        'timestamp': message_handler.get_current_time()
                    }))
                    continue
                
                # Process message
                response = await message_handler.handle_message(
                    user_id, session_id, message_data, websocket
                )
                
                # Send response if any
                if response:
                    await websocket.send_text(json.dumps(response))
                    
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for user {user_id}, session {session_id}")
                break
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    'type': 'error',
                    'message': 'Invalid JSON format',
                    'timestamp': message_handler.get_current_time()
                }))
            except Exception as e:
                logger.error(f"Error processing message for user {user_id}: {e}")
                await websocket.send_text(json.dumps({
                    'type': 'error',
                    'message': 'Internal server error',
                    'timestamp': message_handler.get_current_time()
                }))
    
    except Exception as e:
        logger.error(f"WebSocket connection error for user {user_id}: {e}")
    finally:
        # Clean up connection
        await connection_manager.disconnect(user_id, session_id, "Connection closed")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Secure Messaging App API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": message_handler.get_current_time(),
        "active_connections": len(connection_manager.get_online_users())
    }

@app.websocket("/ws/public/{channel}")
async def public_websocket(websocket: WebSocket, channel: str):
    """Public WebSocket channel for announcements and system messages"""
    await websocket.accept()
    
    try:
        logger.info(f"Public WebSocket connection established for channel {channel}")
        
        # Send welcome message
        await websocket.send_text(json.dumps({
            'type': 'public_channel_connected',
            'channel': channel,
            'timestamp': message_handler.get_current_time()
        }))
        
        # Keep connection alive and handle messages
        while True:
            try:
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # Process public channel message
                response = await message_handler.handle_public_message(
                    channel, message_data, websocket
                )
                
                if response:
                    await websocket.send_text(json.dumps(response))
                    
            except WebSocketDisconnect:
                logger.info(f"Public WebSocket disconnected for channel {channel}")
                break
            except Exception as e:
                logger.error(f"Error in public WebSocket for channel {channel}: {e}")
                break
    
    except Exception as e:
        logger.error(f"Public WebSocket connection error for channel {channel}: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
