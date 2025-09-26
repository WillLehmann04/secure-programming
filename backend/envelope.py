# backend/envelope.py

# SOCP : JSON envelope & signing discipline
# - Canonical JSON for signing
# - Transport signature over payload only
# - HELLO/BOOTSTRAP are exempt; everything else requires a sig

from __future__ import annotations

import base64
import json
import logging
from typing import Callable, Tuple


from backend.crypto import rsa_sign, rsa_verify  # -> bytes, raises on bad inputs

log = logging.getLogger("backend.envelope")


# ---------- Canonical JSON ----------

def canonical_json_bytes(obj: dict) -> bytes:

    """Sorted keys, compact separators, UTF-8 bytes."""

    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


# ---------- Envelope structure check (outer shape only) ----------

def is_valid_envelope(env: dict) -> Tuple[bool, str]:
    req = ("type", "from", "to", "ts", "payload")
    for k in req:
        if k not in env:
            return False, f"missing:{k}"
    if not isinstance(env["payload"], dict):
        return False, "payload:not_object"
    return True, ""


# ---------- Base64url helpers ----------

def b64u_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")

def b64u_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "==") # added '==' padding to be safe for urlsafe decode


# ---------- Transport signature over payload ----------

def sign_payload(payload: dict, private_key) -> str:

    """Return base64url(sig(payload_json)) using RSASSA-PSS over SHA-256."""

    msg = canonical_json_bytes(payload)
    sig = rsa_sign(msg, private_key)
    return b64u_encode(sig)


def verify_payload_sig(payload: dict, sig_b64u: str, public_key) -> bool:
    try:
        sig = b64u_decode(sig_b64u)
    except Exception:
        return False
    msg = canonical_json_bytes(payload)
    try:
        return rsa_verify(msg, sig, public_key)
    except Exception:
        return False


# ---------- Policy (what must be signed?) ----------

# Spec intent: HELLO/BOOTSTRAP can omit sig; everything else requires it.

_HELLO_PREFIXES = ("USER_HELLO", "SERVER_HELLO", "BOOTSTRAP")

def _sig_required(env_type: str) -> bool:
    return not any(env_type.startswith(p) for p in _HELLO_PREFIXES)


# ---------- Verifier factory to plug into TransportServer ----------

def make_verifier(pubkey_lookup: Callable[[str], object]) -> Callable[[dict, object], bool]:

    """
    pubkey_lookup(peer_id:str) -> public_key (object your crypto verifies with)
    Returns a function (env, link) -> bool suitable for TransportServer(verify_envelope=...)
    """
    def _verify(env: dict, link) -> bool:
        t = env.get("type", "")
        if not _sig_required(t):
            return True  # allowed to be unsigned (HELLO/BOOTSTRAP)

        sig = env.get("sig")
        if not sig:
            log.debug("missing sig for type=%s from=%s", t, env.get("from"))
            return False

        pub = pubkey_lookup(env["from"])
        if not pub:
            log.debug("no public key for %s", env.get("from"))
            return False

        return verify_payload_sig(env["payload"], sig, pub)

    return _verify
