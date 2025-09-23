# main.py
# Run: python main.py

from backend.crypto.base64url import base64url_encode, base64url_decode
from backend.crypto.json_format import stabilise_json
from backend.crypto.rsa_key_management import generate_rsa_keypair, load_public_key, load_private_key
from backend.crypto.rsa_oaep import oaep_encrypt, oaep_decrypt
from backend.crypto.rsa_pss import rsa_sign_pss, rsa_verify_pss
from backend.crypto.content_sig import sign_payload, verify_payload

# Optional imports (only if you implemented them)
try:
    from backend.crypto.rsa_oaep import oaep_max_plaintext_len, oaep_encrypt_large, oaep_decrypt_large
    HAS_OAEP_CHUNKING = True
except Exception:
    HAS_OAEP_CHUNKING = False

try:
    from backend.crypto.oaep_messaging import encrypt_for_transport, decrypt_from_transport
    HAS_OAEP_MSG = True
except Exception:
    HAS_OAEP_MSG = False


def banner(title: str):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


# -------------------------- Base64url tests --------------------------

def test_base64url():
    banner("BASE64URL (no padding)")
    samples = [b"", b"A", b"OK", b"hi", b"hello world", b"\x00\xff\x10"]
    for raw in samples:
        enc = base64url_encode(raw)
        assert "=" not in enc
        assert base64url_decode(enc) == raw
    print("[OK] Roundtrip on fixed samples")


# -------------------------- Canonical JSON tests --------------------------

def test_canonical_json():
    banner("Canonical JSON (stable bytes)")
    a = {"z": 1, "a": [2, {"k": 3}]}
    b = {"a": [2, {"k": 3}], "z": 1}
    ca = stabilise_json(a)
    cb = stabilise_json(b)
    assert ca == cb
    assert ca == b'{"a":[2,{"k":3}],"z":1}'
    assert b" " not in ca
    print("[OK] Canonical JSON stable + compact")


# -------------------------- RSA Key Management tests --------------------------

def test_keys():
    banner("RSA Key Management")
    pub_pem, priv_pem = generate_rsa_keypair()
    assert pub_pem.startswith(b"-----BEGIN PUBLIC KEY-----")
    assert priv_pem.startswith(b"-----BEGIN PRIVATE KEY-----")
    pub = load_public_key(pub_pem)
    priv = load_private_key(priv_pem)
    assert pub.key_size == 4096 and priv.key_size == 4096
    print("[OK] Generated and loaded RSA-4096 keys")
    return pub_pem, priv_pem


# -------------------------- RSA-OAEP tests --------------------------

def test_oaep_small(pub_pem, priv_pem):
    banner("RSA-OAEP (SHA-256) small roundtrip")
    pt = b"hello oaep"
    ct = oaep_encrypt(pub_pem, pt)
    assert len(ct) == 512  # modulus size in bytes
    rt = oaep_decrypt(priv_pem, ct)
    assert rt == pt
    print("[OK] OAEP encrypt/decrypt works")


def test_oaep_large_if_available(pub_pem, priv_pem):
    if not HAS_OAEP_CHUNKING:
        banner("RSA-OAEP chunking")
        print("[-] Skipped: chunking not implemented")
        return
    banner("RSA-OAEP chunking")
    maxlen = oaep_max_plaintext_len(pub_pem)
    assert maxlen == 446
    big = b"A" * 5000
    chunks = oaep_encrypt_large(pub_pem, big)
    assert len(chunks) > 1
    rec = oaep_decrypt_large(priv_pem, chunks)
    assert rec == big
    print(f"[OK] Chunked enc/dec OK ({len(chunks)} blocks)")


def test_oaep_messaging_if_available(pub_pem, priv_pem):
    if not HAS_OAEP_MSG:
        banner("OAEP messaging (JSON wire helpers)")
        print("[-] Skipped: messaging not implemented")
        return
    banner("OAEP messaging (JSON wire helpers)")
    data = b"transport test" * 100
    encoded_chunks = encrypt_for_transport(pub_pem, data)
    assert all("=" not in s for s in encoded_chunks)
    recovered = decrypt_from_transport(priv_pem, encoded_chunks)
    assert recovered == data
    print(f"[OK] OAEP messaging wire encode/decode ({len(encoded_chunks)} chunks)")


# -------------------------- RSA-PSS tests --------------------------

def test_pss_bytes(pub_pem, priv_pem):
    banner("RSA-PSS (SHA-256) on raw bytes")
    msg = b"pss test message"
    sig = rsa_sign_pss(priv_pem, msg)
    assert rsa_verify_pss(pub_pem, msg, sig) is True
    assert rsa_verify_pss(pub_pem, msg + b"x", sig) is False
    print("[OK] PSS sign/verify and tamper detection")


def test_payload_sig(pub_pem, priv_pem):
    banner("Transport payload signature (canonical JSON)")
    payload1 = {"b": 2, "a": 1}
    sig = sign_payload(priv_pem, payload1)
    assert verify_payload(pub_pem, payload1, sig) is True
    payload2 = {"a": 1, "b": 2}
    assert verify_payload(pub_pem, payload2, sig) is True
    payload_bad = {"a": 1, "b": 99}
    assert verify_payload(pub_pem, payload_bad, sig) is False
    print("[OK] Payload sign/verify works")


# -------------------------- Run all --------------------------

def run_all():
    test_base64url()
    test_canonical_json()
    pub_pem, priv_pem = test_keys()
    test_oaep_small(pub_pem, priv_pem)
    test_oaep_large_if_available(pub_pem, priv_pem)
    test_oaep_messaging_if_available(pub_pem, priv_pem)
    test_pss_bytes(pub_pem, priv_pem)
    test_payload_sig(pub_pem, priv_pem)

if __name__ == "__main__":
    run_all()
    print("\nAll tests completed ✅")
