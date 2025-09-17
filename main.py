from backend.crypto import rsa_key_management as km

def test_generate_and_load():
    priv_pem, pub_pem = km.generate_rsa_keypair()   # <-- private first, public second
    pub_key  = km.load_public_key(pub_pem)
    priv_key = km.load_private_key(priv_pem)

    print("Public key snippet:", pub_pem.decode().splitlines()[0:2])
    print("Private key snippet:", priv_pem.decode().splitlines()[0:2])

    pub_key = km.load_public_key(pub_pem)
    priv_key = km.load_private_key(priv_pem)

    assert pub_key.key_size == 4096
    assert priv_key.key_size == 4096
    print("RSA key generation + load OK ✅")

if __name__ == "__main__":
    test_generate_and_load()