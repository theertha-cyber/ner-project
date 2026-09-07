"""The telemetry user hash correlates without identifying.

Verification row 16.

Support's first-order question is "which user hit this", and answering it across two
requests needs the same value both times. Nobody reading the log store needs to know who
that user is — so the value has to be stable under an unchanged pepper and must not carry
the identifier or the email it was derived from.
"""

import pytest

from src.shared.config import settings
from src.shared.observability.identity import hash_user_id

pytestmark = [pytest.mark.verification]

USER_ID = "8f14e45f-ea1c-4b0a-9d3e-2b7c6a1f0d55"
EMAIL = "priya.raman@example.com"


class TestTheSameUserIsCorrelatable:
    def test_two_calls_under_one_pepper_agree(self):
        """Row 16 — two requests from one user produce equal hashes."""
        assert hash_user_id(USER_ID) == hash_user_id(USER_ID)

    def test_different_users_differ(self):
        assert hash_user_id(USER_ID) != hash_user_id("a-different-user")

    def test_rotating_the_pepper_changes_the_hash(self, monkeypatch):
        """Correlation across a rotation breaks by design — the design records this as a
        privacy property, not a defect. Pinning it here stops a later change from
        "fixing" it by dropping the pepper."""
        before = hash_user_id(USER_ID)
        monkeypatch.setattr(settings, "telemetry_pepper", "a-rotated-pepper", raising=True)
        assert hash_user_id(USER_ID) != before


class TestTheHashRevealsNothing:
    def test_output_does_not_contain_the_raw_identifier(self):
        digest = hash_user_id(USER_ID)
        assert USER_ID not in digest
        # Nor any recognisable run of it: a "hash" that prefixed the id would pass a
        # naive substring check on the whole value.
        assert not any(part and part in digest for part in USER_ID.split("-"))

    def test_output_does_not_contain_an_email(self):
        digest = hash_user_id(EMAIL)
        assert EMAIL not in digest
        assert "@" not in digest
        assert "example" not in digest

    def test_output_is_short_hex(self):
        digest = hash_user_id(USER_ID)
        assert len(digest) == 16
        assert all(character in "0123456789abcdef" for character in digest)


class TestAbsentUser:
    @pytest.mark.parametrize("value", [None, ""])
    def test_no_user_hashes_to_none(self, value):
        """An unauthenticated request and a widget-key session have no user. Hashing the
        empty string would give all of them one shared identity that looks like a real
        user."""
        assert hash_user_id(value) is None
