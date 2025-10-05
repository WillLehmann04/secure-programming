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

from backend.crypto import (
    rsa_sign_pss,
    base64url_encode,
    base64url_decode,
    stabilise_json,
)

from backend.crypto.rsa_oaep import oaep_encrypt, oaep_decrypt
from backend.identifiers.tables import InMemoryTables
from backend.crypto.rsa_key_management import generate_rsa_keypair, load_private_key, load_public_key

"""
Return (user_id, privkey_pem_bytes, pubkey_pem_str)
cfg of the JSON: { "user_id": "...", "privkey_pem_b64": "...", "pubkey_pem": "..." }
"""


#config
WS_URL = os.environ.get("SOCP_WS", "ws://localhost:8765")
OAEP_HASH_BYTES = 32  # SHA-256
RSA_4096_KEY_BYTES = 4096 // 8  # 512
OAEP_MAX_PLAINTEXT = RSA_4096_KEY_BYTES - 2 * OAEP_HASH_BYTES - 2  # 446 bytes
DEFAULT_CFG_PATH = os.path.join(os.path.dirname(__file__), "client.json")

#client side state
_pending: dict[str, asyncio.Future] = {}   # req_id
_group_key_cache: dict[str, bytes] = {}    # user_id

# small utils
def now_ts() -> str:
    return int(time.time() * 1000)

def sha256_bytes(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()

def chunk_plaintext(plain: bytes, max_chunk: int = OAEP_MAX_PLAINTEXT) -> List[bytes]:
    return [plain[i:i+max_chunk] for i in range(0, len(plain), max_chunk)]

def b64u(data: bytes) -> str:
    return base64url_encode(data)

def signed_transport_sig(payload_obj: dict, privkey_pem: bytes) -> str:
    b = stabilise_json(payload_obj)
    sig = rsa_sign_pss(privkey_pem, b)
    return b64u(sig)

def content_sig_dm(ciphertext_bytes: bytes, frm: str, to: str, ts: str, privkey_pem: bytes) -> str:
    d = sha256_bytes(ciphertext_bytes + frm.encode() + to.encode() + ts.encode())
    return b64u(rsa_sign_pss(privkey_pem, d))

def dm_seen_key(payload: dict) -> str:
    s = f"{payload.get('from')}|{payload.get('to')}|{payload.get('ts')}|{payload.get('ciphertext')}"
    return hashlib.sha256(s.encode()).hexdigest()

def content_sig_public(ciphertext_bytes: bytes, frm: str, ts: str, privkey_pem: bytes) -> str:
    d = sha256_bytes(ciphertext_bytes + frm.encode() + ts.encode())
    return b64u(rsa_sign_pss(privkey_pem, d))

# AES-GCM for public channel
def aesgcm_encrypt(key: bytes, plaintext: bytes, aad: bytes = b"") -> tuple[bytes, bytes]:
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext, aad)
    return nonce, ct

# Key management - replace with our actual decrypt
def load_client_keys_from_config(cfg_path: str) -> Tuple[str, bytes, str, str]:
    cfg = json.loads(Path(cfg_path).read_text(encoding="utf-8"))
    user_id = cfg["user_id"]
    priv_pem = base64url_decode(cfg["privkey_pem_b64"])
    pub_pem = cfg["pubkey_pem"]
    server_id = cfg["server_id"]
    return user_id, priv_pem, pub_pem, server_id

# Envelope builders
''' USER_HELLO '''
def build_user_hello(server_id: str, user_id: str, pubkey_pem: str, privatekey_pem: bytes) -> dict:
    payload = {
        "client": "cli-v1",
        "pubkey": pubkey_pem,
        "enc_pubkey": pubkey_pem,
    }
    return {
        "type": "USER_HELLO",
        "from": user_id,
        "to": server_id,
        "ts": now_ts(),
        "payload": payload,
        "sig": signed_transport_sig(payload, privatekey_pem),
        "alg": "PS256",  # <-- REQUIRED BY SOCP
    }

def build_user_advertise_envelope(
    user_id: str,
    pubkey: str,
    privkey_store: str,
    pake_password: str,
    meta: dict,
    version: str,
    privkey_pem: bytes,
    to: str = "*",
    ts: int = None
):
    """
    Build a SOCP-compliant USER_ADVERTISE envelope.
    """
    if ts is None:
        ts = int(time.time() * 1000)
    payload = {
        "user_id": user_id,
        "pubkey": pubkey,
        "privkey_store": privkey_store,
        "pake_password": pake_password,
        "meta": meta,
        "version": version,
    }
    # You may need to import stabilise_json, rsa_sign_pss, base64url_encode
    payload_bytes = stabilise_json(payload)
    sig = rsa_sign_pss(privkey_pem, payload_bytes)
    sig_b64 = base64url_encode(sig)
    return {
        "type": "USER_ADVERTISE",
        "from": user_id,
        "to": to,
        "ts": ts,
        "payload": payload,
        "sig": sig_b64,
        "alg": "PS256",
    }

def build_user_remove(user_id: str, privkey_pem: bytes) -> dict:
    payload = {
        "user_id": user_id,
        "location": "local"
    }
    payload_bytes = stabilise_json(payload)
    sig = rsa_sign_pss(privkey_pem, payload_bytes)
    sig_b64 = base64url_encode(sig)
    return {
        "type": "USER_REMOVE",
        "from": user_id,
        "to": "",
        "ts": int(time.time() * 1000),
        "payload": payload,
        "sig": sig_b64,
        "alg": "PS256",
    }

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

async def cmd_channel(ws, user_id: str, privkey_pem: bytes, channel_id: str, text: str):#was made before we got rid of the channel option
    ts = now_ts()
    payload = {
        "ciphertext": text,  # plaintext for public channels
        "from": user_id,
        "to": channel_id,
        "ts": ts,
    }
    payload_bytes = stabilise_json(payload)
    sig = rsa_sign_pss(privkey_pem, payload_bytes)
    sig_b64 = base64url_encode(sig)
    env = {
        "type": "MSG_PUBLIC_CHANNEL",
        "from": user_id,
        "to": channel_id,
        "ts": ts,
        "payload": payload,
        "sig": sig_b64,
        "alg": "PS256",
    }
    await ws.send(json.dumps(env))

''' TODO: FIX THSESE  '''
def build_msg_public(nonce_b64u: str, ct_b64u: str, frm: str, ts: int, content_sig_b64u: str, privkey_pem: bytes, channel_id: str) -> dict:
    payload = {
        "nonce": nonce_b64u,
        "ciphertext": ct_b64u,
        "from": frm,
        "to": channel_id,
        "ts": ts,
        "content_sig": content_sig_b64u,
    }
    payload_bytes = stabilise_json(payload)
    sig = rsa_sign_pss(privkey_pem, payload_bytes)
    sig_b64 = base64url_encode(sig)
    return {
        "type": "MSG_PUBLIC_CHANNEL",
        "from": frm,
        "to": channel_id,
        "ts": ts,
        "payload": payload,
        "sig": sig_b64,
        "alg": "PS256",
    }

def build_file_start(manifest: dict, frm: str, to: str | None, ts: str) -> dict:
    return {"type": "FILE_START", "payload": {"manifest": manifest, "from": frm, "to": to, "ts": ts}}

def build_file_chunk(index: int, chunk_b64u: str, frm: str, to: str | None, ts: str) -> dict:
    return {"type": "FILE_CHUNK", "payload": {"index": index, "chunk": chunk_b64u, "from": frm, "to": to, "ts": ts}}

def build_file_end(manifest_summary: dict, frm: str, to: str | None, ts: str) -> dict:
    return {"type": "FILE_END", "payload": {"summary": manifest_summary, "from": frm, "to": to, "ts": ts}}

async def listener(ws, privkey_pem, tables):
    async for msg in ws:
        try:
            obj = json.loads(msg)
        except Exception:
            print("[IN] raw:", msg)
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
            sender = payload.get("from")
            channel = payload.get("to")
            ts = payload.get("ts")
            text = payload.get("ciphertext")
            print(f"[#{channel}] {sender} @ {ts}: {text}")
            continue

        # Cache public keys from USER_ADVERTISE
        if obj.get("type") == "USER_ADVERTISE":
            payload = obj.get("payload", {})
            user_id = payload.get("user_id")
            print(f"DEBUG: Received USER_ADVERTISE for {user_id}")
            pubkey_pem = payload.get("pubkey")
            if user_id and pubkey_pem:
                tables.user_pubkeys[user_id] = pubkey_pem.encode("utf-8")

        rid = obj.get("req_id")
        if rid and rid in _pending:
            _pending.pop(rid).set_result(obj)
            continue

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

# high level commands
async def cmd_list(ws, user_id: str, server_id: str):
    await ws.send(json.dumps({
        "type": "CMD_LIST",
        "from": user_id,
        "to": server_id, 
        "payload": {},
        "ts": now_ts()
    }))

import traceback

async def cmd_tell(ws, user_id: str, privkey_pem: bytes, to: str, text: str, tables):
    print("DEBUG: Entered cmd_tell")
    try:
        plain = text.encode("utf-8")
        print(f"DEBUG: Encoded plain: {plain!r}")
        recipient_pub = tables.user_pubkeys.get(to)
        if not recipient_pub:
            print(f"ERROR: No public key for user {to}. Try /list and wait for USER_ADVERTISE.")
            return
        ts = now_ts()
        if len(plain) <= OAEP_MAX_PLAINTEXT:
            print(f"DEBUG: Message is short ({len(plain)} bytes), using single envelope")
            ciphertext = oaep_encrypt(recipient_pub, plain)
            print(f"DEBUG: Encrypted ciphertext: {ciphertext[:30]!r}...")
            ciphertext_b64u = b64u(ciphertext)
            content_sig = content_sig_dm(ciphertext, user_id, to, str(ts), privkey_pem)
            env = build_msg_direct(ciphertext_b64u, user_id, to, ts, content_sig, privkey_pem)
            print("DEBUG OUTGOING ENVELOPE:", json.dumps(env, indent=2))
            await ws.send(json.dumps(env))
            print("DEBUG: Envelope sent")
        else:
            print(f"DEBUG: Message is long ({len(plain)} bytes), using chunked envelopes")
            chunks = chunk_plaintext(plain)
            print(f"DEBUG: Split into {len(chunks)} chunks")
            for i, ch in enumerate(chunks):
                print(f"DEBUG: Processing chunk {i}, size {len(ch)}")
                recipient_pub = tables.user_pubkeys.get(to)
                print(f"DEBUG: Got recipient_pub for {to}: {recipient_pub[:30]!r}...")
                chunk_ts = now_ts()
                ciphertext = oaep_encrypt(recipient_pub, ch)
                print(f"DEBUG: Encrypted chunk {i}: {ciphertext[:30]!r}...")
                content_sig = content_sig_dm(ciphertext, user_id, to, str(chunk_ts), privkey_pem)
                print(f"DEBUG: Got content_sig for chunk {i}: {content_sig[:30]!r}...")
                payload = {
                    "ciphertext": b64u(ciphertext),
                    "from": user_id,
                    "to": to,
                    "index": i,
                    "ts": chunk_ts,
                    "content_sig": content_sig,
                }
                payload_bytes = stabilise_json(payload)
                print(f"DEBUG: Stabilised payload for chunk {i}: {payload_bytes[:30]!r}...")
                sig = rsa_sign_pss(privkey_pem, payload_bytes)
                sig_b64 = base64url_encode(sig)
                print(f"DEBUG: Envelope sig for chunk {i}: {sig_b64[:30]!r}...")
                env = {
                    "type": "MSG_DIRECT_CHUNK",
                    "from": user_id,
                    "to": to,
                    "ts": chunk_ts,
                    "payload": payload,
                    "sig": sig_b64,
                    "alg": "PS256",
                }
                print("DEBUG OUTGOING ENVELOPE (chunk):", json.dumps(env, indent=2))
                await ws.send(json.dumps(env))
                print(f"DEBUG: Chunk {i} envelope sent")
    except Exception as e:
        print("ERROR in cmd_tell:", e)
        traceback.print_exc()

async def cmd_all(ws, user_id: str, privkey_pem: bytes, text: str):
    await cmd_channel(ws, user_id, privkey_pem, "all", text)

async def cmd_file(ws, user_id: str, privkey_pem: bytes, target: str, path_or_bytes, maybe_bytes=None):
    if maybe_bytes is None:
        p = Path(path_or_bytes); data = p.read_bytes(); filename = p.name
    else:
        data = maybe_bytes; filename = "data.bin"

    total_len = len(data)
    chunks = chunk_plaintext(data)
    sha256_hex = hashlib.sha256(data).hexdigest()
    ts = now_ts()

    start_env = build_file_start({"filename": filename, "size": total_len, "chunks": len(chunks), "sha256": sha256_hex},
                                 user_id, (None if target == "public" else target), ts)
    start_env["transport_sig"] = signed_transport_sig(start_env["payload"], privkey_pem)
    await ws.send(json.dumps(start_env))

    if target == "public":
        gk = await get_public_group_key_for_client(ws, user_id, privkey_pem)

    for i, ch in enumerate(chunks):
        if target == "public":
            nonce, ct = aesgcm_encrypt(gk, ch, aad=f"{user_id}|{ts}|{i}".encode())
            payload_chunk = json.dumps({"nonce": b64u(nonce), "ciphertext": b64u(ct)})
            chunk_b64 = b64u(payload_chunk.encode("utf-8"))
        else:
            #recipient_pub = tables.user_pubkeys.get(to)
            #ct = oaep_encrypt(recipient_pub, ch)
            chunk_b64 = b64u(ct)

        chunk_env = build_file_chunk(i, chunk_b64, user_id, (None if target == "public" else target), now_ts())
        chunk_env["transport_sig"] = signed_transport_sig(chunk_env["payload"], privkey_pem)
        await ws.send(json.dumps(chunk_env))

    end_env = build_file_end({"chunks": len(chunks), "sha256": sha256_hex}, user_id, (None if target == "public" else target), now_ts())
    end_env["transport_sig"] = signed_transport_sig(end_env["payload"], privkey_pem)
    await ws.send(json.dumps(end_env))
    print("file transfer finished (sent)")

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
        print("DEBUG: Sending USER_ADVERTISE envelope:\n", json.dumps(envelope, indent=2))
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
                print("DEBUG: Calling cmd_tell")
                await cmd_tell(ws, user_id, privkey_pem, to, text, tables)
            elif line.startswith("/all "):
                text = line[len("/all "):]
                await cmd_all(ws, user_id, privkey_pem, text)
            elif line.startswith("/file "):
                parts = line.split(" ", 2)
                if len(parts) < 3:
                    print("usage: /file <user|public> <path>"); continue
                target, path = parts[1], parts[2]
                await cmd_file(ws, user_id, privkey_pem, target, path)
            elif line == "/quit":
                env = build_user_remove(user_id, privkey_pem)
                await ws.send(json.dumps(env))
                await ws.close()
                break
            else:
                print("unknown command", line)

        listener_task.cancel()
        await ws.close()


from backend.crypto.rsa_key_management import generate_rsa_keypair
from backend.crypto.base64url import base64url_encode

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