'''
    Group: Group 2
    Members:
        - William Lehmann (A1889855)
        - Edward Chipperfield (A1889447)
        - G A Sadman (A1899867)
        - Aditeya Sahu (A1943902)
        
    Description:
        - This module builds FILE_CHUNK messages for sending file chunks between clients and servers.
'''

from client.helpers.small_utils import now_ts, b64u, base64url_encode, stabilise_json, chunk_plaintext, signed_transport_sig, content_sig_dm, rsa_sign_pss, sha256_bytes
import hashlib
from backend.crypto import base64url_decode

def build_file_chunk(file_id, index, ciphertext_b64u, frm, to, ts, privkey_pem=None):
    to_str = to if to is not None else ""
    ciphertext_bytes = base64url_decode(ciphertext_b64u)

    d = hashlib.sha256(ciphertext_bytes + frm.encode() + to_str.encode() + str(ts).encode()).digest()
    content_sig = b64u(rsa_sign_pss(privkey_pem, d)) if privkey_pem else ""

    payload = {
        "file_id": file_id,
        "index": index,
        "ciphertext": ciphertext_b64u,
        "content_sig": content_sig,
    }
    env = {
        "type": "FILE_CHUNK",
        "from": frm,
        "to": to_str,
        "ts": ts,
        "payload": payload,
    }
    # Envelope signature: sign canonical JSON of payload
    if privkey_pem:
        payload_bytes_for_env_sig = stabilise_json(payload)
        sig = rsa_sign_pss(privkey_pem, payload_bytes_for_env_sig)
        env["sig"] = b64u(sig)
    else:
        env["sig"] = ""
    return env