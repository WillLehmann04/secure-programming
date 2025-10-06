'''
    Group: Group 2
    Members:
        - William Lehmann (A1889855)
        - Edward Chipperfield (A1889447)
        - G A Sadman (A1899867)
        - Aditeya Sahu (A1943902)
        
    Description:
        - This module provides cryptographic utilities including base64url encoding/decoding,
          JSON stabilisation, RSA key management, RSA encryption/decryption, and RSA signing/verification.
        - It consolidates various cryptographic functions for easy import and use across the backend.
'''

'''
    Created: 17/09/2025 @ 1:37pm
    BASE64URL functionality

    Tested: as of 17/09/2025 @ 1:53pm
        - Verified round-trip encode→decode for b"", b"A", b"OK", b"hi", b"hello world", and b"\x00\xff\x10"
        - Verified no padding was encoded
        - Verified padding was added back correctly after decoding
        - Tested edge cases with one or more padding chars
        - Confirmed empty input encodes and decodes correctly
        - Testing bad strings raise errors.
'''

# ========== Imports ========== 
import base64

# ========== Base64 URL Encoding ========== 
def base64url_encode(raw_url: bytes) -> str:
    postp = base64.urlsafe_b64encode(raw_url).decode("ascii")
    return postp.rstrip("=")


# ========== Base64 URL Decoding ========== 
def base64url_decode(postp_url: str) -> bytes:
    length = len(postp_url)
    remainder = length % 4
    missing = (-remainder) % 4    # how many chars needed to reach multiple of 4
    pad = "=" * missing
    return base64.urlsafe_b64decode(postp_url + pad)