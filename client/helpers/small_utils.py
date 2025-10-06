'''
    Group: Group 2
    Members:
        - William Lehmann (A1889855)
        - Edward Chipperfield (A1889447)
        - G A Sadman (A1899867)
        - Aditeya Sahu (A1943902)
        
    Description:
        - This module provides small utility functions for cryptographic operations,
          including timestamp generation, SHA-256 hashing, chunking plaintext,
          and base64 URL encoding.
'''

import hashlib
import time
from typing import Tuple, List
import json
import os
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from backend.crypto import (
    rsa_sign_pss,
    base64url_encode,
    base64url_decode,
    stabilise_json
)

OAEP_HASH_BYTES = 32  # SHA-256
RSA_4096_KEY_BYTES = 4096 // 8  # 512
OAEP_MAX_PLAINTEXT = RSA_4096_KEY_BYTES - 2 * OAEP_HASH_BYTES - 2  # 446 bytes


def now_ts() -> str:
    return int(time.time() * 1000)

def sha256_bytes(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()

def chunk_plaintext(plain: bytes, max_chunk: int = OAEP_MAX_PLAINTEXT) -> List[bytes]:
    return [plain[i:i+max_chunk] for i in range(0, len(plain), max_chunk)]

def b64u(data: bytes) -> str:
    return base64url_encode(data)

def signed_transport_sig(payload_obj: dict, privkey_pem: bytes) -> str:
    b = stabilise_json(payload_obj)
    sig = rsa_sign_pss(privkey_pem, b)
    return b64u(sig)

def content_sig_dm(ciphertext_bytes: bytes, frm: str, to: str, ts: str, privkey_pem: bytes) -> str:
    d = sha256_bytes(ciphertext_bytes + frm.encode() + to.encode() + ts.encode())
    return b64u(rsa_sign_pss(privkey_pem, d))

def dm_seen_key(payload: dict) -> str:
    s = f"{payload.get('from')}|{payload.get('to')}|{payload.get('ts')}|{payload.get('ciphertext')}"
    return hashlib.sha256(s.encode()).hexdigest()

def content_sig_public(ciphertext_bytes: bytes, frm: str, ts: str, privkey_pem: bytes) -> str:
    d = sha256_bytes(ciphertext_bytes + frm.encode() + ts.encode())
    return b64u(rsa_sign_pss(privkey_pem, d))

# AES-GCM for public channel
def aesgcm_encrypt(key: bytes, plaintext: bytes, aad: bytes = b"") -> tuple[bytes, bytes]:
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext, aad)
    return nonce, ct

# Key management - replace with our actual decrypt
def load_client_keys_from_config(cfg_path: str) -> Tuple[str, bytes, str, str]:
    cfg = json.loads(Path(cfg_path).read_text(encoding="utf-8"))
    user_id = cfg["user_id"]
    priv_pem = base64url_decode(cfg["privkey_pem_b64"])
    pub_pem = cfg["pubkey_pem"]
    server_id = cfg["server_id"]
    return user_id, priv_pem, pub_pem, server_id