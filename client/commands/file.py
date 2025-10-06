from client.helpers.small_utils import now_ts, b64u, stabilise_json, chunk_plaintext
from backend.crypto import rsa_sign_pss, oaep_encrypt, oaep_encrypt_large

from client.build_envelopes.file_start import build_file_start
from client.build_envelopes.file_chunk import build_file_chunk
from client.build_envelopes.file_end import build_file_end
from pathlib import Path
import hashlib
import uuid


async def cmd_file(ws, user_id: str, privkey_pem: bytes, target: str, path_or_bytes, maybe_bytes=None, tables=None, pubkey_pem=None):
    file_id = str(uuid.uuid4())
    if maybe_bytes is None:
        p = Path(path_or_bytes)
        data = p.read_bytes()
        filename = p.name
    else:
        data = maybe_bytes
        filename = "data.bin"

    total_len = len(data)
    sha256_hex = hashlib.sha256(data).hexdigest()
    ts_start = now_ts()
    mode = "public" if target == "public" else "dm"
    to = None if target == "public" else target

    # Prepare chunks
    if target == "public":
        RAW_CHUNK_BYTES = 32 * 1024
        raw_chunks = list(chunk_plaintext(data, RAW_CHUNK_BYTES))
        chunks_b64 = [b64u(ch) for ch in raw_chunks]
    else:
        if tables is None or getattr(tables, "user_pubkeys", None) is None:
            print("Recipient key table not available (tables.user_pubkeys missing).")
            return
        recipient_pub = tables.user_pubkeys.get(target)
        if not recipient_pub:
            print(f"Recipient public key for {target} not found.")
            return
        enc_chunks = oaep_encrypt_large(recipient_pub, data)
        chunks_b64 = [b64u(ch) for ch in enc_chunks]

    num_chunks = len(chunks_b64) if chunks_b64 else 0

    # SOCP-compliant FILE_START
    start_env = build_file_start(
        file_id, filename, total_len, sha256_hex, mode, user_id, to, ts_start, privkey_pem
    )
    await ws.send(stabilise_json(start_env).decode("utf-8"))

    # SOCP-compliant FILE_CHUNKs
    for i, ch_b64 in enumerate(chunks_b64):
        chunk_env = build_file_chunk(
            file_id, i, ch_b64, user_id, to, now_ts(), privkey_pem
        )
        await ws.send(stabilise_json(chunk_env).decode("utf-8"))

    # SOCP-compliant FILE_END
    end_env = build_file_end(
        file_id, user_id, to, now_ts(), privkey_pem
    )
    await ws.send(stabilise_json(end_env).decode("utf-8"))
    print(f"file transfer finished (sent): {filename} ({total_len} bytes, {num_chunks} chunks)")