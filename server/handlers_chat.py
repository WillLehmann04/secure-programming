from __future__ import annotations
from typing import Dict, Any
from persistence.dir_json import user_exists, list_group_members
from persistence.membership import join_public_group
from protocol.types import ERR_USER_NOT_FOUND, ERR_NAME_IN_USE, ERR_UNKNOWN_TYPE
from protocol.rpc import resp_error
from server.session import attach, forward_to, fanout_public, online_users, SESSIONS
from server.verify import verify_transport_sig, verify_content_sig


def _is_public_member(uid: str) -> bool:
    try:
        return uid in set(list_group_members("public"))
    except Exception:
        return False


async def handle_chat(type_: str, obj: Dict[str, Any], ws):
    p = obj.get("payload", {}) or {}
    req_id = obj.get("req_id", "")

    # auto-join public
    if type_ == "USER_HELLO":
        uid = p.get("user_id")
        if not isinstance(uid, str) or not uid:
            return {"type": "ERROR", "payload": {"code": ERR_USER_NOT_FOUND, "message": "missing user_id"}}
        if not user_exists(uid):
            return {"type": "ERROR", "payload": {"code": ERR_USER_NOT_FOUND, "message": uid}}
        if uid in SESSIONS:
            return {"type": "ERROR", "payload": {"code": ERR_NAME_IN_USE, "message": uid}}

        # Ensure membership in public - rotates key only if first time joining
        public_version = None
        if not _is_public_member(uid):
            public_version = join_public_group(uid)

        attach(uid, ws)
        ack = {"user_id": uid}
        if public_version is not None:
            ack["public_version"] = public_version
        return {"type": "USER_HELLO_ACK", "payload": ack}

    # /list
    if type_ == "CMD_LIST":
        return {"type": "USER_LIST", "payload": {"users": online_users()}}

    # direct message
    if type_ == "MSG_DIRECT":
        sender = p.get("from", "")
        if not (verify_transport_sig(sender, p, obj.get("transport_sig"))
                and verify_content_sig("MSG_DIRECT", p, sender)):
            return {"type": "ERROR", "payload": {"code": "INVALID_SIG", "message": "drop"}}
        to = p.get("to", "")
        if not await forward_to(to, obj):
            return {"type": "ERROR", "payload": {"code": "USER_NOT_ONLINE", "message": to}}
        return None

    # public message
    if type_ == "MSG_PUBLIC_CHANNEL":
        sender = p.get("from", "")
        if not (verify_transport_sig(sender, p, obj.get("transport_sig"))
                and verify_content_sig("MSG_PUBLIC_CHANNEL", p, sender)):
            return {"type": "ERROR", "payload": {"code": "INVALID_SIG", "message": "drop"}}
        if not _is_public_member(sender):
            return {"type": "ERROR", "payload": {"code": "NOT_IN_PUBLIC_GROUP", "message": sender}}
        await fanout_public(sender, obj)
        return None

    # file pass through
    if type_ in ("FILE_START", "FILE_CHUNK", "FILE_END"):
        to = p.get("to")
        sender = p.get("from", "")
        if to:
            if not await forward_to(to, obj):
                return {"type": "ERROR", "payload": {"code": "USER_NOT_ONLINE", "message": to}}
        else:
            if not _is_public_member(sender):
                return {"type": "ERROR", "payload": {"code": "NOT_IN_PUBLIC_GROUP", "message": sender}}
            await fanout_public(sender, obj)
        return None

    return resp_error(req_id, ERR_UNKNOWN_TYPE, str(type_))
