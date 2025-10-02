# backend/routing.py

# Routing core
# - canonical, bounded dedupe (aligns with Part 4 stabilise_json)
# - local vs remote delivery (aligns with Part 6 handlers)
# - tiny retry buffer for temporarily unknown user locations
# - heartbeat expiry support (works with your existing keepalive logic)
#
# No external deps. Uses asyncio + our existing maps on ctx.

from __future__ import annotations

import asyncio
import json
import time
from collections import deque, defaultdict
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Deque, Dict, List, Optional, Set, Tuple

from backend.crypto.json_format import stabilise_json  # Part 4 canonical JSON


def _canonical_payload_hash(payload: dict) -> str:

    """sha256 over canonicalised JSON bytes (Part 4)."""

    import hashlib
    b = stabilise_json(payload)
    return hashlib.sha256(b).hexdigest()


def _seen_key(frame: dict) -> str:

    """Stable dedupe key: ts|from|to|hash(canonical(payload))."""

    ts = str(frame.get("ts", 0))
    f = frame.get("from", "")
    t = frame.get("to", "")
    h = _canonical_payload_hash(frame.get("payload", {}))
    return f"{ts}|{f}|{t}|{h}"


@dataclass
class Router:

    """
    Central routing engine.

    User/We provides:
      - server_id: this node's id
      - send_to_peer(sid, frame)  -> Awaitable[None]
      - send_to_local(uid, frame) -> Awaitable[None]
      - peers: id -> opaque peer handle (usually a websocket)
      - user_locations: user -> "local" | server_id
      - peer_last_seen: sid -> unix_time

    Router gives us:
      - route_to_user(target, frame) chooses local/remote and emits required wrapper
      - record_presence(user, location) updates directory and flushes queued msgs
      - dedupe() utilities you can call on inbound frames to prevent loops
      - reap_peers(dead_after) helper
    """

    server_id: str
    send_to_peer: Callable[[str, dict], Awaitable[None]]
    send_to_local: Callable[[str, dict], Awaitable[None]]
    peers: Dict[str, Any]
    user_locations: Dict[str, str]
    peer_last_seen: Dict[str, float]

    # bounded dedupe
    dedup_max: int = 10_000
    _seen: Set[str] = field(default_factory=set)
    _seen_q: Deque[str] = field(default_factory=deque)

    # small retry buffer for users whose location is not known yet
    _pending_by_user: Dict[str, Deque[dict]] = field(default_factory=lambda: defaultdict(deque))
    _pending_max_per_user: int = 100

    # ---- DEDUPE -------------------------------------------------------------

    def already_seen(self, frame: dict) -> bool:

        """Return True if frame was already processed; otherwise remember it."""

        key = _seen_key(frame)
        if key in self._seen:
            return True
        self._remember_key(key)
        return False

    def remember(self, frame: dict) -> None:

        """Force-remember a frame as processed (used by code paths that check first)."""

        self._remember_key(_seen_key(frame))

    def _remember_key(self, key: str) -> None:
        self._seen.add(key)
        self._seen_q.append(key)
        if len(self._seen_q) > self.dedup_max:
            old = self._seen_q.popleft()
            self._seen.discard(old)

    # ---- PRESENCE / DIRECTORY ----------------------------------------------

    def record_presence(self, user: str, location: str) -> None:

        """
        Update user location and flush queued messages for that user.
        location: "local" or server_id
        """
        self.user_locations[user] = location
        # flush any queued frames
        q = self._pending_by_user.get(user)
        if not q:
            return
        while q:
            frame = q.popleft()
            # route without re-queuing (if location still unknown, drop to avoid loop)
            asyncio.create_task(self._route_now(user, frame, allow_queue=False))

    # ---- ROUTING ------------------------------------------------------------

    async def route_to_user(self, target: str, frame: dict) -> None:

        """
        Public entry: routing a frame to a target user.
        Wrap as USER_DELIVER for locals, PEER_DELIVER for remotes.
        """
        await self._route_now(target, frame, allow_queue=True)

    async def _route_now(self, target: str, frame: dict, *, allow_queue: bool) -> None:
        if not target:
            # nothing we can do — caller should have validated earlier
            return

        # local delivery
        if self.user_locations.get(target) == "local":
            deliver = {
                "type": "USER_DELIVER",
                "from": self.server_id,
                "to": target,
                "ts": int(time.time() * 1000),
                "payload": frame.get("payload", {}),
            }
            await self.send_to_local(target, deliver)
            return

        # remote delivery
        host_loc = self.user_locations.get(target)
        if host_loc and host_loc in self.peers:
            forward = {
                "type": "PEER_DELIVER",
                "from": self.server_id,
                "to": host_loc,
                "ts": int(time.time() * 1000),
                "payload": {**frame.get("payload", {}), "user_id": target},
            }
            await self.send_to_peer(host_loc, forward)
            return

        # unknown location
        if allow_queue:
            q = self._pending_by_user[target]
            if len(q) >= self._pending_max_per_user:
                q.popleft()  # drop oldest to make space
            q.append(frame)

    # ---- MAINTENANCE --------------------------------------------------------

    async def broadcast_heartbeat(self) -> None:

        """Emitting a HEARTBEAT to all currently-connected peers."""

        hb = {
            "type": "HEARTBEAT",
            "from": self.server_id,
            "to": "*",
            "ts": int(time.time() * 1000),
            "payload": {},
        }
        # fire-and-forget sends
        await asyncio.gather(*[
            self.send_to_peer(sid, hb) for sid in list(self.peers.keys())
        ], return_exceptions=True)

    def note_peer_seen(self, sid: str) -> None:
        self.peer_last_seen[sid] = time.time()

    def reap_peers(self, dead_after: float = 45.0) -> List[str]:

        """
        Removing peers we haven't heard from in dead_after seconds.
        Returns list of removed peer ids.
        """
        now = time.time()
        removed: List[str] = []
        for sid, last in list(self.peer_last_seen.items()):
            if now - last > dead_after:
                removed.append(sid)
                self.peer_last_seen.pop(sid, None)
                self.peers.pop(sid, None)
        return removed
