from __future__ import annotations
import json
from pathlib import Path
from typing import Tuple
from backend.crypto import base64url_decode

def load_client_keys_from_config(cfg_path: str) -> Tuple[str, bytes, str]:
    cfg = json.loads(Path(cfg_path).read_text(encoding="utf-8"))
    return cfg["user_id"], base64url_decode(cfg["privkey_pem_b64"]), cfg["pubkey_pem"]
