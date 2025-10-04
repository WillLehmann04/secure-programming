from __future__ import annotations
import json
from typing import Dict
from websockets.server import WebSocketServerProtocol
from persistence.dir_json import list_group_members

SESSIONS: Dict[str, WebSocketServerProtocol] = {}
WS_TO_USER: Dict[WebSocketServerProtocol, str] = {}

def attach(uid: str, ws: WebSocketServerProtocol) -> None:
    SESSIONS[uid] = ws
    WS_TO_USER[ws] = uid

def detach(ws: WebSocketServerProtocol) -> None:
    uid = WS_TO_USER.pop(ws, None)
    if uid and SESSIONS.get(uid) is ws:
        SESSIONS.pop(uid, None)

def online_users() -> list[str]:
    return sorted(SESSIONS.keys())

async def forward_to(user_id: str, obj: dict) -> bool:
    ws = SESSIONS.get(user_id)
    if ws and ws.open:
        await ws.send(json.dumps(obj))
        return True
    return False

async def fanout_public(except_user: str, obj: dict) -> None:
    public = set(list_group_members("public"))
    for uid, peer in list(SESSIONS.items()):
        if uid != except_user and uid in public and peer.open:
            await peer.send(json.dumps(obj))
