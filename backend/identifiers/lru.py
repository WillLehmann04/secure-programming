'''
    Group: Group 2
    Members:
        - William Lehmann (A1889855)
        - Edward Chipperfield (A1889447)
        - G A Sadman (A1899867)
        - Aditeya Sahu (A1943902)
        
    Description:
        - This module provides a simple LRU cache implementation.
'''

'''
    Created: 23/09/2025 @ 6:37pm
    LRU Implementation

    Tested: as of 23/09/2025 @ 6:50pm
        - Add and contained previously added Strings
        - Add and contained previously added Bytes
        - Tested Capacity
        - Tested Recency Update on duplicate add
        - Tested Duplicate add does not increase size
'''

# ========== Imports ========== 
from collections import OrderedDict

# ========== Functions ========== 
class LRU():
    def __init__(self, capacity: int = 1000):
        self.capacity = capacity
        self.orderedDictionary = OrderedDict()
    
    def contains(self, key:bytes | str) -> bool:
        return key in self.orderedDictionary

    def add(self, key: bytes | str) -> None:
        if key in self.orderedDictionary:
            self.orderedDictionary.move_to_end(key)
            return
        self.orderedDictionary[key] = None
        if len(self.orderedDictionary) > self.capacity:
            self.orderedDictionary.popitem(last=False)