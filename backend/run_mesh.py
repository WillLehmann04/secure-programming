'''
    Group: Group 2
    Members:
        - William Lehmann (A1889855)
        - Edward Chipperfield (Axxxxxxxx)

        
    Description:
        - This is the main entry point for running a server instance.
        - It sets up the server context, routing, and protocol handlers.
        - It also manages peer connections and heartbeats.
'''

# ========== Imports ==========
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid

from backend.crypto import generate_rsa_keypair 
from backend.crypto.rsa_key_management import load_private_key, load_public_key
from backend.crypto.content_sig import sign_server_frame
from backend.server.context import Context
from backend.routing.route import Router
from backend.routing.transport import TransportServer, Link, T_USER_HELLO, T_SERVER_HELLO_PREFIX, T_HEARTBEAT
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
    handle_CMD_LIST,
    handle_SERVER_WELCOME
)

# ========== Config ==========
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("backend.run_mesh")

priv_path = "storage/server_priv.pem"
pub_path = "storage/server_pub.pem"

def load_or_create_keys():
    ''' Load existing RSA keypair from files, or generate new ones. '''
    if not (os.path.exists(priv_path) and os.path.exists(pub_path)):
        priv_pem, pub_pem = generate_rsa_keypair()
        os.makedirs(os.path.dirname(priv_path), exist_ok=True)
        with open(priv_path, "wb") as f:
            f.write(priv_pem)
        with open(pub_path, "wb") as f:
            f.write(pub_pem)

    with open(priv_path, "rb") as f:
        privkey = load_private_key(f.read())
    with open(pub_path, "rb") as f:
        pubkey_pem = f.read()
        pubkey = load_public_key(pubkey_pem)

    return privkey, pubkey


# ========== Functions ==========

def make_context(server_id: str, host: str, port: int, pubkey: str, privkey: str) -> Context:
    # Initialising thse erver and the router
    ctx = Context(server_id=server_id, host=host, port=port, server_public_key_pem=pubkey, server_private_key=privkey)

    async def send_to_peer(sid: str, frame: dict):
        ws = ctx.peers.get(sid)
        if not ws:
            return
        try:
            await ws.send(json.dumps(frame))
        except Exception:
            pass # peer likely closed; let reap handle it later

    async def send_to_local(uid: str, frame: dict):
        ws = ctx.local_users.get(uid)
        if not ws:
            return
        try:
            await ws.send(json.dumps(frame))
        except Exception:
            pass # client likely disconnected

    ctx.router = Router(server_id=ctx.server_id,send_to_peer=send_to_peer,send_to_local=send_to_local,peers=ctx.peers,user_locations=ctx.user_locations,peer_last_seen=ctx.peer_last_seen,)
    return ctx

def adapt(ctx: Context, handler):
    async def _wrapped(env: dict, link: Link):
        await handler(ctx, link.ws, env)
    return _wrapped

async def main():
    host = os.environ.get("SOCP_HOST", "0.0.0.0")
    port = int(os.environ.get("SOCP_PORT", "8765"))
    server_id = str(uuid.uuid4())

    # Build context + router
    privkey, pubkey_pem = load_or_create_keys()

    ctx = make_context(server_id, host, port, pubkey_pem, privkey)
    server = TransportServer(host=host, port=port)

    # Register handlers via adapter
    server.on(f"{T_SERVER_HELLO_PREFIX}_JOIN", adapt(ctx, handle_SERVER_HELLO_JOIN))
    server.on("SERVER_WELCOME",                adapt(ctx, handle_SERVER_WELCOME))
    server.on("SERVER_ANNOUNCE",               adapt(ctx, handle_SERVER_ANNOUNCE))
    server.on("USER_ADVERTISE",               adapt(ctx, handle_USER_ADVERTISE))
    server.on("USER_REMOVE",                  adapt(ctx, handle_USER_REMOVE))
    server.on("PEER_DELIVER",                 adapt(ctx, handle_PEER_DELIVER))
    server.on(T_HEARTBEAT,                    adapt(ctx, handle_HEARTBEAT))

    server.on("CMD_LIST",                     adapt(ctx, handle_CMD_LIST))
    server.on(T_USER_HELLO,                   adapt(ctx, handle_USER_HELLO))
    server.on("MSG_DIRECT",                   adapt(ctx, handle_MSG_DIRECT))
    server.on("MSG_PUBLIC_CHANNEL",           adapt(ctx, handle_MSG_PUBLIC_CHANNEL))
    server.on("FILE_START",                   adapt(ctx, handle_FILE_START))
    server.on("FILE_CHUNK",                   adapt(ctx, handle_FILE_CHUNK))
    server.on("FILE_END",                     adapt(ctx, handle_FILE_END))

    await server.start()
    log.info("Server %s listening at ws://%s:%d", ctx.server_id, host, port)

    async def heartbeat_loop():
        while True:
            await ctx.router.broadcast_heartbeat()
            ctx.router.reap_peers(dead_after=45.0)
            await asyncio.sleep(15)

    asyncio.create_task(heartbeat_loop())
    await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
