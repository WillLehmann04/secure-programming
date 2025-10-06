'''
    Group: Group 2
    Members:
        - William Lehmann (A1889855)
        - Edward Chipperfield (A1889447)
        - G A Sadman (A1899867)
        - Aditeya Sahu (A1943902)
        
    Description:
        - This module handles USER_ADVERTISE messages from users,   
          verifying signatures, storing public keys, and propagating the information.
'''

from backend.crypto import stabilise_json, base64url_decode, rsa_verify_pss
from backend.server.peer_comm_utilities import send_to_all_peers, make_seen_key, remember_seen, send_error
import json

def is_valid_user_advertise(payload, sig_b64):
    '''Check if all required fields are present.'''
    return bool(payload.get("user_id") and payload.get("pubkey") and sig_b64)

def verify_user_advertise_signature(payload, sig_b64, pubkey_pem):
    '''Verify the signature on the USER_ADVERTISE payload.'''
    payload_bytes = stabilise_json(payload)
    sig = base64url_decode(sig_b64)
    return rsa_verify_pss(pubkey_pem, payload_bytes, sig)

async def send_ack(ws, frame):
    ack = {
        "type": "ACK",
        "payload": {
            "msg_ref": "USER_ADVERTISE",
            "from": frame.get("from"),
            "to": frame.get("to"),
            "ts": frame.get("ts"),
            "msg_type": frame.get("type")
        }
    }
    await ws.send(json.dumps(ack))

async def handle_USER_ADVERTISE(ctx, ws, frame):
    payload = frame["payload"]
    sig_b64 = frame.get("sig", "")
    user_id = payload.get("user_id")
    pubkey_pem = payload.get("pubkey")
    if not is_valid_user_advertise(payload, sig_b64):
        await send_error(ws, "BAD_KEY", "missing fields")
        return
    if not verify_user_advertise_signature(payload, sig_b64, pubkey_pem):
        await send_error(ws, "INVALID_SIG", "bad signature")
        return

    key = make_seen_key(frame)
    if remember_seen(ctx, key):
        return  # drop duplicate

    ctx.user_pubkeys[user_id] = pubkey_pem
    ctx.user_advertise_envelopes[user_id] = frame
    ctx.local_users[user_id] = ws
    ctx.router.record_presence(user_id, "local")
    await send_ack(ws, frame)

    for uid, uws in ctx.local_users.items():
        if uws != ws:
            await uws.send(json.dumps(frame))

    await send_to_all_peers(ctx, frame, exclude_ws=ws)
