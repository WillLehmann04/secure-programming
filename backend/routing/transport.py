# backend/transport.py

"""
SOCP — Transport (WebSocket) layer

- One WebSocket listener (single port) for Users and Servers.
- FIRST inbound frame MUST be a HELLO (USER_HELLO or SERVER_HELLO_*).
- Exactly ONE JSON object per WebSocket text frame (no newline framing).
- Normal close (1000); optional app-level HEARTBEAT (WS ping/pong still active).
- Pluggable dispatch table (.on) and a verify_envelope callback for Envelope.

"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Dict, Optional, Tuple

import websockets
from websockets.server import WebSocketServerProtocol
from backend.crypto.content_sig import sign_server_frame

# ------------ Protocol constants (keep aligned with the class spec) ------------

T_SERVER_HELLO_PREFIX = "SERVER_HELLO"    # e.g. SERVER_HELLO_JOIN
T_USER_HELLO          = "USER_HELLO"
T_HEARTBEAT           = "HEARTBEAT"
T_ACK                 = "ACK"
T_ERROR               = "ERROR"

# Standard error codes
ERR_USER_NOT_FOUND = "USER_NOT_FOUND"
ERR_INVALID_SIG    = "INVALID_SIG"
ERR_BAD_KEY        = "BAD_KEY"
ERR_TIMEOUT        = "TIMEOUT"
ERR_UNKNOWN_TYPE   = "UNKNOWN_TYPE"
ERR_NAME_IN_USE    = "NAME_IN_USE"

# ------------ Types ------------------------------------------------------------

Handler = Callable[[dict, "Link"], Awaitable[None]]
EnvelopeVerifier = Callable[[dict, "Link"], bool]   # Part 4 pluggable policy


@dataclass
class Link:

    """A connected peer (user or server)."""

    ws: WebSocketServerProtocol
    role: str                 # "user" | "server"
    peer_id: str              # UUIDv4 string
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


# ------------ Envelope structure (Part 3 only; Part 4 will add signature rules) -

def _is_valid_envelope_structure(env: dict) -> Tuple[bool, str]:

    """
    Minimal structure check for the outer envelope (no signature policy here).
    Required keys: type, from, to, ts, payload
    """
    must = ("type", "from", "to", "ts", "payload")
    for k in must:
        if k not in env:
            return False, f"missing:{k}"
    if not isinstance(env["type"], str):
        return False, "type:not_string"
    if not isinstance(env["from"], str):
        return False, "from:not_string"
    if not isinstance(env["to"], str):
        return False, "to:not_string"
    if not isinstance(env["ts"], (int, float)):
        return False, "ts:not_number"
    if not isinstance(env["payload"], dict):
        return False, "payload:not_object"
    return True, ""


def _is_uuid4(s: str) -> bool:
    try:
        return str(uuid.UUID(s, version=4)) == s
    except Exception:
        return False


# ------------------------------ Transport Server --------------------------------

class TransportServer:

    """
    Single WebSocket listener for both Users and Servers.

    - First frame MUST be HELLO (USER_HELLO or any SERVER_HELLO_*).
    - Each WS text frame must be one JSON envelope.
    - register handlers via .on(msg_type, async handler)
    - plug in Envelope via verify_envelope(env, link) -> bool
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8765,
        *,
        state: Optional[State] = None,
        verify_envelope: Optional[EnvelopeVerifier] = None,
        heartbeat_interval: Optional[int] = 15,   # app-level heartbeat; None disables
        ping_interval: int = 20,
        ping_timeout: int = 20,
        log: Optional[logging.Logger] = None,
    ) -> None:
        self._host = host
        self._port = port
        self.state = state or State()
        self.verify_env = verify_envelope
        self._handlers: Dict[str, Handler] = {}
        self._server = None
        self._ws_kwargs = dict(ping_interval=ping_interval, ping_timeout=ping_timeout)
        self._heartbeat_interval = heartbeat_interval
        self._heartbeat_task: Optional[asyncio.Task] = None

        self.log = log or logging.getLogger("backend.transport")
        self.log.setLevel(logging.INFO)

    # ---- public API -----------------------------------------------------------

    def on(self, msg_type: str, handler: Handler) -> None:

        """Register an async handler for a message type."""

        self._handlers[msg_type] = handler

    async def start(self) -> None:

        """Start the WebSocket listener."""

        self._server = await websockets.serve(self._conn_handler, self._host, self._port, **self._ws_kwargs)
        self.log.info("WebSocket listening on ws://%s:%d", self._host, self._port)
        if self._heartbeat_interval:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop(self) -> None:

        """Gracefully stop the server and close connections."""

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        for link in list(self.state.local_users.values()) + list(self.state.servers.values()):
            try:
                await link.ws.close(code=1000, reason="server shutting down")
            except Exception:
                pass
        self.state.local_users.clear()
        self.state.servers.clear()

    # ---- connection lifecycle -------------------------------------------------

    async def _conn_handler(self, ws: WebSocketServerProtocol) -> None:

        """
        First frame MUST be HELLO.
        - SERVER_HELLO_*  -> classify as server
        - USER_HELLO      -> classify as user (enforce unique name on this server)
        Anything else -> ERROR(UNKNOWN_TYPE) and close.
        """
        link: Optional[Link] = None
        try:
            raw = await ws.recv()
            env = json.loads(raw)
            ok, why = _is_valid_envelope_structure(env)
            if not ok:
                await self._send_error(ws, "", ERR_UNKNOWN_TYPE, f"bad_first_frame:{why}")
                return

            msg_type = env["type"]
            peer_id = env["from"]

            if not _is_uuid4(peer_id):
                await self._send_error(ws, "", ERR_BAD_KEY, "from:not_uuid4")
                return

            if msg_type.startswith(T_SERVER_HELLO_PREFIX):
                link = Link(ws=ws, role="server", peer_id=peer_id)
                self.state.servers[peer_id] = link
                self.log.info("server connected: %s", link.tag())

            elif msg_type == T_USER_HELLO:
                link = Link(ws=ws, role="user", peer_id=peer_id)
                self.log.info("user hello received: %s", link.tag())

            else:
                await self._send_error(ws, "", ERR_UNKNOWN_TYPE, "first frame must be HELLO")
                return

            await self._dispatch(env, link)

            async for message in ws:
                await self._handle_frame(message, link)

        except websockets.ConnectionClosed:
            pass
        except Exception as e:
            self.log.exception("link error: %s", e)
        finally:
            if link:
                if link.role == "user":
                    self.state.local_users.pop(link.peer_id, None)
                    self.state.user_locations.pop(link.peer_id, None)
                    # Broadcast USER_REMOVE to all mesh peers
                    user_remove_env = {
                        "type": "USER_REMOVE",
                        "from": link.peer_id,
                        "to": "",
                        "ts": int(time.time() * 1000),
                        "payload": {"user_id": link.peer_id, "location": "local"},
                        "sig": "",
                        "alg": "PS256",
                    }
                    for peer_link in self.state.servers.values():
                        try:
                            await peer_link.ws.send(json.dumps(user_remove_env))
                        except Exception:
                            pass

                    # Call the protocol handler locally as well
                    if "USER_REMOVE" in self._handlers:
                        await self._handlers["USER_REMOVE"](user_remove_env, link)

                else:
                    self.state.servers.pop(link.peer_id, None)
                self.log.info("disconnected: %s", link.tag())
    async def _handle_frame(self, message: str, link: Link) -> None:

        """Parse, structure-check, optional signature-check, then dispatch."""

        try:
            env = json.loads(message)
        except Exception:
            await self._send_error(link.ws, link.peer_id, ERR_UNKNOWN_TYPE, "invalid_json")
            return

        ok, why = _is_valid_envelope_structure(env)
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

        """Dispatch by message type. Unknown type -> ERROR(UNKNOWN_TYPE)."""

        link.last_seen = time.time()
        handler = self._handlers.get(env["type"])
        if not handler:
            await self._send_error(link.ws, link.peer_id, ERR_UNKNOWN_TYPE, f"no_handler:{env['type']}")
            return
        try:
            await handler(env, link)
        except Exception as e:
            self.log.exception("handler error for %s: %s", env["type"], e)
            await self._send_error(link.ws, link.peer_id, ERR_TIMEOUT, f"handler_exception:{env['type']}")

    # ---- optional app-level heartbeat (WS ping/pong still active) -------------

    async def _heartbeat_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._heartbeat_interval)
                now_ms = int(time.time() * 1000)
                payload = {}
                sig_b64 = sign_server_frame(self.ctx, payload)  # Pass the correct ctx
                heart = {
                    "type": T_HEARTBEAT,
                    "from": self.ctx.server_id,
                    "to": "*",
                    "ts": now_ms,
                    "payload": payload,
                    "sig": sig_b64,
                    "alg": "PS256"
                }
                msg = json.dumps(heart, separators=(",", ":"), ensure_ascii=False)
                # Broadcast to servers
                tasks = [asyncio.create_task(link.ws.send(msg)) for link in self.state.servers.values()]
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.CancelledError:
            return

    # ---- error helper ---------------------------------------------------------

    async def _send_error(self, ws: WebSocketServerProtocol, to_id: str, code: str, detail: str) -> None:
        env = {
            "type": T_ERROR,
            "from": "server",
            "to": to_id,
            "ts": int(time.time() * 1000),
            "payload": {"code": code, "detail": detail},
        }
        try:
            await ws.send(json.dumps(env, separators=(",", ":"), ensure_ascii=False))
        except Exception:
            pass

Transport = TransportServer
__all__ = ["TransportServer", "Transport"]