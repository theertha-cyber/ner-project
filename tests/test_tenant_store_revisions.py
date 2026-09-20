"""Verification for `src/shared/tenant_store/revisions` and `apply.py` (ADR-017,
Design D5) — scenario #18: re-applying a revision is a no-op.

There are no shipped revisions yet (`tenant_template` at head 043 is fully captured by
`baseline.py` alone), so this exercises the interface itself with a throwaway revision
module registered for the duration of the test, plus `apply.apply()`'s own
idempotency (baseline + zero revisions, applied twice).
"""

import types
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from src.shared.tenant_store import apply as apply_module
from src.shared.tenant_store import revisions as revisions_module

DATABASE_URL = "postgresql://ner:ner@localhost:55432/ner_test"


@pytest.fixture
def engine():
    eng = create_engine(DATABASE_URL, poolclass=NullPool)
    yield eng
    eng.dispose()


@pytest.fixture
def scratch_schema(engine):
    schema = f"tenant_revtest_{uuid.uuid4().hex[:8]}"
    yield schema
    with engine.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))


def test_apply_baseline_twice_is_a_noop(engine, scratch_schema):
    with engine.begin() as conn:
        store_id_1, rev_1 = apply_module.apply(conn, scratch_schema, "revtest-tenant")
    with engine.begin() as conn:
        store_id_2, rev_2 = apply_module.apply(conn, scratch_schema, "revtest-tenant")

    assert store_id_1 == store_id_2
    assert rev_1 == rev_2


def test_reapplying_a_revision_is_a_noop(monkeypatch, engine, scratch_schema):
    """A throwaway revision module, registered for the duration of this test, applied
    twice to the same schema: no error, and the schema shape is unchanged."""
    fake_revision = types.ModuleType("src.shared.tenant_store.revisions._faketest")
    fake_revision.REVISION = 9999
    fake_revision.statements = lambda schema: [
        f"CREATE TABLE IF NOT EXISTS {schema}.revision_marker (id INTEGER PRIMARY KEY)"
    ]
    monkeypatch.setattr(revisions_module, "_discover", lambda: [fake_revision])

    with engine.begin() as conn:
        apply_module.apply(conn, scratch_schema, "revtest-tenant")
        apply_module.apply(conn, scratch_schema, "revtest-tenant")

    with engine.connect() as conn:
        revision = conn.execute(
            text(f"SELECT schema_revision FROM {scratch_schema}.platform_store_meta")
        ).scalar_one()
        table_count = conn.execute(
            text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = :s AND table_name = 'revision_marker'"
            ),
            {"s": scratch_schema},
        ).scalar_one()

    assert revision == 9999
    assert table_count == 1


def test_pending_revisions_filters_by_current_revision(monkeypatch):
    low = types.SimpleNamespace(REVISION=1)
    high = types.SimpleNamespace(REVISION=2)
    monkeypatch.setattr(revisions_module, "_discover", lambda: [low, high])

    assert revisions_module.pending_revisions(0) == [low, high]
    assert revisions_module.pending_revisions(1) == [high]
    assert revisions_module.pending_revisions(2) == []


def test_latest_revision_defaults_to_baseline_when_no_revisions_exist(monkeypatch):
    monkeypatch.setattr(revisions_module, "_discover", lambda: [])
    assert revisions_module.latest_revision() == revisions_module.BASELINE_REVISION


def test_revision_003_adds_attachments_column_and_is_idempotent(engine, scratch_schema):
    """Revision 003 is what `alembic/versions/055_chat_messages_attachments.py`
    delegates to for its `upgrade()` DDL — this exercises it directly, applied
    twice, against a schema that already has `chat_messages` (via the baseline)."""
    with engine.begin() as conn:
        apply_module.apply(conn, scratch_schema, "revtest-tenant")
        apply_module.apply(conn, scratch_schema, "revtest-tenant")

    with engine.connect() as conn:
        column = conn.execute(
            text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_schema = :s AND table_name = 'chat_messages' "
                "AND column_name = 'attachments'"
            ),
            {"s": scratch_schema},
        ).scalar_one()
        revision = conn.execute(
            text(f"SELECT schema_revision FROM {scratch_schema}.platform_store_meta")
        ).scalar_one()

    assert column == "jsonb"
    assert revision == revisions_module.latest_revision()
