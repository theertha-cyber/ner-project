"""`/metrics` is reachable without auth, counts requests, and carries no tenant label.

Verification rows 22, 23 and 24.

Row 24 is the one worth reading twice. `tenant_id` is available in context at every point
a metric is recorded, and adding it looks obviously useful — which is precisely why the
design forbids it here. Prometheus label cardinality multiplies by tenant count, and a
metric label is visible to everyone with dashboard access, which makes per-tenant
consumption figures commercially sensitive.

Row 24 is scoped to the families *this* change declares, enumerated in
`FOUNDATION_FAMILIES` below. The workload-instrumentation change adds five families that
carry `tenant_id` deliberately, governed by `TENANT_LABEL_ALLOWLIST` in
`src/shared/observability/domain_metrics.py` and enforced by
`tests/shared/test_domain_metrics_declarations.py`. A blanket scan of every line on the
endpoint would go red the moment those land, and the tempting repair is to weaken the
assertion rather than to scope it — so it is scoped here, once, deliberately.
"""

import re

import httpx
import pytest

pytestmark = [pytest.mark.verification]

# Two services rather than one, per the evidence requirement for row 22 — a single app
# would not catch a service whose exempt-path list was missed.
SERVICES = ("annotation_service", "analytics_service")


def _app(service):
    import importlib

    return importlib.import_module(f"src.{service}.main").app


async def _get(app, path, headers=None):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(path, headers=headers or {})


def _sample_lines(body):
    return [line for line in body.splitlines() if line and not line.startswith("#")]


# The families `observability-foundation` itself puts on the endpoint. Row 24 is asserted
# against these by name, not against every line, so that a later change adding an
# allowlisted tenant-labelled family does not turn this assertion red and invite weakening
# it. Anything added here must be a family this change owns.
FOUNDATION_FAMILIES = (
    "http_requests_total",
    "http_request_duration_seconds",
    "ner_db_connections_in_use",
)


def _foundation_sample_lines(body):
    return [
        line
        for line in _sample_lines(body)
        if any(line.startswith(family) for family in FOUNDATION_FAMILIES)
    ]


class TestTheEndpointResponds:
    """Row 22."""

    @pytest.mark.parametrize("service", SERVICES)
    async def test_metrics_returns_200_without_an_authorization_header(self, service):
        response = await _get(_app(service), "/metrics")

        assert response.status_code == 200, (
            "a scraper holds no JWT; requiring one makes the metrics unscrapeable"
        )

    @pytest.mark.parametrize("service", SERVICES)
    async def test_the_body_is_prometheus_text_exposition(self, service):
        response = await _get(_app(service), "/metrics")

        assert response.headers["content-type"].startswith("text/plain")
        assert "# HELP" in response.text
        assert "# TYPE" in response.text

    @pytest.mark.parametrize("service", SERVICES)
    async def test_the_red_families_are_exposed(self, service):
        body = (await _get(_app(service), "/metrics")).text

        assert "http_requests_total" in body
        assert "http_request_duration_seconds" in body

    @pytest.mark.parametrize("service", SERVICES)
    async def test_the_database_gauge_carries_a_real_sample(self, service):
        """Asserting the family *name* appears is not enough — it matches the `# HELP`
        line, which prometheus_client emits for a family with no samples at all.

        That is not hypothetical. The first implementation read `pool.size()` and
        `pool.checkedout()`; every service builds its engine with `NullPool`, which
        implements neither, so both families were declared on the endpoint and never once
        carried a value. The endpoint looked correct and the dashboard would have been
        permanently empty.
        """
        body = (await _get(_app(service), "/metrics")).text

        samples = [
            line
            for line in _sample_lines(body)
            if line.startswith("ner_db_connections_in_use")
        ]
        assert samples, (
            "ner_db_connections_in_use has no sample — a declared-but-empty family is "
            "worse than an absent one, because nothing on the endpoint says it is missing"
        )
        assert 'pool_class="' in samples[0], (
            "the pool class is what makes the number interpretable: 2 in use means "
            "something different under NullPool than under QueuePool"
        )


class TestRequestMetricsIncrement:
    """Row 23 — two readings either side of a served request."""

    async def test_the_counter_rises_across_a_served_request(self):
        app = _app("annotation_service")

        def _health_count(body):
            for line in _sample_lines(body):
                if line.startswith('http_requests_total{handler="/health"'):
                    return float(line.rsplit(" ", 1)[1])
            return 0.0

        before = _health_count((await _get(app, "/metrics")).text)
        await _get(app, "/health")
        after = _health_count((await _get(app, "/metrics")).text)

        assert after > before


class TestNoTenantLabel:
    """Row 24 — every label set, on every family this change declares, on every service."""

    @pytest.mark.parametrize("service", SERVICES)
    async def test_no_foundation_family_carries_a_tenant_label(self, service):
        body = (await _get(_app(service), "/metrics")).text

        offenders = [
            line
            for line in _foundation_sample_lines(body)
            if "tenant_id=" in line
        ]
        assert offenders == [], (
            "a tenant label multiplies cardinality by tenant count and discloses "
            f"per-tenant consumption to everyone with dashboard access: {offenders[:3]}"
        )

    @pytest.mark.parametrize("service", SERVICES)
    async def test_no_foundation_family_carries_a_tenant_slug_either(self, service):
        offenders = [
            line
            for line in _foundation_sample_lines((await _get(_app(service), "/metrics")).text)
            if "tenant_slug=" in line or re.search(r"[{,]tenant=", line)
        ]
        assert offenders == [], offenders[:3]

    @pytest.mark.parametrize("service", SERVICES)
    async def test_the_enumerated_families_are_actually_present(self, service):
        """The scope above is only meaningful if the names in it match real families.

        A typo in `FOUNDATION_FAMILIES` would silently reduce the assertion above to
        checking nothing at all, which is the exact failure mode narrowing a scan invites.
        """
        body = (await _get(_app(service), "/metrics")).text
        present = {
            family
            for family in FOUNDATION_FAMILIES
            for line in _sample_lines(body)
            if line.startswith(family)
        }

        assert present == set(FOUNDATION_FAMILIES), (
            "families named in the scope but absent from the endpoint: "
            f"{sorted(set(FOUNDATION_FAMILIES) - present)}"
        )
