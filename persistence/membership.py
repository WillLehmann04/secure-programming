from __future__ import annotations
from typing import Optional, List

from persistence.dir_json import (
    user_exists,
    add_member as add_member_row,
    remove_member,
    list_group_members,
    get_pubkey,
    get_wrapped_key,
)
from persistence.rotation import rotate_public_key_and_share, generate_wrapped_public_keyset

def join_public_group(user_id: str, role: str = "member") -> int:
    """
    Adds a user to the 'public' group and rotates the group key for all members (incl. the new one).
    Returns new public version.
    """
    if not user_exists(user_id):
        raise ValueError("User must be registered before joining public")
    if not get_pubkey(user_id):
        raise ValueError("User has no pubkey in directory")

    current = list_group_members("public")
    if user_id not in current:
        current.append(user_id)

    new_version = rotate_public_key_and_share(current)

    # Persist role alongside the now-persisted wrapped key
    wrapped = get_wrapped_key("public", user_id) or ""
    add_member_row("public", user_id, role, wrapped)
    return new_version

def leave_public_group(user_id: str) -> int:
    """
    Removes user from 'public' and rotates the group key for remaining members.
    Returns new public version.
    """
    remove_member("public", user_id)
    remaining = list_group_members("public")
    return rotate_public_key_and_share(remaining)
