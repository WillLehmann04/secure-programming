'''
    Created: 17/09/2025 @ 4:52pm
    RSA Signing and Verification.

    Tested: as of 17/09/2025 @ pm
        - 
'''

# ========== Imports ========== 
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidSignature

from .rsa_key_management import load_private_key, load_public_key

# ========== Functionals ========== 
def rsa_sign_pss(private_key_or_pem, data: bytes) -> bytes:
    priv = load_private_key(private_key_or_pem)
    return priv.sign(
        data,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH,
        ),
        hashes.SHA256(),
    )

def rsa_verify_pss(public_key_or_pem, data: bytes, sig: bytes) -> bool:
    pub = load_public_key(public_key_or_pem)
    try:
        pub.verify(
            sig,
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return True
    except InvalidSignature:
        return False