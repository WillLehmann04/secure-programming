from peer_comm_utilities import send_to_all_peers, make_seen_key, remember_seen, send_error
from backend.crypto.json_format import stabilise_json, base64url_decode, rsa_verify_pss
import hashlib

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
    # Verify envelope signature
    payload_bytes = stabilise_json(payload)
    sig = base64url_decode(sig_b64)
    if not rsa_verify_pss(pubkey_pem, payload_bytes, sig):
        await send_error(ws, "INVALID_SIG", "bad envelope signature")
        return
    # Verify content signature
    content_sig = payload.get("content_sig", "")
    ciphertext_b64 = payload.get("ciphertext", "")
    ciphertext = base64url_decode(ciphertext_b64)
    d = hashlib.sha256(ciphertext + sender_id.encode() + recipient_id.encode() + str(ts).encode()).digest()
    content_sig_bytes = base64url_decode(content_sig)
    if not rsa_verify_pss(pubkey_pem, d, content_sig_bytes):
        await send_error(ws, "INVALID_SIG", "bad content signature")
        return
    # Route to recipient
    try:
        await ctx.router.route_to_user(recipient_id, frame)
    except Exception as e:
        await send_error(ws, "USER_NOT_FOUND", str(e))