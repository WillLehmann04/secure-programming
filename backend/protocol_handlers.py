# backend/protocol_handlers.py

import json, hashlib, time
from collections import deque
from typing import Tuple

# Part-4 canonical JSON
try:
    from backend.crypto.json_format import stabilise_json
except Exception:
    # very defensive fallback; your repo already has stabilise_json
    import json as _json
    def stabilise_json(obj) -> bytes:
        return _json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


# ---------- small helpers: canonical hash & bounded dedupe ----------

def _canonical_payload_hash(payload: dict) -> str:
    """sha256 over canonicalised JSON bytes (aligns with Part 4)."""
    b = stabilise_json(payload)
    return hashlib.sha256(b).hexdigest()


def make_seen_key(frame: dict) -> str:
    """Stable dedupe key: ts|from|to|hash(canonical(payload)) (see §5.3)."""
    ts = str(frame.get("ts", 0))
    f  = frame.get("from", "")
    t  = frame.get("to", "")
    h  = _canonical_payload_hash(frame.get("payload", {}))
    return f"{ts}|{f}|{t}|{h}"


DEDUP_MAX = 10_000  # keep last N keys


def _ensure_ctx_deduper(ctx) -> Tuple[set, deque]:
    """
    Be tolerant: if teammates' ctx didn't predefine seen_ids/seen_queue,
    create them lazily here so code still works.
    """
    ids = getattr(ctx, "seen_ids", None)
    q   = getattr(ctx, "seen_queue", None)
    if ids is None or q is None:
        ids, q = set(), deque()
        setattr(ctx, "seen_ids", ids)
        setattr(ctx, "seen_queue", q)
    return ids, q


def remember_seen(ctx, key: str) -> bool:
    """
    Returns True if key already seen; otherwise records it (bounded) and returns False.
    Works even if ctx didn’t originally expose seen_ids/seen_queue.
    """
    ids, q = _ensure_ctx_deduper(ctx)
    if key in ids:
        return True
    ids.add(key)
    q.append(key)
    if len(q) > DEDUP_MAX:
        old = q.popleft()
        ids.discard(old)
    return False


async def send_error(ws, code: str, detail: str = ""):
    await ws.send(json.dumps({
        "type": "ERROR",
        "payload": {"code": code, "detail": detail}
    }))


# ---------- §5 Server <-> Server ----------

async def handle_SERVER_HELLO_JOIN(ctx, ws, frame):
    """
    Bootstrap (client -> introducer). We accept join, reply with SERVER_WELCOME,
    and record address (host/port) taken from payload.
    """
    peer_id = frame.get("from")
    pay     = frame.get("payload", {}) or {}
    host, port = pay.get("host"), pay.get("port")
    if not (peer_id and host and port):
        return await send_error(ws, "UNKNOWN_TYPE", "bad join payload")

    ctx.peers[peer_id] = ws
    ctx.server_addrs[peer_id] = (host, int(port))
    ctx.peer_last_seen[peer_id] = time.time()

    # known peers snapshot
    peers_brief = [{"id": sid, "host": h, "port": p} for sid, (h, p) in ctx.server_addrs.items()]

    await ws.send(json.dumps({
        "type": "SERVER_WELCOME",
        "from": ctx.server_id,
        "to":   peer_id,
        "ts":   int(time.time() * 1000),
        "payload": {
            "assigned_id": peer_id,   # if your design assigns IDs, return them here
            "peers": peers_brief
        },
        "sig": ""  # transport verification happens upstream in real build
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
    pay = frame.get("payload", {}) or {}
    host, port = pay.get("host"), pay.get("port")
    if sid and host and port:
        ctx.server_addrs[sid] = (host, int(port))
        ctx.peer_last_seen[sid] = time.time()


async def handle_USER_ADVERTISE(ctx, ws, frame):
    """
    Presence gossip (§5.2). Receivers verify, set mapping, and re-gossip.
    """
    # dedupe to prevent gossip storms
    if remember_seen(ctx, make_seen_key(frame)):
        return

    user_id = frame.get("payload", {}).get("user_id") or frame.get("from")
    loc     = frame.get("payload", {}).get("location") or frame.get("from_server")
    if not (user_id and loc):
        return

    ctx.user_locations[user_id] = loc

    # re-gossip to other peers (fan-out)
    for sid, pws in ctx.peers.items():
        if pws != ws:
            await pws.send(json.dumps(frame))


async def handle_USER_REMOVE(ctx, ws, frame):
    user_id = frame.get("payload", {}).get("user_id")
    loc     = frame.get("payload", {}).get("location")
    if not user_id:
        return
    # delete only if mapping still points to that server (§5.2)
    if ctx.user_locations.get(user_id) == loc:
        ctx.user_locations.pop(user_id, None)


async def handle_PEER_DELIVER(ctx, ws, frame):
    """
    Forwarded delivery (§5.3). Do not decrypt; just route.
    Use dedupe to suppress duplicates / loops.
    """
    # Prefer Router's dedupe if available
    router = getattr(ctx, "router", None)
    if router is not None:
        if router.already_seen(frame):
            return
    else:
        # fallback to local LRU
        if remember_seen(ctx, make_seen_key(frame)):
            return

    target = frame.get("payload", {}).get("user_id") or frame.get("to")
    await _route_to_user(ctx, ws, frame, target)


async def handle_HEARTBEAT(ctx, ws, frame):
    sid = frame.get("from")
    if sid:
        ctx.peer_last_seen[sid] = time.time()


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
    """
    # local users
    for uid, uws in ctx.local_users.items():
        if uws is not ws:
            await uws.send(json.dumps(frame))
    # peers
    for _, pws in ctx.peers.items():
        await pws.send(json.dumps(frame))


async def handle_FILE_START(ctx, ws, frame):
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
    Delegate routing to the Router (Part 7).
    This keeps Part 3/4/6 code cohesive and avoids drift.
    """
    router = getattr(ctx, "router", None)
    if router is None:
        # Absolute fallback (shouldn’t happen once Router is wired in run_mesh.py)
        # Local
        if target in ctx.local_users:
            deliver = {
                "type": "USER_DELIVER",
                "from": ctx.server_id,
                "to": target,
                "ts": int(time.time() * 1000),
                "payload": frame.get("payload", {})
            }
            await ctx.local_users[target].send(json.dumps(deliver))
            return
        # Remote
        host_loc = ctx.user_locations.get(target)
        if host_loc and host_loc in ctx.peers and host_loc != "local":
            forward = {
                "type": "PEER_DELIVER",
                "from": ctx.server_id,
                "to": host_loc,
                "ts": int(time.time() * 1000),
                "payload": {**frame.get("payload", {}), "user_id": target}
            }
            await ctx.peers[host_loc].send(json.dumps(forward))
            return
        # Not found
        return
    # Normal path via Router
    await router.route_to_user(target, frame)


# (import placed at bottom to avoid circular import if transport imports handlers)
import asyncio  # noqa
