from .rsa_oaep import oaep_encrypt_large, oaep_decrypt_large
from .base64url import base64url_encode, base64url_decode
from hashlib import sha256


# ========== Helper function to convert String to bytes ========== 
def convert_to_bytes(data: str) -> bytes:
    if (isinstance(data, bytes)):
        return data
    return str(data).encode('utf-8')

# ========== Encryptionf or Direct messaging absed off socp9.2 ========== 
def direct_message_sig(private_pem: bytes, ciphertext_b64: bytes, from_id: str, timestamp: int) -> str:
    message = sha256()
    from .rsa_pss import rsa_sign_pss
    return rsa_sign_pss(private_pem, private_pem)