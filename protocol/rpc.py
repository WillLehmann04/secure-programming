from __future__ import annotations
import uuid
from typing import Dict, Any
from .types import *

def new_req_id() -> str:
    return uuid.uuid4().hex

# client side builders
def req_dir_get_pubkey(user_id: str) -> Dict[str, Any]:
    rid = new_req_id()
    return {"req_id": rid, "type": DIR_GET_PUBKEY, "payload": {"user_id": user_id}}

def req_dir_get_wrapped_public_key(user_id: str) -> Dict[str, Any]:
    rid = new_req_id()
    return {"req_id": rid, "type": DIR_GET_WRAPPED_PUBLIC_KEY, "payload": {"user_id": user_id}}

# server side resp builders
def resp_dir_pubkey(req_id: str, user_id: str, pubkey_pem: str) -> Dict[str, Any]:
    return {"req_id": req_id, "type": DIR_PUBKEY, "payload": {"user_id": user_id, "pubkey": pubkey_pem}}

def resp_dir_wrapped_public_key(req_id: str, user_id: str, wrapped_b64u: str) -> Dict[str, Any]:
    return {"req_id": req_id, "type": DIR_WRAPPED_PUBLIC_KEY,
            "payload": {"group": "public", "user_id": user_id, "wrapped_key": wrapped_b64u}}

def resp_error(req_id: str, code: str, message: str) -> Dict[str, Any]:
    return {"req_id": req_id, "type": ERROR, "payload": {"code": code, "message": message}}


# def validate_msg_shape(obj: Dict[str, Any]) -> bool:
    if not isinstance(obj, dict): return False
    if "type" not in obj: return False
    if obj["type"] in (DIR_GET_PUBKEY, DIR_GET_WRAPPED_PUBLIC_KEY, DIR_PUBKEY, DIR_WRAPPED_PUBLIC_KEY, ERROR):
        return True
    return False
