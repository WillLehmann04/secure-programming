import asyncio
import json
import uuid
from backend.crypto import base64url_decode
from backend.crypto.rsa_oaep import oaep_decrypt
from backend.identifiers.tables import InMemoryTables
from .utils import dm_seen_key


class Transport:
    def __init__(self, ws):
        self.ws = ws
        self._pending: dict[str, asyncio.Future] = {}
        self.tables = InMemoryTables()

    async def rpc(self, typ: str, payload: dict, timeout: float = 5.0) -> dict:
        rid = uuid.uuid4().hex
        fut = asyncio.get_event_loop().create_future()
        self._pending[rid] = fut
        await self.ws.send(json.dumps({"req_id": rid, "type": typ, "payload": payload}))
        try:
            return await asyncio.wait_for(fut, timeout)
        finally:
            self._pending.pop(rid, None)

    async def listener(self, privkey_pem: bytes):
        async for msg in self.ws:
            try:
                obj = json.loads(msg)
            except Exception:
                print("[IN] raw:", msg)
                continue

            if obj.get("type") == "USER_DELIVER":
                payload = obj.get("payload", {})
                key = dm_seen_key(payload)
                if self.tables.seen_ids.contains(key):
                    print(f"[DM from {payload.get('from')}] <duplicate/replay detected, dropped>")
                    continue
                self.tables.seen_ids.add(key)
                ciphertext_b64 = payload.get("ciphertext")
                sender = payload.get("from")
                ts = payload.get("ts")
                if ciphertext_b64:
                    try:
                        plaintext = oaep_decrypt(privkey_pem, base64url_decode(ciphertext_b64))
                        print(f"[DM from {sender} @ {ts}] {plaintext.decode('utf-8', errors='replace')}")
                    except Exception as e:
                        print(f"[DM from {sender} @ {ts}] <decryption failed: {e}>")
                continue

            if obj.get("type") == "MSG_PUBLIC_CHANNEL":
                payload = obj.get("payload", {})
                sender = payload.get("from")
                channel = payload.get("to")
                ts = payload.get("ts")
                text = payload.get("ciphertext")
                print(f"[#{channel}] {sender} @ {ts}: {text}")
                continue

            if obj.get("type") == "USER_ADVERTISE":
                payload = obj.get("payload", {})
                user_id = payload.get("user_id")
                pubkey_pem = payload.get("pubkey")
                if user_id and pubkey_pem:
                    self.tables.user_pubkeys[user_id] = pubkey_pem.encode("utf-8")
                continue

            rid = obj.get("req_id")
            if rid and rid in self._pending:
                self._pending.pop(rid).set_result(obj)
                continue

            print("[IN ]", json.dumps(obj, indent=2))
