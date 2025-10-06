'''
    Group: Group 2
    Members:
        - William Lehmann (A1889855)
        - Edward Chipperfield (A1889447)
        - G A Sadman (A1899867)
        - Aditeya Sahu (A1943902)
        
    Description:
        - This module provides cryptographic utilities including base64url encoding/decoding,
            JSON stabilization, RSA key management, RSA encryption/decryption, and RSA signing/verification.
'''

from hashlib import sha256
from .base64url import base64url_encode, base64url_decode
from .json_format import stabilise_json
from .rsa_pss import rsa_sign_pss, rsa_verify_pss

# ========== Helper function to convert String to bytes ========== 
def convert_to_bytes(data: str) -> bytes:
    if (isinstance(data, bytes)):
        return data
    return str(data).encode('utf-8')

# ========== Direct Message Signatures ========== 

def sign_direct_message_signature(private_key_pem: bytes, ciphertext_b64: str, from_ID: str, to_ID: str, timestamp: int) -> str:
    # SOCP section 12 specifies for DM (SHA256 ciphertext OR from OR to or TIMESTAMP)
    blob = (ciphertext_b64 + from_ID + to_ID + str(timestamp)).encode('utf-8')
    signature = rsa_sign_pss(private_key_pem, blob)
    return base64url_encode(signature)

def verify_direct_message_signature(public_key_pem: bytes, signature_b64: str, ciphertext_b64: str, from_ID: str, to_ID: str, timestamp: int) -> bool:
    # SOCP section 12 specifies for DM (SHA256 ciphertext OR from OR to or TIMESTAMP)
    blob = (ciphertext_b64 + from_ID + to_ID + str(timestamp)).encode('utf-8')
    signature = base64url_decode(signature_b64)           # expects str -> bytes
    return rsa_verify_pss(public_key_pem, blob, signature)

def sign_server_frame(ctx, payload):
    payload_bytes = stabilise_json(payload)
    sig = rsa_sign_pss(ctx.server_private_key, payload_bytes)
    return base64url_encode(sig)

def verify_server_frame(server_pubkey_pem, payload, sig_b64):
    payload_bytes = stabilise_json(payload)
    sig = base64url_decode(sig_b64)
    return rsa_verify_pss(server_pubkey_pem, payload_bytes, sig)