'''
    Group: Group 2
    Members:
        - William Lehmann (A1889855)
        - Edward Chipperfield (A1889447)
        - G A Sadman (A1899867)
        - Aditeya Sahu (A1943902)
        
    Description:
        - This module handles SERVER_ANNOUNCE messages from peer servers,
          updating the server address list and last seen timestamps.
'''

import json
from backend.server.peer_comm_utilities import send_error
from backend.crypto.content_sig import sign_server_frame, verify_server_frame
import time

async def handle_SERVER_ANNOUNCE(ctx, ws, frame):
    peer_id = frame.get("from")
    peer_pubkey = ctx.peer_pubkeys.get(peer_id)
    if not peer_pubkey or not verify_server_frame(peer_pubkey, frame["payload"], frame["sig"]):
        await send_error(ws, "INVALID_SIG", "bad server signature")
        return

    sid = frame.get("from"); pay = frame.get("payload",{})
    host, port = pay.get("host"), pay.get("port")
    if sid and host and port:
        ctx.server_addrs[sid] = (host, int(port))
        ctx.peer_last_seen[sid] = time.time()
