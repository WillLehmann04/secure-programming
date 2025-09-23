from typing import Optional, Dict
from cryptography.hazmat.primitives import serialization, hashes
from backend.crypto.rsa_key_management import load_public_key
from backend.crypto.base64url import base64url_encode

class IdDirectory:
    def __init__(self):
        self._users: Dict[str, dict] = {}    # user_id -> { "pub_pem": bytes, "kid": str, ... }
        self._servers: Dict[str, dict] = {}  # server_id -> { "pub_pem": bytes, "kid": str, ... }

    @staticmethod
    def compute_kid(pub_pem: bytes) -> str:
        spki_der = load_public_key(pub_pem).public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo
        )
        h = hashes.Hash(hashes.SHA256())
        h.update(spki_der)
        return base64url_encode(h.finalize())

    # --- Users ---

    def insert_user(self, user_id: str, pub_pem: bytes, **meta) -> None:
        # Store public key and derived kid; allow extra metadata (display name, caps, etc.)
        self._users[user_id] = {"pub_pem": pub_pem, "kid": self.compute_kid(pub_pem), **meta}

    def get_user_pubkey(self, user_id: str) -> Optional[bytes]:
        rec = self._users.get(user_id)
        return rec["pub_pem"] if rec else None

    def get_user_kid(self, user_id: str) -> Optional[str]:
        rec = self._users.get(user_id)
        return rec["kid"] if rec else None

    # --- Servers ---

    def upsert_server(self, server_id: str, pub_pem: bytes, **meta) -> None:
        self._servers[server_id] = {"pub_pem": pub_pem, "kid": self.compute_kid(pub_pem), **meta}

    def get_server_pubkey(self, server_id: str) -> Optional[bytes]:
        rec = self._servers.get(server_id)
        return rec["pub_pem"] if rec else None

    def get_server_kid(self, server_id: str) -> Optional[str]:
        rec = self._servers.get(server_id)
        return rec["kid"] if rec else None