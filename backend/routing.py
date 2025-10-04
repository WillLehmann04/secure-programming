# backend/routing.py
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import deque, defaultdict
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Deque, Dict, Optional, Set

# Prefer team's canonical JSON if present; otherwise a safe fallback.
try:
    from backend.crypto.json_format import stabilise_json as _stabilise_json
except Exception:
    _stabilise_json = None  # fallback below

# Part 4: sign only the payload; attach alg/sig on the outer envelope.
from backend.envelope import sign_payload


def _canonical_bytes(obj: dict) -> bytes:
    """Deterministic JSON -> bytes for hashing/dedupe."""
    if _stabilise_json:
        return _stabilise_json(obj)
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _payload_hash(payload: dict) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _seen_key(frame: dict) -> str:
    """Stable dedupe key: ts|from|to|hash(canonical(payload))."""
    ts = str(frame.get("ts", 0))
    f = frame.get("from", "")
    t = frame.get("to", "")
    h = _payload_hash(frame.get("payload", {}))
    return f"{ts}|{f}|{t}|{h}"


@dataclass
class Router:
    """
    Central routing engine.

    You provide:
      - server_id: this node's id (UUIDv4 string)
      - send_to_peer(sid, frame_dict)  -> Awaitable[None]
      - send_to_local(uid, frame_dict) -> Awaitable[None]
      - peers:          dict[server_id] -> (opaque, usually a websocket)
      - user_locations: dict[user_id]   -> "local" | server_id
      - peer_last_seen: dict[server_id] -> unix_time
      - server_privkey: Optional[object] (if set, payloads are signed with Part 4)

    Router gives you:
      - route_to_user(target, frame) choosing local/remote
      - record_presence(user, location) to update directory + flush queued msgs
      - already_seen/remember for loop-suppression
      - broadcast_heartbeat / note_peer_seen / reap_peers helpers
    """

    server_id: str
    send_to_peer: Callable[[str, dict], Awaitable[None]]
    send_to_local: Callable[[str, dict], Awaitable[None]]
    peers: Dict[str, Any]
    user_locations: Dict[str, str]
    peer_last_seen: Dict[str, float]
    server_privkey: Optional[Any] = None  # RSAPrivateKey or None

    # bounded dedupe
    dedup_max: int = 10_000
    _seen: Set[str] = field(default_factory=set)
    _seen_q: Deque[str] = field(default_factory=deque)

    # small retry buffer for users whose location is not known yet
    _pending_by_user: Dict[str, Deque[dict]] = field(
        default_factory=lambda: defaultdict(deque)
    )
    _pending_max_per_user: int = 100

    # --------- helpers ---------
    def _mk_env(self, msg_type: str, to_id: str, payload: dict) -> dict:
        """
        Build the outer envelope. If a server key is present, sign the payload
        per Part 4 and attach 'sig'/'alg'.
        """
        env = {
            "type": msg_type,
            "from": self.server_id,
            "to": to_id,
            "ts": int(time.time() * 1000),
            "payload": payload,
        }
        if self.server_privkey is not None:
            signed = sign_payload(payload, self.server_privkey)  # {"payload","sig","alg"}
            env["payload"] = signed["payload"]
            env["sig"] = signed["sig"]
            env["alg"] = signed["alg"]
        return env

    # --------- dedupe ----------
    def already_seen(self, frame: dict) -> bool:
        key = _seen_key(frame)
        if key in self._seen:
            return True
        self._remember_key(key)
        return False

    def remember(self, frame: dict) -> None:
        self._remember_key(_seen_key(frame))

    def _remember_key(self, key: str) -> None:
        self._seen.add(key)
        self._seen_q.append(key)
        if len(self._seen_q) > self.dedup_max:
            old = self._seen_q.popleft()
            self._seen.discard(old)

    # --------- presence ----------
    def record_presence(self, user: str, location: str) -> None:
        """Update directory and flush any queued messages for this user."""
        self.user_locations[user] = location
        q = self._pending_by_user.get(user)
        if not q:
            return
        while q:
            frame = q.popleft()
            asyncio.create_task(self._route_now(user, frame, allow_queue=False))

    # --------- routing ----------
    async def route_to_user(self, target: str, frame: dict, *, allow_queue: bool = True) -> bool:
        """Public entry-point. Returns True if delivered/forwarded, else False."""
        return await self._route_now(target, frame, allow_queue=allow_queue)

    async def _route_now(self, target: str, frame: dict, *, allow_queue: bool) -> bool:
        if not target:
            return False

        # Local delivery -> USER_DELIVER
        if self.user_locations.get(target) == "local":
            deliver = self._mk_env("USER_DELIVER", target, payload=frame.get("payload", {}))
            await self.send_to_local(target, deliver)
            return True

        # Remote delivery -> PEER_DELIVER (include 'user_id' for hosting peer)
        host_loc = self.user_locations.get(target)
        if host_loc and host_loc in self.peers and host_loc != "local":
            fwd_payload = dict(frame.get("payload", {}))
            fwd_payload["user_id"] = target
            forward = self._mk_env("PEER_DELIVER", host_loc, payload=fwd_payload)
            await self.send_to_peer(host_loc, forward)
            return True

        # Unknown location -> optionally queue
        if allow_queue:
            q = self._pending_by_user[target]
            if len(q) >= self._pending_max_per_user:
                q.popleft()  # drop oldest
            q.append(frame)
        return False

    # --------- maintenance ----------
    async def broadcast_heartbeat(self) -> None:
        hb = self._mk_env("HEARTBEAT", "*", payload={})
        await asyncio.gather(
            *[self.send_to_peer(sid, hb) for sid in list(self.peers.keys())],
            return_exceptions=True,
        )

    def note_peer_seen(self, sid: str) -> None:
        self.peer_last_seen[sid] = time.time()

    def reap_peers(self, dead_after: float = 45.0) -> list[str]:
        """
        Remove peers not seen for > dead_after seconds.
        Returns the list of removed server_ids.
        """
        now = time.time()
        removed: list[str] = []
        for sid, last in list(self.peer_last_seen.items()):
            if now - last > dead_after:
                removed.append(sid)
                self.peer_last_seen.pop(sid, None)
                self.peers.pop(sid, None)
        return removed
