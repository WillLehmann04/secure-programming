'''
    Group: Group 2
    Members:
        - William Lehmann (A1889855)
        - Edward Chipperfield (A1889447)
        - G A Sadman (A1899867)
        - Aditeya Sahu (A1943902)
        
    Description:
        - This module builds USER_HELLO messages for client-server communication.
'''

from client.helpers.small_utils import now_ts, b64u, base64url_encode, stabilise_json, chunk_plaintext, signed_transport_sig, content_sig_dm, rsa_sign_pss, sha256_bytes

''' USER_HELLO '''
def build_user_hello(server_id: str, user_id: str, pubkey_pem: str, privatekey_pem: bytes) -> dict:
    payload = {
        "client": "cli-v1",
        "pubkey": pubkey_pem,
        "enc_pubkey": pubkey_pem,
    }
    return {
        "type": "USER_HELLO",
        "from": user_id,
        "to": server_id,
        "ts": now_ts(),
        "payload": payload,
        "sig": signed_transport_sig(payload, privatekey_pem),
        "alg": "PS256",  # <-- REQUIRED BY SOCP
    }