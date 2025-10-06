'''
    Group: Group 2
    Members:
        - William Lehmann (A1889855)
        - Edward Chipperfield (A1889447)
        - G A Sadman (A1899867)
        - Aditeya Sahu (A1943902)
        
    Description:
        - This module handles SERVER_WELCOME messages from peer servers,
          registering the peer server and storing its public key.
'''

from backend.crypto import rsa_verify_pss, base64url_decode, stabilise_json, load_public_key
from backend.server.peer_comm_utilities import send_error
from backend.crypto.content_sig import sign_server_frame, verify_server_frame

async def handle_SERVER_WELCOME(ctx, ws, frame):
    peer_id = frame.get("from")
    peer_pubkey_pem = frame["payload"].get("pubkey")
    if peer_pubkey_pem:
        ctx.peer_pubkeys[peer_id] = load_public_key(peer_pubkey_pem)
    peer_pubkey = ctx.peer_pubkeys.get(peer_id)
    if not peer_pubkey or not verify_server_frame(peer_pubkey, frame["payload"], frame["sig"]):
        await send_error(ws, "INVALID_SIG", "bad server signature")
        return

    ctx.peers[peer_id] = ws
    print(f"[SERVER_WELCOME] Registered peer {peer_id}. Peers now: {list(ctx.peers.keys())}")
    