# backend/crypto/rsa_oaep.py
from __future__ import annotations
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from .rsa_key_management import load_public_key, load_private_key

def _as_bytes(maybe_bytes_or_str):
    return maybe_bytes_or_str.encode("utf-8") if isinstance(maybe_bytes_or_str, str) else maybe_bytes_or_str

def rsa_encrypt_oaep(pubkey_pem: bytes | str, plaintext: bytes) -> bytes:
    """
    RSA-OAEP with SHA-256 (MGF1=SHA-256), as required by SOCP v1.3.
    pubkey_pem may be bytes or str (PEM).
    """
    pub = load_public_key(_as_bytes(pubkey_pem))
    return pub.encrypt(
        plaintext,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

def rsa_decrypt_oaep(privkey_pem: bytes | str, ciphertext: bytes) -> bytes:
    """
    RSA-OAEP with SHA-256 (MGF1=SHA-256).
    privkey_pem may be bytes or str (PEM).
    """
    priv = load_private_key(_as_bytes(privkey_pem))
    return priv.decrypt(
        ciphertext,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
