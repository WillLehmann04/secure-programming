'''
    Group: Group 2
    Members:
        - William Lehmann (A1889855)
        - Edward Chipperfield (A1889447)
        - G A Sadman (A1899867)
        - Aditeya Sahu (A1943902)
        
    Description:
        - This module builds FILE_END messages for sending file transfer completion notifications between clients and servers.
'''

from client.helpers.small_utils import b64u, stabilise_json, rsa_sign_pss
import hashlib
def build_file_end(file_id, frm, to, ts, privkey_pem=None):
    to_str = to if to is not None else ""
    payload = {
        "file_id": file_id
    }
    # Content signature: hash b"" + frm + to + ts
    d = hashlib.sha256(b"" + frm.encode() + to_str.encode() + str(ts).encode()).digest()
    content_sig = b64u(rsa_sign_pss(privkey_pem, d)) if privkey_pem else ""
    payload["content_sig"] = content_sig

    env = {
        "type": "FILE_END",
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