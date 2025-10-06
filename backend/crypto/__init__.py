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
        - It consolidates various cryptographic functions for easy import and use across the backend.
'''

from .base64url import base64url_encode, base64url_decode
from .json_format import stabilise_json
from .rsa_key_management import generate_rsa_keypair, load_public_key, load_private_key
from .rsa_oaep import oaep_encrypt, oaep_decrypt, oaep_max_plaintext_len, oaep_encrypt_large, oaep_decrypt_large
from .rsa_pss import rsa_sign_pss, rsa_verify_pss

__all__ = [
    "base64url_encode", "base64url_decode",
    "stabilise_json",
    "load_public_key", "load_private_key", "generate_rsa_keypair",
    "rsa_encrypt_oaep", "rsa_decrypt_oaep", "rsa_oaep_max_plaintext_len",
    "rsa_encrypt_large", "rsa_decrypt_large",
    "rsa_sign_pss", "rsa_verify_pss",
    "sign_payload", "verify_payload",
]