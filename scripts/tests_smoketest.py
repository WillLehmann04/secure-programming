# backend/tests_smoketest.py
from __future__ import annotations

import asyncio
import json
import time
import uuid
import websockets

from backend.server.context import Ctx
from backend.routing import Router
from backend.routing.transport import (
    TransportServer,
    Link,
    T_USER_HELLO,
    T_HEARTBEAT,
    T_SERVER_HELLO_PREFIX,
)
from backend.server.protocol_handlers import (
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

# ---------- tiny adapter so transport can call our part-6 handlers ----------
def adapt(ctx: Ctx, handler):
    async def _wrapped(env: dict, link: Link):
        await handler(ctx, link.ws, env)
    return _wrapped


async def start_stack(host="127.0.0.1", port=8765) -> tuple[Ctx, TransportServer]:
    """Spin up a minimal stack: Ctx + Router + Transport + Part-6 handlers."""
    server_id = str(uuid.uuid4())
    ctx = Ctx(server_id=server_id, host=host, port=port)

    # Wire Router send-callbacks into ctx maps
    async def _send_to_peer(sid: str, frame: dict):
        ws = ctx.peers.get(sid)
        if ws:
            await ws.send(json.dumps(frame))

    async def _send_to_local(uid: str, frame: dict):
        ws = ctx.local_users.get(uid)
        if ws:
            await ws.send(json.dumps(frame))

    ctx.router = Router(
        server_id=ctx.server_id,
        send_to_peer=_send_to_peer,
        send_to_local=_send_to_local,
        peers=ctx.peers,
        user_locations=ctx.user_locations,
        peer_last_seen=ctx.peer_last_seen,
    )

    server = TransportServer(host=host, port=port)

    # Part-5 (server<->server) + Part-6 (user<->server) handlers
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

    await server.start()
    return ctx, server


# ---------- minimal client helpers ----------
def frame(ftype, frm, to, payload):
    return {
        "type": ftype,
        "from": frm,
        "to": to,
        "ts": int(time.time() * 1000),
        "payload": payload,
        "sig": "",  # transport-sig omitted for smoketest
    }


async def user_connect(uri: str, user_id: str):
    """Open a WS and perform USER_HELLO with a UUID user_id."""
    ws = await websockets.connect(uri, open_timeout=3)
    await ws.send(json.dumps(frame("USER_HELLO", user_id, "*", {})))
    msg = json.loads(await ws.recv())
    assert msg.get("type") == "ACK", f"{user_id} did not receive ACK: {msg}"
    return ws


async def run():
    ctx, server = await start_stack(host="127.0.0.1", port=8765)
    uri = "ws://127.0.0.1:8765"

    # Use UUIDv4 user IDs to satisfy the transport’s validator
    alice_id = str(uuid.uuid4())
    bob_id   = str(uuid.uuid4())

    alice = await user_connect(uri, alice_id)
    bob   = await user_connect(uri, bob_id)

    # Alice -> Bob direct message (opaque encrypted blob)
    dm_payload = {"ciphertext": "opaque-bytes-here", "meta": {"alg": "aes-gcm"}}
    await alice.send(json.dumps(frame("MSG_DIRECT", alice_id, bob_id, dm_payload)))

    # Bob must receive a single USER_DELIVER with same payload
    deliver = json.loads(await bob.recv())
    assert deliver.get("type") == "USER_DELIVER", deliver
    assert deliver.get("to") == bob_id, deliver
    assert deliver.get("payload") == dm_payload, deliver

    print("Smoke test OK: direct message delivered once to Bob.")

    await alice.close()
    await bob.close()
    await server.stop()


if __name__ == "__main__":
    asyncio.run(run())
