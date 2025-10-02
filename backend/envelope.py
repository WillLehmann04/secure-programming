# backend/envelope.py

from __future__ import annotations

import logging
from typing import Callable, Tuple

# --- Team crypto modules (names as your teammates defined) ---
try:
    # stabilise_json(obj) -> bytes
    from backend.crypto import json_format as jf
except Exception:
    jf = None

try:
    # base64url_encode(bytes)->str , base64url_decode(str)->bytes
    from backend.crypto import base64url as b64u
except Exception:
    b64u = None

# Optional future module; if added later we’ll prefer it.
try:
    from backend.crypto import rsa_pss as team_pss
except Exception:
    team_pss = None

# --- Fallback libraries (we only use these if team_pss is not present) ---
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding as _padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey


# -----------------------------
# Canonicalize payload for signing (team function first)
# -----------------------------

def _get_canonical_bytes(payload: dict) -> bytes:
    """
    Serialize payload deterministically for signing.
    Prefer backend.crypto.json_format.stabilise_json.
    """
    if jf and hasattr(jf, "stabilise_json"):
        return jf.stabilise_json(payload)
    # ultra-safe fallback: minimal sortable JSON (bytes)
    import json
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


# -----------------------------
# Base64url helpers (team functions)
# -----------------------------

def _get_b64u_helpers() -> Tuple[Callable[[bytes], str], Callable[[str], bytes]]:

    """
    Return (encode_fn, decode_fn) that match our base64url module.
    """
    if not b64u or not hasattr(b64u, "base64url_encode") or not hasattr(b64u, "base64url_decode"):
        import base64

        def _enc(d: bytes) -> str:
            return base64.urlsafe_b64encode(d).rstrip(b"=").decode("ascii")

        def _dec(s: str) -> bytes:
            b = s.encode("ascii")
            pad = (-len(b)) % 4
            if pad:
                b += b"=" * pad
            return base64.urlsafe_b64decode(b)

        return _enc, _dec

    return b64u.base64url_encode, b64u.base64url_decode


# -----------------------------
# RSA-PSS helpers
# -----------------------------

def _get_pss_funcs() -> Tuple[Callable[[bytes, RSAPrivateKey], bytes],
                               Callable[[RSAPublicKey, bytes, bytes], bool]]:
    

    if team_pss:
        cand = [
            ("sign", "verify"),
            ("pss_sign", "pss_verify"),
        ]
        for sname, vname in cand:
            s = getattr(team_pss, sname, None)
            v = getattr(team_pss, vname, None)
            if callable(s) and callable(v):
                def _sign(priv: RSAPrivateKey, msg: bytes) -> bytes:
                    return s(priv, msg)  # type: ignore[misc]

                def _verify(pub: RSAPublicKey, msg: bytes, sig: bytes) -> bool:
                    return bool(v(pub, msg, sig))  # type: ignore[misc]

                return _sign, _verify

    def _sign(priv: RSAPrivateKey, msg: bytes) -> bytes:
        return priv.sign(
            msg,
            _padding.PSS(mgf=_padding.MGF1(hashes.SHA256()), salt_length=_padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )

    def _verify(pub: RSAPublicKey, msg: bytes, sig: bytes) -> bool:
        try:
            pub.verify(
                sig,
                msg,
                _padding.PSS(mgf=_padding.MGF1(hashes.SHA256()), salt_length=_padding.PSS.MAX_LENGTH),
                hashes.SHA256(),
            )
            return True
        except Exception:
            return False

    return _sign, _verify


# -----------------------------
# Public API: sign/verify envelope
# -----------------------------

def sign_payload(payload: dict, privkey: RSAPrivateKey) -> dict:

    """
    Returns {"payload": payload, "sig": <b64url>, "alg": "PS256"}
    """
    enc, _dec = _get_b64u_helpers()
    msg = _get_canonical_bytes(payload)

    raw_sign, _raw_verify = _get_pss_funcs()
    sig_bytes = raw_sign(privkey, msg)
    sig_b64u = enc(sig_bytes)

    return {"payload": payload, "sig": sig_b64u, "alg": "PS256"}


def make_verifier(pubkey_lookup: Callable[[str], RSAPublicKey]) -> Callable[[dict], bool]:

    """
    Returns a verifier(env) that:
      * extracts sender id from env["from"]
      * gets the sender's public key via pubkey_lookup(sender_id)
      * verifies the signature over canonical(payload)
    """
    _, dec = _get_b64u_helpers()
    _raw_sign, raw_verify = _get_pss_funcs()

    def verifier(env: dict) -> bool:
        try:
            sender_id = env["from"]
            payload = env["payload"]
            sig_b64 = env["sig"]
            pub = pubkey_lookup(sender_id)

            msg = _get_canonical_bytes(payload)
            sig_bytes = dec(sig_b64)
            return raw_verify(pub, msg, sig_bytes)
        except Exception as e:
            logging.warning("envelope verify failed: %s", e)
            return False

    return verifier


def is_valid_envelope(env: dict, pubkey_lookup: Callable[[str], RSAPublicKey]) -> bool:

    """
    Convenience wrapper for quick checks.
    """
    return make_verifier(pubkey_lookup)(env)
