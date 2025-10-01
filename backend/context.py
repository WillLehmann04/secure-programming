# backend/context.py
from __future__ import annotations
from collections import deque

class Ctx:
    def __init__(self, server_id: str, host: str = "0.0.0.0", port: int = 8765):
        self.server_id = server_id
        self.host = host
        self.port = port

        # server<->server mesh
        self.peers = {}              # sid -> websocket
        self.server_addrs = {}       # sid -> (host, port)
        self.peer_last_seen = {}     # sid -> last heartbeat time (float)

        # users connected to *this* server
        self.local_users = {}        # user_id -> websocket
        self.user_locations = {}     # user_id -> "local" | server_id

        # dedupe memory (bounded by run_mesh wiring)
        self.seen_ids = set()        # keys from make_seen_key(frame)
        self.seen_queue = deque()    # for bounded LRU if you later enable it

        # will be set by the runner
        self.router = None           # backend.routing.Router
