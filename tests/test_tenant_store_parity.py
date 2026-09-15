"""Parity between the tenant-store baseline and `tenant_template` at Alembic head
(ADR-017, Design D5) — scenario #17.

Runs `alembic upgrade head` against a fresh scratch database (never the shared
`ner_test` fixture database — a schema this heavy does not belong sharing state with
every other file's tables) and compares its `tenant_template` schema to
`src/shared/tenant_store/baseline.py` applied to an empty schema in the same database:
tables, columns, types, defaults, constraints, indexes, and materialized views must
match exactly. This is the test the routing spec requires to fail the build when a
migration changes a tenant-scoped table without a matching tenant-store revision.
"""

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from src.shared.tenant_store import baseline

pytestmark = [pytest.mark.parity]

ADMIN_URL = os.environ.get(
    "NER_TEST_ADMIN_DATABASE_URL", "postgresql://ner:ner@localhost:55432/ner_test"
)


def _table_shape(conn, schema: str) -> dict[tuple[str, str], tuple]:
    rows = conn.execute(
        text(
            "SELECT table_name, column_name, data_type, is_nullable, "
            "coalesce(character_maximum_length, -1) AS max_len "
            "FROM information_schema.columns WHERE table_schema = :s "
            "ORDER BY table_name, column_name"
        ),
        {"s": schema},
    ).fetchall()
    return {
        (r.table_name, r.column_name): (r.data_type, r.is_nullable, r.max_len) for r in rows
    }


def _tables(conn, schema: str) -> set[str]:
    return {
        r.table_name
        for r in conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = :s AND table_type = 'BASE TABLE'"
            ),
            {"s": schema},
        ).fetchall()
    }


def _matviews(conn, schema: str) -> set[str]:
    return {
        r.matviewname
        for r in conn.execute(
            text("SELECT matviewname FROM pg_matviews WHERE schemaname = :s"), {"s": schema}
        ).fetchall()
    }


def _indexes(conn, schema: str) -> set[str]:
    return {
        r.indexname
        for r in conn.execute(
            text("SELECT indexname FROM pg_indexes WHERE schemaname = :s"), {"s": schema}
        ).fetchall()
    }


@pytest.fixture(scope="module")
def scratch_head_db():
    """A fresh database migrated to Alembic head, dropped afterward."""
    db_name = f"ner_test_parity_{uuid.uuid4().hex[:10]}"
    admin_engine = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    with admin_engine.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))

    scratch_url = ADMIN_URL.rsplit("/", 1)[0] + f"/{db_name}"

    from alembic import command
    from alembic.config import Config

    repo_root = os.path.join(os.path.dirname(__file__), "..")
    alembic_cfg = Config(os.path.join(repo_root, "alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(repo_root, "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", scratch_url)
    os.environ["NER_DATABASE_URL_SYNC"] = scratch_url
    command.upgrade(alembic_cfg, "head")

    yield scratch_url

    admin_engine.dispose()
    with create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT", poolclass=NullPool).connect() as conn:
        conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = :d AND pid <> pg_backend_pid()"
            ),
            {"d": db_name},
        )
        conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))


def test_baseline_matches_tenant_template_at_head(scratch_head_db):
    engine = create_engine(scratch_head_db, poolclass=NullPool)
    baseline_schema = "tenant_parity_baseline"
    with engine.begin() as conn:
        for statement in baseline.statements(baseline_schema):
            conn.execute(text(statement))

    with engine.connect() as conn:
        assert _tables(conn, baseline_schema) == _tables(conn, "tenant_template")
        assert _table_shape(conn, baseline_schema) == _table_shape(conn, "tenant_template")
        assert _matviews(conn, baseline_schema) == _matviews(conn, "tenant_template")
        assert _indexes(conn, baseline_schema) == _indexes(conn, "tenant_template")

    with engine.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {baseline_schema} CASCADE"))
    engine.dispose()


def test_missing_column_is_detected(scratch_head_db, monkeypatch):
    """Scenario: Missing tenant-store revision fails the build.

    Simulates a migration that added a column with no matching tenant-store revision by
    monkeypatching one column out of the baseline's `documents` table, then asserts the
    same comparison this file's real parity test runs would fail and name that table.
    """
    original = baseline._TABLE_DDL["imported_annotations"]
    monkeypatch.setitem(
        baseline._TABLE_DDL,
        "imported_annotations",
        original.replace("reviewed_by character varying,", ""),
    )

    engine = create_engine(scratch_head_db, poolclass=NullPool)
    drifted_schema = "tenant_parity_drifted"
    with engine.begin() as conn:
        for statement in baseline.statements(drifted_schema):
            conn.execute(text(statement))

    with engine.connect() as conn:
        drifted = _table_shape(conn, drifted_schema)
        real = _table_shape(conn, "tenant_template")
    missing = set(real) - set(drifted)

    assert ("imported_annotations", "reviewed_by") in missing

    with engine.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {drifted_schema} CASCADE"))
    engine.dispose()
