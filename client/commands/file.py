from client.helpers.small_utils import now_ts, b64u, base64url_encode, stabilise_json, chunk_plaintext, signed_transport_sig, content_sig_dm, rsa_sign_pss, sha256_bytes, aesgcm_encrypt
from backend.crypto import rsa_sign_pss, oaep_encrypt, oaep_encrypt_large

from client.build_envelopes.file_start import build_file_start
from client.build_envelopes.file_chunk import build_file_chunk
from client.build_envelopes.file_end import build_file_end
from pathlib import Path
import hashlib
import json


async def cmd_file(ws, user_id: str, privkey_pem: bytes, target: str, path_or_bytes, maybe_bytes=None, tables=None, pubkey_pem=None):
    if maybe_bytes is None:
        p = Path(path_or_bytes)
        data = p.read_bytes()
        filename = p.name
    else:
        data = maybe_bytes
        filename = "data.bin"

    total_len = len(data)
    sha256_hex = hashlib.sha256(data).hexdigest()
    ts = now_ts()

    # Prepare and send FILE_START
    start_env = build_file_start(
        {"filename": filename, "size": total_len, "chunks": None, "sha256": sha256_hex},
        user_id, (None if target == "public" else target), ts, privkey_pem, pubkey_pem
    )
    await ws.send(json.dumps(start_env))

    if target == "public":
        print("public")
    else:
        recipient_pub = tables.user_pubkeys.get(target)
        if not recipient_pub:
            print(f"Recipient public key for {target} not found.")
            return
        encrypted_chunks = oaep_encrypt_large(recipient_pub, data)
        chunks = encrypted_chunks
        num_chunks = len(chunks)

    # Update chunk count in FILE_START (optional, for accuracy)
    start_env["payload"]["manifest"]["chunks"] = num_chunks

    # Send FILE_CHUNKs
    for i, ch in enumerate(chunks):
        if target == "public":
            nonce, ct = aesgcm_encrypt(gk, ch, aad=f"{user_id}|{ts}|{i}".encode())
            payload_chunk = json.dumps({"nonce": b64u(nonce), 
            "ciphertext": b64u(ct)})
            chunk_b64 = b64u(payload_chunk.encode("utf-8"))
        else:
            chunk_b64 = b64u(ch)

        chunk_env = build_file_chunk(
            i, chunk_b64, user_id, (None if target == "public" else target), now_ts(), privkey_pem, pubkey_pem
        )
        await ws.send(json.dumps(chunk_env))

    # Send FILE_END
    end_env = build_file_end(
        {"chunks": num_chunks, "sha256": sha256_hex},
        user_id, (None if target == "public" else target), now_ts(), privkey_pem, pubkey_pem
    )
    await ws.send(json.dumps(end_env))
    print("file transfer finished (sent)")