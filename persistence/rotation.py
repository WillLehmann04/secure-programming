from __future__ import annotations
import os
from typing import Dict, Iterable, Tuple
from backend.crypto import rsa_encrypt_oaep, base64url_encode

from persistence.dir_json import (
    list_group_members,
    get_pubkey,
    bump_public_version_and_rewrap,
)

def _wrap_for_members(members: Iterable[str], clear_group_key: bytes) -> Dict[str, str]:
    """
    Wrap a clear 32-byte group key for each member with RSA-OAEP/SHA-256, b64url encode.
    Returns { user_id: wrapped_key_b64u }.
    """
    out: Dict[str, str] = {}
    for uid in members:
        pub = get_pubkey(uid)
        if not pub:
            # Skip any users without a directory pubkey
            continue
        wrapped = rsa_encrypt_oaep(pub.encode("utf-8") if isinstance(pub, str) else pub, clear_group_key)
        out[uid] = base64url_encode(wrapped)
    return out

def generate_wrapped_public_keyset(
    explicit_members: Iterable[str] | None = None,
) -> Tuple[Dict[str, str], bytes]:
    """
    Generate a fresh 256-bit group key (in RAM), wrap for each member, and return:
        (wrapped_map, clear_group_key)
    Caller decides when to bump version and persist the wrapped_map.
    """
    members = list(explicit_members) if explicit_members is not None else list_group_members("public")
    clear_group_key = os.urandom(32)  # plaintext only in RAM
    wrapped = _wrap_for_members(members, clear_group_key)
    return wrapped, clear_group_key

def rotate_public_key_and_share(explicit_members: Iterable[str] | None = None) -> int:
    """
    Convenience: generate a new 32-byte group key, wrap for members,
    bump public version, persist wrapped keys. Returns the new version.
    """
    wrapped, clear = generate_wrapped_public_keyset(explicit_members)
    try:
        bump_public_version_and_rewrap(wrapped)
    finally:
        # Drop plaintext reference; never persisted
        del clear
    from persistence.dir_json import public_group_version
    return public_group_version()
