from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List
from beanie import PydanticObjectId

from app.models.user import User, UserStatus
from app.security.auth import verify_token, get_password_hash
from app.security.validation import validate_username, validate_email

router = APIRouter()
security = HTTPBearer()

class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None

class UpdateSettingsRequest(BaseModel):
    settings: dict

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
async def get_users(
    current_user: User = Depends(get_current_user),
    search: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0)
):
    """Get list of users with optional search"""
    try:
        # Build query
        query = {'is_active': True}
        
        if search:
            query['$or'] = [
                {'username': {'$regex': search, '$options': 'i'}},
                {'display_name': {'$regex': search, '$options': 'i'}},
                {'email': {'$regex': search, '$options': 'i'}}
            ]
        
        # Get users
        users = await User.find(query).skip(offset).limit(limit).to_list()
        
        # Format response
        result = []
        for user in users:
            result.append({
                'id': str(user.id),
                'username': user.username,
                'display_name': user.display_name,
                'bio': user.bio,
                'avatar_url': user.avatar_url,
                'status': user.status,
                'last_seen': user.last_seen.isoformat() if user.last_seen else None,
                'is_verified': user.is_verified
            })
        
        return {
            'success': True,
            'users': result,
            'total': len(result)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get users: {str(e)}"
        )

@router.get("/{user_id}")
async def get_user(
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get user details by ID"""
    try:
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
            detail=f"Failed to get user: {str(e)}"
        )

@router.put("/{user_id}")
async def update_user(
    user_id: str,
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_user)
):
    """Update user profile"""
    try:
        # Check if user is updating their own profile
        if str(current_user.id) != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own profile"
            )
        
        user = await User.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Update fields
        if request.display_name is not None:
            user.display_name = request.display_name
        if request.bio is not None:
            user.bio = request.bio
        if request.avatar_url is not None:
            user.avatar_url = request.avatar_url
        
        user.updated_at = datetime.utcnow()
        await user.save()
        
        return {
            'success': True,
            'user': {
                'id': str(user.id),
                'username': user.username,
                'display_name': user.display_name,
                'bio': user.bio,
                'avatar_url': user.avatar_url,
                'status': user.status,
                'last_seen': user.last_seen.isoformat() if user.last_seen else None,
                'is_verified': user.is_verified,
                'updated_at': user.updated_at.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user: {str(e)}"
        )

@router.put("/{user_id}/settings")
async def update_user_settings(
    user_id: str,
    request: UpdateSettingsRequest,
    current_user: User = Depends(get_current_user)
):
    """Update user settings"""
    try:
        # Check if user is updating their own settings
        if str(current_user.id) != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own settings"
            )
        
        user = await User.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Update settings
        user.settings.update(request.settings)
        user.updated_at = datetime.utcnow()
        await user.save()
        
        return {
            'success': True,
            'settings': user.settings
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update settings: {str(e)}"
        )

@router.post("/{user_id}/avatar")
async def upload_avatar(
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    """Upload user avatar (placeholder - would integrate with file upload)"""
    try:
        # Check if user is updating their own avatar
        if str(current_user.id) != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own avatar"
            )
        
        user = await User.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # In a real implementation, this would handle file upload
        # For now, return a placeholder response
        return {
            'success': True,
            'message': 'Avatar upload endpoint - integrate with file upload service',
            'avatar_url': user.avatar_url
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload avatar: {str(e)}"
        )

@router.get("/{user_id}/presence")
async def get_user_presence(
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get user presence status"""
    try:
        user = await User.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return {
            'success': True,
            'presence': {
                'user_id': str(user.id),
                'status': user.status,
                'last_seen': user.last_seen.isoformat() if user.last_seen else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user presence: {str(e)}"
        )

@router.post("/{user_id}/block")
async def block_user(
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    """Block a user (placeholder implementation)"""
    try:
        # Check if user exists
        user_to_block = await User.get(user_id)
        if not user_to_block:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check if trying to block self
        if str(current_user.id) == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot block yourself"
            )
        
        # In a real implementation, this would add to blocked users list
        # For now, return a placeholder response
        return {
            'success': True,
            'message': f'User {user_to_block.username} has been blocked'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to block user: {str(e)}"
        )

@router.delete("/{user_id}/block")
async def unblock_user(
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    """Unblock a user (placeholder implementation)"""
    try:
        # Check if user exists
        user_to_unblock = await User.get(user_id)
        if not user_to_unblock:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # In a real implementation, this would remove from blocked users list
        # For now, return a placeholder response
        return {
            'success': True,
            'message': f'User {user_to_unblock.username} has been unblocked'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unblock user: {str(e)}"
        )
