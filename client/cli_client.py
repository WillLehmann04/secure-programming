import asyncio
import json
import os
import sys
import hashlib
import time
import uuid
from pathlib import Path
from typing import Tuple, List
import websockets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # for public-channel symmetric


## TEMP
from .helpers.small_utils import now_ts, b64u, base64url_encode, stabilise_json, chunk_plaintext, signed_transport_sig, content_sig_dm, rsa_sign_pss, sha256_bytes, dm_seen_key, aesgcm_encrypt, load_client_keys_from_config
from backend.crypto import (
    rsa_sign_pss,
    base64url_encode,
    base64url_decode,
    stabilise_json,
    oaep_encrypt_large,
)

from backend.crypto.rsa_oaep import oaep_encrypt, oaep_decrypt
from backend.identifiers.tables import InMemoryTables
from backend.crypto.rsa_key_management import generate_rsa_keypair, load_private_key, load_public_key

from .commands.tell import cmd_tell
from .commands.list import cmd_list
from .commands.all import cmd_all
from .commands.file import cmd_file


from .build_envelopes.user_hello import build_user_hello
from .build_envelopes.user_advertise import build_user_advertise_envelope
from .build_envelopes.user_remove import build_user_remove

"""
Return (user_id, privkey_pem_bytes, pubkey_pem_str)
cfg of the JSON: { "user_id": "...", "privkey_pem_b64": "...", "pubkey_pem": "..." }
"""


#config
WS_URL = os.environ.get("SOCP_WS", "ws://localhost:8765")
DEFAULT_CFG_PATH = os.path.join(os.path.dirname(__file__), "client.json")

#client side state
_pending: dict[str, asyncio.Future] = {}   # req_id
_group_key_cache: dict[str, bytes] = {}    # user_id

# Envelope builders

from backend.crypto.rsa_key_management import generate_rsa_keypair
from backend.crypto.base64url import base64url_encode


''' TODO: FIX THSESE  '''
async def listener(ws, privkey_pem, tables):
    async for msg in ws:
        try:
            obj = json.loads(msg)
        except Exception:
            #print("[IN] raw:", msg)
            continue

        if obj.get("type") == "USER_DELIVER":
            payload = obj.get("payload", {})
            key = dm_seen_key(payload)
            if tables.seen_ids.contains(key):
                print(f"[DM from {payload.get('from')}] <duplicate/replay detected, dropped>")
                continue
            tables.seen_ids.add(key)
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
            sender = obj.get("from")
            channel = obj.get("to")
            ts = obj.get("ts")
            text = payload.get("text", "")
            print(f"[#{channel}] {sender} @ {ts}: {text}")
            continue

        # Cache public keys from USER_ADVERTISE
        if obj.get("type") == "USER_ADVERTISE":
            payload = obj.get("payload", {})
            user_id = payload.get("user_id")
            pubkey_pem = payload.get("pubkey")
            if user_id and pubkey_pem:
                tables.user_pubkeys[user_id] = pubkey_pem.encode("utf-8")

        rid = obj.get("req_id")
        if rid and rid in _pending:
            _pending.pop(rid).set_result(obj)
            continue

        print("[IN]", json.dumps(obj, indent=2))




async def rpc(ws, typ: str, payload: dict, timeout: float = 5.0) -> dict:
    rid = uuid.uuid4().hex
    fut = asyncio.get_event_loop().create_future()
    _pending[rid] = fut
    await ws.send(json.dumps({"req_id": rid, "type": typ, "payload": payload}))
    try:
        return await asyncio.wait_for(fut, timeout)
    finally:
        _pending.pop(rid, None)

async def get_public_group_key_for_client(ws, me: str, privkey_pem: bytes) -> bytes:
    if me in _group_key_cache:
        return _group_key_cache[me]
    resp = await rpc(ws, "DIR_GET_WRAPPED_PUBLIC_KEY", {"user_id": me})
    if resp.get("type") == "ERROR":
        raise RuntimeError(f"DIR_GET_WRAPPED_PUBLIC_KEY failed: {resp['payload']}")
    wrapped_b64 = resp["payload"]["wrapped_key"]
    clear = oaep_decrypt(privkey_pem, base64url_decode(wrapped_b64))
    _group_key_cache[me] = clear  # 32-byte key; RAM only
    return clear

# MAIN LOOP
async def main_loop(cfg_path: str):
    # Load all required fields from config
    cfg = json.loads(Path(cfg_path).read_text(encoding="utf-8"))
    user_id = cfg["user_id"]
    privkey_pem = base64url_decode(cfg["privkey_pem_b64"])
    pubkey_pem = cfg["pubkey_pem"]
    server_id = cfg["server_id"]
    privkey_store = cfg.get("privkey_store", "")
    pake_password = cfg.get("pake_password", "")
    meta = cfg.get("meta", {"display_name": user_id})
    version = cfg.get("version", "1.0")

    async with websockets.connect(WS_URL) as ws:
        # send USER_HELLO once
        envelope = build_user_hello(server_id, user_id, pubkey_pem, privkey_pem)
        await ws.send(json.dumps(envelope))
        print("sent USER_HELLO; awaiting server responses...")

        # send SOCP-compliant USER_ADVERTISE
        envelope = build_user_advertise_envelope(
            user_id, pubkey_pem, privkey_store, pake_password, meta, version, privkey_pem
        )
        await ws.send(json.dumps(envelope))
        print("sent USER_ADVERTISE")

        # background listener
        tables = InMemoryTables()
        listener_task = asyncio.create_task(listener(ws, privkey_pem, tables))

        print("Enter commands: /list, /tell <user> <text>, /all <text>, /file <user|public> <path>")
        while True:
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            if line == "/list":
                await cmd_list(ws, user_id, server_id)
            elif line.startswith("/tell "):
                parts = line.split(" ", 2)
                if len(parts) < 3:
                    print("usage: /tell <user> <text>")
                    continue
                to, text = parts[1], parts[2]
                await cmd_tell(ws, user_id, privkey_pem, to, text, tables)
            elif line.startswith("/all "):
                text = line[len("/all "):]
                await cmd_all(ws, user_id, privkey_pem, text)
            elif line.startswith("/file "):
                parts = line.split(" ", 2)
                if len(parts) < 3:
                    print("usage: /file <user|public> <path>"); continue
                target, path = parts[1], parts[2]
                await cmd_file(ws, user_id, privkey_pem, target, path, tables=tables, pubkey_pem=pubkey_pem)
            elif line == "/quit":
                env = build_user_remove(user_id, privkey_pem)
                await ws.send(json.dumps(env))
                await ws.close()
                break
            else:
                print("unknown command", line)

        listener_task.cancel()
        await ws.close()

def ensure_client_config(cfg_path: str):
    if os.path.exists(cfg_path):
        return
    user_id = str(uuid.uuid4())
    privkey_pem, pubkey_pem = generate_rsa_keypair()
    config = {
        "user_id": user_id,
        "pubkey_pem": pubkey_pem.decode("utf-8"),
        "privkey_pem_b64": base64url_encode(privkey_pem),
        "server_id": "",
    }
    Path(cfg_path).parent.mkdir(parents=True, exist_ok=True)
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print(f"Generated new client config at {cfg_path}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cfg_path = sys.argv[1]
    else:
        cfg_path = DEFAULT_CFG_PATH
    ensure_client_config(cfg_path)
    asyncio.run(main_loop(cfg_path))