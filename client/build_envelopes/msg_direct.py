'''
    Group: Group 2
    Members:
        - William Lehmann (A1889855)
        - Edward Chipperfield (A1889447)
        - G A Sadman (A1899867)
        - Aditeya Sahu (A1943902)
        
    Description:
        - This module builds MSG_DIRECT messages for sending direct messages between clients.
'''

from backend.crypto import rsa_sign_pss, base64url_encode, stabilise_json

''' MSG_DIRECT '''
def build_msg_direct(ciphertext, sender_user_id, recipient_user_id, ts, content_sig, privkey_pem):
    payload = {
        "ciphertext": ciphertext,
        "from": sender_user_id,
        "to": recipient_user_id,
        "ts": ts,
        "content_sig": content_sig,
    }
    payload_bytes = stabilise_json(payload)
    sig = rsa_sign_pss(privkey_pem, payload_bytes)
    sig_b64 = base64url_encode(sig)
    return {
        "type": "MSG_DIRECT",
        "from": sender_user_id,
        "to": recipient_user_id,
        "ts": ts,
        "payload": payload,
        "sig": sig_b64,
        "alg": "PS256",
    }
