# backend/protocol_handlers.py
"""
Implements:
- Server bootstrap & announce
- Presence gossip (USER_ADVERTISE/REMOVE)
- Forwarded delivery (direct, public, file)
- User HELLO and routing integration
"""

import time, json

# 5.1 Bootstrap flow ---------------------------------------------------------

async def handle_SERVER_HELLO_JOIN(ctx, ws, env):
    """Handle a join request from another server."""
    sid = env["from"]
    ctx.peers[sid] = ws
    ctx.server_addrs[sid] = (env["payload"]["host"], env["payload"]["port"])
    ctx.peer_last_seen[sid] = time.time()

    # Reply with SERVER_WELCOME
    welcome = {
        "type": "SERVER_WELCOME",
        "from": ctx.server_id,
        "to": sid,
        "ts": int(time.time() * 1000),
        "payload": {
            "peers": [
                {"id": pid, "host": h, "port": p}
                for pid, (h, p) in ctx.server_addrs.items()
            ]
        }
    }
    await ws.send(json.dumps(welcome))

    # Broadcast SERVER_ANNOUNCE to other peers
    announce = {
        "type": "SERVER_ANNOUNCE",
        "from": ctx.server_id,
        "to": "*",
        "ts": int(time.time() * 1000),
        "payload": {"id": ctx.server_id, "host": ctx.host, "port": ctx.port},
    }
    for psid, pws in ctx.peers.items():
        if pws != ws:
            await pws.send(json.dumps(announce))


async def handle_SERVER_ANNOUNCE(ctx, ws, env):
    sid = env["payload"]["id"]
    ctx.server_addrs[sid] = (env["payload"]["host"], env["payload"]["port"])
    ctx.peers[sid] = ws
    ctx.peer_last_seen[sid] = time.time()

# 5.2 Presence gossip --------------------------------------------------------

async def handle_USER_ADVERTISE(ctx, ws, env):
    """Spread user presence across the mesh."""
    user = env["from"]
    sid = env["payload"]["server_id"]
    ctx.user_locations[user] = sid
    # Re-gossip to other servers
    for psid, pws in ctx.peers.items():
        if pws != ws:
            await pws.send(json.dumps(env))


async def handle_USER_REMOVE(ctx, ws, env):
    """Handle a user disconnect broadcast."""
    user = env["from"]
    if ctx.user_locations.get(user) == env["payload"]["server_id"]:
        ctx.user_locations.pop(user, None)
    # Re-gossip to other servers
    for psid, pws in ctx.peers.items():
        if pws != ws:
            await pws.send(json.dumps(env))

# 5.3 Forwarded delivery -----------------------------------------------------

async def handle_MSG_DIRECT(ctx, ws, env):
    """Route an end-to-end encrypted DM (server doesn’t decrypt)."""
    target = env["to"]
    await ctx.router.route_to_user(target, env)


async def handle_PEER_DELIVER(ctx, ws, env):
    """Forward a message from a server to a user."""
    user = env["payload"]["user_id"]
    await ctx.router.route_to_user(user, env)

# 5.4 Health is already implemented (heartbeat in run_mesh) ------------------


# 6) User↔Server protocol ----------------------------------------------------

async def handle_USER_HELLO(ctx, ws, env):
    """Register a new user on this server."""
    uid = env["from"]
    if uid in ctx.local_users:
        # Duplicate user ID, reject
        err = {
            "type": "ERROR",
            "from": ctx.server_id,
            "to": uid,
            "ts": int(time.time() * 1000),
            "payload": {"code": "NAME_IN_USE", "detail": "user already connected"},
        }
        await ws.send(json.dumps(err))
        return

    ctx.local_users[uid] = ws
    ctx.user_locations[uid] = "local"

    # Gossip presence to peers
    advertise = {
        "type": "USER_ADVERTISE",
        "from": uid,
        "to": "*",
        "ts": int(time.time() * 1000),
        "payload": {"server_id": ctx.server_id},
    }
    for sid, pws in ctx.peers.items():
        await pws.send(json.dumps(advertise))


async def handle_MSG_PUBLIC_CHANNEL(ctx, ws, env):
    """Fan-out public messages to all users and peers."""
    for uid, uws in ctx.local_users.items():
        await uws.send(json.dumps(env))
    for sid, pws in ctx.peers.items():
        await pws.send(json.dumps(env))


async def handle_FILE_START(ctx, ws, env):
    await ctx.router.route_to_user(env["to"], env)

async def handle_FILE_CHUNK(ctx, ws, env):
    await ctx.router.route_to_user(env["to"], env)

async def handle_FILE_END(ctx, ws, env):
    await ctx.router.route_to_user(env["to"], env)


async def handle_HEARTBEAT(ctx, ws, env):
    sid = env["from"]
    ctx.peer_last_seen[sid] = time.time()
