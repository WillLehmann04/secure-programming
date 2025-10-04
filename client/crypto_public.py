from __future__ import annotations
import os, hashlib
from typing import Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from backend.crypto import rsa_encrypt_oaep, rsa_decrypt_oaep, rsa_sign_pss, base64url_encode, base64url_decode, stabilise_json

def sha256_bytes(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()

def aesgcm_encrypt(key: bytes, plaintext: bytes, aad: bytes=b"") -> Tuple[bytes, bytes]:
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext, aad)
    return nonce, ct

def b64u(b: bytes) -> str:
    return base64url_encode(b)

def transport_sig(payload_obj: dict, privkey_pem: bytes) -> str:
    return b64u(rsa_sign_pss(privkey_pem, stabilise_json(payload_obj)))

def content_sig_dm(ciphertext: bytes, frm: str, to: str, ts: str, privkey_pem: bytes) -> str:
    return b64u(rsa_sign_pss(privkey_pem, sha256_bytes(ciphertext + frm.encode() + to.encode() + ts.encode())))

def content_sig_public(ciphertext: bytes, frm: str, ts: str, privkey_pem: bytes) -> str:
    return b64u(rsa_sign_pss(privkey_pem, sha256_bytes(ciphertext + frm.encode() + ts.encode())))
