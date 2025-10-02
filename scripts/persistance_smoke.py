
#Unfinished Init Test

from __future__ import annotations
import json
from persistence.dir_json import (
    ensure_public_group, public_group_version, register_user, get_pubkey,
    add_member, list_group_members, get_wrapped_key


    
)
from persistence.membership import join_public_group, leave_public_group

def pretty(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        print(path, "=>", json.dumps(obj, indent=2, sort_keys=True))
        
    except FileNotFoundError:
        print(path, "=> <missing>")

def main():
    ensure_public_group()
    print("public version:", public_group_version())

    # Is alice missing?
    try:
        register_user("alice", "PEM_OR_JWK_ALICE", "ENC_PRIVKEY_B64URL_ALICE", "PAKE_VERIFIER_ALICE", {"display_name":"Alice"})
    except Exception:
        pass
    assert get_pubkey("alice")

 