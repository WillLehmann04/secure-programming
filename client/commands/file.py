from pathlib import Path
import hashlib
import json

from client.helpers.small_utils import (
    now_ts,
    b64u,
    stabilise_json,
    chunk_plaintext,
)
from backend.crypto import oaep_encrypt_large

from client.build_envelopes.file_start import build_file_start
from client.build_envelopes.file_chunk import build_file_chunk
from client.build_envelopes.file_end import build_file_end


async def cmd_file(
    ws,
    user_id: str,
    privkey_pem: bytes,
    target: str,
    path_or_bytes,
    maybe_bytes=None,
    tables=None,
    pubkey_pem=None
):
 
    if target == "public" or target is None:
        print("/file is DM-only: please supply a user id/handle from /list.")
        return

    if maybe_bytes is None:
        clean_path = str(path_or_bytes).strip().strip('"').strip("'")
        p = Path(clean_path)
        if not p.is_file():
            print(f"File not found: {clean_path}")
            return
        data = p.read_bytes()
        filename = p.name
    else:
        data = maybe_bytes
        filename = "data.bin"

    total_len = len(data)
    sha256_hex = hashlib.sha256(data).hexdigest()
    ts0 = now_ts()

    if tables is None or getattr(tables, "user_pubkeys", None) is None:
        print("Recipient key table not available (tables.user_pubkeys missing).")
        return
    recipient_pub = tables.user_pubkeys.get(target)
    if not recipient_pub:
        print(f"Recipient public key for '{target}' not found.")
        return

    enc_chunks: list[bytes] = oaep_encrypt_large(recipient_pub, data)
    chunks_b64 = [b64u(ch) for ch in enc_chunks]
    num_chunks = len(chunks_b64)

    start_manifest = {
        "filename": filename,
        "size": total_len,
        "chunks": num_chunks,
        "sha256": sha256_hex,
    }
    start_env = build_file_start(
        start_manifest,
        user_id,
        target,
        ts0,
        privkey_pem,
        pubkey_pem,
    )
    await ws.send(json.dumps(stabilise_json(start_env)))
    for i, ch_b64 in enumerate(chunks_b64):
        chunk_env = build_file_chunk(
            i,
            ch_b64,
            user_id,
            target,
            now_ts(),
            privkey_pem,
            pubkey_pem,
        )
        await ws.send(json.dumps(stabilise_json(chunk_env)))

    end_env = build_file_end(
        {"chunks": num_chunks, "sha256": sha256_hex},
        user_id,
        target,
        now_ts(),
        privkey_pem,
        pubkey_pem,
    )
    await ws.send(json.dumps(stabilise_json(end_env)))

    print(f"file transfer finished: {filename} ({total_len} bytes, {num_chunks} chunks)")
