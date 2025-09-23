# persistence/rotation.py
from __future__ import annotations
import os
from typing import Dict, Iterable

# Import your crypto helpers (names per your spec/crypto module)
# Adjust the import path to wherever you put them.
from crypto.primitives import rsa_encrypt_oaep, b64url_encode

from persistence.dir_json import (
    list_group_members,
    get_pubkey,
    bump_public_version_and_rewrap,
)

def _wrap_for_members(members: Iterable[str], clear_group_key: bytes) -> Dict[str, str]:
    """
    Wrap a clear 32-byte group key for each member with RSA-OAEP, then base64url-encode.
    Returns { user_id: wrapped_key_b64u }.
    """
    result: Dict[str, str] = {}
    for uid in members:
        pub = get_pubkey(uid)
        if not pub:
            # Member has no pubkey in directory; skip (or raise) per your policy.
            continue
        wrapped = rsa_encrypt_oaep(pub, clear_group_key)   # -> bytes
        result[uid] = b64url_encode(wrapped)               # -> str (no padding)
    return result

def rotate_public_key_and_share(explicit_members: Iterable[str] | None = None) -> int:
    """
    Generates a fresh 256-bit (32-byte) public-channel key in RAM only,
    wraps for each member, bumps version, and persists only wrapped keys.
    Returns the new public group version.
    """
    members = list(explicit_members) if explicit_members is not None else list_group_members("public")
    clear_group_key = os.urandom(32)  # keep ONLY in memory
    try:
        new_wrapped = _wrap_for_members(members, clear_group_key)
        if not new_wrapped and members:
            # Nothing wrapped—likely missing pubkeys. Choose: raise or silently continue.
            raise RuntimeError("No wrapped keys produced; missing pubkeys?")
        bump_public_version_and_rewrap(new_wrapped)
    finally:
        # Best-effort: wipe reference to key
        del clear_group_key
    # Read back version lazily to avoid a second file read; your caller can query if needed.
    # If you want, return persisted version by importing public_group_version() and calling it.
    from persistence.dir_json import public_group_version
    return public_group_version()
