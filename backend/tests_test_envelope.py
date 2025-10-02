# backend/tests_test_envelope.py

from backend.crypto import rsa_key_management as km
from backend.envelope import sign_payload, make_verifier, is_valid_envelope
from backend.keydir import keydir

def run():

    # 1) generate a keypair for the sender


    priv_pem, pub_pem = km.generate_rsa_keypair()
    priv = km.load_private_key(priv_pem)
    pub  = km.load_public_key(pub_pem)

    # store sender pubkey (simulate registration)

    sender_id = "11111111-1111-4111-8111-111111111111"
    keydir.add_public_key(sender_id, pub)

    # 2) craft envelope that REQUIRES a signature

    payload = {"msg": "hello world"}
    env = {
        "type": "DM_SEND",
        "from": sender_id,
        "to":   "22222222-2222-4222-8222-222222222222",
        "ts":   1700000000000,
        "payload": payload,
    }

    # 3) sign payload with sender private key

    env["sig"] = sign_payload(env["payload"], priv)["sig"]

    # 4) build pubkey lookup + verifier

    def pubkey_lookup(_payload_or_env):
        
        return keydir.get_public_key(sender_id)

    # quick structure + signature check
    ok = is_valid_envelope(env, pubkey_lookup)
    assert ok, "is_valid_envelope() failed unexpectedly"

    verifier = make_verifier(lambda peer_id: keydir.get_public_key(peer_id))
    assert verifier(env), "make_verifier() failed unexpectedly"

    print("Envelope verify OK ✅")

if __name__ == "__main__":
    run()
