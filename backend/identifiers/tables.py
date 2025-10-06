# A reminder of the spec from the recent document in discord
"""
    Spec-mandated in-memory tables:

    servers        : Map<ServerID, Link>           # active WS links to other servers
    server_addrs   : Map<ServerID, (host, port)>   # known addresses for reconnection
    local_users    : Map<UserID, Link>             # active WS links to clients
    user_locations : Map<UserID, "local" | ServerID>  # where a user currently lives
    seen_ids       : LRUSet<HashKey>               # replay/loop suppression
"""

'''
    Created: 23/09/2025 @ 6:44pm
    UUIDv4 Identifiers implementation

    Tested: as of 23/09/2025 @ XX:XXpm
        - Tested return types
        - Checked valid V4 UUID
        - Tested Uniqueness
'''

# ========== Imports ========== 
from .lru import LRU
from dataclasses import dataclass

ServerID = str
UserID = str

@dataclass
class Link:
    peer_id: str 
    send: callable 
    closed: bool = False 

    def close(self):
        self.closed = True

# ========== InMemory Class ========== 
class InMemoryTables:
    def __init__(self):
        self.servers: dict[ServerID, Link] = {}
        self.server_addresses: dict[ServerID, tuple[str, int]] = {}
        self.local_users: dict[UserID, Link] = {}
        self.user_locations: dict[UserID, f"local" | ServerID] = {}
        self.seen_ids: LRU = LRU(capacity=1000)
        self.user_pubkeys: dict[str, bytes] = {}
        self.group_members: dict[str, set[str]] = {}  # group_id -> set of user_ids
        self.group_keys: dict[str, bytes] = {}

    def attach_server(self, sid: ServerID, link: Link) -> None:
        self.servers[sid] = link

    def detach_server(self, sid: ServerID) -> None:
        self.servers.pop(sid, None)

    def attach_user_local(self, uid: UserID, link: Link) -> None:
        self.local_users[uid] = link
        self.user_locations[uid] = "local"

    def move_user_to_server(self, uid: UserID, sid: ServerID) -> None:
        # If a user migrates (or is known to be on another server), update location.
        self.local_users.pop(uid, None)
        self.user_locations[uid] = sid

    def remove_user(self, uid: UserID) -> None:
        # Cleanup when a client disconnects and you no longer know their location.
        self.local_users.pop(uid, None)
        self.user_locations.pop(uid, None)

