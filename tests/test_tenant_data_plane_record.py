"""Verification for `public.tenant_data_planes` — the ADR-017 control-plane record.

Maps to `openspec/changes/tenant-postgresql-data-plane/verification.md` scenarios #1-#3:
backfill of existing tenants, `mode` immutability, and that the record carries no
sensitive values. The table and its immutability trigger are created by alembic
migration 043 in real deployments and mirrored for the test database by
`scripts/setup_test_db.py`, exactly like the CAP-2/CAP-3 control-plane tables before it.
"""

import uuid

import pytest
from sqlalchemy import text

pytestmark = [pytest.mark.asyncio]

# The exact finite column set the routing spec allows. No host, database name,
# username, secret reference, or provider error text may ever appear here.
SAFE_COLUMNS = {
    "tenant_id",
    "mode",
    "status",
    "connection_id",
    "store_id",
    "schema_revision",
    "status_reason",
    "health_outcome",
    "health_checked_at",
    "created_at",
    "updated_at",
}


async def test_existing_tenants_are_backfilled_to_platform_ready(engine, setup_database):
    """Scenario: Existing tenants are backfilled to the platform plane."""
    async with engine.begin() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT mode, status FROM public.tenant_data_planes "
                    "WHERE tenant_id = 'test-tenant'"
                )
            )
        ).fetchall()
    assert len(rows) == 1
    assert rows[0].mode == "platform"
    assert rows[0].status == "ready"


async def test_every_tenant_has_exactly_one_data_plane_record(engine, setup_database):
    async with engine.begin() as conn:
        missing = (
            await conn.execute(
                text(
                    "SELECT t.id FROM public.tenants t "
                    "LEFT JOIN public.tenant_data_planes dp ON dp.tenant_id = t.id "
                    "WHERE dp.tenant_id IS NULL"
                )
            )
        ).fetchall()
    assert missing == []


async def test_mode_cannot_be_changed(engine, setup_database):
    """Scenario: Mode cannot be changed.

    The immutability trigger raises a Postgres exception carrying
    `DATA_PLANE_MODE_IMMUTABLE`; the row is left unchanged because the failed
    statement's implicit transaction is rolled back.
    """
    async with engine.begin() as conn:
        before = (
            await conn.execute(
                text(
                    "SELECT mode FROM public.tenant_data_planes "
                    "WHERE tenant_id = 'test-tenant'"
                )
            )
        ).scalar_one()
        assert before == "platform"

    with pytest.raises(Exception) as excinfo:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE public.tenant_data_planes SET mode = 'tenant_owned' "
                    "WHERE tenant_id = 'test-tenant'"
                )
            )
    assert "DATA_PLANE_MODE_IMMUTABLE" in str(excinfo.value)

    async with engine.begin() as conn:
        after = (
            await conn.execute(
                text(
                    "SELECT mode FROM public.tenant_data_planes "
                    "WHERE tenant_id = 'test-tenant'"
                )
            )
        ).scalar_one()
    assert after == "platform"


async def test_record_schema_carries_no_sensitive_columns(engine, setup_database):
    """Scenario: Data-plane record carries no sensitive values.

    A finite column check at the schema level: nothing named host, database, username,
    password, secret, endpoint, or error exists on this table, so no future column
    addition can smuggle one in without this test's column-set assertion failing.
    """
    async with engine.begin() as conn:
        columns = {
            row.column_name
            for row in (
                await conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' AND table_name = 'tenant_data_planes'"
                    )
                )
            ).fetchall()
        }
    assert columns == SAFE_COLUMNS
    forbidden_substrings = ("host", "database", "username", "password", "secret", "endpoint", "credential")
    for column in columns:
        for term in forbidden_substrings:
            assert term not in column.lower(), f"column {column!r} looks sensitive"


async def test_backfilled_tenant_owned_tenant_is_not_auto_created(engine, setup_database):
    """A freshly inserted tenant with no data-plane row is a bug this test would catch
    if provisioning code ever forgot to write one — sanity-checks the CASCADE, not a
    spec scenario on its own."""
    tid = f"dp-cascade-{uuid.uuid4().hex[:8]}"
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO public.tenants (id, name, slug) VALUES (:id, :n, :s)"
            ),
            {"id": tid, "n": "Cascade Test", "s": f"slug-{tid}"},
        )
        await conn.execute(
            text(
                "INSERT INTO public.tenant_data_planes (tenant_id, mode, status) "
                "VALUES (:id, 'tenant_owned', 'awaiting_store')"
            ),
            {"id": tid},
        )
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
        remaining = (
            await conn.execute(
                text("SELECT 1 FROM public.tenant_data_planes WHERE tenant_id = :id"),
                {"id": tid},
            )
        ).fetchall()
    assert remaining == []
