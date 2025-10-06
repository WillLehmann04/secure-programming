# backend/transport.py

# Transport (WebSockets)

'''Single listener for *both* servers and users. The very first message
on a connection must be a HELLO (server or user) so we can classify
the peer and register it.

Each subsequent WebSocket text frame is one JSON object (no newline framing).'''

from __future__ import annotations
import asyncio, json, logging, time, uuid
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Dict, Optional, Tuple

import websockets
from websockets.server import WebSocketServerProtocol

# frame types
T_SERVER_HELLO_PREFIX = "SERVER_HELLO"   # e.g. SERVER_HELLO_JOIN
T_USER_HELLO          = "USER_HELLO"
T_HEARTBEAT           = "HEARTBEAT"
T_ACK                 = "ACK"
T_ERROR               = "ERROR"

# error codes
ERR_USER_NOT_FOUND = "USER_NOT_FOUND"
ERR_INVALID_SIG    = "INVALID_SIG"
ERR_BAD_KEY        = "BAD_KEY"
ERR_TIMEOUT        = "TIMEOUT"
ERR_UNKNOWN_TYPE   = "UNKNOWN_TYPE"
ERR_NAME_IN_USE    = "NAME_IN_USE"

Handler = Callable[[dict, "Link"], Awaitable[None]]
Verifier = Callable[[dict, "Link"], bool]


@dataclass
class Link:
    """Represents a connected peer (either a server or a user)."""
    ws: WebSocketServerProtocol
    role: str                   # "server" or "user"
    peer_id: str                # UUIDv4
    connected_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    def tag(self) -> str:
        return f"{self.role}:{self.peer_id}"


@dataclass
class State:
    servers: Dict[str, Link] = field(default_factory=dict)          # server_id -> Link
    server_addrs: Dict[str, Tuple[str, int]] = field(default_factory=dict)
    local_users: Dict[str, Link] = field(default_factory=dict)      # user_id -> Link
    user_locations: Dict[str, str] = field(default_factory=dict)    # user_id -> "local" | server_id


# quick envelope sanity check (structure only)

def _is_uuid4(s: str) -> bool:
    try:
        return str(uuid.UUID(s, version=4)) == s
    except Exception:
        return False


def _struct_ok(env: dict) -> Tuple[bool, str]:
    """Basic shape check. Signatures are checked by the caller’s policy."""
    for k in ("type", "from", "to", "ts", "payload"):
        if k not in env:
            return False, f"missing:{k}"
    if not isinstance(env["payload"], dict):
        return False, "payload:not_object"
    return True, ""


# the actual server

class TransportServer:
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8765,
        *,
        state: Optional[State] = None,
        verify_env: Optional[Verifier] = None,   # can be None if you don’t want checks here
        heartbeat_interval: int = 15,
    ) -> None:
        self.host = host
        self.port = port
        self.state = state or State()
        self.verify_env = verify_env
        self.handlers: Dict[str, Handler] = {}
        self._hb_interval = heartbeat_interval
        self._hb_task: Optional[asyncio.Task] = None
        self.log = logging.getLogger("backend.transport")
        self.log.setLevel(logging.INFO)

    # register handlers
    def on(self, msg_type: str, handler: Handler) -> None:
        self.handlers[msg_type] = handler

    # start/stop
    async def start(self) -> None:
        self._server = await websockets.serve(self._on_conn, self.host, self.port)
        self.log.info("WebSocket listening on ws://%s:%d", self.host, self.port)
        if self._hb_interval:
            self._hb_task = asyncio.create_task(self._heartbeat_loop())

    async def stop(self) -> None:
        if self._hb_task:
            self._hb_task.cancel()
        if hasattr(self, "_server"):
            self._server.close()
            await self._server.wait_closed()

    # connection lifecycle
    async def _on_conn(self, ws: WebSocketServerProtocol) -> None:
        link: Optional[Link] = None
        try:
            hello = json.loads(await ws.recv())
            ok, why = _struct_ok(hello)
            if not ok:
                await self._send_error(ws, "", ERR_UNKNOWN_TYPE, why)
                return

            peer_id = hello["from"]
            if not _is_uuid4(peer_id):
                await self._send_error(ws, "", ERR_BAD_KEY, "from:not_uuid4")
                return

            if hello["type"].startswith(T_SERVER_HELLO_PREFIX):
                link = Link(ws=ws, role="server", peer_id=peer_id)
                self.state.servers[peer_id] = link
                self.log.info("server connected: %s", link.tag())
            elif hello["type"] == T_USER_HELLO:
                if peer_id in self.state.local_users:
                    await self._send_error(ws, peer_id, ERR_NAME_IN_USE, "user already here")
                    return
                link = Link(ws=ws, role="user", peer_id=peer_id)
                self.state.local_users[peer_id] = link
                self.state.user_locations[peer_id] = "local"
                self.log.info("user connected: %s", link.tag())
            else:
                await self._send_error(ws, "", ERR_UNKNOWN_TYPE, "first frame must be HELLO")
                return

            # Let app code react to the HELLO
            await self._dispatch(hello, link)

            # Normal loop
            async for raw in ws:
                await self._handle_frame(raw, link)

        except websockets.ConnectionClosed:
            pass
        except Exception as e:
            self.log.exception("link error: %s", e)
        finally:
            if link:
                # drop from whichever map it belongs to
                self.state.local_users.pop(link.peer_id, None)
                self.state.servers.pop(link.peer_id, None)
                self.log.info("disconnected: %s", link.tag())

    async def _handle_frame(self, raw: str, link: Link) -> None:
        try:
            env = json.loads(raw)
        except Exception:
            await self._send_error(link.ws, link.peer_id, ERR_UNKNOWN_TYPE, "invalid_json")
            return

        ok, why = _struct_ok(env)
        if not ok:
            await self._send_error(link.ws, link.peer_id, ERR_UNKNOWN_TYPE, why)
            return

        if self.verify_env:
            try:
                if not self.verify_env(env, link):
                    await self._send_error(link.ws, link.peer_id, ERR_INVALID_SIG, "verification_failed")
                    return
            except Exception as e:
                self.log.warning("verify_env raised: %s", e)
                await self._send_error(link.ws, link.peer_id, ERR_INVALID_SIG, "verifier_exception")
                return

        await self._dispatch(env, link)

    async def _dispatch(self, env: dict, link: Link) -> None:
        handler = self.handlers.get(env["type"])
        if not handler:
            await self._send_error(link.ws, link.peer_id, ERR_UNKNOWN_TYPE, f"no handler for {env['type']}")
            return
        try:
            await handler(env, link)
        except Exception as e:
            self.log.exception("handler error for %s: %s", env["type"], e)
            await self._send_error(link.ws, link.peer_id, ERR_TIMEOUT, "handler_exception")

    # app-level heartbeat (WS ping/pong still exists underneath)
    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(self._hb_interval)
            beat = {
                "type": T_HEARTBEAT,
                "from": "server",
                "to": "*",
                "ts": int(time.time() * 1000),
                "payload": {},
            }
            msg = json.dumps(beat)
            await asyncio.gather(
                *(link.ws.send(msg) for link in self.state.servers.values()),
                return_exceptions=True,
            )

    async def _send_error(self, ws: WebSocketServerProtocol, to_id: str, code: str, detail: str) -> None:
        env = {
            "type": T_ERROR,
            "from": "server",
            "to": to_id,
            "ts": int(time.time() * 1000),
            "payload": {"code": code, "detail": detail},
        }
        try:
            await ws.send(json.dumps(env))
        except Exception:
            pass
