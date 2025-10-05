import json

from .constants import OAEP_MAX_PLAINTEXT
from .utils import now_ts, chunk_plaintext, b64u
from .crypto_helpers import content_sig_dm
from .envelopes import msg_direct, msg_direct_chunk
from backend.crypto.rsa_oaep import oaep_encrypt


async def cmd_list(ws, user_id: str, server_id: str):
    # minimal payload – server responds with known users
    await ws.send(json.dumps({
        'type': 'CMD_LIST',
        'from': user_id,
        'to': server_id,
        'payload': {},
        'ts': now_ts(),
    }))


async def cmd_tell(ws, user_id: str, privkey_pem: bytes, to: str, text: str, tables):
    try:
        if not text:
            return  # nothing to do

        plain = text.encode('utf-8')

        recipient_pub = tables.user_pubkeys.get(to)
        if not recipient_pub:
            print(f"No public key for '{to}'. Try /list and wait for USER_ADVERTISE.")
            return

        ts = now_ts()
        if len(plain) <= OAEP_MAX_PLAINTEXT:
            # one-shot envelope
            ciphertext = oaep_encrypt(recipient_pub, plain)
            ciphertext_b64u = b64u(ciphertext)
            content_sig = content_sig_dm(ciphertext, user_id, to, str(ts), privkey_pem)
            env = msg_direct(ciphertext_b64u, user_id, to, ts, content_sig, privkey_pem)
            await ws.send(json.dumps(env))
            return

        # long message – chunk it
        chunks = chunk_plaintext(plain)
        for i, ch in enumerate(chunks):
            # Re-read pubkey every loop in case directory updates mid-send.
            recipient_pub = tables.user_pubkeys.get(to)
            chunk_ts = now_ts()
            ciphertext = oaep_encrypt(recipient_pub, ch)
            content_sig = content_sig_dm(ciphertext, user_id, to, str(chunk_ts), privkey_pem)

            payload = {
                'ciphertext': b64u(ciphertext),
                'from': user_id,
                'to': to,
                'index': i,
                'ts': chunk_ts,
                'content_sig': content_sig,
            }
            env = msg_direct_chunk(payload, privkey_pem, user_id, to, chunk_ts)
            await ws.send(json.dumps(env))

    except Exception as e:
        print("cmd_tell failed:", e)


async def cmd_channel(ws, user_id: str, privkey_pem: bytes, channel_id: str, text: str):
    ts = now_ts()
    payload = {'ciphertext': text, 'from': user_id, 'to': channel_id, 'ts': ts}

    from backend.crypto import rsa_sign_pss, base64url_encode, stabilise_json

    env = {
        'type': 'MSG_PUBLIC_CHANNEL',
        'from': user_id,
        'to': channel_id,
        'ts': ts,
        'payload': payload,
        'sig': base64url_encode(rsa_sign_pss(privkey_pem, stabilise_json(payload))),
        'alg': 'PS256',
    }
    await ws.send(json.dumps(env))
