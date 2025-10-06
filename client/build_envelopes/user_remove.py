'''
    Group: Group 2
    Members:
        - William Lehmann (A1889855)
        - Edward Chipperfield (A1889447)
        - G A Sadman (A1899867)
        - Aditeya Sahu (A1943902)
        
    Description:
        - This module builds USER_REMOVE messages for removing a user from the system.
'''

from client.helpers.small_utils import now_ts, b64u, base64url_encode, stabilise_json, chunk_plaintext, signed_transport_sig, content_sig_dm, rsa_sign_pss, sha256_bytes


def build_user_remove(user_id: str, privkey_pem: bytes) -> dict:
    payload = {
        "user_id": user_id,
        "location": "local"
    }

    payload_bytes = stabilise_json(payload)
    sig = rsa_sign_pss(privkey_pem, payload_bytes)
    sig_b64 = base64url_encode(sig)

    return {
        "type": "USER_REMOVE",
        "from": user_id,
        "to": "",
        "ts": now_ts(),
        "payload": payload,
        "sig": sig_b64,
        "alg": "PS256",
    }