'''
    Group: Group 2
    Members:
        - William Lehmann (A1889855)
        - Edward Chipperfield (A1889447)
        - G A Sadman (A1899867)
        - Aditeya Sahu (A1943902)
        
    Description:
        - This is the main entry point for running the server mesh.
          It sets up the server, loads or generates RSA keys, and initialises the context.
'''

# ==== Imports ====
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

import os, websockets, time
# ==== Config ====
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


# ==== Functions ====

def make_context(server_id: str, host: str, port: int, pubkey: str, privkey: str) -> Context:
    # Initialising thse erver and the router
    context = Context(server_id=server_id, host=host, port=port, server_public_key_pem=pubkey, server_private_key=privkey)

    async def send_to_peer(sid: str, frame: dict):
        ws = context.peers.get(sid)
        if not ws:
            print(f"[DEBUG] No peer websocket for server id {sid}")
            return
        try:
            print(f"[DEBUG] Sending frame to peer {sid}: {frame.get('type')}")
            await ws.send(json.dumps(frame))
        except Exception as e:
            print(f"[DEBUG] Failed to send to peer {sid}: {e}")

    async def send_to_local(uid: str, frame: dict):
        ws = context.local_users.get(uid)
        if not ws:
            return
        try:
            await ws.send(json.dumps(frame))
        except Exception:
            pass # client likely disconnected

    context.router = Router(server_id=context.server_id,send_to_peer=send_to_peer,send_to_local=send_to_local,peers=context.peers,user_locations=context.user_locations,peer_last_seen=context.peer_last_seen,)
    return context

def adapt(context: Context, handler):
    async def _wrapped(env: dict, link: Link):
        await handler(context, link.ws, env)
    return _wrapped


async def connect_to_peers(context, server):
    # Ensure peers_pending exists
    if not hasattr(context, "peers_pending"):
        context.peers_pending = {}

    for peer_addr in os.environ.get("SOCP_PEERS", "").split(","):
        peer_addr = peer_addr.strip()
        if not peer_addr:
            continue
        try:
            print(f"[DEBUG] Attempting to connect to peer at {peer_addr}")
            ws = await websockets.connect(peer_addr)
            peer_id = None  # We'll get this from the SERVER_WELCOME frame
            context.peers_pending[ws] = peer_addr  # Track pending peer connections

            async def peer_listener():
                nonlocal peer_id
                try:
                    # Send SERVER_HELLO_JOIN
                    payload = {"host": context.host, "port": context.port}
                    from_id = context.server_id
                    sig_b64 = sign_server_frame(context, payload)
                    join = {
                        "type": "SERVER_HELLO_JOIN",
                        "from": from_id,
                        "to": "*",
                        "ts": int(time.time() * 1000),
                        "payload": payload,
                        "sig": sig_b64,
                        "alg": "PS256"
                    }
                    await ws.send(json.dumps(join))
                    print(f"[DEBUG] Sent SERVER_HELLO_JOIN to {peer_addr}")

                    # Listen for frames from the peer
                    async for msg in ws:
                        env = json.loads(msg)
                        # When we get SERVER_WELCOME, register the peer
                        if env.get("type") == "SERVER_WELCOME":
                            peer_id = env.get("from")
                            context.peers[peer_id] = ws
                            print(f"[DEBUG] Registered peer {peer_id} from {peer_addr}")
                        # Dispatch frame to the server's handler
                        await server._dispatch(env, Link(ws, role="server", peer_id=peer_id))
                except Exception as e:
                    print(f"[DEBUG] Peer connection to {peer_addr} closed: {e}")
                finally:
                    if peer_id and peer_id in context.peers:
                        del context.peers[peer_id]
                    if ws in context.peers_pending:
                        del context.peers_pending[ws]

            asyncio.create_task(peer_listener())
        except Exception as e:
            print(f"[DEBUG] Failed to connect to peer {peer_addr}: {e}")

async def main():
    host = os.environ.get("SOCP_HOST", "0.0.0.0")
    port = int(os.environ.get("SOCP_PORT", "8765"))
    server_id = str(uuid.uuid4())

    # Build context + router
    privkey, pubkey_pem = load_or_create_keys()

    context = make_context(server_id, host, port, pubkey_pem, privkey)
    server = TransportServer(host=host, port=port)

    # Register handlers via adapter
    server.on(f"{T_SERVER_HELLO_PREFIX}_JOIN", adapt(context, handle_SERVER_HELLO_JOIN))
    server.on("SERVER_WELCOME",                adapt(context, handle_SERVER_WELCOME))
    server.on("SERVER_ANNOUNCE",               adapt(context, handle_SERVER_ANNOUNCE))
    server.on("USER_ADVERTISE",               adapt(context, handle_USER_ADVERTISE))
    server.on("USER_REMOVE",                  adapt(context, handle_USER_REMOVE))
    server.on("PEER_DELIVER",                 adapt(context, handle_PEER_DELIVER))
    server.on(T_HEARTBEAT,                    adapt(context, handle_HEARTBEAT))

    server.on("CMD_LIST",                     adapt(context, handle_CMD_LIST))
    server.on(T_USER_HELLO,                   adapt(context, handle_USER_HELLO))
    server.on("MSG_DIRECT",                   adapt(context, handle_MSG_DIRECT))
    server.on("MSG_PUBLIC_CHANNEL",           adapt(context, handle_MSG_PUBLIC_CHANNEL))
    server.on("FILE_START",                   adapt(context, handle_FILE_START))
    server.on("FILE_CHUNK",                   adapt(context, handle_FILE_CHUNK))
    server.on("FILE_END",                     adapt(context, handle_FILE_END))


    await connect_to_peers(context, server)
    await server.start()
    log.info("Server %s listening at ws://%s:%d", context.server_id, host, port)

    async def heartbeat_loop():
        while True:
            await context.router.broadcast_heartbeat()
            context.router.reap_peers(dead_after=45.0)
            await asyncio.sleep(15)

    asyncio.create_task(heartbeat_loop())
    await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
