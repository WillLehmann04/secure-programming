'''
    Group: Group 2
    Members:
        - William Lehmann (A1889855)
        - Edward Chipperfield (Axxxxxxxx)
        
    Description:
        - This module contains protocol handlers for various message types.
        - It handles both server-to-server and user-to-server messages.
        - It includes signature verification, deduplication, and routing logic.
'''


import json, hashlib, time
from collections import deque
from backend.crypto.content_sig import sign_server_frame, verify_server_frame
from backend.crypto.json_format import stabilise_json
from backend.crypto.rsa_pss import rsa_verify_pss
from backend.crypto.json_format import stabilise_json
from backend.crypto import base64url_decode
from backend.crypto.rsa_key_management import load_public_key

from .peer_comm_utilities import send_to_all_peers, make_seen_key, remember_seen, send_error

# ---------- Server <-> Server ----------

async def handle_SERVER_HELLO_JOIN(ctx, ws, frame):
    peer_id = frame["from"]
    if peer_id in ctx.peers:
        old_ws = ctx.peers[peer_id]
        if old_ws != ws:
            # Tie-break: keep connection from lower server_id
            if ctx.server_id < peer_id:
                await ws.close(code=1000, reason="tie-break: keep outgoing")
                return
            else:
                await old_ws.close(code=1000, reason="tie-break: keep incoming")
    ctx.peers[peer_id] = ws

    print(f"[SERVER_HELLO_JOIN] Registered peer {peer_id}. Peers now: {list(ctx.peers.keys())}")
    pay = frame.get("payload", {})
    host, port = pay.get("host"), pay.get("port")
    if not (peer_id and host and port):
        return await send_error(ws, "UNKNOWN_TYPE", "bad join payload")
    ctx.server_addrs[peer_id] = (host, int(port))
    ctx.peer_last_seen[peer_id] = time.time()

    # Send all known USER_ADVERTISEs to the new peer
    for user_id, env in ctx.user_advertise_envelopes.items():
        await ws.send(json.dumps(env))

    # Announce yourself to all peers (including the new one)
    payload = {"host": ctx.host, "port": ctx.port}
    sig_b64 = sign_server_frame(ctx, payload)
    announce = {
        "type": "SERVER_ANNOUNCE",
        "from": ctx.server_id,
        "to": "*",
        "ts": int(time.time() * 1000),
        "payload": payload,
        "sig": sig_b64,
        "alg": "PS256"
    }
    for peer_sid, peer_ws in ctx.peers.items():
        try:
            await peer_ws.send(json.dumps(announce))
        except Exception:
            pass


async def handle_SERVER_ANNOUNCE(ctx, ws, frame):
    peer_id = frame.get("from")
    peer_pubkey = ctx.peer_pubkeys.get(peer_id)
    if not peer_pubkey or not verify_server_frame(peer_pubkey, frame["payload"], frame["sig"]):
        await send_error(ws, "INVALID_SIG", "bad server signature")
        return

    sid = frame.get("from"); pay = frame.get("payload",{})
    host, port = pay.get("host"), pay.get("port")
    if sid and host and port:
        ctx.server_addrs[sid] = (host, int(port))
        ctx.peer_last_seen[sid] = time.time()

# ---------- User Advertisement ----------

async def handle_USER_ADVERTISE(ctx, ws, frame):
    """Handle a new or relayed USER_ADVERTISE."""
    payload = frame["payload"]
    sig_b64 = frame.get("sig", "")
    user_id = payload.get("user_id")
    pubkey_pem = payload.get("pubkey")

    if not (user_id and pubkey_pem and sig_b64):
        await send_error(ws, "BAD_KEY", "missing fields")
        return
    
    payload_bytes = stabilise_json(payload)
    sig = base64url_decode(sig_b64)

    if not rsa_verify_pss(pubkey_pem, payload_bytes, sig):
        await send_error(ws, "INVALID_SIG", "bad signature")
        return

    key = make_seen_key(frame)
    if remember_seen(ctx, key):
        return  # drop duplicate

    # Store the user's public key and envelope
    ctx.user_pubkeys[user_id] = pubkey_pem
    ctx.user_advertise_envelopes[user_id] = frame

    # Register the user as local and record their presence
    ctx.local_users[user_id] = ws
    ctx.router.record_presence(user_id, "local")
    await ws.send(json.dumps({
        "type": "ACK",
        "payload": {
            "msg_ref": "USER_ADVERTISE",
            "from": frame.get("from"),
            "to": frame.get("to"),
            "ts": frame.get("ts"),
            "msg_type": frame.get("type")
        }
    }))

    # Fan-out to all local users except the sender
    for uid, uws in ctx.local_users.items():
        if uws != ws:
            await uws.send(json.dumps(frame))

    # Relay to all peers except the sender
    await send_to_all_peers(ctx, frame, exclude_ws=ws)


async def handle_MSG_PUBLIC_CHANNEL(ctx, ws, frame):
    key = make_seen_key(frame)
    if remember_seen(ctx, key):
        return  # Drop duplicate

    # Fan-out to all local users
    for uid, uws in ctx.local_users.items():
        await uws.send(json.dumps(frame))
    # Relay to all peers (except the one we got it from)
    await send_to_all_peers(ctx, frame, exclude_ws=ws)


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

    #print("HANDLE_USER_REMOVE", frame)
    user_id = frame.get("payload",{}).get("user_id")
    if user_id in ctx.user_locations:
        ctx.user_locations.pop(user_id, None)
        for sid, pws in ctx.peers.items():
            if pws != ws:
                await pws.send(json.dumps(frame))

async def handle_PEER_DELIVER(ctx, ws, frame):
    key = make_seen_key(frame)
    if remember_seen(ctx, key): return
    target = frame.get("payload",{}).get("user_id") or frame.get("to")
    await ctx.router.route_to_user(target, frame.get("payload",{}).get("forwarded", frame))

async def handle_HEARTBEAT(ctx, ws, frame):
    sid = frame.get("from")
    if sid: ctx.router.note_peer_seen(sid)


# ---------- User <-> Server ----------
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
            "ts": int(time.time() * 1000),
            "payload": {
                "user_id": other_uid,
                "pubkey": pubkey_pem,
                # Add other fields if you store them (privkey_store, meta, etc)
            },
            "sig": "",  # If you store the original sig, use it here
            "alg": "PS256"
        }
        await ws.send(json.dumps(user_adv))


async def handle_CMD_LIST(ctx, ws, frame):
    # Only local users
    users = list(ctx.local_users.keys())
    await ws.send(json.dumps({
        "type": "USER_LIST",
        "payload": {"users": users}
    }))

async def handle_SERVER_WELCOME(ctx, ws, frame):
    peer_id = frame.get("from")
    peer_pubkey_pem = frame["payload"].get("pubkey")
    if peer_pubkey_pem:
        ctx.peer_pubkeys[peer_id] = load_public_key(peer_pubkey_pem)
    peer_pubkey = ctx.peer_pubkeys.get(peer_id)
    if not peer_pubkey or not verify_server_frame(peer_pubkey, frame["payload"], frame["sig"]):
        await send_error(ws, "INVALID_SIG", "bad server signature")
        return

    ctx.peers[peer_id] = ws
    print(f"[SERVER_WELCOME] Registered peer {peer_id}. Peers now: {list(ctx.peers.keys())}")

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

async def handle_FILE_START(ctx, ws, frame):  await handle_MSG_DIRECT(ctx, ws, frame)
async def handle_FILE_CHUNK(ctx, ws, frame):  await handle_MSG_DIRECT(ctx, ws, frame)
async def handle_FILE_END(ctx, ws, frame):    await handle_MSG_DIRECT(ctx, ws, frame)

# ---------- registration ----------
def register_protocol_handlers(server, ctx):
    server.on("SERVER_WELCOME", lambda env, link: handle_SERVER_WELCOME(ctx, link.ws, env))
    server.on("SERVER_HELLO_JOIN", lambda env, link: handle_SERVER_HELLO_JOIN(ctx, link.ws, env))
    server.on("SERVER_ANNOUNCE",   lambda env, link: handle_SERVER_ANNOUNCE(ctx, link.ws, env))
    server.on("USER_ADVERTISE",    lambda env, link: handle_USER_ADVERTISE(ctx, link.ws, env))
    server.on("USER_REMOVE",       lambda env, link: handle_USER_REMOVE(ctx, link.ws, env))
    server.on("PEER_DELIVER",      lambda env, link: handle_PEER_DELIVER(ctx, link.ws, env))
    server.on("HEARTBEAT",         lambda env, link: handle_HEARTBEAT(ctx, link.ws, env))

    server.on("CMD_LIST",          lambda env, link: handle_CMD_LIST(ctx, link.ws, env))
    server.on("USER_HELLO",        lambda env, link: handle_USER_HELLO(ctx, link.ws, env))
    server.on("MSG_DIRECT",        lambda env, link: handle_MSG_DIRECT(ctx, link.ws, env))
    server.on("MSG_PUBLIC_CHANNEL",lambda env, link: handle_MSG_PUBLIC_CHANNEL(ctx, link.ws, env))
    server.on("FILE_START",        lambda env, link: handle_FILE_START(ctx, link.ws, env))
    server.on("FILE_CHUNK",        lambda env, link: handle_FILE_CHUNK(ctx, link.ws, env))
    server.on("FILE_END",          lambda env, link: handle_FILE_END(ctx, link.ws, env))
