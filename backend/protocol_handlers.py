# backend/protocol_handlers.py
import json, hashlib, time
from collections import deque
from backend.crypto.json_format import stabilise_json

# ---------- utilities ----------
def make_seen_key(frame: dict) -> str:
    ts = str(frame.get("ts", 0))
    f  = frame.get("from", "")
    t  = frame.get("to", "")
    payload_bytes = stabilise_json(frame.get("payload", {}))
    h = hashlib.sha256(payload_bytes).hexdigest()
    return f"{ts}|{f}|{t}|{h}"

DEDUP_MAX = 10_000

def remember_seen(ctx, key: str) -> bool:
    if key in ctx.seen_ids: return True
    ctx.seen_ids.add(key)
    ctx.seen_queue.append(key)  # bounded by maxlen
    return False

async def send_error(ws, code: str, detail: str = ""):
    await ws.send(json.dumps({"type":"ERROR","payload":{"code":code,"detail":detail}}))

# ---------- Server <-> Server ----------
async def handle_SERVER_HELLO_JOIN(ctx, ws, frame):
    sid = frame.get("from")
    pay = frame.get("payload", {})
    host, port = pay.get("host"), pay.get("port")
    if not (sid and host and port):
        return await send_error(ws, "UNKNOWN_TYPE", "bad join payload")
    ctx.peers[sid] = ws
    ctx.server_addrs[sid] = (host, int(port))
    ctx.peer_last_seen[sid] = time.time()

    peers_brief = [{"id": k, "host": h, "port": p} for k,(h,p) in ctx.server_addrs.items()]
    await ws.send(json.dumps({
        "type":"SERVER_WELCOME","from":ctx.server_id,"to":sid,"ts":int(time.time()*1000),
        "payload":{"assigned_id": sid, "peers": peers_brief},"sig":""
    }))

async def handle_SERVER_ANNOUNCE(ctx, ws, frame):
    sid = frame.get("from"); pay = frame.get("payload",{})
    host, port = pay.get("host"), pay.get("port")
    if sid and host and port:
        ctx.server_addrs[sid] = (host, int(port))
        ctx.peer_last_seen[sid] = time.time()

async def handle_USER_ADVERTISE(ctx, ws, frame):
    key = make_seen_key(frame)
    if remember_seen(ctx, key): return
    user_id = frame.get("payload",{}).get("user_id") or frame.get("from")
    loc     = frame.get("payload",{}).get("location") or frame.get("from_server")
    if not (user_id and loc): return
    ctx.router.record_presence(user_id, loc)
    for sid,pws in ctx.peers.items():
        if pws != ws:
            await pws.send(json.dumps(frame))

async def handle_USER_REMOVE(ctx, ws, frame):
    user_id = frame.get("payload",{}).get("user_id")
    loc     = frame.get("payload",{}).get("location")
    if user_id and ctx.user_locations.get(user_id) == loc:
        ctx.user_locations.pop(user_id, None)

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

async def handle_MSG_DIRECT(ctx, ws, frame):
    target = frame.get("to")
    try:
        await ctx.router.route_to_user(target, frame)
    except Exception as e:
        await send_error(ws, "USER_NOT_FOUND", str(e))

async def handle_MSG_PUBLIC_CHANNEL(ctx, ws, frame):
    # fan-out to local users
    for uid, uws in ctx.local_users.items():
        if uws is not ws:
            await uws.send(json.dumps(frame))
    # fan-out to peers
    for _, pws in ctx.peers.items():
        await pws.send(json.dumps(frame))

async def handle_FILE_START(ctx, ws, frame):  await handle_MSG_DIRECT(ctx, ws, frame)
async def handle_FILE_CHUNK(ctx, ws, frame):  await handle_MSG_DIRECT(ctx, ws, frame)
async def handle_FILE_END(ctx, ws, frame):    await handle_MSG_DIRECT(ctx, ws, frame)

# ---------- registration ----------
def register_protocol_handlers(server, ctx):
    server.on("SERVER_HELLO_JOIN", lambda env, link: handle_SERVER_HELLO_JOIN(ctx, link.ws, env))
    server.on("SERVER_ANNOUNCE",   lambda env, link: handle_SERVER_ANNOUNCE(ctx, link.ws, env))
    server.on("USER_ADVERTISE",    lambda env, link: handle_USER_ADVERTISE(ctx, link.ws, env))
    server.on("USER_REMOVE",       lambda env, link: handle_USER_REMOVE(ctx, link.ws, env))
    server.on("PEER_DELIVER",      lambda env, link: handle_PEER_DELIVER(ctx, link.ws, env))
    server.on("HEARTBEAT",         lambda env, link: handle_HEARTBEAT(ctx, link.ws, env))

    server.on("USER_HELLO",        lambda env, link: handle_USER_HELLO(ctx, link.ws, env))
    server.on("MSG_DIRECT",        lambda env, link: handle_MSG_DIRECT(ctx, link.ws, env))
    server.on("MSG_PUBLIC_CHANNEL",lambda env, link: handle_MSG_PUBLIC_CHANNEL(ctx, link.ws, env))
    server.on("FILE_START",        lambda env, link: handle_FILE_START(ctx, link.ws, env))
    server.on("FILE_CHUNK",        lambda env, link: handle_FILE_CHUNK(ctx, link.ws, env))
    server.on("FILE_END",          lambda env, link: handle_FILE_END(ctx, link.ws, env))
