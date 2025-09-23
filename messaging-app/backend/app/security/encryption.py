from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os
import hashlib
from typing import Tuple, Optional

from app.config import settings

class EncryptionManager:
    def __init__(self):
        self.master_key = settings.ENCRYPTION_KEY.encode()
        self._fernet = Fernet(self.master_key)
    
    def encrypt_message(self, message: str, key: Optional[bytes] = None) -> Tuple[str, str]:
        """Encrypt a message with optional custom key"""
        if key:
            fernet = Fernet(key)
        else:
            fernet = self._fernet
            
        encrypted_data = fernet.encrypt(message.encode())
        iv = base64.b64encode(os.urandom(16)).decode()
        return base64.b64encode(encrypted_data).decode(), iv
    
    def decrypt_message(self, encrypted_message: str, iv: str, key: Optional[bytes] = None) -> str:
        """Decrypt a message with optional custom key"""
        if key:
            fernet = Fernet(key)
        else:
            fernet = self._fernet
            
        encrypted_data = base64.b64decode(encrypted_message)
        decrypted_data = fernet.decrypt(encrypted_data)
        return decrypted_data.decode()
    
    def generate_key_pair(self) -> Tuple[str, str]:
        """Generate RSA key pair for E2E encryption"""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        public_key = private_key.public_key()
        
        # Serialize keys
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        return private_pem.decode(), public_pem.decode()
    
    def encrypt_private_key(self, private_key: str, password: str) -> str:
        """Encrypt private key with password"""
        # Derive key from password
        salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        
        # Encrypt private key
        fernet = Fernet(key)
        encrypted_key = fernet.encrypt(private_key.encode())
        
        # Combine salt and encrypted key
        combined = salt + encrypted_key
        return base64.b64encode(combined).decode()
    
    def decrypt_private_key(self, encrypted_private_key: str, password: str) -> str:
        """Decrypt private key with password"""
        # Decode and split salt and encrypted key
        combined = base64.b64decode(encrypted_private_key)
        salt = combined[:16]
        encrypted_key = combined[16:]
        
        # Derive key from password
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        
        # Decrypt private key
        fernet = Fernet(key)
        decrypted_key = fernet.decrypt(encrypted_key)
        return decrypted_key.decode()
    
    def encrypt_file(self, file_data: bytes, key: Optional[bytes] = None) -> Tuple[bytes, str]:
        """Encrypt file data"""
        if key:
            fernet = Fernet(key)
        else:
            fernet = self._fernet
            
        encrypted_data = fernet.encrypt(file_data)
        iv = base64.b64encode(os.urandom(16)).decode()
        return encrypted_data, iv
    
    def decrypt_file(self, encrypted_data: bytes, iv: str, key: Optional[bytes] = None) -> bytes:
        """Decrypt file data"""
        if key:
            fernet = Fernet(key)
        else:
            fernet = self._fernet
            
        return fernet.decrypt(encrypted_data)
    
    def generate_file_hash(self, file_data: bytes) -> str:
        """Generate SHA-256 hash of file data"""
        return hashlib.sha256(file_data).hexdigest()
    
    def verify_file_integrity(self, file_data: bytes, expected_hash: str) -> bool:
        """Verify file integrity using hash"""
        actual_hash = self.generate_file_hash(file_data)
        return actual_hash == expected_hash

# Global encryption manager instance
encryption_manager = EncryptionManager()

# Convenience functions
def encrypt_message(message: str, key: Optional[bytes] = None) -> Tuple[str, str]:
    return encryption_manager.encrypt_message(message, key)

def decrypt_message(encrypted_message: str, iv: str, key: Optional[bytes] = None) -> str:
    return encryption_manager.decrypt_message(encrypted_message, iv, key)

def generate_key_pair() -> Tuple[str, str]:
    return encryption_manager.generate_key_pair()

def encrypt_file(file_data: bytes, key: Optional[bytes] = None) -> Tuple[bytes, str]:
    return encryption_manager.encrypt_file(file_data, key)

def decrypt_file(encrypted_data: bytes, iv: str, key: Optional[bytes] = None) -> bytes:
    return encryption_manager.decrypt_file(encrypted_data, iv, key)
