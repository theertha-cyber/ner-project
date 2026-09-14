"""The four counters Exit Gate 3 names: mismatch, auth failure, rate-limit rejection.

Verification rows 27, 28, 29, 32 and 33.

Every assertion here reads the counter's own value either side of the event rather than
scraping `/metrics` and matching a substring. A substring match on the exposition text
passes against the `# HELP` line of a family that has never carried a sample, which is the
failure mode the foundation change hit with the database pool gauges.
"""

import logging

import pytest
from prometheus_client import REGISTRY

from src.shared.observability import domain_metrics as dm

pytestmark = [pytest.mark.verification]


def _value(family: dm.Family, **labels) -> float:
    """The current value of one series, or 0 when it has never been recorded."""
    name = family.name if family.kind != "counter" else family.name
    resolved = {label.name: label.coerce(labels.get(label.name)) for label in family.labels}
    value = REGISTRY.get_sample_value(name, resolved or None)
    return float(value or 0.0)


class TestTenantMismatchIsCounted:
    """Rows 27, 28 and 29."""

    def test_constructing_the_error_increments_the_counter(self, caplog):
        """Row 27. The counter lives in the constructor, so *raising* is not required —
        which is the whole point of design Decision 4: a future raise site cannot forget.
        """
        from src.shared.exceptions import TenantMismatchError

        before = _value(dm.TENANT_MISMATCH)
        with caplog.at_level(logging.WARNING):
            TenantMismatchError()
        after = _value(dm.TENANT_MISMATCH)

        assert after == before + 1

    def test_the_rejection_also_produces_a_warning_record(self, caplog):
        """Row 27's second clause. The correlation fields are attached by the foundation's
        logging filter rather than by the call site, so what is asserted here is that a
        record at WARNING or above exists for the filter to decorate."""
        from src.shared.exceptions import TenantMismatchError

        with caplog.at_level(logging.WARNING, logger="src.shared.exceptions"):
            TenantMismatchError()

        records = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert records, "a cross-tenant attempt must not be logged below WARNING"
        assert any("tenant_mismatch" in r.getMessage() for r in records)

    def test_a_mismatch_and_an_invalid_token_increment_different_counters(self):
        """Row 28 — an attempted cross-tenant access is not an ordinary permission denial,
        and a single `auth_failures` family would make the two indistinguishable."""
        from src.shared.auth import decode_token
        from src.shared.exceptions import AuthError, TenantMismatchError

        mismatch_before = _value(dm.TENANT_MISMATCH)
        auth_before = _value(dm.AUTH_FAILURES, reason="malformed_token")

        TenantMismatchError()
        with pytest.raises(AuthError):
            decode_token("not-a-token")

        assert _value(dm.TENANT_MISMATCH) == mismatch_before + 1
        assert _value(dm.AUTH_FAILURES, reason="malformed_token") == auth_before + 1

    def test_the_mismatch_counter_declares_no_tenant_label(self):
        """Row 29 — asserted against the declaration, which is where the label would be
        added, rather than against an endpoint that only shows families already recorded."""
        assert dm.TENANT_MISMATCH.label_names == ()
        assert "ner_tenant_mismatch_total" not in dm.TENANT_LABEL_ALLOWLIST


class TestAuthFailuresAreCountedByReason:
    """Row 32."""

    def test_a_missing_bearer_header_increments_under_its_own_reason(self):
        before = _value(dm.AUTH_FAILURES, reason="missing_header")
        dm.record_auth_failure("missing_header")

        assert _value(dm.AUTH_FAILURES, reason="missing_header") == before + 1

    def test_a_malformed_token_and_an_expired_token_are_distinct_reasons(self):
        from datetime import datetime, timedelta, timezone

        from jose import jwt

        from src.shared.config import settings
        from src.shared.exceptions import AuthError

        from src.shared.auth import decode_token

        malformed_before = _value(dm.AUTH_FAILURES, reason="malformed_token")
        expired_before = _value(dm.AUTH_FAILURES, reason="expired_token")

        with pytest.raises(AuthError):
            decode_token("plainly.not.ajwt")

        expired = jwt.encode(
            {
                "sub": "u",
                "exp": datetime.now(timezone.utc) - timedelta(hours=1),
                "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            },
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(AuthError):
            decode_token(expired)

        assert _value(dm.AUTH_FAILURES, reason="malformed_token") == malformed_before + 1
        assert _value(dm.AUTH_FAILURES, reason="expired_token") == expired_before + 1

    def test_a_token_signed_with_the_wrong_key_is_its_own_reason(self):
        from jose import jwt

        from src.shared.auth import decode_token
        from src.shared.config import settings
        from src.shared.exceptions import AuthError

        before = _value(dm.AUTH_FAILURES, reason="invalid_signature")
        forged = jwt.encode({"sub": "u"}, "a-different-secret-entirely", algorithm=settings.jwt_algorithm)

        with pytest.raises(AuthError):
            decode_token(forged)

        assert _value(dm.AUTH_FAILURES, reason="invalid_signature") == before + 1, (
            "a wave of signature failures is a key rotation or an attack; a wave of "
            "malformed tokens is a broken client — they must not share a series"
        )

    def test_no_token_fragment_reaches_any_label(self):
        """Row 32's second clause. The reason is drawn from the exception type, so there is
        no path by which token material could become a label — asserted by checking that
        the declared value set is closed and contains nothing token-shaped."""
        reason_label = dm.AUTH_FAILURES.labels[0]

        assert reason_label.values == dm.AUTH_FAILURE_REASONS
        assert all("." not in value and len(value) < 32 for value in reason_label.values)
        assert reason_label.coerce("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9") == dm.OTHER


class TestRateLimitRejectionsAreCounted:
    """Row 33."""

    def test_a_caller_over_its_limit_increments_the_rejection_counter(self):
        from src.chat_api.services.rate_limiter import SlidingWindowRateLimiter

        limiter = SlidingWindowRateLimiter()
        before = _value(dm.RATE_LIMIT_REJECTIONS, tenant_id="tenant-over-limit", scope="internal")

        allowed_first = limiter.check("internal:tenant-over-limit", limit=1, window=60)[0]
        allowed_second = limiter.check("internal:tenant-over-limit", limit=1, window=60)[0]

        assert allowed_first is True
        assert allowed_second is False
        assert (
            _value(dm.RATE_LIMIT_REJECTIONS, tenant_id="tenant-over-limit", scope="internal")
            == before + 1
        )

    def test_the_widget_scope_is_counted_separately_from_the_internal_one(self):
        from src.chat_api.services.rate_limiter import SlidingWindowRateLimiter

        limiter = SlidingWindowRateLimiter()
        before = _value(dm.RATE_LIMIT_REJECTIONS, tenant_id="tenant-scoped", scope="widget")

        limiter.check("widget:tenant-scoped", limit=1, window=60)
        limiter.check("widget:tenant-scoped", limit=1, window=60)

        assert (
            _value(dm.RATE_LIMIT_REJECTIONS, tenant_id="tenant-scoped", scope="widget")
            == before + 1
        )

    def test_the_family_is_on_the_tenant_allowlist(self):
        """The tenant label here is deliberate: a rejected request produces the least
        trace, so "which tenant is being throttled" is not answerable by joining one."""
        assert "ner_rate_limit_rejections_total" in dm.TENANT_LABEL_ALLOWLIST
