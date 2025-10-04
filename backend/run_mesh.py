# backend/run_mesh.py
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid

from backend.context import Ctx
from backend.routing import Router
from backend.transport import (
    TransportServer,
    Link,
    T_USER_HELLO,
    T_SERVER_HELLO_PREFIX,
    T_HEARTBEAT,
)

from backend.protocol_handlers import (
    handle_SERVER_HELLO_JOIN,
    handle_SERVER_ANNOUNCE,
    handle_USER_ADVERTISE,
    handle_USER_REMOVE,
    handle_PEER_DELIVER,
    handle_HEARTBEAT,
    handle_USER_HELLO,
    handle_MSG_DIRECT,
    handle_MSG_PUBLIC_CHANNEL,
    handle_FILE_START,
    handle_FILE_CHUNK,
    handle_FILE_END,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("backend.run_mesh")


def _mk_ctx(server_id: str, host: str, port: int) -> Ctx:
    """
    Build your process context and attach a Router with concrete send functions.
    """
    ctx = Ctx(server_id=server_id, host=host, port=port)

    # --- send functions the Router will call ---
    async def _send_to_peer(sid: str, frame: dict):
        ws = ctx.peers.get(sid)
        if not ws:
            return
        try:
            await ws.send(json.dumps(frame, separators=(",", ":"), ensure_ascii=False))
        except Exception:
            # peer likely closed; stale entry will be reaped by the hb loop
            pass

    async def _send_to_local(uid: str, frame: dict):
        ws = ctx.local_users.get(uid)
        if not ws:
            return
        try:
            await ws.send(json.dumps(frame, separators=(",", ":"), ensure_ascii=False))
        except Exception:
            # client likely disconnected
            pass

    # Attach the Router to ctx (so handlers can use ctx.router)
    ctx.router = Router(
        server_id=ctx.server_id,
        send_to_peer=_send_to_peer,
        send_to_local=_send_to_local,
        peers=ctx.peers,
        user_locations=ctx.user_locations,
        peer_last_seen=ctx.peer_last_seen,
        # If you want server-side payload signing on hop frames, pass privkey:
        # server_privkey=ctx.server_privkey,
        server_privkey=None,
    )
    return ctx


# --- adapt your Part-6 handler signatures (ctx, ws, frame) -> (env, link) ---
def adapt(ctx: Ctx, handler):
    async def _wrapped(env: dict, link: Link):
        # env is the envelope (your "frame"); link.ws is the websocket
        await handler(ctx, link.ws, env)
    return _wrapped


async def main():
    # Config (env vars override defaults)
    host = os.environ.get("SOCP_HOST", "0.0.0.0")
    port = int(os.environ.get("SOCP_PORT", "8765"))
    server_id = os.environ.get("SOCP_SERVER_ID") or str(uuid.uuid4())

    # Context + Router
    ctx = _mk_ctx(server_id, host, port)

    # Transport
    server = TransportServer(host=host, port=port)

    # Handlers
    server.on(f"{T_SERVER_HELLO_PREFIX}_JOIN", adapt(ctx, handle_SERVER_HELLO_JOIN))
    server.on("SERVER_ANNOUNCE",              adapt(ctx, handle_SERVER_ANNOUNCE))
    server.on("USER_ADVERTISE",               adapt(ctx, handle_USER_ADVERTISE))
    server.on("USER_REMOVE",                  adapt(ctx, handle_USER_REMOVE))
    server.on("PEER_DELIVER",                 adapt(ctx, handle_PEER_DELIVER))
    server.on(T_HEARTBEAT,                    adapt(ctx, handle_HEARTBEAT))

    server.on(T_USER_HELLO,                   adapt(ctx, handle_USER_HELLO))
    server.on("MSG_DIRECT",                   adapt(ctx, handle_MSG_DIRECT))
    server.on("MSG_PUBLIC_CHANNEL",           adapt(ctx, handle_MSG_PUBLIC_CHANNEL))
    server.on("FILE_START",                   adapt(ctx, handle_FILE_START))
    server.on("FILE_CHUNK",                   adapt(ctx, handle_FILE_CHUNK))
    server.on("FILE_END",                     adapt(ctx, handle_FILE_END))

    # Start + background heartbeat/housekeeping that reuses Router helpers
    await server.start()
    log.info("Server %s listening at ws://%s:%d", ctx.server_id, host, port)

    async def hb_loop():
        while True:
            await ctx.router.broadcast_heartbeat()
            ctx.router.reap_peers(dead_after=45.0)
            await asyncio.sleep(15)

    asyncio.create_task(hb_loop())
    await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
