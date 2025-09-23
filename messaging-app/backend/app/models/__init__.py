# app/models/__init__.py
from .base import Base

# Re-export your models here so imports are consistent
from .user import User, UserSession  # adjust to your actual models

__all__ = ["Base", "User", "UserSession"]
