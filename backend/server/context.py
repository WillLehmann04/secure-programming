# backend/context.py
import json
from collections import deque

class Context:
    def __init__(self, server_id: str, host: str, port: int):
        self.server_id = server_id
        self.host = host
        self.port = port

        # server mesh
        self.peers = {}            # sid -> ws
        self.server_addrs = {}     # sid -> (host, port)
        self.peer_last_seen = {}   # sid -> last heartbeat ts
        self.user_pubkeys = {}
        self.peer_pubkeys = {}
        self.user_advertise_envelopes = {}

        # users
        self.local_users = {}      # uid -> ws
        self.user_locations = {}   # uid -> "local" | sid

        # dedupe (simple bounded set+queue)
        self.seen_ids = set()
        self.seen_queue = deque(maxlen=10000)

        # router will be attached by main.py
        self.router = None

    # --- tiny send helpers used by Router lambdas ---
    async def send_to_local(self, uid: str, frame: dict) -> None:
        ws = self.local_users.get(uid)
        if ws:
            await ws.send(json.dumps(frame, separators=(",", ":"), ensure_ascii=False))

    async def send_to_peer(self, sid: str, frame: dict) -> None:
        ws = self.peers.get(sid)
        if ws:
            await ws.send(json.dumps(frame, separators=(",", ":"), ensure_ascii=False))
