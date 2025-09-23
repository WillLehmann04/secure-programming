from .json_format import stabilise_json
from .rsa_pss import rsa_sign_pss, rsa_verify_pss

def sign_payload(priv, payload_obj) -> bytes:
    return rsa_sign_pss(priv, stabilise_json(payload_obj))

def verify_payload(pub, payload_obj, sig: bytes) -> bool:
    return rsa_verify_pss(pub, stabilise_json(payload_obj), sig)