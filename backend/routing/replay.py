from hashlib import sha256
from backend.crypto.json_format import stabilise_json
from backend.crypto.base64url import base64url_decode

def frame_hash_key(envelope: dict) -> bytes:
    h = sha256()
    h.update(str(envelope.get("type", "")).encode("utf-8"))
    h.update(str(envelope.get("from", "")).encode("utf-8"))
    h.update(str(envelope.get("to", "")).encode("utf-8"))
    h.update(str(envelope.get("ts", "")).encode("utf-8"))
    h.update(stabilise_json(envelope.get("payload", {})))
    sig_b64 = envelope.get("sig")
    if isinstance(sig_b64, str):
        try:
            h.update(base64url_decode(sig_b64))
        except Exception:
            pass
    return h.digest()