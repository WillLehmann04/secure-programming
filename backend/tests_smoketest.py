# backend/tests_smoketest.py
from __future__ import annotations
import asyncio, json, os, uuid

import websockets

URI = os.environ.get("SOCP_URI", "ws://127.0.0.1:8765")

async def user_client(user_id: str, name: str):
    ws = await websockets.connect(URI)
    # USER_HELLO (first frame must use UUIDv4 in "from")
    await ws.send(json.dumps({
        "type": "USER_HELLO",
        "from": user_id,
        "to":   "",
        "ts":   0,
        "payload": {}
    }))
    # Expect ACK
    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
    assert msg.get("type") == "ACK", f"{name} did not receive ACK: {msg}"
    print(f"[{name}] HELLO -> ACK OK")

    return ws

async def run_smoke_test():
    print("Starting smoke test against", URI)

    # two UUIDv4 user IDs
    alice_id = str(uuid.uuid4())
    bob_id   = str(uuid.uuid4())

    alice = await user_client(alice_id, "alice")
    bob   = await user_client(bob_id,   "bob")

    # Alice sends a direct message to Bob (server should route)
    dm = {
        "type": "MSG_DIRECT",
        "from": alice_id,
        "to":   bob_id,
        "ts":   1,
        "payload": {"ct": "hello-bob"}   # treated as opaque by server
    }
    await alice.send(json.dumps(dm))
    print("[alice] -> MSG_DIRECT sent")

    # Bob should receive USER_DELIVER with the payload
    deliver = json.loads(await asyncio.wait_for(bob.recv(), timeout=3))
    assert deliver["type"] == "USER_DELIVER", deliver
    assert deliver["to"] == bob_id
    assert deliver["payload"] == dm["payload"]
    print("[bob] <- USER_DELIVER OK")

    # Public broadcast from Bob (Alice should get it)
    pub = {
        "type": "MSG_PUBLIC_CHANNEL",
        "from": bob_id,
        "to":   "*",
        "ts":   2,
        "payload": {"msg": "hi-all"}
    }
    await bob.send(json.dumps(pub))
    got = json.loads(await asyncio.wait_for(alice.recv(), timeout=3))
    assert got["type"] == "MSG_PUBLIC_CHANNEL", got
    assert got["payload"] == pub["payload"]
    print("[alice] <- MSG_PUBLIC_CHANNEL OK")

    await alice.close(); await bob.close()
    print("Smoke test PASSED")

if __name__ == "__main__":
    asyncio.run(run_smoke_test())
