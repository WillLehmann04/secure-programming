# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pydantic.alias_generators import to_snake
from typing import Optional  # remove if unused


class Settings(BaseSettings):
    # Core
    app_name: str = "Messaging App"
    debug: bool = False

    # Use validation_alias for env var names in Pydantic v2
    database_url: str = Field(
        default="sqlite:///./dev.db",
        validation_alias="DATABASE_URL",
    )

    # WebSocket
    WS_HEARTBEAT_INTERVAL: int = 30   # seconds
    WS_CONNECTION_TIMEOUT: int = 300  # seconds

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 10

    # Message Limits
    MAX_MESSAGE_LENGTH: int = 4000
    MAX_MESSAGES_PER_CONVERSATION: int = 10000

    # Session Management
    MAX_SESSIONS_PER_USER: int = 5
    SESSION_TIMEOUT: int = 3600  # seconds

    # Pydantic v2 settings config (replaces old inner Config)
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,   # set False if you want env keys to be case-insensitive
    )


settings = Settings()
