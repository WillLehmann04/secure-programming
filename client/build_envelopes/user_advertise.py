'''
    Group: Group 2
    Members:
        - William Lehmann (A1889855)
        - Edward Chipperfield (A1889447)
        - G A Sadman (A1899867)
        - Aditeya Sahu (A1943902)
        
    Description:
        - This module builds USER_ADVERTISE messages for advertising user information.
'''

from client.helpers.small_utils import now_ts, b64u, base64url_encode, stabilise_json, chunk_plaintext, signed_transport_sig, content_sig_dm, rsa_sign_pss, sha256_bytes


def build_user_advertise_envelope(
    user_id: str,
    pubkey: str,
    privkey_store: str,
    pake_password: str,
    meta: dict,
    version: str,
    privkey_pem: bytes,
    to: str = "*",
    ts: int = None
):
    payload = {
        "user_id": user_id,
        "pubkey": pubkey,
        "privkey_store": privkey_store,
        "pake_password": pake_password,
        "meta": meta,
        "version": version,
    }

    payload_bytes = stabilise_json(payload)
    sig = rsa_sign_pss(privkey_pem, payload_bytes)
    sig_b64 = base64url_encode(sig)

    return {
        "type": "USER_ADVERTISE",
        "from": user_id,
        "to": to,
        "ts": now_ts(),
        "payload": payload,
        "sig": sig_b64,
        "alg": "PS256",
    }
