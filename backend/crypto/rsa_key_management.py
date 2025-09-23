from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

def generate_rsa_keypair(bits: int = 4096) -> tuple[bytes, bytes]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return private_pem, public_pem

def load_public_key(public_pem: bytes | str):
    if isinstance(public_pem, str):
        public_pem = public_pem.encode("utf-8")
    return serialization.load_pem_public_key(public_pem)

def load_private_key(private_pem: bytes | str):
    if isinstance(private_pem, str):
        private_pem = private_pem.encode("utf-8")
    return serialization.load_pem_private_key(private_pem, password=None)
