from backend.crypto import rsa_sign_pss, base64url_encode, stabilise_json
from .utils import now_ts

ALG = "PS256"


def _sign_env(payload: dict, privkey_pem: bytes) -> str:
    payload_bytes = stabilise_json(payload)
    return base64url_encode(rsa_sign_pss(privkey_pem, payload_bytes))


def user_hello(server_id: str, user_id: str, pubkey_pem: str, privatekey_pem: bytes) -> dict:
    payload = {"client": "cli-v1", "pubkey": pubkey_pem, "enc_pubkey": pubkey_pem}
    return {
        "type": "USER_HELLO",
        "from": user_id,
        "to": server_id,
        "ts": now_ts(),
        "payload": payload,
        "sig": _sign_env(payload, privatekey_pem),
        "alg": ALG,
    }


def user_advertise(
    user_id: str,
    pubkey: str,
    privkey_store: str,
    pake_password: str,
    meta: dict,
    version: str,
    privkey_pem: bytes,
    to: str = "*",
    ts: int | None = None,
) -> dict:
    ts = ts or now_ts()
    payload = {
        "user_id": user_id,
        "pubkey": pubkey,
        "privkey_store": privkey_store,
        "pake_password": pake_password,
        "meta": meta,
        "version": version,
    }
    return {
        "type": "USER_ADVERTISE",
        "from": user_id,
        "to": to,
        "ts": ts,
        "payload": payload,
        "sig": _sign_env(payload, privkey_pem),
        "alg": ALG,
    }


def user_remove(user_id: str, privkey_pem: bytes) -> dict:
    payload = {"user_id": user_id, "location": "local"}
    return {
        "type": "USER_REMOVE",
        "from": user_id,
        "to": "",
        "ts": now_ts(),
        "payload": payload,
        "sig": _sign_env(payload, privkey_pem),
        "alg": ALG,
    }


def msg_direct(
    ciphertext_b64u: str,
    sender_user_id: str,
    recipient_user_id: str,
    ts: int,
    content_sig_b64u: str,
    privkey_pem: bytes,
) -> dict:
    payload = {
        "ciphertext": ciphertext_b64u,
        "from": sender_user_id,
        "to": recipient_user_id,
        "ts": ts,
        "content_sig": content_sig_b64u,
    }
    return {
        "type": "MSG_DIRECT",
        "from": sender_user_id,
        "to": recipient_user_id,
        "ts": ts,
        "payload": payload,
        "sig": _sign_env(payload, privkey_pem),
        "alg": ALG,
    }


def msg_direct_chunk(
    payload: dict,
    privkey_pem: bytes,
    sender_user_id: str,
    recipient_user_id: str,
    ts: int,
) -> dict:
    # payload must already contain: ciphertext (b64u), from, to, index, ts, content_sig
    return {
        "type": "MSG_DIRECT_CHUNK",
        "from": sender_user_id,
        "to": recipient_user_id,
        "ts": ts,
        "payload": payload,
        "sig": _sign_env(payload, privkey_pem),
        "alg": ALG,
    }


def msg_public(
    nonce_b64u: str,
    ct_b64u: str,
    frm: str,
    ts: int,
    content_sig_b64u: str,
    privkey_pem: bytes,
    channel_id: str,
) -> dict:
    payload = {
        "nonce": nonce_b64u,
        "ciphertext": ct_b64u,
        "from": frm,
        "to": channel_id,
        "ts": ts,
        "content_sig": content_sig_b64u,
    }
    return {
        "type": "MSG_PUBLIC_CHANNEL",
        "from": frm,
        "to": channel_id,
        "ts": ts,
        "payload": payload,
        "sig": _sign_env(payload, privkey_pem),
        "alg": ALG,
    }








def file_start(manifest: dict, frm: str, to: str | None, ts: int) -> dict:
    return {"type": "FILE_START", "payload": {"manifest": manifest, "from": frm, "to": to, "ts": ts}}


def file_chunk(index: int, chunk_b64u: str, frm: str, to: str | None, ts: int) -> dict:
    return {"type": "FILE_CHUNK", "payload": {"index": index, "chunk": chunk_b64u, "from": frm, "to": to, "ts": ts}}


def file_end(manifest_summary: dict, frm: str, to: str | None, ts: int) -> dict:
    return {"type": "FILE_END", "payload": {"summary": manifest_summary, "from": frm, "to": to, "ts": ts}}
