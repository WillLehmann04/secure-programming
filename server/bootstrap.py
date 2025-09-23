# server/bootstrap.py
from __future__ import annotations
import sys
from persistence.dir_json import ensure_public_group, public_group_version

def init_persistence() -> None:
    """
    Initialise persistence for SOCP v1.3.
    Ensures the 'public' group exists at version 1.
    """
    ensure_public_group()
    v = public_group_version()
    if v < 1:
        # Defensive: ensure_public_group should always create version 1
        print("Error: public group version not initialised", file=sys.stderr)
        sys.exit(1)
    print(f"[persistence] public group ready (version={v})")
