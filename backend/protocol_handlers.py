# backend/protocol_handlers.py

from __future__ import annotations

import json
import hashlib
import time
from collections import deque

from backend.crypto.json_format import stabilise_json

# ---------- utilities ----------

def make_seen_key(frame: dict) -> str:
    """hash(ts|from|to|hash(canonical(payload))) per §5.3"""
    ts = str(frame.get("ts", 0))
    f  = frame.get("from", "")
    t  = frame.get("to", "")
    payload_bytes = stabilise_json(frame.get("payload", {}))  # canonical bytes (Part 4)
    h = hashlib.sha256(payload_bytes).hexdigest()
    return f"{ts}|{f}|{t}|{h}"

# Bounded dedupe memory: keep last N seen keys
DEDUP_MAX = 10_000  # adjust if needed

def remember_seen(ctx, key: str) -> bool:
    """
    Returns True if key was already seen.
    Otherwise records it (bounded) and returns False.
    Requires ctx.seen_ids: set[str] and ctx.seen_queue: deque[str]
    """
    if key in ctx.seen_ids:
        return True
    ctx.seen_ids.add(key)
    ctx.seen_queue.append(key)
    if len(ctx.seen_queue) > DEDUP_MAX:
        old = ctx.seen_queue.popleft()
        ctx.seen_ids.discard(old)
    return False


async def send_error(ws, code: str, detail: str = ""):
    # Transport will wrap/shape this as needed; we keep it simple here.
    await ws.send(json.dumps({
        "type": "ERROR",
        "payload": {"code": code, "detail": detail}
    }))

# ---------- §5 Server <-> Server ----------

async def handle_SERVER_HELLO_JOIN(ctx, ws, frame):
    """
    Bootstrap (client -> introducer). We accept join, reply with SERVER_WELCOME,
    and record address + pubkey (address is taken from payload).
    """
    peer_id = frame.get("from")
    pay = frame.get("payload", {})
    host, port = pay.get("host"), pay.get("port")
    if not (peer_id and host and port):
        return await send_error(ws, "UNKNOWN_TYPE", "bad join payload")

    ctx.peers[peer_id] = ws
    ctx.server_addrs[peer_id] = (host, int(port))
    ctx.peer_last_seen[peer_id] = time.time()

    # known peers snapshot
    peers_brief = [
        {"id": sid, "host": h, "port": p}
        for sid, (h, p) in ctx.server_addrs.items()
    ]

    await ws.send(json.dumps({
        "type": "SERVER_WELCOME",
        "from": ctx.server_id,
        "to":   peer_id,
        "ts":   int(time.time() * 1000),
        "payload": {
            "assigned_id": peer_id,   # if you assign IDs, return them here
            "peers": peers_brief
        },
        "sig": ""  # transport already verified upstream in real build
    }))

    # announce ourselves to mesh
    announce = {
        "type": "SERVER_ANNOUNCE",
        "from": ctx.server_id,
        "to":   "*",
        "ts":   int(time.time() * 1000),
        "payload": {"host": ctx.host, "port": ctx.port}
    }
    for sid, pws in ctx.peers.items():
        if pws is not ws:
            await pws.send(json.dumps(announce))

async def handle_SERVER_ANNOUNCE(ctx, ws, frame):
    """Install/update peer address book (§5.1)."""
    sid = frame.get("from")
    pay = frame.get("payload", {})
    host, port = pay.get("host"), pay.get("port")
    if sid and host and port:
        ctx.server_addrs[sid] = (host, int(port))
        ctx.peer_last_seen[sid] = time.time()

async def handle_USER_ADVERTISE(ctx, ws, frame):
    """
    Presence gossip (§5.2). Receivers verify, set mapping, and re-gossip.
    We dedupe to prevent gossip storms.
    """
    # dedupe advertise frames
    key = make_seen_key(frame)
    if remember_seen(ctx, key):
        return

    user_id = frame.get("payload", {}).get("user_id") or frame.get("from")
    loc     = frame.get("payload", {}).get("location") or frame.get("from_server")
    if not (user_id and loc):
        return

    ctx.user_locations[user_id] = loc
    # Tell router so it can flush queued messages for this user.
    if hasattr(ctx, "router") and ctx.router:
        ctx.router.record_presence(user_id, loc)

    # re-gossip to other peers (fan-out)
    for sid, pws in ctx.peers.items():
        if pws != ws:
            await pws.send(json.dumps(frame))

async def handle_USER_REMOVE(ctx, ws, frame):
    """Remove presence mapping if it still points to given location."""
    user_id = frame.get("payload", {}).get("user_id")
    loc     = frame.get("payload", {}).get("location")
    if not user_id:
        return
    if ctx.user_locations.get(user_id) == loc:
        ctx.user_locations.pop(user_id, None)

async def handle_PEER_DELIVER(ctx, ws, frame):
    """
    Forwarded delivery (§5.3). Do not decrypt; just route.
    Use seen_ids to suppress duplicates / loops.
    """
    key = make_seen_key(frame)
    if remember_seen(ctx, key):
        return  # duplicate; drop

    target = frame.get("payload", {}).get("user_id") or frame.get("to")
    await _route_to_user(ctx, ws, frame, target)

async def handle_HEARTBEAT(ctx, ws, frame):
    """Peer keepalive (§5.4)."""
    sid = frame.get("from")
    if sid:
        ctx.peer_last_seen[sid] = time.time()
        if hasattr(ctx, "router") and ctx.router:
            ctx.router.note_peer_seen(sid)

# ---------- §6 User <-> Server ----------

async def handle_USER_HELLO(ctx, ws, frame):
    """
    Uniqueness check; on success:
    - register local session
    - set user_locations[u] = "local"
    - broadcast USER_ADVERTISE
    """
    user_id = frame.get("from")
    if not user_id:
        return await send_error(ws, "UNKNOWN_TYPE", "missing user id")
    if user_id in ctx.local_users:
        return await send_error(ws, "NAME_IN_USE", "duplicate user")

    ctx.local_users[user_id] = ws
    ctx.user_locations[user_id] = "local"
    if hasattr(ctx, "router") and ctx.router:
        ctx.router.record_presence(user_id, "local")

    advert = {
        "type": "USER_ADVERTISE",
        "from": ctx.server_id,
        "to":   "*",
        "ts":   int(time.time() * 1000),
        "payload": {"user_id": user_id, "location": ctx.server_id}
    }
    for _, pws in ctx.peers.items():
        await pws.send(json.dumps(advert))

    await ws.send(json.dumps({"type": "ACK", "payload": {"msg_ref": "USER_HELLO"}}))

async def handle_MSG_DIRECT(ctx, ws, frame):
    """
    End-to-end encrypted DM (§6.2). Server does NOT decrypt.
    Route same-server or to remote via PEER_DELIVER envelope.
    """
    target = frame.get("to")
    await _route_to_user(ctx, ws, frame, target)

async def handle_MSG_PUBLIC_CHANNEL(ctx, ws, frame):
    """
    Public broadcast (§6.3). Fan-out to locals + peers.
    (Key distribution messages like PUBLIC_CHANNEL_KEY_SHARE can reuse this routing.)
    """
    # local users
    for uid, uws in ctx.local_users.items():
        if uws is not ws:
            await uws.send(json.dumps(frame))
    # peers
    for _, pws in ctx.peers.items():
        await pws.send(json.dumps(frame))

async def handle_FILE_START(ctx, ws, frame):
    """File transfer (§6.4) — same routing as DM."""
    target = frame.get("to")
    await _route_to_user(ctx, ws, frame, target)

async def handle_FILE_CHUNK(ctx, ws, frame):
    target = frame.get("to")
    await _route_to_user(ctx, ws, frame, target)

async def handle_FILE_END(ctx, ws, frame):
    target = frame.get("to")
    await _route_to_user(ctx, ws, frame, target)

# ---------- routing core (authoritative §7) ----------

async def _route_to_user(ctx, ws, frame, target: str):
    """
    Delegate to the Router (Part 7).
    Router will wrap as USER_DELIVER for local or PEER_DELIVER for remote.
    """
    if hasattr(ctx, "router") and ctx.router:
        await ctx.router.route_to_user(target, frame)
    else:
        # Fallback (shouldn't happen if run_mesh wired Router)
        # Local-only naive delivery:
        if target in ctx.local_users:
            deliver = {
                "type": "USER_DELIVER",
                "from": ctx.server_id,
                "to":   target,
                "ts":   int(time.time() * 1000),
                "payload": frame.get("payload", {})
            }
            await ctx.local_users[target].send(json.dumps(deliver))

# ---------- heartbeat helpers (§5.4) ----------

async def periodic_heartbeats(ctx, send_fn):
    """
    send_fn(sid, frame_dict) must send a frame to peer sid.
    Transport can schedule this as an asyncio.Task.
    """
    while True:
        now_ms = int(time.time() * 1000)
        hb = {"type": "HEARTBEAT", "from": ctx.server_id, "to": "*", "ts": now_ms, "payload": {}}
        for sid in list(ctx.peers.keys()):
            await send_fn(sid, hb)
        # reap dead peers
        now = time.time()
        for sid, last in list(ctx.peer_last_seen.items()):
            if now - last > 45:
                ctx.peers.pop(sid, None)
                ctx.peer_last_seen.pop(sid, None)
        await asyncio.sleep(15)


# (import placed at bottom to avoid circular import if transport imports handlers)
import asyncio  # noqa
