import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from backend.crypto import rsa_sign_pss, stabilise_json, base64url_encode
from .utils import sha256_bytes


def signed_transport_sig(payload_obj: dict, privkey_pem: bytes) -> str:
    b = stabilise_json(payload_obj)
    sig = rsa_sign_pss(privkey_pem, b)
    return base64url_encode(sig)


def content_sig_dm(ciphertext_bytes: bytes, frm: str, to: str, ts: str, privkey_pem: bytes) -> str:
    d = sha256_bytes(ciphertext_bytes + frm.encode() + to.encode() + ts.encode())
    return base64url_encode(rsa_sign_pss(privkey_pem, d))


def content_sig_public(ciphertext_bytes: bytes, frm: str, ts: str, privkey_pem: bytes) -> str:
    d = sha256_bytes(ciphertext_bytes + frm.encode() + ts.encode())
    return base64url_encode(rsa_sign_pss(privkey_pem, d))


def aesgcm_encrypt(key: bytes, plaintext: bytes, aad: bytes = b"") -> tuple[bytes, bytes]:
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext, aad)
    return nonce, ct
