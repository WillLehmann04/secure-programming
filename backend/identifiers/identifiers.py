'''
    Created: 23/09/2025 @ 12:42pm
    UUIDv4 Identifiers implementation

    Tested: as of 23/09/2025 @ XX:XXpm
        - Tested return types
        - Checked valid V4 UUID
        - Tested Uniqueness
'''

# ========== Imports ========== 
import uuid # to make compliant with UUID4
from dataclasses import dataclass

# ========== Identifiers ========== 
UserID = str
ServerID = str
Link    = any

# ========== Functions ========== 
def new_user_identifer() -> UserID:
    return str(uuid.uuid4()) # Returning UUID 4 to be compliant with SOCP1.3

def new_server_id() -> ServerID:
    return str(uuid.uuid4())

@dataclass
class Link:
    peer_id: str 
    send: callable 
    closed: bool = False 

    def close(self):
        self.closed = True