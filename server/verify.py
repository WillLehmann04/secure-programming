from __future__ import annotations
import hashlib
from typing import Dict, Any, Optional
from persistence.dir_json import get_pubkey
from backend.crypto import rsa_verify_pss, stabilise_json, base64url_decode

def _sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()

def verify_transport_sig(sender_id: str, payload: Dict[str, Any], sig_b64u: Optional[str]) -> bool:
    if not isinstance(sig_b64u, str) or not sig_b64u:
        return False
    pub = get_pubkey(sender_id)
    if not pub:
        return False
    msg = stabilise_json(payload)
    sig = base64url_decode(sig_b64u)
    return rsa_verify_pss(pub, msg, sig)

def verify_content_sig(frame_type: str, payload: Dict[str, Any], sender_id: str) -> bool:
    sig_b64 = payload.get("content_sig")
    if not isinstance(sig_b64, str):
        return False
    pub = get_pubkey(sender_id)
    if not pub:
        return False
    frm = payload.get("from", "")
    if frm != sender_id:
        return False
    try:
        ct = base64url_decode(payload.get("ciphertext", ""))
    except Exception:
        return False
    ts = str(payload.get("ts", ""))
    if frame_type == "MSG_DIRECT":
        to = payload.get("to", "")
        digest = _sha256(ct + frm.encode() + to.encode() + ts.encode())
    elif frame_type == "MSG_PUBLIC_CHANNEL":
        digest = _sha256(ct + frm.encode() + ts.encode())
    else:
        return False
    sig = base64url_decode(sig_b64)
    return rsa_verify_pss(pub, digest, sig)
