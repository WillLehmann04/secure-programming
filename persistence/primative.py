# crypto/primitives.py
# TEMPORARY shim for wiring tests — REPLACE with real RSA-4096 OAEP/SHA-256 + PSS/SHA-256
import base64

def rsa_encrypt_oaep(pubkey_pem_or_jwk: str, plaintext: bytes) -> bytes:
    # TODO: implement real RSA OAEP/SHA-256 using your crypto lib (e.g., cryptography)
    # For now, NOT secure — just echoes plaintext to demonstrate persistence wiring.
    return plaintext

def b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
