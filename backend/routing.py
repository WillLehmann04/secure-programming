# backend/routing.py

#Routing core

'''Given a destination user id, decide whether the message stays on this
server or needs to be forwarded to another one. We also do a simple
loop-breaker (dedupe) and keep a tiny queue for users whose location
isn’t known yet.'''


from __future__ import annotations
import asyncio, json, time, hashlib
from collections import deque, defaultdict
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Deque, Dict, Optional, Set, List

# Prefer the team’s canonical JSON; fall back to a tiny deterministic dump.
try:
    from backend.crypto.json_format import stabilise_json as _canon
except Exception:
    _canon = None

from backend.envelope import sign_payload


# small helpers

def _canon_bytes(obj: dict) -> bytes:
    if _canon:
        return _canon(obj)
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def _payload_hash(payload: dict) -> str:
    return hashlib.sha256(_canon_bytes(payload)).hexdigest()


def _seen_key(frame: dict) -> str:
    """Combine ts/from/to/hash(payload) so loops don’t spam the mesh."""
    ts = str(frame.get("ts", 0))
    return f"{ts}|{frame.get('from','')}|{frame.get('to','')}|{_payload_hash(frame.get('payload', {}))}"


# router 

@dataclass
class Router:
    server_id: str
    send_to_peer: Callable[[str, dict], Awaitable[None]]
    send_to_local: Callable[[str, dict], Awaitable[None]]
    peers: Dict[str, Any]
    user_locations: Dict[str, str]
    peer_last_seen: Dict[str, float]
    server_privkey: Optional[Any] = None   # if set, we sign payloads on hop

    # dedupe memory (bounded)
    dedup_max: int = 10_000
    _seen: Set[str] = field(default_factory=set)
    _seen_q: Deque[str] = field(default_factory=deque)

    # small buffer for unknown destinations
    _pending: Dict[str, Deque[dict]] = field(default_factory=lambda: defaultdict(deque))
    _pending_max: int = 100

    # envelope builder (kept here because it needs server_id + optional signing)
    def _wrap(self, mtype: str, to_id: str, payload: dict) -> dict:
        env = {
            "type": mtype,
            "from": self.server_id,
            "to": to_id,
            "ts": int(time.time() * 1000),
            "payload": payload,
        }
        if self.server_privkey:  # Part 4 hop-signing (transport sig)
            signed = sign_payload(payload, self.server_privkey)
            env["sig"], env["alg"] = signed["sig"], signed["alg"]
        return env

    # dedupe
    def already_seen(self, frame: dict) -> bool:
        key = _seen_key(frame)
        if key in self._seen:
            return True
        self._seen.add(key)
        self._seen_q.append(key)
        if len(self._seen_q) > self.dedup_max:
            old = self._seen_q.popleft()
            self._seen.discard(old)
        return False

    # presence / directory 
    def record_presence(self, user: str, location: str) -> None:
        """Update directory and flush any queued messages."""
        self.user_locations[user] = location
        q = self._pending.get(user)
        if not q:
            return
        while q:
            frame = q.popleft()
            asyncio.create_task(self._route_now(user, frame, allow_queue=False))

    # routing
    async def route_to_user(self, target: str, frame: dict, *, allow_queue: bool = True) -> bool:
        """Public entry point. Returns True if we delivered/forwarded."""
        return await self._route_now(target, frame, allow_queue=allow_queue)

    async def _route_now(self, target: str, frame: dict, *, allow_queue: bool) -> bool:
        if not target:
            return False

        loc = self.user_locations.get(target)

        # (1) Local delivery
        if loc == "local":
            deliver = self._wrap("USER_DELIVER", target, frame.get("payload", {}))
            await self.send_to_local(target, deliver)
            return True

        # (2) Remote delivery
        if loc and loc in self.peers and loc != "local":
            payload = dict(frame.get("payload", {}))
            payload["user_id"] = target
            forward = self._wrap("PEER_DELIVER", loc, payload)
            await self.send_to_peer(loc, forward)
            return True

        # (3) Unknown — optionally queue
        if allow_queue:
            q = self._pending[target]
            if len(q) >= self._pending_max:
                q.popleft()  # make space
            q.append(frame)
        return False

    # maintenance
    async def broadcast_heartbeat(self) -> None:
        beat = self._wrap("HEARTBEAT", "*", {})
        await asyncio.gather(
            *(self.send_to_peer(sid, beat) for sid in list(self.peers.keys())),
            return_exceptions=True,
        )

    def note_peer_seen(self, sid: str) -> None:
        self.peer_last_seen[sid] = time.time()

    def reap_peers(self, dead_after: float = 45.0) -> List[str]:
        """Remove peers that haven’t pinged within `dead_after` seconds."""
        now = time.time()
        removed: List[str] = []
        for sid, last in list(self.peer_last_seen.items()):
            if now - last > dead_after:
                removed.append(sid)
                self.peer_last_seen.pop(sid, None)
                self.peers.pop(sid, None)
        return removed
