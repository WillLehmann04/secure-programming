'''
    Group: Group 2
    Members:
        - William Lehmann (A1889855)
        - Edward Chipperfield (A1889447)
        - G A Sadman (A1899867)
        - Aditeya Sahu (A1943902)
        
    Description:
        - This module defines the Context class, which maintains the server's state,
          including connected peers, user sessions, public keys, and message deduplication.
'''

import json
from collections import deque

class Context:
    def __init__(self, server_id: str, host: str, port: int, server_public_key_pem: bytes = None, server_private_key = None):
        self.server_id = server_id
        self.host = host
        self.port = port
        self.server_public_key_pem = server_public_key_pem
        self.server_private_key = server_private_key

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
