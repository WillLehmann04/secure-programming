from __future__ import annotations
import json

from backend.crypto import (
    generate_rsa_keypair,
    rsa_decrypt_oaep,
    base64url_encode, base64url_decode,
)

from persistence.dir_json import (
    ensure_public_group,
    register_user,
    get_pubkey,
    get_wrapped_key,
    list_group_members,
    public_group_version,
)
from persistence.membership import join_public_group
from persistence.rotation import generate_wrapped_public_keyset, bump_public_version_and_rewrap

def pretty(p): 
    try:
        print(p, "=>", json.dumps(json.load(open(p, "r", encoding="utf-8")), indent=2, sort_keys=True))
    except FileNotFoundError:
        print(p, "=> <missing>")

def main():
    ensure_public_group()

    # Generate RSA keys for Alice
    priv_pem, pub_pem = generate_rsa_keypair(2048)  # change to 4096 for final

    try:
        register_user("alice", pub_pem.decode("utf-8"), "ENC_PRIVKEY_B64URL_PLACEHOLDER", "PAKE_VERIFIER_PLACEHOLDER", {"display_name":"Alice"})
    except Exception:
        pass

    assert get_pubkey("alice"), "alice must have a pubkey"

    wrapped_map, clear_group_key = generate_wrapped_public_keyset(["alice"])
    bump_public_version_and_rewrap(wrapped_map)

    wrapped_b64 = get_wrapped_key("public", "alice")
    assert wrapped_b64, "wrapped key must exist"
    decrypted = rsa_decrypt_oaep(priv_pem, base64url_decode(wrapped_b64))

    print("E2E decrypt OK:", decrypted == clear_group_key)
    print("public version:", public_group_version())
    print("members:", list_group_members("public"))

if __name__ == "__main__":
    main()
