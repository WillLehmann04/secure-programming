from __future__ import annotations
import json, hashlib, time
from pathlib import Path
from typing import List
from backend.crypto import rsa_encrypt_oaep, rsa_decrypt_oaep, base64url_encode, base64url_decode
from .rpc import rpc
from .crypto_public import aesgcm_encrypt, transport_sig, content_sig_dm, content_sig_public, b64u

OAEP_HASH_BYTES = 32
RSA_4096_KEY_BYTES = 4096 // 8
OAEP_MAX_PLAINTEXT = RSA_4096_KEY_BYTES - 2*OAEP_HASH_BYTES - 2
_group_key_cache: dict[str, bytes] = {}

def now_ts() -> str:
    return str(int(time.time()))

def chunk(plain: bytes, max_chunk=OAEP_MAX_PLAINTEXT) -> List[bytes]:
    return [plain[i:i+max_chunk] for i in range(0, len(plain), max_chunk)]

async def get_recipient_pubpem(ws, user_id: str) -> bytes:
    resp = await rpc(ws, "DIR_GET_PUBKEY", {"user_id": user_id})
    if resp.get("type") == "ERROR":
        raise RuntimeError(f"DIR_GET_PUBKEY failed: {resp['payload']}")
    return resp["payload"]["pubkey"].encode()

async def get_public_group_key(ws, me: str, privkey_pem: bytes) -> bytes:
    if me in _group_key_cache:
        return _group_key_cache[me]
    resp = await rpc(ws, "DIR_GET_WRAPPED_PUBLIC_KEY", {"user_id": me})
    if resp.get("type") == "ERROR":
        raise RuntimeError(f"DIR_GET_WRAPPED_PUBLIC_KEY failed: {resp['payload']}")
    clear = rsa_decrypt_oaep(privkey_pem, base64url_decode(resp["payload"]["wrapped_key"]))
    _group_key_cache[me] = clear
    return clear

async def cmd_list(ws, user_id: str):
    await ws.send(json.dumps({"type":"CMD_LIST","payload":{"from":user_id},"ts": now_ts()}))

async def cmd_tell(ws, user_id: str, privkey_pem: bytes, to: str, text: str):
    plain = text.encode()
    ts = now_ts()
    if len(plain) <= OAEP_MAX_PLAINTEXT:
        pub = await get_recipient_pubpem(ws, to)
        ct = rsa_encrypt_oaep(pub, plain)
        env = {"type":"MSG_DIRECT","payload":{
            "ciphertext": b64u(ct), "from": user_id, "to": to, "ts": ts,
            "content_sig": content_sig_dm(ct, user_id, to, ts, privkey_pem)
        }}
        env["transport_sig"] = transport_sig(env["payload"], privkey_pem)
        await ws.send(json.dumps(env))
    else:
        for i, ch in enumerate(chunk(plain)):
            pub = await get_recipient_pubpem(ws, to)
            ct = rsa_encrypt_oaep(pub, ch)
            ts_i = now_ts()
            env = {"type":"MSG_DIRECT_CHUNK","payload":{
                "ciphertext": b64u(ct), "from": user_id, "to": to, "index": i, "ts": ts_i,
                "content_sig": content_sig_dm(ct, user_id, to, ts_i, privkey_pem)
            }}
            env["transport_sig"] = transport_sig(env["payload"], privkey_pem)
            await ws.send(json.dumps(env))

async def cmd_all(ws, user_id: str, privkey_pem: bytes, text: str):
    plain = text.encode()
    ts = now_ts()
    gk = await get_public_group_key(ws, user_id, privkey_pem)
    nonce, ct = aesgcm_encrypt(gk, plain, aad=f"{user_id}|{ts}".encode())
    env = {"type":"MSG_PUBLIC_CHANNEL","payload":{
        "nonce": b64u(nonce), "ciphertext": b64u(ct), "from": user_id, "ts": ts,
        "content_sig": content_sig_public(ct, user_id, ts, privkey_pem)
    }}
    env["transport_sig"] = transport_sig(env["payload"], privkey_pem)
    await ws.send(json.dumps(env))

async def cmd_file(ws, user_id: str, privkey_pem: bytes, target: str, path: str):
    data = Path(path).read_bytes()
    sha256_hex = hashlib.sha256(data).hexdigest()
    parts = [data[i:i+OAEP_MAX_PLAINTEXT] for i in range(0, len(data), OAEP_MAX_PLAINTEXT)]
    ts = now_ts()
    start = {"type":"FILE_START","payload":{"manifest":{
        "filename": Path(path).name, "size": len(data), "chunks": len(parts), "sha256": sha256_hex
    },"from": user_id, "to": (None if target=="public" else target), "ts": ts}}
    start["transport_sig"] = transport_sig(start["payload"], privkey_pem)
    await ws.send(json.dumps(start))
    if target == "public":
        gk = await get_public_group_key(ws, user_id, privkey_pem)
    for i, ch in enumerate(parts):
        if target == "public":
            import json as _json
            from backend.crypto import base64url_encode as _b64u
            from .crypto_public import aesgcm_encrypt as _enc
            n, c = _enc(gk, ch, aad=f"{user_id}|{ts}|{i}".encode())
            chunk_b64 = _b64u(_json.dumps({"nonce": _b64u(n), "ciphertext": _b64u(c)}).encode())
        else:
            pub = await get_recipient_pubpem(ws, target)
            from backend.crypto import rsa_encrypt_oaep as _enc_rsa, base64url_encode as _b64
            chunk_b64 = _b64(_enc_rsa(pub, ch))
        env = {"type":"FILE_CHUNK","payload":{"index": i, "chunk": chunk_b64, "from": user_id, "to": (None if target=="public" else target), "ts": now_ts()}}
        env["transport_sig"] = transport_sig(env["payload"], privkey_pem)
        await ws.send(json.dumps(env))
    end = {"type":"FILE_END","payload":{"summary":{"chunks": len(parts), "sha256": sha256_hex}, "from": user_id, "to": (None if target=="public" else target), "ts": now_ts()}}
    end["transport_sig"] = transport_sig(end["payload"], privkey_pem)
    await ws.send(json.dumps(end))
