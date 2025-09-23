# persistence/membership.py
from __future__ import annotations
from typing import Optional

from persistence.dir_json import (
    user_exists,
    add_member,
    remove_member,
    list_group_members,
    get_pubkey,
)
from persistence.rotation import rotate_public_key_and_share

def join_public_group(user_id: str, role: str = "member") -> int:
    """
    Adds the user to the 'public' group and rotates the group key.
    Returns the new public group version.
    """
    if not user_exists(user_id):
        raise ValueError("User must be registered before joining public group")

    # If you want to avoid a full rotation each join, you could just wrap current key for this user.
    # For clean semantics, rotate on membership change:
    # First ensure the user has a pubkey
    if not get_pubkey(user_id):
        raise ValueError("User has no pubkey; cannot join")

    # Provisional add (store placeholder wrapped_key now or after rotate).
    # Spec allows storing only wrapped keys; we’ll add after rotate so we persist the right wrapped key.
    # To avoid a race with concurrent joins, you could serialize joins with your server lock.

    # Rotate and share to all existing + the new member
    current = list_group_members("public")
    # Include the new member in the wrapping set
    if user_id not in current:
        current.append(user_id)

    new_version = rotate_public_key_and_share(current)
    # After rotate, members file already has wrapped keys for everyone (including this user)
    # We still want to persist the role entry for display/ACL purposes:
    # Find the newly wrapped key and persist the role entry for this user:
    from persistence.dir_json import get_wrapped_key, add_member as add_member_raw
    wrapped = get_wrapped_key("public", user_id)
    if not wrapped:
        # As a fallback, persist role anyway (without wrapped_key).
        add_member_raw("public", user_id, role, wrapped_key_b64u="")
    else:
        add_member_raw("public", user_id, role, wrapped_key_b64u=wrapped)

    return new_version

def leave_public_group(user_id: str) -> int:
    """
    Removes the user from 'public' and rotates the key.
    Returns the new public group version.
    """
    # Remove user first
    remove_member("public", user_id)
    # Rotate for remaining members
    remaining = list_group_members("public")
    new_version = rotate_public_key_and_share(remaining)
    return new_version
