from client.helpers.small_utils import now_ts, b64u, base64url_encode, stabilise_json, chunk_plaintext, signed_transport_sig, content_sig_dm, rsa_sign_pss, sha256_bytes
import json

def build_file_end(manifest_summary: dict, frm: str, to: str | None, ts: str, privkey_pem: bytes, pubkey_pem: str) -> dict:
    summary_bytes = json.dumps(manifest_summary, sort_keys=True, separators=(",", ":")).encode("utf-8")
    d = sha256_bytes(summary_bytes + frm.encode() + (to or "").encode() + str(ts).encode())
    content_sig = base64url_encode(rsa_sign_pss(privkey_pem, d))
    payload = {
        "summary": manifest_summary,
        "from": frm,
        "to": to,
        "ts": ts,
        "pubkey": pubkey_pem,
        "content_sig": content_sig,
    }
    payload_bytes = stabilise_json(payload)
    sig = rsa_sign_pss(privkey_pem, payload_bytes)
    sig_b64 = base64url_encode(sig)
    return {
        "type": "FILE_END",
        "from": frm,
        "to": to,
        "ts": ts,
        "payload": payload,
        "sig": sig_b64,
        "alg": "PS256",
    }
    