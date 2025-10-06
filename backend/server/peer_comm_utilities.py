'''
    Group: Group 2
    Members:
        - William Lehmann (A1889855)
        - Edward Chipperfield (A1889447)
        - G A Sadman (A1899867)
        - Aditeya Sahu (A1943902)
        
    Description:
        - This module provides utility functions for peer server communication,
          including sending messages to all peers, generating deduplication keys,
          and managing user sessions.
'''

import json
from backend.crypto.json_format import stabilise_json
import hashlib
import time

# ---------- Peer Communication Utilities ----------
async def send_to_all_peers(ctx, frame, exclude_ws=None):
    ''' Send the frame call to all peer servers'''
    for sid, peer_ws in ctx.peers.items():
        if exclude_ws is not None and peer_ws is exclude_ws:
            continue
        await peer_ws.send(json.dumps(frame))

def make_seen_key(frame: dict) -> str:
    ''' Generate a deduplication key for a frame '''
    ts = str(frame.get("ts", 0))
    sender  = frame.get("from", "")
    recipient  = frame.get("to", "")
    payload_bytes = stabilise_json(frame.get("payload", {}))
    hash = hashlib.sha256(payload_bytes).hexdigest()
    return f"{ts}|{sender}|{recipient}|{hash}"

def remember_seen(ctx, key: str) -> bool:
    if key in ctx.seen_ids: return True
    ctx.seen_ids.add(key)
    ctx.seen_queue.append(key)  # bounded by maxlen
    return False

async def send_error(ws, code: str, detail: str = ""):
    try:
        await ws.send(json.dumps({"type":"ERROR","payload":{"code":code,"detail":detail}}))
    except Exception:
        pass  # Ignore errors if the websocket is already closed


def now_ts() -> str:
    return int(time.time() * 1000)