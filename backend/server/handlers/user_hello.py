from backend.crypto import rsa_verify_pss, base64url_decode, stabilise_json, load_public_key
from backend.server.peer_comm_utilities import send_error, verify_server_frame, now_ts
import json, time

async def handle_USER_HELLO(ctx, ws, frame):
    uid = frame.get("from")
    if not uid: return await send_error(ws, "UNKNOWN_TYPE", "missing user id")

    # last-login-wins (optional) — replace with reject if you prefer strict
    old = ctx.local_users.get(uid)
    if old and old is not ws:
        try: await old.close(code=1000, reason="replaced")
        except Exception: pass
        ctx.local_users.pop(uid, None)
        ctx.user_locations.pop(uid, None)

    ctx.local_users[uid] = ws
    ctx.router.record_presence(uid, "local")
    await ws.send(json.dumps({"type":"ACK","payload":{"msg_ref":"USER_HELLO"}}))

    for other_uid, env in ctx.user_advertise_envelopes.items():
        if other_uid == uid:
            continue
        await ws.send(json.dumps(env))

    # Send all known USER_ADVERTISEs to the newly connected user
    for other_uid, pubkey_pem in ctx.user_pubkeys.items():
        if other_uid == uid:
            continue
        # You may want to store the full USER_ADVERTISE envelope for each user
        # For now, reconstruct a minimal one:
        user_adv = {
            "type": "USER_ADVERTISE",
            "from": other_uid,
            "to": "*",
            "ts": now_ts(),
            "payload": {
                "user_id": other_uid,
                "pubkey": pubkey_pem,
            },
            "sig": frame.get("sig", ""),
            "alg": "PS256"
        }
        await ws.send(json.dumps(user_adv))