"""Local Compose delivery evidence (CAP-6, ADR-014).

Hermetic by design: every assertion inspects files or in-memory fakes, so
this module passes with no running stack, no database, and no Azure
resources. Live stack evidence (``docker compose ps``, ``/health``,
``alembic heads``, ``telemetry_scan.py``) is captured separately and
referenced from ``verification.md``.

Covers ``local-compose-data-source-delivery`` scenarios:
- Local rolling deployment succeeds (compose sequencing/readiness contract).
- Additive migration compatibility holds (chain + additive-only).
- Operational telemetry is safe and declared (finite-label contract).
- Dev fixture direct-query performance check (10 sequential fixture
  queries, p95 <= 10 s, 0 errors — a dev operating target, not a
  production SLO).

Live Azure verification stays deferred per run provisioning; the
``FixtureExternalDatabase`` below is the approved stand-in.
"""

import math
import pathlib
import re
import time

import pytest
import yaml

pytestmark = [pytest.mark.verification]

ROOT = pathlib.Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "alembic" / "versions"
COMPOSE = ROOT / "docker-compose.yml"

CHAIN = ["039", "040", "041", "042", "043"]

EXPECTED_LABELS = {
    "ner_data_source_lifecycle_total": {
        "provider": {"azure_blob", "azure_postgresql", "other"},
        "action": {"create", "update", "test", "activate", "pause",
                   "replace", "retire", "other"},
        "outcome": {"success", "rejected", "error", "other"},
    },
    "ner_data_source_tests_total": {
        "provider": {"azure_blob", "azure_postgresql", "other"},
        "outcome": {"passed", "failed", "not_run", "other"},
        "reason": {"none", "validation_failed", "secret_unavailable",
                   "connection_failed", "tls_validation_failed",
                   "authorization_failed", "prerequisite_missing", "other"},
    },
    "ner_blob_sync_total": {
        "trigger": {"manual", "scheduled", "retry", "catchup", "other"},
        "outcome": {"succeeded", "failed", "blocked", "lease_held", "other"},
    },
    "ner_external_pg_query_total": {
        "outcome": {"success", "drift_blocked", "validation_rejected",
                    "execution_failed", "other"},
        "reason": {"none", "clean", "drift_mismatch",
                   "metadata_unavailable", "fingerprint_failure",
                   "not_single_select", "write_or_ddl",
                   "multiple_statements", "subquery", "cte", "union_or_setop",
                   "window_function", "unapproved_relation",
                   "unapproved_column", "unapproved_join",
                   "unapproved_function", "inline_literal", "role_switch",
                   "other"},
    },
}

# Services carrying CAP-2 through CAP-4 runtime increments; every one must
# gate on db-init so migrations land before the new code serves traffic.
SEQUENCED_SERVICES = [
    "gateway", "document_service", "extraction_service",
    "annotation_service", "training_service", "chat_api",
    "analytics_service", "celery_worker", "celery_worker_extraction",
]


def _revisions(versions_dir: pathlib.Path = VERSIONS) -> dict[str, str | None]:
    found: dict[str, str | None] = {}
    for path in versions_dir.glob("*.py"):
        src = path.read_text(encoding="utf-8")
        rev = re.search(r"^revision\s*=\s*[\"']([^\"']+)[\"']",
                        src, re.MULTILINE)
        down = re.search(r"^down_revision\s*=\s*[\"']([^\"']+)[\"']",
                         src, re.MULTILINE)
        if rev:
            if down is None and re.search(r"^down_revision\s*=\s*None",
                                          src, re.MULTILINE) is None \
                    and re.search(r"^down_revision\s*=", src,
                                  re.MULTILINE) is not None:
                raise AssertionError(
                    f"{path.name}: non-string down_revision; "
                    "branched migrations need an explicit decision")
            found[rev.group(1)] = down.group(1) if down else None
    return found


def _chain_heads(revs: dict[str, str | None]) -> list[str]:
    referenced = {d for d in revs.values() if d is not None}
    return [r for r in revs if r not in referenced]


def _write_rev(directory: pathlib.Path, rev: str, down: str | None) -> None:
    down_line = f'down_revision = "{down}"' if down else "down_revision = None"
    (directory / f"{rev}_test.py").write_text(
        f'revision = "{rev}"\n{down_line}\n'
        "def upgrade():\n    pass\ndef downgrade():\n    pass\n",
        encoding="utf-8")


def test_chain_check_rejects_branch_and_broken_link(tmp_path):
    branched = tmp_path / "branched"
    branched.mkdir()
    _write_rev(branched, "039", None)
    _write_rev(branched, "040", "039")
    _write_rev(branched, "041x", "040")
    _write_rev(branched, "041y", "040")
    assert sorted(_chain_heads(_revisions(branched))) == ["041x", "041y"]

    broken = tmp_path / "broken"
    broken.mkdir()
    _write_rev(broken, "039", None)
    _write_rev(broken, "040", "038-missing")
    revs = _revisions(broken)
    assert revs["040"] == "038-missing"
    assert "038-missing" not in revs


def test_migration_chain_is_linear_with_single_head():
    revs = _revisions()
    for want, prev in zip(CHAIN, [None] + CHAIN[:-1]):
        assert want in revs, f"revision {want} missing from chain"
        if prev is None:
            continue
        assert revs[want] == prev, \
            f"revision {want} links to {revs[want]!r}, expected {prev!r}"
    referenced = {d for d in revs.values() if d is not None}
    heads = _chain_heads(revs)
    assert heads == [CHAIN[-1]], f"expected single head {CHAIN[-1]!r}, got {heads}"
    assert sorted(referenced - set(revs)) == [], \
        f"broken links: {sorted(referenced - set(revs))}"


def test_data_source_revisions_are_additive_only():
    destructive = re.compile(r"(?i)drop\s+(table|column)|op\.drop_")
    for rev in CHAIN[1:]:
        matches = list(VERSIONS.glob(f"{rev}_*.py"))
        assert len(matches) == 1, f"expected one file for {rev}"
        src = matches[0].read_text(encoding="utf-8")
        upgrade = src.split("def upgrade", 1)[1].split("def downgrade", 1)[0]
        hits = destructive.findall(upgrade)
        assert not hits, f"{rev} upgrade() is not additive-only: {hits}"


def _compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def test_db_init_applies_migrations_before_app_services():
    services = _compose()["services"]
    init_cmd = str(services["db-init"]["command"])
    assert "alembic upgrade head" in init_cmd
    assert services["db-init"].get("restart") == "no"


def test_sequenced_services_gate_on_db_init_and_healthy_deps():
    services = _compose()["services"]
    for name in SEQUENCED_SERVICES:
        assert name in services, f"{name} missing from compose"
        deps = services[name].get("depends_on", {})
        assert deps.get("db-init", {}).get("condition") == \
            "service_completed_successfully", \
            f"{name} must wait for db-init"
        assert deps.get("postgres-test", {}).get("condition") == \
            "service_healthy", f"{name} must wait for healthy postgres"


def test_infrastructure_healthchecks_exist():
    services = _compose()["services"]
    assert "pg_isready" in str(
        services["postgres-test"]["healthcheck"]["test"])
    assert "redis-cli" in str(services["redis"]["healthcheck"]["test"])


def test_app_service_host_ports_are_unique():
    services = _compose()["services"]
    seen: dict[str, str] = {}
    for name in SEQUENCED_SERVICES + ["model_serving", "portal"]:
        for mapping in services[name].get("ports", []):
            host = str(mapping).split(":")[0].strip('"')
            assert host not in seen, \
                f"host port {host} shared by {seen[host]} and {name}"
            seen[host] = name


def test_terminal_outcome_telemetry_is_declared_and_finite():
    from src.shared.observability import domain_metrics as dm

    for family_name, labels in EXPECTED_LABELS.items():
        assert family_name in dm.FAMILIES, \
            f"metric family {family_name} is not declared"
        family = dm.FAMILIES[family_name]
        assert "tenant_id" not in family.label_names, \
            f"{family_name} must not carry tenant_id"
        actual = {label.name: set(label.values)
                  for label in family.labels}
        assert actual == labels, \
            f"{family_name} label drift: {actual!r} != {labels!r}"


async def test_fixture_direct_query_perf_dev_target():
    """10 sequential drift-gated fixture queries: 0 errors, p95 <= 10 s.

    Dev operating target only (TDD NFR-PERF-001); not a production SLO.
    ``FixtureExternalDatabase`` is the approved Azure stand-in while live
    verification stays deferred.
    """
    from src.shared.external_postgres import connector
    from src.shared.external_postgres import drift as drift_mod
    from src.shared.external_postgres.contract import canonical_fingerprint

    canonical = {
        "version": 1,
        "relations": {
            "orders": {"columns": ["id", "customer_id", "total"],
                       "primary_key": "id"},
            "customers": {"columns": ["id", "name"], "primary_key": "id"},
        },
        "joins": [{"left": "orders", "right": "customers",
                   "left_key": "customer_id", "right_key": "id"}],
    }
    contract = {
        "canonical": canonical,
        "fingerprint": canonical_fingerprint(canonical["relations"],
                                             canonical["joins"]),
    }
    statement = (
        "SELECT c.name, COUNT(o.id) FROM orders AS o "
        "JOIN customers AS c ON o.customer_id = c.id "
        "WHERE c.name = %(name)s GROUP BY c.name"
    )
    database = drift_mod.FixtureExternalDatabase(
        metadata={"orders": ["id", "customer_id", "total"],
                  "customers": ["id", "name"]},
        rows=[{"name": "acme", "count": 3}],
    )

    durations: list[float] = []
    errors = 0
    for _ in range(10):
        start = time.perf_counter()
        try:
            result = await connector.execute_external_query(
                database, contract, statement, {"name": "acme"})
            assert result["row_count"] == 1
        except Exception:
            errors += 1
        durations.append(time.perf_counter() - start)

    assert errors == 0, f"{errors}/10 fixture queries failed"
    ordered = sorted(durations)
    p95 = ordered[min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1)]
    assert p95 <= 10.0, f"fixture p95 {p95:.3f}s exceeds 10 s dev target"
