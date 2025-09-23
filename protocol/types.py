# protocol/types.py
from __future__ import annotations

# ---- Message types (client -> server) ----
DIR_GET_PUBKEY = "DIR_GET_PUBKEY"
DIR_GET_WRAPPED_PUBLIC_KEY = "DIR_GET_WRAPPED_PUBLIC_KEY"

# ---- Message types (server -> client) ----
DIR_PUBKEY = "DIR_PUBKEY"
DIR_WRAPPED_PUBLIC_KEY = "DIR_WRAPPED_PUBLIC_KEY"
ERROR = "ERROR"

# ---- Common error codes ----
ERR_BAD_JSON = "BAD_JSON"
ERR_UNKNOWN_TYPE = "UNKNOWN_TYPE"
ERR_USER_NOT_FOUND = "USER_NOT_FOUND"
ERR_NO_WRAPPED_KEY = "NO_WRAPPED_KEY"
ERR_DIR_LOOKUP_FAILED = "DIR_LOOKUP_FAILED"   # client-side timeout/transport issues
ERR_NAME_IN_USE = "NAME_IN_USE"               # for USER_HELLO (used later)

# Minimal shape docs (for human readers)
# Request: { "req_id": "<uuid>", "type": <one of *_GET_*>, "payload": {...} }
# Response: { "req_id": "<same uuid>", "type": <DIR_* or ERROR>, "payload": {...} }
