from .rsa_oaep import oaep_encrypt_large, oaep_decrypt_large
from .base64url import base64url_encode, base64url_decode

def encrypt_for_transport(public_pem: bytes, data: bytes) -> list[str]:
    return [base64url_encode(c) for c in oaep_encrypt_large(public_pem, data)]

def decrypt_from_transport(private_pem: bytes, encoded_chunks: list[str]) -> bytes:
    chunks = [base64url_decode(s) for s in encoded_chunks]
    return oaep_decrypt_large(private_pem, chunks)