from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse
from datetime import datetime
from typing import Optional
import os
import uuid
import hashlib
import mimetypes
from PIL import Image
import io

from app.models.user import User
from app.models.message import MessageAttachment
from app.security.auth import verify_token
from app.security.validation import validate_file_upload
from app.config import settings

router = APIRouter()
security = HTTPBearer()

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

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Upload a file"""
    try:
        # Read file content
        file_content = await file.read()
        
        # Validate file
        validation_result = validate_file_upload(
            file_content, 
            file.filename or "unknown", 
            file.content_type or "application/octet-stream"
        )
        
        if not validation_result['is_valid']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File validation failed: {', '.join(validation_result['errors'])}"
            )
        
        # Generate file ID and paths
        file_id = str(uuid.uuid4())
        file_extension = os.path.splitext(file.filename or "unknown")[1]
        file_name = f"{file_id}{file_extension}"
        
        # Create upload directory if it doesn't exist
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = os.path.join(upload_dir, file_name)
        
        # Save file
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        # Generate file hash
        file_hash = hashlib.sha256(file_content).hexdigest()
        
        # Generate thumbnail for images
        thumbnail_url = None
        if file.content_type and file.content_type.startswith('image/'):
            try:
                thumbnail_url = await generate_thumbnail(file_path, file_id)
            except Exception as e:
                print(f"Failed to generate thumbnail: {e}")
        
        # Create file URL
        file_url = f"/api/files/{file_id}"
        
        # Create attachment record
        attachment = MessageAttachment(
            message_id="",  # Will be updated when attached to message
            file_name=file.filename or "unknown",
            file_size=len(file_content),
            mime_type=file.content_type or "application/octet-stream",
            file_url=file_url,
            thumbnail_url=thumbnail_url,
            file_hash=file_hash
        )
        
        await attachment.save()
        
        return {
            'success': True,
            'file': {
                'id': str(attachment.id),
                'file_name': attachment.file_name,
                'file_size': attachment.file_size,
                'mime_type': attachment.mime_type,
                'file_url': attachment.file_url,
                'thumbnail_url': attachment.thumbnail_url,
                'file_hash': attachment.file_hash,
                'uploaded_at': attachment.created_at.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}"
        )

@router.get("/{file_id}")
async def get_file(
    file_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get file by ID"""
    try:
        # Get attachment record
        attachment = await MessageAttachment.get(file_id)
        if not attachment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Check if user has access to the file
        # In a real implementation, you'd check if user is in the conversation
        # where this file was uploaded
        
        # Get file path
        file_extension = os.path.splitext(attachment.file_name)[1]
        file_name = f"{file_id}{file_extension}"
        file_path = os.path.join("uploads", file_name)
        
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found on disk"
            )
        
        # Return file
        return FileResponse(
            path=file_path,
            filename=attachment.file_name,
            media_type=attachment.mime_type
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get file: {str(e)}"
        )

@router.get("/{file_id}/thumbnail")
async def get_file_thumbnail(
    file_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get file thumbnail"""
    try:
        # Get attachment record
        attachment = await MessageAttachment.get(file_id)
        if not attachment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        if not attachment.thumbnail_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Thumbnail not available"
            )
        
        # Get thumbnail path
        thumbnail_path = attachment.thumbnail_url.replace("/api/files/", "uploads/")
        
        if not os.path.exists(thumbnail_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Thumbnail not found on disk"
            )
        
        # Return thumbnail
        return FileResponse(
            path=thumbnail_path,
            media_type="image/jpeg"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get thumbnail: {str(e)}"
        )

@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a file"""
    try:
        # Get attachment record
        attachment = await MessageAttachment.get(file_id)
        if not attachment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Check if user has permission to delete
        # In a real implementation, you'd check if user is the uploader
        # or has admin permissions in the conversation
        
        # Delete file from disk
        file_extension = os.path.splitext(attachment.file_name)[1]
        file_name = f"{file_id}{file_extension}"
        file_path = os.path.join("uploads", file_name)
        
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Delete thumbnail if exists
        if attachment.thumbnail_url:
            thumbnail_path = attachment.thumbnail_url.replace("/api/files/", "uploads/")
            if os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
        
        # Delete attachment record
        await attachment.delete()
        
        return {
            'success': True,
            'message': 'File deleted successfully'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}"
        )

async def generate_thumbnail(file_path: str, file_id: str) -> str:
    """Generate thumbnail for image file"""
    try:
        # Open image
        with Image.open(file_path) as img:
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # Resize to thumbnail size
            img.thumbnail((200, 200), Image.Resampling.LANCZOS)
            
            # Save thumbnail
            thumbnail_path = os.path.join("uploads", f"{file_id}_thumb.jpg")
            img.save(thumbnail_path, "JPEG", quality=85)
            
            return f"/api/files/{file_id}/thumbnail"
            
    except Exception as e:
        print(f"Error generating thumbnail: {e}")
        return None

@router.post("/upload/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Upload user avatar"""
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only image files are allowed for avatars"
            )
        
        # Read file content
        file_content = await file.read()
        
        # Validate file size (max 5MB for avatars)
        if len(file_content) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Avatar file too large. Maximum 5MB allowed."
            )
        
        # Generate avatar filename
        file_extension = os.path.splitext(file.filename or "avatar")[1]
        avatar_filename = f"avatar_{current_user.id}{file_extension}"
        
        # Create avatars directory
        avatars_dir = "uploads/avatars"
        os.makedirs(avatars_dir, exist_ok=True)
        
        avatar_path = os.path.join(avatars_dir, avatar_filename)
        
        # Save avatar
        with open(avatar_path, "wb") as f:
            f.write(file_content)
        
        # Generate thumbnail
        try:
            with Image.open(avatar_path) as img:
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Resize to 200x200
                img = img.resize((200, 200), Image.Resampling.LANCZOS)
                
                # Save as JPEG
                avatar_filename_jpg = f"avatar_{current_user.id}.jpg"
                avatar_path_jpg = os.path.join(avatars_dir, avatar_filename_jpg)
                img.save(avatar_path_jpg, "JPEG", quality=90)
                
                # Update user avatar URL
                avatar_url = f"/api/files/avatars/{avatar_filename_jpg}"
                current_user.avatar_url = avatar_url
                await current_user.save()
                
                return {
                    'success': True,
                    'avatar_url': avatar_url
                }
                
        except Exception as e:
            print(f"Error processing avatar: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process avatar image"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload avatar: {str(e)}"
        )

@router.get("/avatars/{filename}")
async def get_avatar(filename: str):
    """Get avatar file"""
    try:
        avatar_path = os.path.join("uploads/avatars", filename)
        
        if not os.path.exists(avatar_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Avatar not found"
            )
        
        return FileResponse(
            path=avatar_path,
            media_type="image/jpeg"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get avatar: {str(e)}"
        )
