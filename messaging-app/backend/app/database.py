from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.config import settings
from app.models.user import User, UserSession
from app.models.conversation import Conversation, ConversationParticipant
from app.models.message import Message, MessageAttachment, MessageReaction

class Database:
    client: AsyncIOMotorClient = None
    database = None

db = Database()

async def init_database():
    """Initialize database connection and collections"""
    db.client = AsyncIOMotorClient(settings.MONGODB_URL)
    db.database = db.client[settings.DATABASE_NAME]
    
    # Initialize Beanie with the database
    await init_beanie(
        database=db.database,
        document_models=[
            User,
            UserSession,
            Conversation,
            ConversationParticipant,
            Message,
            MessageAttachment,
            MessageReaction
        ]
    )

async def close_database():
    """Close database connection"""
    if db.client:
        db.client.close()

def get_database():
    """Get database instance"""
    return db.database
