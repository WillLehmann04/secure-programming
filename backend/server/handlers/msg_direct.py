'''
    Group: Group 2
    Members:
        - William Lehmann (A1889855)
        - Edward Chipperfield (A1889447)
        - G A Sadman (A1899867)
        - Aditeya Sahu (A1943902)
        
    Description:
        - This module handles direct messaging between users, including signature verification and routing.
'''

from backend.server.peer_comm_utilities import send_to_all_peers, make_seen_key, remember_seen, send_error
from backend.crypto import stabilise_json, base64url_decode, rsa_verify_pss
import hashlib

async def verify_envelope(pubkey_pem, payload, sig_b64):
    payload_bytes = stabilise_json(payload)
    sig = base64url_decode(sig_b64)
    return rsa_verify_pss(pubkey_pem, payload_bytes, sig)

async def verify_content(pubkey_pem, payload, sender_id, recipient_id, ts):
    content_sig = payload.get("content_sig", "")
    ciphertext_b64 = payload.get("ciphertext", "")
    ciphertext = base64url_decode(ciphertext_b64)
    d = hashlib.sha256(ciphertext + sender_id.encode() + recipient_id.encode() + str(ts).encode()).digest()
    content_sig_bytes = base64url_decode(content_sig)
    return rsa_verify_pss(pubkey_pem, d, content_sig_bytes)

async def handle_MSG_DIRECT(ctx, ws, frame):
    payload = frame["payload"]
    sig_b64 = frame.get("sig", "")
    sender_id = frame.get("from")
    recipient_id = frame.get("to")
    ts = str(frame.get("ts"))
    pubkey_pem = ctx.user_pubkeys.get(sender_id)

    if not (pubkey_pem and sig_b64):
        await send_error(ws, "BAD_KEY", "missing sender pubkey or sig")
        return
    
    if not await verify_envelope(pubkey_pem, payload, sig_b64):
        await send_error(ws, "INVALID_SIG", "bad envelope signature")
        return
    
    if not await verify_content(pubkey_pem, payload, sender_id, recipient_id, ts):
        await send_error(ws, "INVALID_SIG", "bad content signature")
        return
    try:
        await ctx.router.route_to_user(recipient_id, frame)
    except Exception as e:
        await send_error(ws, "USER_NOT_FOUND", str(e))