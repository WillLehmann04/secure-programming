'''
    Created: 17/09/2025 @ 1:37pm
    BASE64URL functionality
'''

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