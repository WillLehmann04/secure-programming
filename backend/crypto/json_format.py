'''
    Created: 17/09/2025 @ 1:58pm
    Stabilise JSON functionality

    Tested: as of 17/09/2025 @ 2:19pm
        - Tested same objects with different orders producing the same bytes size
        - Exact expected outputs
        - Nested objects with array output maintained.
        - UTF-8 Preserved
        - Output is in bytes.
'''

# ========== Imports ========== 
import json

# ========== stabilise Json ========== 
# as required for signing and verifying payloads.
def stabilise_json(obj) -> bytes:
    return json.dumps(
        obj, # Original message / content to be transferred.
        separators=(",", ":"), # Eliminate white space / reduce bytes required.
        sort_keys=True, # so the same payload has identical bytes each time.,
        ensure_ascii=False,
        allow_nan=False
    ).encode("utf-8") # Protocol document says protocol frames need to be utf-8