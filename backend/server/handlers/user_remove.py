'''
    Group: Group 2
    Members:
        - William Lehmann (A1889855)
        - Edward Chipperfield (A1889447)
        - G A Sadman (A1899867)
        - Aditeya Sahu (A1943902)
        
    Description:
        - This module handles USER_REMOVE messages from users,  removing the user from the server's records
          and notifying other connected servers of the removal.
'''

from backend.crypto import rsa_verify_pss, base64url_decode, stabilise_json
import json
from backend.server.peer_comm_utilities import send_error

async def handle_USER_REMOVE(ctx, ws, frame):
    payload = frame["payload"]
    sig_b64 = frame.get("sig", "")
    user_id = payload.get("user_id")
    pubkey_pem = ctx.user_pubkeys.get(user_id)
    if not (user_id and pubkey_pem and sig_b64):
        await send_error(ws, "BAD_KEY", "missing fields or unknown user")
        return
    payload_bytes = stabilise_json(payload)
    sig = base64url_decode(sig_b64)
    if not rsa_verify_pss(pubkey_pem, payload_bytes, sig):
        await send_error(ws, "INVALID_SIG", "bad signature")
        return

    user_id = frame.get("payload",{}).get("user_id")
    if user_id in ctx.user_locations:
        ctx.user_locations.pop(user_id, None)
        for sid, pws in ctx.peers.items():
            if pws != ws:
                await pws.send(json.dumps(frame))