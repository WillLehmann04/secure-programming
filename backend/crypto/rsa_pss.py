# backend/crypto/rsa_pss.py
from __future__ import annotations
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from .rsa_key_management import load_private_key, load_public_key

def _as_bytes(pem_or_str):
    return pem_or_str.encode("utf-8") if isinstance(pem_or_str, str) else pem_or_str

def rsa_sign_pss(privkey_pem: bytes | str, message: bytes) -> bytes:
    """
    RSA-PSS with SHA-256, salt_length = MAX_LENGTH (spec-compliant).
    """
    priv = load_private_key(_as_bytes(privkey_pem))
    return priv.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH,
        ),
        hashes.SHA256(),
    )

def rsa_verify_pss(pubkey_pem: bytes | str, message: bytes, signature: bytes) -> bool:
    """
    Returns True if signature is valid under RSA-PSS/SHA-256.
    """
    pub = load_public_key(_as_bytes(pubkey_pem))
    try:
        pub.verify(
            signature,
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False
