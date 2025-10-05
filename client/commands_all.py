#/ALL
from .utils import b64u, now_ts
async def cmd_all(ws, user_id: str, privkey_pem: bytes, text: str, tables, channel_id: str = "public"):

    if not text:
        return

    import os, hashlib, json
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from backend.crypto import rsa_sign_pss, stabilise_json, base64url_encode as _b64
    from backend.crypto.rsa_oaep import oaep_decrypt

    # helpers local imports so i dont mess anything up
    def _sha256(b: bytes) -> bytes:
        return hashlib.sha256(b).digest()

    def _content_sig_public(ciphertext_b64u: str, frm: str, ts_val: int) -> str:
        msg = (ciphertext_b64u + frm + str(ts_val)).encode("utf-8")
        return _b64(rsa_sign_pss(privkey_pem, _sha256(msg)))

    # get or unwrap the group key from tables
    gk = getattr(tables, "public_group_key", None)
    if gk is None:
        wrapped_b64u = getattr(tables, "wrapped_public_key_b64u", None)
        if not wrapped_b64u:
            print("No public group key available yet. Wait for a KEY_SHARE/advert (or have the server push it).")
            return
        try:
            from backend.crypto import base64url_decode as _b64d
            gk = oaep_decrypt(privkey_pem, _b64d(wrapped_b64u))  # expect 32 bytes
            tables.public_group_key = gk  # cache for next time
        except Exception as e:
            print("Failed to unwrap public group key:", e)
            return

    # encrypt with AES-GCM
    nonce = os.urandom(12)
    aes = AESGCM(gk)
    pt = text.encode("utf-8")
    ct = aes.encrypt(nonce, pt, aad=user_id.encode("utf-8"))

    # build payload + signatures
    nonce_b64u = b64u(nonce)
    ct_b64u = b64u(ct)
    ts = now_ts()  # keep consistent with your codebase (seconds)
    content_sig_b64u = _content_sig_public(ct_b64u, user_id, ts)

    payload = {
        "ciphertext": ct_b64u,
        "nonce": nonce_b64u,
        "content_sig": content_sig_b64u,
    }

    # hop-level transport sig over canonical payload
    transport_sig_b64u = _b64(rsa_sign_pss(privkey_pem, stabilise_json(payload)))

    frame = {
        "type": "MSG_PUBLIC_CHANNEL",
        "from": user_id,
        "to": channel_id,
        "ts": ts,
        "payload": payload,
        "sig": transport_sig_b64u,
        "alg": "PS256",
    }

    await ws.send(json.dumps(frame))
    print(f"[sent] /all -> {channel_id} ({len(pt)} bytes)")