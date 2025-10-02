from __future__ import annotations
import json, os, fcntl
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime, timezone

# JSON "DB"

BASE = Path("storage")
BASE.mkdir(exist_ok=True)
LOCKFILE = BASE / "_lock"

def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

class _JsonFile:
    def __init__(self, filename: str):
        self.path = BASE / filename
        if not self.path.exists():
            self._atomic_write({})

    def read(self) -> dict:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def _atomic_write(self, obj: dict) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, separators=(",", ":"), sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    def update(self, mutator) -> dict:
        with open(LOCKFILE, "a") as lf:
            fcntl.flock(lf, fcntl.LOCK_EX)
            data = self.read()
            mutator(data)
            self._atomic_write(data)
            fcntl.flock(lf, fcntl.LOCK_UN)
        return data

# Files for users groups and memberships
_users  = _JsonFile("users.json")
_groups = _JsonFile("groups.json")
_members = _JsonFile("group_members.json")

# Bootdstrap + queries

def ensure_public_group() -> None:
    def mut(d):
        if "public" not in d:
            d["public"] = {
                "creator_id": "system",
                "created_at": _utcnow(),
                "meta": {"desc": "default broadcast group"},
                "version": 1,
            }
    _groups.update(mut)

def public_group_version() -> int:
    g = _groups.read()
    return int(g.get("public", {}).get("version", 0))

def list_group_members(group_id: str = "public") -> List[str]:
    m = _members.read()
    return sorted((m.get(group_id) or {}).keys())

# Users (Dir)

def register_user(user_id: str, pubkey: str, privkey_store: str,
                  pake_verifier: str, meta: Optional[dict] = None) -> None:
    if not user_id or not pubkey or not privkey_store or not pake_verifier:
        raise ValueError("missing required user fields")
    def mut(d):
        if user_id in d:
            raise ValueError("user exists")
        d[user_id] = {
            "pubkey": pubkey,
            "privkey_store": privkey_store,   # encrypted blob (base64url)
            "pake_password": pake_verifier,
            "meta": meta or {},
            "version": 1,
        }
    _users.update(mut)

def get_pubkey(user_id: str) -> Optional[str]:
    return _users.read().get(user_id, {}).get("pubkey")

def user_exists(user_id: str) -> bool:
    return user_id in _users.read()

def get_user_meta(user_id: str) -> Optional[dict]:
    row = _users.read().get(user_id)
    return row.get("meta") if row else None

def add_member(group_id: str, user_id: str, role: str, wrapped_key_b64u: str) -> None:
    if not wrapped_key_b64u:
        raise ValueError("wrapped_key_b64u is required")
    def mut(d):
        d.setdefault(group_id, {})
        d[group_id][user_id] = {
            "role": role,
            "wrapped_key": wrapped_key_b64u,  # store wrapped key only
            "added_at": _utcnow(),
        }
    _members.update(mut)

def remove_member(group_id: str, user_id: str) -> None:
    def mut(d):
        if group_id in d and user_id in d[group_id]:
            del d[group_id][user_id]
            if not d[group_id]:
                del d[group_id]
    _members.update(mut)

def get_wrapped_key(group_id: str, user_id: str) -> Optional[str]:
    return (_members.read().get(group_id, {}) or {}).get(user_id, {}).get("wrapped_key")

def bump_public_version_and_rewrap(new_wrapped_keys: Dict[str, str]) -> None:
    """
    Call this after generating a fresh random 32-byte group key in memory and
    wrapping it with each member's public key (RSA-OAEP). Only the wrapped keys
    are persisted here.
    """
    if not isinstance(new_wrapped_keys, dict):
        raise ValueError("new_wrapped_keys must be a dict[user_id -> wrapped_key_b64u]")

    def mut_groups(g):
        if "public" not in g:
            raise ValueError("public group missing; call ensure_public_group() first")
        g["public"]["version"] = int(g["public"].get("version", 0)) + 1

    def mut_members(m):
        m.setdefault("public", {})
        for uid, wrapped in new_wrapped_keys.items():
            existing_role = (m["public"].get(uid, {}) or {}).get("role", "member")
            m["public"][uid] = {
                "role": existing_role,
                "wrapped_key": wrapped,
                "added_at": _utcnow(),
            }

    _groups.update(mut_groups)
    _members.update(mut_members)

# Smoke Test Helper Function (We can Remove)
if __name__ == "__main__":
    ensure_public_group()
    assert public_group_version() >= 1
    if not user_exists("alice"):
        register_user("alice", "PEM_OR_JWK", "ENC_PRIVKEY_B64URL", "PAKE_VERIFIER", {"display_name": "Alice"})
    add_member("public", "alice", "member", "WRAPPED_KEY_FOR_ALICE_V1")
    print("Members:", list_group_members("public"))
    bump_public_version_and_rewrap({"alice": "WRAPPED_KEY_FOR_ALICE_V2"})
    print("Version:", public_group_version())
