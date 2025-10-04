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
    rsa_encrypt_oaep,
    rsa_decrypt_oaep,
    rsa_sign_pss,
    base64url_encode,
    base64url_decode,
    stabilise_json,
)

"""
Return (user_id, privkey_pem_bytes, pubkey_pem_str)
cfg of the JSON: { "user_id": "...", "privkey_pem_b64": "...", "pubkey_pem": "..." }
"""


#config
WS_URL = os.environ.get("SOCP_WS", "ws://localhost:8765")
OAEP_HASH_BYTES = 32  # SHA-256
RSA_4096_KEY_BYTES = 4096 // 8  # 512
OAEP_MAX_PLAINTEXT = RSA_4096_KEY_BYTES - 2 * OAEP_HASH_BYTES - 2  # 446 bytes

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

def content_sig_public(ciphertext_bytes: bytes, frm: str, ts: str, privkey_pem: bytes) -> str:
    d = sha256_bytes(ciphertext_bytes + frm.encode() + ts.encode())
    return b64u(rsa_sign_pss(privkey_pem, d))

# AES-GCM for public channel
def aesgcm_encrypt(key: bytes, plaintext: bytes, aad: bytes = b"") -> tuple[bytes, bytes]:
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext, aad)
    return nonce, ct

# Key management - replace with our actual decrypt
def load_client_keys_from_config(cfg_path: str) -> Tuple[str, bytes, str]:
    """
    Return (user_id, privkey_pem_bytes, pubkey_pem_str)
    cfg of the JSON: { "user_id": "...", "privkey_pem_b64": "...", "pubkey_pem": "..." }
    """
    cfg = json.loads(Path(cfg_path).read_text(encoding="utf-8"))
    user_id = cfg["user_id"]
    priv_pem = base64url_decode(cfg["privkey_pem_b64"])
    pub_pem = cfg["pubkey_pem"]
    return user_id, priv_pem, pub_pem

# Envelope builders
''' USER_HELLO '''
def build_user_hello(server_id: str, user_id: str, pubkey_pem: str, privatekey_pem: bytes) -> dict:
    ''' -- CRAFT THE PAYLOAD -- '''
    payload = {
        "client": "cli-v1",
        "pubkey": pubkey_pem,
        "enc_pubkey": pubkey_pem,  # placeholder; actual key exchange not implemented
    }   

    return {
        "type": "USER_HELLO",
        "from": user_id,
        "to": server_id,
        "ts": now_ts(),
        "payload": payload,
        "sig": signed_transport_sig(payload, privatekey_pem),
    }

''' MSG_DIRECT '''
def build_msg_direct(ciphertext: str, sender_user_id: str, recipient_user_id: str, sender_pub: str, content_sig: str, privkey_pem: bytes) -> dict:
    ''' -- CRAFT THE PAYLOAD -- '''
    payload = {
        "ciphertext": ciphertext,
        "sender_pub": sender_pub,
        "content_sig": content_sig,
    }

    return {
        "type": "MSG_DIRECT",
        "from": sender_user_id,
        "to": recipient_user_id,
        "ts": now_ts(),
        "payload": payload,
        "sig": signed_transport_sig(payload, privkey_pem),
    }

    #payload = {"ciphertext": ciphertext_b64u, "from": frm, "to": to, "ts": ts, "content_sig": content_sig_b64u}
    #return {"type": "MSG_DIRECT", "payload": payload}


''' TODO: FIX THSESE  '''
def build_msg_public(nonce_b64u: str, ct_b64u: str, frm: str, ts: str, content_sig_b64u: str) -> dict:
    payload = {"nonce": nonce_b64u, "ciphertext": ct_b64u, "from": frm, "ts": ts, "content_sig": content_sig_b64u}
    return {"type": "MSG_PUBLIC_CHANNEL", "payload": payload}

def build_file_start(manifest: dict, frm: str, to: str | None, ts: str) -> dict:
    return {"type": "FILE_START", "payload": {"manifest": manifest, "from": frm, "to": to, "ts": ts}}

def build_file_chunk(index: int, chunk_b64u: str, frm: str, to: str | None, ts: str) -> dict:
    return {"type": "FILE_CHUNK", "payload": {"index": index, "chunk": chunk_b64u, "from": frm, "to": to, "ts": ts}}

def build_file_end(manifest_summary: dict, frm: str, to: str | None, ts: str) -> dict:
    return {"type": "FILE_END", "payload": {"summary": manifest_summary, "from": frm, "to": to, "ts": ts}}

# Cleient RPC Pumping
async def listener(ws):
    async for msg in ws:
        try:
            obj = json.loads(msg)
        except Exception:
            print("[IN ] raw:", msg)
            continue

        rid = obj.get("req_id")
        if rid and rid in _pending:
            _pending.pop(rid).set_result(obj)
            continue

        # unsolicited frames
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

# Dir lookups
async def get_recipient_pubpem(ws, user_id: str) -> bytes:
    resp = await rpc(ws, "DIR_GET_PUBKEY", {"user_id": user_id})
    if resp.get("type") == "ERROR":
        raise RuntimeError(f"DIR_GET_PUBKEY failed: {resp['payload']}")
    return resp["payload"]["pubkey"].encode("utf-8")

async def get_public_group_key_for_client(ws, me: str, privkey_pem: bytes) -> bytes:
    if me in _group_key_cache:
        return _group_key_cache[me]
    resp = await rpc(ws, "DIR_GET_WRAPPED_PUBLIC_KEY", {"user_id": me})
    if resp.get("type") == "ERROR":
        raise RuntimeError(f"DIR_GET_WRAPPED_PUBLIC_KEY failed: {resp['payload']}")
    wrapped_b64 = resp["payload"]["wrapped_key"]
    clear = rsa_decrypt_oaep(privkey_pem, base64url_decode(wrapped_b64))
    _group_key_cache[me] = clear  # 32-byte key; RAM only
    return clear

# high level commands
async def cmd_list(ws, user_id: str):
    await ws.send(json.dumps({"type": "CMD_LIST", "payload": {"from": user_id}, "ts": now_ts()}))

async def cmd_tell(ws, user_id: str, privkey_pem: bytes, to: str, text: str):
    plain = text.encode("utf-8")
    ts = now_ts()
    if len(plain) <= OAEP_MAX_PLAINTEXT:
        recipient_pub = await get_recipient_pubpem(ws, to)
        ciphertext = rsa_encrypt_oaep(recipient_pub, plain)
        ciphertext_b64u = b64u(ciphertext)
        content_sig = content_sig_dm(ciphertext, user_id, to, ts, privkey_pem)
        env = build_msg_direct(ciphertext_b64u, user_id, to, ts, content_sig)
        env["transport_sig"] = signed_transport_sig(env["payload"], privkey_pem)
        await ws.send(json.dumps(env))
    else:
        chunks = chunk_plaintext(plain)
        for i, ch in enumerate(chunks):
            recipient_pub = await get_recipient_pubpem(ws, to)
            ciphertext = rsa_encrypt_oaep(recipient_pub, ch)
            payload_ts = now_ts()
            content_sig = content_sig_dm(ciphertext, user_id, to, payload_ts, privkey_pem)
            env = {
                "type": "MSG_DIRECT_CHUNK",
                "payload": {
                    "ciphertext": b64u(ciphertext),
                    "from": user_id,
                    "to": to,
                    "index": i,
                    "ts": payload_ts,
                    "content_sig": content_sig,
                },
            }
            env["transport_sig"] = signed_transport_sig(env["payload"], privkey_pem)
            await ws.send(json.dumps(env))

async def cmd_all(ws, user_id: str, privkey_pem: bytes, text: str):
    plain = text.encode("utf-8")
    ts = now_ts()
    # unwrap current 32-byte public group key (symmetric)
    gk = await get_public_group_key_for_client(ws, user_id, privkey_pem)
    # encrypt with AES-GCM
    nonce, ct = aesgcm_encrypt(gk, plain, aad=f"{user_id}|{ts}".encode())
    nonce_b64 = b64u(nonce)
    ct_b64 = b64u(ct)
    content_sig = content_sig_public(ct, user_id, ts, privkey_pem)
    env = build_msg_public(nonce_b64, ct_b64, user_id, ts, content_sig)
    env["transport_sig"] = signed_transport_sig(env["payload"], privkey_pem)
    await ws.send(json.dumps(env))

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
            recipient_pub = await get_recipient_pubpem(ws, target)
            ct = rsa_encrypt_oaep(recipient_pub, ch)
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
    user_id, privkey_pem, pubkey_pem = load_client_keys_from_config(cfg_path)
    async with websockets.connect(WS_URL) as ws:
        # send USER_HELLO once
        await ws.send(json.dumps(build_user_hello(user_id, pubkey_pem)))
        print("sent USER_HELLO; awaiting server responses...")

        # background listener
        listener_task = asyncio.create_task(listener(ws))

        print("Enter commands: /list, /tell <user> <text>, /all <text>, /file <user|public> <path>")
        while True:
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            if line == "/list":
                await cmd_list(ws, user_id)
            elif line.startswith("/tell "):
                parts = line.split(" ", 2)
                if len(parts) < 3:
                    print("usage: /tell <user> <text>"); continue
                to, text = parts[1], parts[2]
                await cmd_tell(ws, user_id, privkey_pem, to, text)
            elif line.startswith("/all "):
                text = line[len("/all "):]
                await cmd_all(ws, user_id, privkey_pem, text)
            elif line.startswith("/file "):
                parts = line.split(" ", 2)
                if len(parts) < 3:
                    print("usage: /file <user|public> <path>"); continue
                target, path = parts[1], parts[2]
                await cmd_file(ws, user_id, privkey_pem, target, path)
            elif line in ("/quit", "/exit"):
                break
            else:
                print("unknown command", line)

        listener_task.cancel()
        await ws.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: cli_client.py <client_config.json>")
        sys.exit(1)
    asyncio.run(main_loop(sys.argv[1]))
