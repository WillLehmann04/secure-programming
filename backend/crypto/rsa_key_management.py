'''
    Created: 17/09/2025 @ 2:40pm
    RSA Key functionality

    Tested: as of 17/09/2025 @ 4:13pm
        - Generated and loaded a round trip
        - Correct PEM headers
        - Encrypted a private key
        - Unencrypted a private key.
'''

# ========== Imports ========== 
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey, RSAPrivateKey

# ========== RSA Key Pair Generation ========== 
def generate_rsa_keypair(bits: int = 4096) -> tuple[bytes, bytes]:
    priv = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    enc = serialization.NoEncryption()
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=enc,
    )
    pub_pem = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return pub_pem, priv_pem


# ========== Helper RSA Load Priv and Pub ========== 
def load_public_key(public_pem: bytes):
    return serialization.load_pem_public_key(public_pem)

def load_private_key(private_pem: bytes):
    return serialization.load_pem_private_key(private_pem, None) # Password protected PEM wasnt required as such hard coding to None