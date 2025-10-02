from __future__ import annotations
from typing import Dict, Any
from protocol.rpc import resp_dir_pubkey, resp_dir_wrapped_public_key, resp_error
from protocol.types import ERR_USER_NOT_FOUND, ERR_NO_WRAPPED_KEY
from persistence.dir_json import get_pubkey, get_wrapped_key

def handle_dir_get_pubkey(req_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    user_id = (payload or {}).get("user_id", "")
    if not user_id:
        return resp_error(req_id, ERR_USER_NOT_FOUND, "missing user_id")
    pub = get_pubkey(user_id)
    if not pub:
        return resp_error(req_id, ERR_USER_NOT_FOUND, user_id)
    return resp_dir_pubkey(req_id, user_id, pub)

def handle_dir_get_wrapped_public_key(req_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    user_id = (payload or {}).get("user_id", "")
    if not user_id:
        return resp_error(req_id, ERR_NO_WRAPPED_KEY, "missing user_id")
    wrapped = get_wrapped_key("public", user_id)
    if not wrapped:
        return resp_error(req_id, ERR_NO_WRAPPED_KEY, f"{user_id} has no wrapped key")
    return resp_dir_wrapped_public_key(req_id, user_id, wrapped)
