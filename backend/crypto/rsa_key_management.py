'''
    Created: 17/09/2025 @ 2:40pm
    RSA Key functionality

    Tested: as of 17/09/2025 @ pm
        - Verified round-trip encode→decode for b"", b"A", b"OK", b"hi", b"hello world", and b"\x00\xff\x10"
'''

# ========== Imports ========== 
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

# ========== RSA Key Pair Generation ========== 
def generate_rsa_keypair(bits: int = 4096) -> tuple[bytes, bytes]:
    #Private Key generation
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=bits) # public exponent as required by the outline document.

    # Export private key
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    # Export Public key
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    return private_pem, public_pem


# ========== Helper RSA Load Priv and Pub ========== 
def load_public_key(public_pem: bytes):
    return serialization.load_pem_public_key(public_pem)

def load_private_key(private_pem: bytes):
    return serialization.load_pem_private_key(private_pem, None) # Password protected PEM wasnt required as such hard coding to None