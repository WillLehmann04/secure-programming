# backend/keydir.py

from __future__ import annotations
from typing import Optional, Dict

class KeyDirectory:

    """
    Minimal key directory used by Part 4 verifier.
    Replace the in-memory dict with your teammate's DB/storage later.
    """
    def __init__(self):
        self._pubkeys: Dict[str, object] = {}  # peer_id -> RSA public key object

    def add_public_key(self, peer_id: str, pubkey: object) -> None:
        self._pubkeys[peer_id] = pubkey

    def get_public_key(self, peer_id: str) -> Optional[object]:
        return self._pubkeys.get(peer_id)

keydir = KeyDirectory()
