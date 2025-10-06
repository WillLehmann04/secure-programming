from pathlib import Path

def get_server_id() -> str:
    path = Path(__file__).parent.parent / "storage" / "server_id.txt"
    with path.open("r", encoding="utf-8") as f:
        return f.read().strip()

from __future__ import annotations
import asyncio, json, hashlib
from typing import Dict, Any, Callable, Optional

from ..protocol.types import *

import websockets
from websockets.server import WebSocketServerProtocol

from server.bootstrap import init_persistence
from persistence.dir_json import (
    user_exists, get_pubkey, list_group_members,
)
from protocol.types import (
    DIR_GET_PUBKEY, DIR_GET_WRAPPED_PUBLIC_KEY,
    ERR_BAD_JSON, ERR_UNKNOWN_TYPE, ERR_NAME_IN_USE, ERR_USER_NOT_FOUND,
)
from protocol.rpc import resp_error
from server.handlers_directory import (
    handle_dir_get_pubkey,
    handle_dir_get_wrapped_public_key,
)

# Crypto helpers
from backend.crypto import rsa_verify_pss, stabilise_json, base64url_decode

SESSIONS: Dict[str, WebSocketServerProtocol] = {}   # user_id -> websocket
WS_TO_USER: Dict[WebSocketServerProtocol, str] = {} # reverse map
SERVER_SESSIONS: Dict[str, WebSocketServerProtocol] = {}  # server_id -> websocket

def _sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()

def _verify_transport_sig(sender_id: str, payload: Dict[str, Any], sig_b64u: Optional[str]) -> bool:
    if not isinstance(sig_b64u, str) or not sig_b64u:
        return False
    pub = get_pubkey(sender_id)
    if not pub:
        return False
    msg = stabilise_json(payload)                         # canonical bytes of the payload
    sig = base64url_decode(sig_b64u)
    return rsa_verify_pss(pub, msg, sig)

def _verify_content_sig(frame_type: str, payload: Dict[str, Any], sender_id: str) -> bool:
    """
    MSG_DIRECT: sha256(ciphertext || from || to || ts)
    MSG_PUBLIC_CHANNEL: sha256(ciphertext || from || ts)
      - ciphertext is base64url string in both cases
      - signature is base64url in payload["content_sig"]
    """
    sig_b64 = payload.get("content_sig")
    if not isinstance(sig_b64, str):
        return False
    pub = get_pubkey(sender_id)
    if not pub:
        return False

    frm = payload.get("from", "")
    if frm != sender_id:
        return False

    try:
        ct = base64url_decode(payload.get("ciphertext", ""))
    except Exception:
        return False

    ts = str(payload.get("ts", ""))
    if frame_type == "MSG_DIRECT":
        to = payload.get("to", "")
        digest = _sha256(ct + frm.encode() + to.encode() + ts.encode())
    elif frame_type == "MSG_PUBLIC_CHANNEL":
        digest = _sha256(ct + frm.encode() + ts.encode())
    else:
        return False

    sig = base64url_decode(sig_b64)
    return rsa_verify_pss(pub, digest, sig)

def _is_public_member(user_id: str) -> bool:
    try:
        return user_id in set(list_group_members("public"))
    except Exception:
        return False

async def _fanout_public_all_servers(except_user: str, obj: Dict[str, Any]) -> None:
    await _fanout_public(except_user, obj)  # local users
    for server_id, ws in SERVER_SESSIONS.items():
        if ws.open:
            await ws.send(json.dumps(obj))

# Router for RPC
from typing import Awaitable
Handler = Callable[[str, Dict[str, Any]], Dict[str, Any]]
ROUTES: Dict[str, Handler] = {
    DIR_GET_PUBKEY: handle_dir_get_pubkey,
    DIR_GET_WRAPPED_PUBLIC_KEY: handle_dir_get_wrapped_public_key,
}

async def _forward_to(user_id: str, obj: Dict[str, Any]) -> bool:
    ws = SESSIONS.get(user_id)
    if ws and ws.open:
        await ws.send(json.dumps(obj))
        return True
    return False

async def _fanout_public(except_user: str, obj: Dict[str, Any]) -> None:
    # Deliver only to connected members in the 'public' group
    public_members = set(list_group_members("public"))
    for uid, peer in list(SESSIONS.items()):
        if uid != except_user and uid in public_members and peer.open:
            await peer.send(json.dumps(obj))

async def _handle_connection(ws: WebSocketServerProtocol):
    try:
        async for msg in ws:
            try:
                obj = json.loads(msg)
            except Exception:
                await ws.send(json.dumps(resp_error("", ERR_BAD_JSON, "invalid JSON")))
                continue

            t = obj.get("type")
            req_id = obj.get("req_id", "")
            p = obj.get("payload", {}) or {}

            # Dir RPCs
            route = ROUTES.get(t)
            if route:
                try:
                    resp = route(req_id, p)
                except Exception:
                    resp = resp_error(req_id, "INTERNAL", "server error")
                await ws.send(json.dumps(resp))
                continue

            if t == "USER_HELLO":
                uid = obj.get("from")
                if not isinstance(uid, str) or not uid:
                    error = {
                        "type": ERROR,
                        "from": uid,
                        "to": obj.get("to"),
                        "payload": {"code": "USER_NOT_FOUND", "detail": "missing user_id"},
                        "sig": "",
                    }
                    await ws.send(json.dumps(error))
                    continue

                # Enforce the user exists in the directory, also not already connected under that name
                if not user_exists(uid):
                    await ws.send(json.dumps({"type":"ERROR","payload":{"code":ERR_USER_NOT_FOUND,"message":uid}}))
                    continue
                if uid in SESSIONS:
                    await ws.send(json.dumps({"type":"ERROR","payload":{"code":ERR_NAME_IN_USE,"message":uid}}))
                    continue

                # Record session
                SESSIONS[uid] = ws
                WS_TO_USER[ws] = uid

                ###  As per SOCP a user advertise needs to be sent when an ack is about to be sent

                advertise = {
                    "type": "USER_ADVERTISE",
                    "from": get_server_id(),
                    "to": obj.get("to"),
                    "payload": {
                        "user_id": uid,
                        "pubkey": get_pubkey(uid).public_bytes().decode(),
                    },
                    "sig": "",
                }



                
                ''' CONSTRUCT ACK '''
                ACK = {
                    "type": "ACK",
                    "from": uid,
                    "to": obj.get("to"),
                    "payload": {"msg_ref": uid},
                    "sig":"",
                }

                await ws.send(json.dumps(ACK))
                continue

            if t == "CMD_LIST":
                online = sorted(SESSIONS.keys())
                await ws.send(json.dumps({"type":"USER_LIST","payload":{"users":online}}))
                continue

            if t == "MSG_DIRECT":
                sender = p.get("from","")
                if not _verify_transport_sig(sender, p, obj.get("transport_sig")) or not _verify_content_sig("MSG_DIRECT", p, sender):
                    await ws.send(json.dumps({"type":"ERROR","payload":{"code":"INVALID_SIG","message":"drop"}}))
                    continue
                to = p.get("to","")
                if not await _forward_to(to, obj):
                    await ws.send(json.dumps({"type":"ERROR","payload":{"code":"USER_NOT_ONLINE","message":to}}))
                continue

                if t == "MSG_PUBLIC_CHANNEL":
                    sender = p.get("from","")
                if not _verify_transport_sig(sender, p, obj.get("transport_sig")) or not _verify_content_sig("MSG_PUBLIC_CHANNEL", p, sender):
                    await ws.send(json.dumps({"type":"ERROR","payload":{"code":"INVALID_SIG","message":"drop"}}))
                    continue
                if not _is_public_member(sender):
                    await ws.send(json.dumps({"type":"ERROR","payload":{"code":"NOT_IN_PUBLIC_GROUP","message":sender}}))
                    continue
                # Broadcast to all servers and local users
                await _fanout_public_all_servers(sender, obj)
                continue

            # Simple file routing - currently no extra validation
            if t in ("FILE_START","FILE_CHUNK","FILE_END"):
                to = p.get("to")
                sender = p.get("from","")
                if to:
                    # direct file transfer
                    if not await _forward_to(to, obj):
                        await ws.send(json.dumps({"type":"ERROR","payload":{"code":"USER_NOT_ONLINE","message":to}}))
                else:
                    # public fanout
                    if not _is_public_member(sender):
                        await ws.send(json.dumps({"type":"ERROR","payload":{"code":"NOT_IN_PUBLIC_GROUP","message":sender}}))
                    else:
                        await _fanout_public(sender, obj)
                continue

            # Unknown type
            await ws.send(json.dumps(resp_error(req_id, ERR_UNKNOWN_TYPE, str(t))))

    finally:
        # Cleanup mapping on disconnect
        uid = WS_TO_USER.pop(ws, None)
        if uid and SESSIONS.get(uid) is ws:
            SESSIONS.pop(uid, None)


# --- Add connect_to_servers implementation ---
import websockets

async def connect_to_servers():
    from server.bootstrap import get_bootstrap_servers
    servers = get_bootstrap_servers()
    for entry in servers:
        host = entry["host"]
        port = entry["port"]
        server_id = f"{host}:{port}"
        try:
            ws = await websockets.connect(f"ws://{host}:{port}")
            SERVER_SESSIONS[server_id] = ws
            # Optionally: create a task to handle incoming messages from this server
            print(f"Connected to server {server_id}")
        except Exception as e:
            print(f"Failed to connect to server {server_id}: {e}")

async def main():
    init_persistence()
    await connect_to_servers()
    async with websockets.serve(_handle_connection, "0.0.0.0", 8765, max_size=2**20):
        print("WS server on :8765")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
