import re
import html
from typing import List, Optional, Dict, Any
from app.config import settings

def validate_message(content: str, message_type: str = "text") -> Dict[str, Any]:
    """Validate message content and return validation result"""
    errors = []
    
    # Check message length
    if len(content) > settings.MAX_MESSAGE_LENGTH:
        errors.append(f"Message too long. Maximum {settings.MAX_MESSAGE_LENGTH} characters allowed.")
    
    # Check for empty content (except for system messages)
    if message_type != "system" and not content.strip():
        errors.append("Message content cannot be empty.")
    
    # Check for malicious content
    if contains_malicious_content(content):
        errors.append("Message contains potentially malicious content.")
    
    # Check for excessive mentions
    mention_count = content.count('@')
    if mention_count > 50:  # Reasonable limit
        errors.append("Too many mentions in message.")
    
    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "sanitized_content": sanitize_input(content)
    }

def validate_file_upload(file_data: bytes, filename: str, mime_type: str) -> Dict[str, Any]:
    """Validate file upload and return validation result"""
    errors = []
    
    # Check file size
    if len(file_data) > settings.MAX_FILE_SIZE:
        errors.append(f"File too large. Maximum {settings.MAX_FILE_SIZE // (1024*1024)}MB allowed.")
    
    # Check file type
    if mime_type not in settings.ALLOWED_FILE_TYPES:
        errors.append(f"File type {mime_type} not allowed.")
    
    # Check filename
    if not is_safe_filename(filename):
        errors.append("Invalid filename.")
    
    # Check for malicious file content
    if contains_malicious_file_content(file_data, mime_type):
        errors.append("File contains potentially malicious content.")
    
    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "file_size": len(file_data)
    }

def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent XSS and other attacks"""
    if not text:
        return text
    
    # HTML escape
    sanitized = html.escape(text)
    
    # Remove potentially dangerous characters
    sanitized = re.sub(r'[<>"\']', '', sanitized)
    
    # Normalize whitespace
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    
    return sanitized

def contains_malicious_content(content: str) -> bool:
    """Check if content contains potentially malicious patterns"""
    malicious_patterns = [
        r'<script[^>]*>.*?</script>',  # Script tags
        r'javascript:',  # JavaScript URLs
        r'data:text/html',  # Data URLs
        r'vbscript:',  # VBScript URLs
        r'on\w+\s*=',  # Event handlers
        r'<iframe[^>]*>',  # Iframe tags
        r'<object[^>]*>',  # Object tags
        r'<embed[^>]*>',  # Embed tags
        r'<link[^>]*>',  # Link tags
        r'<meta[^>]*>',  # Meta tags
    ]
    
    content_lower = content.lower()
    for pattern in malicious_patterns:
        if re.search(pattern, content_lower, re.IGNORECASE | re.DOTALL):
            return True
    
    return False

def contains_malicious_file_content(file_data: bytes, mime_type: str) -> bool:
    """Check if file contains potentially malicious content"""
    # Check for executable signatures
    executable_signatures = [
        b'MZ',  # PE executable
        b'\x7fELF',  # ELF executable
        b'\xfe\xed\xfa',  # Mach-O executable
        b'#!/',  # Shell script
    ]
    
    for signature in executable_signatures:
        if file_data.startswith(signature):
            return True
    
    # Check for embedded scripts in images
    if mime_type.startswith('image/'):
        if b'<script' in file_data.lower() or b'javascript:' in file_data.lower():
            return True
    
    return False

def is_safe_filename(filename: str) -> bool:
    """Check if filename is safe"""
    if not filename or len(filename) > 255:
        return False
    
    # Check for dangerous characters
    dangerous_chars = ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|']
    for char in dangerous_chars:
        if char in filename:
            return False
    
    # Check for reserved names (Windows)
    reserved_names = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9']
    if filename.upper() in reserved_names:
        return False
    
    return True

def validate_email(email: str) -> bool:
    """Validate email address format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_username(username: str) -> bool:
    """Validate username format"""
    if not username or len(username) < 3 or len(username) > 50:
        return False
    
    # Only allow alphanumeric characters, underscores, and hyphens
    pattern = r'^[a-zA-Z0-9_-]+$'
    return re.match(pattern, username) is not None

def validate_password_strength(password: str) -> Dict[str, Any]:
    """Validate password strength"""
    errors = []
    
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long.")
    
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter.")
    
    if not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter.")
    
    if not re.search(r'\d', password):
        errors.append("Password must contain at least one number.")
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        errors.append("Password must contain at least one special character.")
    
    # Check for common passwords
    common_passwords = ['password', '123456', 'qwerty', 'abc123', 'password123']
    if password.lower() in common_passwords:
        errors.append("Password is too common.")
    
    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "strength": calculate_password_strength(password)
    }

def calculate_password_strength(password: str) -> str:
    """Calculate password strength score"""
    score = 0
    
    if len(password) >= 8:
        score += 1
    if len(password) >= 12:
        score += 1
    if re.search(r'[A-Z]', password):
        score += 1
    if re.search(r'[a-z]', password):
        score += 1
    if re.search(r'\d', password):
        score += 1
    if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        score += 1
    if len(password) >= 16:
        score += 1
    
    if score <= 2:
        return "weak"
    elif score <= 4:
        return "medium"
    elif score <= 6:
        return "strong"
    else:
        return "very_strong"
