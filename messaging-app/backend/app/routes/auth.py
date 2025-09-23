from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from typing import Optional
import secrets

from app.models.user import User, UserSession, UserStatus
from app.security.auth import (
    create_access_token, create_refresh_token, verify_token,
    get_password_hash, verify_password, generate_session_token,
    generate_salt, create_session_hash
)
from app.security.validation import validate_password_strength, validate_email, validate_username

router = APIRouter()
security = HTTPBearer()

class SignUpRequest(BaseModel):
    email: EmailStr
    username: str
    display_name: str
    password: str

class SignInRequest(BaseModel):
    email: EmailStr
    password: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class MagicLinkRequest(BaseModel):
    email: EmailStr

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

@router.post("/signup")
async def sign_up(request: SignUpRequest):
    """Register a new user"""
    try:
        # Validate input
        if not validate_email(request.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )
        
        if not validate_username(request.username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username must be 3-50 characters and contain only letters, numbers, underscores, and hyphens"
            )
        
        # Validate password strength
        password_validation = validate_password_strength(request.password)
        if not password_validation['is_valid']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Password validation failed: {', '.join(password_validation['errors'])}"
            )
        
        # Check if user already exists
        existing_user = await User.find_one({
            '$or': [
                {'email': request.email},
                {'username': request.username}
            ]
        })
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email or username already exists"
            )
        
        # Create user
        salt = generate_salt()
        password_hash = get_password_hash(request.password)
        
        user = User(
            email=request.email,
            username=request.username,
            display_name=request.display_name,
            password_hash=password_hash,
            salt=salt,
            status=UserStatus.OFFLINE
        )
        
        await user.save()
        
        # Create session
        session_token = generate_session_token()
        session_hash = create_session_hash(session_token, salt)
        refresh_token = create_refresh_token({'user_id': str(user.id)})
        
        session = UserSession(
            user_id=str(user.id),
            session_token=session_hash,
            refresh_token=refresh_token,
            expires_at=datetime.utcnow() + timedelta(days=7),
            is_active=True
        )
        
        await session.save()
        
        # Create access token
        access_token = create_access_token({'user_id': str(user.id)})
        
        return {
            'success': True,
            'user': {
                'id': str(user.id),
                'email': user.email,
                'username': user.username,
                'display_name': user.display_name,
                'status': user.status,
                'created_at': user.created_at.isoformat()
            },
            'access_token': access_token,
            'refresh_token': refresh_token,
            'session_token': session_token
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@router.post("/signin")
async def sign_in(request: SignInRequest):
    """Sign in user"""
    try:
        # Find user by email
        user = await User.find_one({'email': request.email})
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Verify password
        if not verify_password(request.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is deactivated"
            )
        
        # Create session
        session_token = generate_session_token()
        session_hash = create_session_hash(session_token, user.salt)
        refresh_token = create_refresh_token({'user_id': str(user.id)})
        
        session = UserSession(
            user_id=str(user.id),
            session_token=session_hash,
            refresh_token=refresh_token,
            expires_at=datetime.utcnow() + timedelta(days=7),
            is_active=True
        )
        
        await session.save()
        
        # Create access token
        access_token = create_access_token({'user_id': str(user.id)})
        
        # Update user status
        user.status = UserStatus.ONLINE
        user.last_seen = datetime.utcnow()
        await user.save()
        
        return {
            'success': True,
            'user': {
                'id': str(user.id),
                'email': user.email,
                'username': user.username,
                'display_name': user.display_name,
                'status': user.status,
                'last_seen': user.last_seen.isoformat() if user.last_seen else None
            },
            'access_token': access_token,
            'refresh_token': refresh_token,
            'session_token': session_token
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sign in failed: {str(e)}"
        )

@router.post("/refresh")
async def refresh_token(request: RefreshTokenRequest):
    """Refresh access token"""
    try:
        # Verify refresh token
        payload = verify_token(request.refresh_token, "refresh")
        
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        user_id = payload.get('user_id')
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        # Check if user exists and is active
        user = await User.get(user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Create new access token
        access_token = create_access_token({'user_id': str(user.id)})
        
        return {
            'success': True,
            'access_token': access_token
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token refresh failed: {str(e)}"
        )

@router.post("/magic-link")
async def send_magic_link(request: MagicLinkRequest):
    """Send magic link for passwordless sign in"""
    try:
        # Find user by email
        user = await User.find_one({'email': request.email})
        
        if not user:
            # Don't reveal if user exists or not
            return {
                'success': True,
                'message': 'If an account exists with this email, a magic link has been sent'
            }
        
        # Generate magic link token
        magic_token = secrets.token_urlsafe(32)
        
        # In a real implementation, you would:
        # 1. Store the magic token with expiration
        # 2. Send email with magic link
        # 3. Handle magic link verification
        
        return {
            'success': True,
            'message': 'Magic link sent to your email',
            'magic_token': magic_token  # Only for development
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Magic link sending failed: {str(e)}"
        )

@router.post("/change-password")
async def change_password(request: ChangePasswordRequest, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Change user password"""
    try:
        # Verify access token
        payload = verify_token(credentials.credentials)
        
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token"
            )
        
        user_id = payload.get('user_id')
        user = await User.get(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Verify current password
        if not verify_password(request.current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Validate new password
        password_validation = validate_password_strength(request.new_password)
        if not password_validation['is_valid']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Password validation failed: {', '.join(password_validation['errors'])}"
            )
        
        # Update password
        user.password_hash = get_password_hash(request.new_password)
        await user.save()
        
        # Invalidate all existing sessions
        await UserSession.find({'user_id': user_id}).update_many({'$set': {'is_active': False}})
        
        return {
            'success': True,
            'message': 'Password changed successfully'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Password change failed: {str(e)}"
        )

@router.post("/signout")
async def sign_out(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Sign out user"""
    try:
        # Verify access token
        payload = verify_token(credentials.credentials)
        
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token"
            )
        
        user_id = payload.get('user_id')
        
        # Deactivate all user sessions
        await UserSession.find({'user_id': user_id}).update_many({'$set': {'is_active': False}})
        
        # Update user status
        user = await User.get(user_id)
        if user:
            user.status = UserStatus.OFFLINE
            await user.save()
        
        return {
            'success': True,
            'message': 'Signed out successfully'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sign out failed: {str(e)}"
        )

@router.get("/me")
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user information"""
    try:
        # Verify access token
        payload = verify_token(credentials.credentials)
        
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token"
            )
        
        user_id = payload.get('user_id')
        user = await User.get(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return {
            'success': True,
            'user': {
                'id': str(user.id),
                'email': user.email,
                'username': user.username,
                'display_name': user.display_name,
                'bio': user.bio,
                'avatar_url': user.avatar_url,
                'status': user.status,
                'last_seen': user.last_seen.isoformat() if user.last_seen else None,
                'is_verified': user.is_verified,
                'created_at': user.created_at.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user information: {str(e)}"
        )
