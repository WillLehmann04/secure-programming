# backend/envelope.py
"""
Envelope helpers
----------------
Wraps payloads in a stable JSON shape and (optionally) signs them.
We always sign the *payload* only (per our protocol), then attach
`sig` and `alg` alongside the payload in the outer frame.
"""

from __future__ import annotations
import time
import logging
from typing import Callable, Optional, Tuple

# Prefer our own crypto helpers if they exist.
try:
    from backend.crypto import json_format as json_mod         # stabilise_json(obj)->bytes
except Exception:
    json_mod = None

try:
    from backend.crypto import base64url as b64u_mod           # base64url_encode/ decode
except Exception:
    b64u_mod = None

try:
    from backend.crypto import rsa_pss as team_pss             # team-provided PSS impl
except Exception:
    team_pss = None

# Cryptography fallback if our team modules aren’t complete.
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey


# canonical JSON 

def _canon_bytes(obj: dict) -> bytes:
    """Deterministic JSON -> bytes (team function first, otherwise a safe fallback)."""
    if json_mod and hasattr(json_mod, "stabilise_json"):
        return json_mod.stabilise_json(obj)
    import json
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


# base64url helpers

def _b64_helpers() -> Tuple[Callable[[bytes], str], Callable[[str], bytes]]:
    """Return (encode, decode) — prefer teammate module if available."""
    if b64u_mod and hasattr(b64u_mod, "base64url_encode"):
        return b64u_mod.base64url_encode, b64u_mod.base64url_decode

    # tiny local fallback
    import base64

    def enc(b: bytes) -> str:
        return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

    def dec(s: str) -> bytes:
        raw = s.encode()
        raw += b"=" * ((4 - len(raw) % 4) % 4)  # pad to multiple of 4
        return base64.urlsafe_b64decode(raw)

    return enc, dec


# RSA-PSS helpers

def _pss_funcs():
    """
    Return (sign, verify) functions.
    If the team module exists we’ll use that; otherwise fall back to cryptography.
    """
    if team_pss:
        for sname, vname in (("sign", "verify"), ("pss_sign", "pss_verify")):
            s = getattr(team_pss, sname, None)
            v = getattr(team_pss, vname, None)
            if callable(s) and callable(v):
                return s, v

    # fallback implementation
    def _sign(priv: RSAPrivateKey, msg: bytes) -> bytes:
        return priv.sign(
            msg,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )

    def _verify(pub: RSAPublicKey, msg: bytes, sig: bytes) -> bool:
        try:
            pub.verify(
                sig,
                msg,
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                            salt_length=padding.PSS.MAX_LENGTH),
                hashes.SHA256(),
            )
            return True
        except Exception:
            return False

    return _sign, _verify


#  public API

def sign_payload(payload: dict, privkey: RSAPrivateKey) -> dict:
    """Return {"payload": payload, "sig": <b64url>, "alg": "PS256"}."""
    enc, _ = _b64_helpers()
    sign, _verify = _pss_funcs()
    msg = _canon_bytes(payload)
    sig_b = sign(privkey, msg)
    return {"payload": payload, "sig": enc(sig_b), "alg": "PS256"}


def make_verifier(pub_lookup: Callable[[str], RSAPublicKey]):
    """
    Build a verifier function that:
      - pulls the sender id out of env["from"]
      - fetches that sender’s public key
      - verifies the signature over the canonical payload bytes
    """
    _, dec = _b64_helpers()
    _sign, verify = _pss_funcs()

    def _verify_env(env: dict) -> bool:
        try:
            sender = env["from"]
            payload = env["payload"]
            sig = dec(env["sig"])
            pub = pub_lookup(sender)
            return verify(pub, _canon_bytes(payload), sig)
        except Exception as e:
            logging.warning("envelope verify failed for %r: %s", env.get("from"), e)
            return False

    return _verify_env


def is_valid_envelope(env: dict, pub_lookup: Callable[[str], RSAPublicKey]) -> bool:
    """Handy one-liner for ‘does this envelope verify?’."""
    return make_verifier(pub_lookup)(env)


# helpers used by transport / routing

def make_envelope(
    typ: str,
    from_id: str,
    to: str,
    payload: dict,
    *,
    sign_with: Optional[RSAPrivateKey] = None,
    ts: Optional[int] = None,
) -> dict:
    """Build the standard frame. If sign_with is provided, sign the payload."""
    frame = {
        "type": typ,
        "from": from_id,
        "to": to,
        "ts": int(ts if ts is not None else time.time() * 1000),
        "payload": payload,
    }
    if sign_with:
        sig = sign_payload(payload, sign_with)
        frame["sig"], frame["alg"] = sig["sig"], sig["alg"]
    return frame


def verify_envelope_signature(env: dict, pub_lookup: Callable[[str], RSAPublicKey]) -> bool:
    """True iff env contains a valid signature for its payload."""
    return "sig" in env and is_valid_envelope(env, pub_lookup)
