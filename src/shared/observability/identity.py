"""Opaque user identity for telemetry.

Support needs to follow one person's session across a trace; nobody reading the log
store needs to know who that person is. A keyed hash gives the first without the second.

The key is a pepper held only in the environment (`NER_TELEMETRY_PEPPER`, no default —
see `Settings.telemetry_pepper`). An unkeyed digest would be reversible by enumeration
over a tenant's user list, which would put raw identity back into a store with broader
read access than the database.

Rotating the pepper breaks correlation of one user across the rotation. That is a
privacy property, not a defect: correlation windows are shorter than log retention.
"""

import hashlib
import hmac
from typing import Any

from src.shared.config import settings

# 64 bits of digest. Collision probability stays negligible at platform user counts,
# and a short value keeps the field cheap in every record it appears on.
_HASH_LENGTH = 16


def hash_user_id(user_id: Any | None) -> str | None:
    """HMAC-SHA256 of the user identifier under the configured pepper, truncated.

    Returns `None` for an absent identifier — an unauthenticated request or a
    widget-key session has no user, and hashing the empty string would fabricate one
    shared identity for all of them.
    """
    if user_id is None:
        return None
    raw = str(user_id)
    if not raw:
        return None
    digest = hmac.new(
        settings.telemetry_pepper.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:_HASH_LENGTH]
