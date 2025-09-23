import json
import base64
import hashlib
from typing import Dict, Any, Optional, Tuple
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os
import secrets
from datetime import datetime

from app.config import settings

class EncryptionHandler:
    """Handles end-to-end encryption for WebSocket messages"""
    
    def __init__(self):
        self.user_keys: Dict[str, Dict[str, str]] = {}  # {user_id: {public_key, private_key}}
        self.conversation_keys: Dict[str, bytes] = {}  # {conversation_id: symmetric_key}
        self.key_exchanges: Dict[str, Dict[str, Any]] = {}  # {exchange_id: exchange_data}
    
    def generate_user_keypair(self, user_id: str) -> Tuple[str, str]:
        """Generate RSA key pair for a user"""
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
        
        self.user_keys[user_id] = {
            'public_key': public_pem.decode(),
            'private_key': private_pem.decode()
        }
        
        return public_pem.decode(), private_pem.decode()
    
    def get_user_public_key(self, user_id: str) -> Optional[str]:
        """Get user's public key"""
        return self.user_keys.get(user_id, {}).get('public_key')
    
    def get_user_private_key(self, user_id: str) -> Optional[str]:
        """Get user's private key"""
        return self.user_keys.get(user_id, {}).get('private_key')
    
    def encrypt_message_for_user(self, message: str, recipient_public_key: str) -> Dict[str, str]:
        """Encrypt a message for a specific user using their public key"""
        try:
            # Load recipient's public key
            public_key = serialization.load_pem_public_key(recipient_public_key.encode())
            
            # Generate a random AES key for this message
            aes_key = os.urandom(32)  # 256-bit key
            iv = os.urandom(16)  # 128-bit IV
            
            # Encrypt message with AES
            cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
            encryptor = cipher.encryptor()
            
            # Pad message to block size
            message_bytes = message.encode('utf-8')
            padding_length = 16 - (len(message_bytes) % 16)
            padded_message = message_bytes + bytes([padding_length] * padding_length)
            
            encrypted_message = encryptor.update(padded_message) + encryptor.finalize()
            
            # Encrypt AES key with recipient's public key
            encrypted_aes_key = public_key.encrypt(
                aes_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            return {
                'encrypted_message': base64.b64encode(encrypted_message).decode(),
                'encrypted_key': base64.b64encode(encrypted_aes_key).decode(),
                'iv': base64.b64encode(iv).decode(),
                'algorithm': 'RSA-OAEP+AES-256-CBC'
            }
            
        except Exception as e:
            raise Exception(f"Failed to encrypt message: {str(e)}")
    
    def decrypt_message_for_user(self, encrypted_data: Dict[str, str], user_id: str) -> str:
        """Decrypt a message using user's private key"""
        try:
            private_key_pem = self.get_user_private_key(user_id)
            if not private_key_pem:
                raise Exception("User private key not found")
            
            # Load private key
            private_key = serialization.load_pem_private_key(
                private_key_pem.encode(),
                password=None
            )
            
            # Decode encrypted data
            encrypted_message = base64.b64decode(encrypted_data['encrypted_message'])
            encrypted_aes_key = base64.b64decode(encrypted_data['encrypted_key'])
            iv = base64.b64decode(encrypted_data['iv'])
            
            # Decrypt AES key with private key
            aes_key = private_key.decrypt(
                encrypted_aes_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # Decrypt message with AES
            cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
            decryptor = cipher.decryptor()
            
            decrypted_padded = decryptor.update(encrypted_message) + decryptor.finalize()
            
            # Remove padding
            padding_length = decrypted_padded[-1]
            decrypted_message = decrypted_padded[:-padding_length]
            
            return decrypted_message.decode('utf-8')
            
        except Exception as e:
            raise Exception(f"Failed to decrypt message: {str(e)}")
    
    def generate_conversation_key(self, conversation_id: str) -> bytes:
        """Generate a symmetric key for a conversation"""
        key = os.urandom(32)  # 256-bit key
        self.conversation_keys[conversation_id] = key
        return key
    
    def get_conversation_key(self, conversation_id: str) -> Optional[bytes]:
        """Get conversation's symmetric key"""
        return self.conversation_keys.get(conversation_id)
    
    def encrypt_message_for_conversation(self, message: str, conversation_id: str) -> Dict[str, str]:
        """Encrypt a message for a conversation using symmetric key"""
        try:
            key = self.get_conversation_key(conversation_id)
            if not key:
                key = self.generate_conversation_key(conversation_id)
            
            iv = os.urandom(16)
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
            encryptor = cipher.encryptor()
            
            # Pad message
            message_bytes = message.encode('utf-8')
            padding_length = 16 - (len(message_bytes) % 16)
            padded_message = message_bytes + bytes([padding_length] * padding_length)
            
            encrypted_message = encryptor.update(padded_message) + encryptor.finalize()
            
            return {
                'encrypted_message': base64.b64encode(encrypted_message).decode(),
                'iv': base64.b64encode(iv).decode(),
                'algorithm': 'AES-256-CBC'
            }
            
        except Exception as e:
            raise Exception(f"Failed to encrypt message for conversation: {str(e)}")
    
    def decrypt_message_for_conversation(self, encrypted_data: Dict[str, str], conversation_id: str) -> str:
        """Decrypt a message from a conversation"""
        try:
            key = self.get_conversation_key(conversation_id)
            if not key:
                raise Exception("Conversation key not found")
            
            encrypted_message = base64.b64decode(encrypted_data['encrypted_message'])
            iv = base64.b64decode(encrypted_data['iv'])
            
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
            decryptor = cipher.decryptor()
            
            decrypted_padded = decryptor.update(encrypted_message) + decryptor.finalize()
            
            # Remove padding
            padding_length = decrypted_padded[-1]
            decrypted_message = decrypted_padded[:-padding_length]
            
            return decrypted_message.decode('utf-8')
            
        except Exception as e:
            raise Exception(f"Failed to decrypt message from conversation: {str(e)}")
    
    def initiate_key_exchange(self, initiator_id: str, recipient_id: str) -> str:
        """Initiate a key exchange between two users"""
        exchange_id = secrets.token_urlsafe(32)
        
        # Generate ephemeral key pair for this exchange
        ephemeral_private = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        ephemeral_public = ephemeral_private.public_key()
        
        ephemeral_public_pem = ephemeral_public.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        self.key_exchanges[exchange_id] = {
            'initiator_id': initiator_id,
            'recipient_id': recipient_id,
            'ephemeral_private': ephemeral_private,
            'ephemeral_public': ephemeral_public_pem.decode(),
            'created_at': datetime.utcnow(),
            'status': 'pending'
        }
        
        return exchange_id
    
    def complete_key_exchange(self, exchange_id: str, recipient_public_key: str) -> Dict[str, str]:
        """Complete a key exchange and return shared secret"""
        if exchange_id not in self.key_exchanges:
            raise Exception("Key exchange not found")
        
        exchange = self.key_exchanges[exchange_id]
        
        try:
            # Load recipient's public key
            recipient_pub_key = serialization.load_pem_public_key(recipient_public_key.encode())
            
            # Generate shared secret using ECDH (simplified version)
            # In a real implementation, you'd use ECDH for key agreement
            shared_secret = os.urandom(32)
            
            # Encrypt shared secret with recipient's public key
            encrypted_secret = recipient_pub_key.encrypt(
                shared_secret,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            exchange['status'] = 'completed'
            exchange['shared_secret'] = shared_secret
            
            return {
                'encrypted_secret': base64.b64encode(encrypted_secret).decode(),
                'ephemeral_public': exchange['ephemeral_public']
            }
            
        except Exception as e:
            exchange['status'] = 'failed'
            raise Exception(f"Failed to complete key exchange: {str(e)}")
    
    def sign_message(self, message: str, user_id: str) -> str:
        """Sign a message with user's private key"""
        try:
            private_key_pem = self.get_user_private_key(user_id)
            if not private_key_pem:
                raise Exception("User private key not found")
            
            private_key = serialization.load_pem_private_key(
                private_key_pem.encode(),
                password=None
            )
            
            # Create signature
            signature = private_key.sign(
                message.encode('utf-8'),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            return base64.b64encode(signature).decode()
            
        except Exception as e:
            raise Exception(f"Failed to sign message: {str(e)}")
    
    def verify_message_signature(self, message: str, signature: str, user_id: str) -> bool:
        """Verify a message signature"""
        try:
            public_key_pem = self.get_user_public_key(user_id)
            if not public_key_pem:
                return False
            
            public_key = serialization.load_pem_public_key(public_key_pem.encode())
            
            signature_bytes = base64.b64decode(signature)
            
            public_key.verify(
                signature_bytes,
                message.encode('utf-8'),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            return True
            
        except Exception:
            return False
    
    def create_message_hash(self, message: str) -> str:
        """Create SHA-256 hash of message for integrity checking"""
        return hashlib.sha256(message.encode('utf-8')).hexdigest()
    
    def verify_message_integrity(self, message: str, expected_hash: str) -> bool:
        """Verify message integrity using hash"""
        actual_hash = self.create_message_hash(message)
        return actual_hash == expected_hash

# Global encryption handler instance
encryption_handler = EncryptionHandler()
