import json
from pathlib import Path
from typing import Tuple
from backend.crypto import base64url_decode


def load_client_cfg(cfg_path: str) -> Tuple[str, bytes, str, str, str, str, dict, str]:
    cfg = json.loads(Path(cfg_path).read_text(encoding="utf-8"))
    user_id = cfg["user_id"]
    privkey_pem = base64url_decode(cfg["privkey_pem_b64"])
    pubkey_pem = cfg["pubkey_pem"]
    server_id = cfg["server_id"]
    privkey_store = cfg.get("privkey_store", "")
    pake_password = cfg.get("pake_password", "")
    meta = cfg.get("meta", {"display_name": user_id})
    version = cfg.get("version", "1.0")
    return user_id, privkey_pem, pubkey_pem, server_id, privkey_store, pake_password, meta, version
