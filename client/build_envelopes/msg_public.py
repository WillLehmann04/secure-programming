from client.helpers.small_utils import base64url_encode, stabilise_json, rsa_sign_pss

def build_msg_public(nonce_b64u: str, ct_b64u: str, frm: str, ts: int, content_sig_b64u: str, privkey_pem: bytes, channel_id: str) -> dict:
    payload = {
        "nonce": nonce_b64u,
        "ciphertext": ct_b64u,
        "from": frm,
        "to": channel_id,
        "ts": ts,
        "content_sig": content_sig_b64u,
    }
    payload_bytes = stabilise_json(payload)
    sig = rsa_sign_pss(privkey_pem, payload_bytes)
    sig_b64 = base64url_encode(sig)
    return {
        "type": "MSG_PUBLIC_CHANNEL",
        "from": frm,
        "to": channel_id,
        "ts": ts,
        "payload": payload,
        "sig": sig_b64,
        "alg": "PS256",
    }
