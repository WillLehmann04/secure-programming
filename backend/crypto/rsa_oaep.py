'''
    Created: 17/09/2025 @ 4:32pm
    RSA Key functionality

    Tested: as of 17/09/2025 @ pm
        - 
'''

# ========== Imports ========== 
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from .rsa_key_management import load_private_key, load_public_key
from typing import Iterable, List

# ========== RSA OAEP Encryption ========== 

def oaep_encrypt(public_pem: bytes, plaintext: bytes) -> bytes:
    public_key = load_public_key(public_pem) 
    return public_key.encrypt(
        plaintext,
        padding.OAEP(
            mgf=padding.MGF1(hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

def oaep_decrypt(private_pem: bytes, ciphertext: bytes) -> bytes:
    private_key = load_private_key(private_pem)
    return private_key.decrypt(
        ciphertext,
        padding.OAEP(
            mgf=padding.MGF1(hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

# ========== Helper Function ==========
#  
def oaep_max_plaintext_len(public_pem: bytes) -> int:
    key_bits = load_public_key(public_pem).key_size
    k = (key_bits + 7) // 8        # modulus bytes
    hlen = 32                      # SHA-256
    return k - 2*hlen - 2          # 4096-bit -> 512-64-2 = 446

def _chunks(b: bytes, n: int) -> List[bytes]:
    if n <= 0: raise ValueError("chunk size must be > 0")
    return [b[i:i+n] for i in range(0, len(b), n)]

def oaep_encrypt_large(public_pem: bytes, data: bytes) -> List[bytes]:
    maxlen = oaep_max_plaintext_len(public_pem)
    return [oaep_encrypt(public_pem, c) for c in _chunks(data, maxlen)]

def oaep_decrypt_large(private_pem: bytes, blocks: Iterable[bytes]) -> bytes:
    return b"".join(oaep_decrypt(private_pem, c) for c in blocks)