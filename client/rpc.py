from __future__ import annotations
import asyncio, json, uuid

_pending: dict[str, asyncio.Future] = {}

async def listener(ws):
    async for raw in ws:
        try:
            obj = json.loads(raw)
        except Exception:
            print("[IN ] raw:", raw); continue
        rid = obj.get("req_id")
        if rid and rid in _pending:
            _pending.pop(rid).set_result(obj); continue
        print("[IN ]", json.dumps(obj, indent=2))

async def rpc(ws, typ: str, payload: dict, timeout: float = 5.0) -> dict:
    rid = uuid.uuid4().hex
    fut = asyncio.get_event_loop().create_future()
    _pending[rid] = fut
    await ws.send(json.dumps({"req_id": rid, "type": typ, "payload": payload}))
    try:
        return await asyncio.wait_for(fut, timeout)
    finally:
        _pending.pop(rid, None)
