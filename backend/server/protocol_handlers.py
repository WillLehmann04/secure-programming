'''
    Group: Group 2
    Members:
        - William Lehmann (A1889855)
        - Edward Chipperfield (A1889447)
        - G A Sadman (A1899867)
        - Aditeya Sahu (A1943902)
        
    Description:
        - This module contains protocol handlers for various message types.
        - It handles both server-to-server and user-to-server messages.
        - It includes signature verification, deduplication, and routing logic.
'''


import json, hashlib, time
from collections import deque
from backend.crypto.content_sig import sign_server_frame, verify_server_frame
from backend.crypto.rsa_key_management import load_public_key

from .peer_comm_utilities import send_to_all_peers, make_seen_key, remember_seen, send_error

from backend.server.handlers.msg_direct import handle_MSG_DIRECT
from backend.server.handlers.user_advertise import handle_USER_ADVERTISE
from backend.server.handlers.user_remove import handle_USER_REMOVE
from backend.server.handlers.server_announce import handle_SERVER_ANNOUNCE
from backend.server.handlers.server_hello_join import handle_SERVER_HELLO_JOIN
from backend.server.handlers.server_welcome import handle_SERVER_WELCOME
from backend.server.handlers.user_hello import handle_USER_HELLO    

from backend.server.handlers.cmd_list import handle_CMD_LIST

# ---------- User Advertisement ----------

async def handle_MSG_PUBLIC_CHANNEL(ctx, ws, frame):
    key = make_seen_key(frame)
    if remember_seen(ctx, key):
        return  # Drop duplicate

    # Fan-out to all local users
    for uid, uws in ctx.local_users.items():
        await uws.send(json.dumps(frame))
    # Relay to all peers (except the one we got it from)
    await send_to_all_peers(ctx, frame, exclude_ws=ws)

async def handle_PEER_DELIVER(ctx, ws, frame):
    key = make_seen_key(frame)
    if remember_seen(ctx, key): return
    target = frame.get("payload",{}).get("user_id") or frame.get("to")
    await ctx.router.route_to_user(target, frame.get("payload",{}).get("forwarded", frame))

async def handle_HEARTBEAT(ctx, ws, frame):
    sid = frame.get("from")
    if sid: ctx.router.note_peer_seen(sid)


# ---------- User <-> Server ----------



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
