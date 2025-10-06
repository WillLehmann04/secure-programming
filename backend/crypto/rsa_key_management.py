'''
    Group: Group 2
    Members:
        - William Lehmann (A1889855)
        - Edward Chipperfield (A1889447)
        - G A Sadman (A1899867)
        - Aditeya Sahu (A1943902)
        
    Description:
        - This module provides RSA key management functionality including key generation,
          loading public and private keys from PEM format, and handling key objects.
'''

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey, RSAPrivateKey

def generate_rsa_keypair(bits: int = 4096) -> tuple[bytes, bytes]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return private_pem, public_pem

def load_public_key(public_pem_or_obj):
    if isinstance(public_pem_or_obj, RSAPublicKey):
        return public_pem_or_obj
    if isinstance(public_pem_or_obj, str):
        public_pem_or_obj = public_pem_or_obj.encode("utf-8")
    return serialization.load_pem_public_key(public_pem_or_obj)

def load_private_key(private_pem_or_obj):
    if isinstance(private_pem_or_obj, RSAPrivateKey):
        return private_pem_or_obj
    if isinstance(private_pem_or_obj, str):
        private_pem_or_obj = private_pem_or_obj.encode("utf-8")
    return serialization.load_pem_private_key(private_pem_or_obj, password=None)
