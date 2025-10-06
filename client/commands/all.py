'''
    Group: Group 2
    Members:
        - William Lehmann (A1889855)
        - Edward Chipperfield (A1889447)
        - G A Sadman (A1899867)
        - Aditeya Sahu (A1943902)
        
    Description:
        - Implements the /all command.
        - Broadcasts a public message to all connected users via MSG_PUBLIC_CHANNEL.
        - The server will propagate it to all connected peers and local clients.
'''

import json
import time
from backend.crypto.content_sig import sign_server_frame
from backend.crypto.json_format import stabilise_json
from backend.crypto.rsa_pss import rsa_sign_pss
from backend.crypto.base64url import base64url_encode

async def cmd_all(ws, user_id, privkey_pem, text):
    """
    Broadcast a message to all users (public channel).
    Builds a MSG_PUBLIC_CHANNEL envelope and sends it to the server.
    """

    ts = int(time.time() * 1000)
    payload = {
        "text": text,
        "from": user_id,
        "to": "all",
        "ts": ts,
    }

    # Sign payload for authenticity
    payload_bytes = stabilise_json(payload)
    sig = rsa_sign_pss(privkey_pem, payload_bytes)
    sig_b64 = base64url_encode(sig)

    env = {
        "type": "MSG_PUBLIC_CHANNEL",
        "from": user_id,
        "to": "all",
        "ts": ts,
        "payload": payload,
        "sig": sig_b64,
        "alg": "PS256",
    }

    print(f"[DEBUG] Sending broadcast: {text}")
    await ws.send(json.dumps(env))
    print(f"[Broadcast Sent] {text}")