import hashlib
from typing import List
import time

from backend.crypto import base64url_encode
from .constants import OAEP_MAX_PLAINTEXT


def now_ts() -> int:
    return int(time.time() * 1000)


def sha256_bytes(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def b64u(data: bytes) -> str:
    return base64url_encode(data)


def chunk_plaintext(plain: bytes, max_chunk: int = OAEP_MAX_PLAINTEXT) -> List[bytes]:
    return [plain[i:i + max_chunk] for i in range(0, len(plain), max_chunk)]


def dm_seen_key(payload: dict) -> str:
    s = f"{payload.get('from')}|{payload.get('to')}|{payload.get('ts')}|{payload.get('ciphertext')}"
    return hashlib.sha256(s.encode()).hexdigest()
