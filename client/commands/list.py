import json
from client.helpers.small_utils import now_ts, b64u, base64url_encode, stabilise_json, chunk_plaintext, signed_transport_sig, content_sig_dm, rsa_sign_pss, sha256_bytes


async def cmd_list(ws, user_id: str, server_id: str):
    await ws.send(json.dumps({
        "type": "CMD_LIST",
        "from": user_id,
        "to": server_id, 
        "payload": {},
        "ts": now_ts()
    }))