from client.helpers.small_utils import now_ts, b64u, base64url_encode, stabilise_json, chunk_plaintext, signed_transport_sig, content_sig_dm, rsa_sign_pss, sha256_bytes
from backend.crypto import rsa_sign_pss, oaep_encrypt
import json
import traceback
OAEP_HASH_BYTES = 32  # SHA-256s
RSA_4096_KEY_BYTES = 4096 // 8  # 512
OAEP_MAX_PLAINTEXT = RSA_4096_KEY_BYTES - 2 * OAEP_HASH_BYTES - 2  # 446 bytes

from client.build_envelopes.msg_direct import build_msg_direct

async def cmd_tell(ws, user_id: str, privkey_pem: bytes, to: str, text: str, tables):
    try:
        plain = text.encode("utf-8")
        recipient_pub = tables.user_pubkeys.get(to)
        if not recipient_pub:
            return
        ts = now_ts()
        if len(plain) <= OAEP_MAX_PLAINTEXT:
            ciphertext = oaep_encrypt(recipient_pub, plain)
            ciphertext_b64u = b64u(ciphertext)
            content_sig = content_sig_dm(ciphertext, user_id, to, str(ts), privkey_pem)
            env = build_msg_direct(ciphertext_b64u, user_id, to, ts, content_sig, privkey_pem)
            await ws.send(json.dumps(env))
        else:
            chunks = chunk_plaintext(plain)
            for i, ch in enumerate(chunks):
                recipient_pub = tables.user_pubkeys.get(to)
                chunk_ts = now_ts()
                ciphertext = oaep_encrypt(recipient_pub, ch)
                content_sig = content_sig_dm(ciphertext, user_id, to, str(chunk_ts), privkey_pem)
                payload = {
                    "ciphertext": b64u(ciphertext),
                    "from": user_id,
                    "to": to,
                    "index": i,
                    "ts": chunk_ts,
                    "content_sig": content_sig,
                }
                payload_bytes = stabilise_json(payload)
                sig = rsa_sign_pss(privkey_pem, payload_bytes)
                sig_b64 = base64url_encode(sig)
                env = {
                    "type": "MSG_DIRECT_CHUNK",
                    "from": user_id,
                    "to": to,
                    "ts": chunk_ts,
                    "payload": payload,
                    "sig": sig_b64,
                    "alg": "PS256",
                }
                await ws.send(json.dumps(env))
                print(f"[DM to {to} @ {chunk_ts}] {ch.decode('utf-8', errors='replace')}")
    except Exception as e:
        traceback.print(e)