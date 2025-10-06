'''
    Group: Group 2
    Members:
        - William Lehmann (A1889855)
        - Edward Chipperfield (A1889447)
        - G A Sadman (A1899867)
        - Aditeya Sahu (A1943902)
        
    Description:
        - This module implements a message routing system for a distributed server architecture.
'''


import json
import time
from typing import Any, Awaitable, Callable, Deque, Dict, List, Set
from collections import deque, defaultdict
from dataclasses import dataclass, field

def _seen_key(frame: dict) -> str:
    # ts|from|to|sha256(canonical(payload)) — simple & stable
    import hashlib, json as _json
    ts = str(frame.get("ts", 0))
    f  = frame.get("from", "")
    t  = frame.get("to", "")
    # canonicalise for stability across nodes
    b  = _json.dumps(frame.get("payload", {}), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    h  = hashlib.sha256(b).hexdigest()
    return f"{ts}|{f}|{t}|{h}"

@dataclass
class Router:
    server_id: str
    send_to_peer: Callable[[str, dict], Awaitable[None]]
    send_to_local: Callable[[str, dict], Awaitable[None]]
    peers: Dict[str, Any]                 # sid -> ws
    user_locations: Dict[str, str]        # uid -> "local" | sid
    peer_last_seen: Dict[str, float]      # sid -> unix ts

    # bounded dedupe
    dedup_max: int = 10_000
    _seen: Set[str] = field(default_factory=set)
    _seen_q: Deque[str] = field(default_factory=deque)

    # retry buffer for unknown locations
    _pending_by_user: Dict[str, Deque[dict]] = field(default_factory=lambda: defaultdict(deque))
    _pending_max_per_user: int = 100

    # ---- DEDUPE ----
    def already_seen(self, frame: dict) -> bool:
        k = _seen_key(frame)
        if k in self._seen:
            return True
        self._remember(k)
        return False

    def _remember(self, k: str) -> None:
        self._seen.add(k)
        self._seen_q.append(k)
        if len(self._seen_q) > self.dedup_max:
            old = self._seen_q.popleft()
            self._seen.discard(old)

    # ---- PRESENCE ----
    def record_presence(self, user: str, location: str) -> None:
        self.user_locations[user] = location
        q = self._pending_by_user.get(user)
        if not q: return
        while q:
            frame = q.popleft()
            # fire & forget
            import asyncio
            asyncio.create_task(self._route_now(user, frame, allow_queue=False))

    # ---- ROUTING ----
    async def route_to_user(self, target: str, frame: dict) -> None:
        await self._route_now(target, frame, allow_queue=True)

    async def _route_now(self, target: str, frame: dict, *, allow_queue: bool) -> None:
        if not target: return

        # local
        if self.user_locations.get(target) == "local":
            deliver = {
                "type": "USER_DELIVER",
                "from": frame.get("from"),
                "to":   target,
                "ts":   int(time.time()*1000),
                "payload": frame.get("payload", {}),
            }
            await self.send_to_local(target, deliver)
            return

        # remote
        host = self.user_locations.get(target)
        if host and host in self.peers:
            fwd = {
                "type": "PEER_DELIVER",
                "from": self.server_id,
                "to":   host,
                "ts":   int(time.time()*1000),
                "payload": {"user_id": target, "forwarded": frame},
            }
            await self.send_to_peer(host, fwd)
            return

        # unknown
        if allow_queue:
            q = self._pending_by_user[target]
            if len(q) >= self._pending_max_per_user:
                q.popleft()
            q.append(frame)

    # ---- HEARTBEAT / REAP ----
    async def broadcast_heartbeat(self) -> None:
        hb = {"type":"HEARTBEAT","from":self.server_id,"to":"*","ts":int(time.time()*1000),"payload":{}}
        import asyncio
        await asyncio.gather(*[self.send_to_peer(sid, hb) for sid in list(self.peers.keys())], return_exceptions=True)

    def note_peer_seen(self, sid: str) -> None:
        self.peer_last_seen[sid] = time.time()

    def reap_peers(self, dead_after: float = 45.0) -> List[str]:
        now = time.time()
        gone: List[str] = []
        for sid,last in list(self.peer_last_seen.items()):
            if now - last > dead_after:
                gone.append(sid)
                self.peer_last_seen.pop(sid, None)
                self.peers.pop(sid, None)
        return gone
