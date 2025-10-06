'''
    Group: Group 2
    Members:
        - William Lehmann (A1889855)
        - Edward Chipperfield (A1889447)
        - G A Sadman (A1899867)
        - Aditeya Sahu (A1943902)
        
    Description:
        - This module handles SERVER_HELLO_JOIN messages from peer servers,
          registering new peer connections and sharing known user advertisements.
'''

from backend.server.peer_comm_utilities import send_to_all_peers, make_seen_key, remember_seen, send_error, now_ts
import json, time
from backend.crypto.content_sig import sign_server_frame, verify_server_frame

async def handle_SERVER_HELLO_JOIN(ctx, ws, frame):
    peer_id = frame["from"]
    if peer_id in ctx.peers:
        old_ws = ctx.peers[peer_id]
        if old_ws != ws:
            # Tie-break: keep connection from lower server_id
            if ctx.server_id < peer_id:
                await ws.close(code=1000, reason="tie-break: keep outgoing")
                return
            else:
                await old_ws.close(code=1000, reason="tie-break: keep incoming")
    ctx.peers[peer_id] = ws

    print(f"[SERVER_HELLO_JOIN] Registered peer {peer_id}. Peers now: {list(ctx.peers.keys())}")
    pay = frame.get("payload", {})
    host, port = pay.get("host"), pay.get("port")
    if not (peer_id and host and port):
        return await send_error(ws, "UNKNOWN_TYPE", "bad join payload")
    ctx.server_addrs[peer_id] = (host, int(port))
    ctx.peer_last_seen[peer_id] = time.time()

    # Send all known USER_ADVERTISEs to the new peer
    for user_id, env in ctx.user_advertise_envelopes.items():
        await ws.send(json.dumps(env))

    # Announce yourself to all peers (including the new one)
    payload = {"host": ctx.host, "port": ctx.port}
    sig_b64 = sign_server_frame(ctx, payload)
    announce = {
        "type": "SERVER_ANNOUNCE",
        "from": ctx.server_id,
        "to": "*",
        "ts": now_ts(),
        "payload": payload,
        "sig": sig_b64,
        "alg": "PS256"
    }
    for peer_sid, peer_ws in ctx.peers.items():
        try:
            await peer_ws.send(json.dumps(announce))
        except Exception:
            pass