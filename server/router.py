
from __future__ import annotations
import json
from protocol.types import DIR_GET_PUBKEY, DIR_GET_WRAPPED_PUBLIC_KEY, ERR_BAD_JSON
from protocol.rpc import resp_error
from server.handlers_directory import handle_dir_get_pubkey, handle_dir_get_wrapped_public_key
from server.handlers_chat import handle_chat
from server.session import detach

ROUTES = {
    DIR_GET_PUBKEY: handle_dir_get_pubkey,
    DIR_GET_WRAPPED_PUBLIC_KEY: handle_dir_get_wrapped_public_key,
}

async def handle_connection(ws):
    try:
        async for raw in ws:
            try:
                obj = json.loads(raw)
            except Exception:
                await ws.send(json.dumps(resp_error("", ERR_BAD_JSON, "invalid JSON")))
                continue

            t = obj.get("type"); req_id = obj.get("req_id",""); payload = obj.get("payload",{}) or {}

            if t in ROUTES:
                try:
                    resp = ROUTES[t](req_id, payload)
                except Exception:
                    resp = resp_error(req_id, "INTERNAL", "server error")
                await ws.send(json.dumps(resp))
                continue

            resp = await handle_chat(t, obj, ws)
            if resp is not None:
                await ws.send(json.dumps(resp))
    finally:
        detach(ws)
