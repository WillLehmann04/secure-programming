'''
    Group: Group 2
    Members:
        - William Lehmann (A1889855)
        - Edward Chipperfield (A1889447)
        - G A Sadman (A1899867)
        - Aditeya Sahu (A1943902)
        
    Description:
        - This module implements the /tell command for sending direct messages (DMs) between users. 
'''

from client.helpers.small_utils import now_ts, b64u, base64url_encode, stabilise_json, chunk_plaintext, signed_transport_sig, content_sig_dm, rsa_sign_pss, sha256_bytes
from backend.crypto import rsa_sign_pss, oaep_encrypt
import uuid
import json
import traceback

OAEP_HASH_BYTES = 32
RSA_4096_KEY_BYTES = 4096 // 8
OAEP_MAX_PLAINTEXT = RSA_4096_KEY_BYTES - 2 * OAEP_HASH_BYTES - 2  # 446 bytes

from client.build_envelopes.msg_direct import build_msg_direct


async def cmd_tell(ws, user_id: str, privkey_pem: bytes, to: str, text: str, tables):
    try:
        plain = text.encode("utf-8")
        recipient_pub = tables.user_pubkeys.get(to)
        if not recipient_pub:
            return

        ts = now_ts()
        dm_id = str(uuid.uuid4())
        if len(plain) <= OAEP_MAX_PLAINTEXT:
            ciphertext = oaep_encrypt(recipient_pub, plain)
            ciphertext_b64u = b64u(ciphertext)
            content_sig = content_sig_dm(ciphertext, user_id, to, str(ts), privkey_pem)

            env = build_msg_direct(
                ciphertext_b64u, user_id, to, ts, content_sig, privkey_pem
            )
            await ws.send(stabilise_json(env).decode("utf-8"))
            return

        chunks = chunk_plaintext(plain)
        for i, ch in enumerate(chunks):
            chunk_ts = now_ts()
            ciphertext = oaep_encrypt(recipient_pub, ch)
            content_sig = content_sig_dm(ciphertext, user_id, to, str(chunk_ts), privkey_pem)

            payload = {
                "ciphertext": b64u(ciphertext),
                "from": user_id,
                "to": to,
                "index": i,
                "ts": chunk_ts,
                "dm_id": dm_id,
                "msg_id": f"{dm_id}:{i}",
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
            await ws.send(stabilise_json(env).decode("utf-8"))
            print(f"[DM to {to} @ {chunk_ts}] {ch.decode('utf-8', errors='replace')}")

    except Exception as e:
        traceback.print(e)