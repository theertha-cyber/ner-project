import pytest
import pytest_asyncio
from sqlalchemy import text


def _run_tenant_schema_ddl(conn, ddl_template: str):
    conn.execute(text(ddl_template.format(schema="tenant_template")))
    result = conn.execute(text("SELECT id FROM public.tenants"))
    for row in result:
        tid = row[0]
        schema = f"tenant_{tid.replace('-', '_')}"
        conn.execute(text(ddl_template.format(schema=schema)))


@pytest.mark.asyncio
class TestApplyToAllTenantSchemas:

    async def test_new_column_propagates_to_existing_tenant(self, engine, setup_database):
        async with engine.begin() as conn:
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS tenant_test_tenant"))
            await conn.execute(text(
                "CREATE TABLE tenant_test_tenant.test_table "
                "(LIKE tenant_template.training_jobs "
                "INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES)"
            ))
        async with engine.begin() as conn:
            _run_tenant_schema_ddl(
                conn,
                "ALTER TABLE {schema}.test_table ADD COLUMN IF NOT EXISTS foo VARCHAR",
            )
        async with engine.begin() as conn:
            tmpl_cols = await conn.execute(
                text("SELECT column_name FROM information_schema.columns "
                     "WHERE table_schema = 'tenant_template' AND table_name = 'test_table'")
            )
            tmpl_names = {r[0] for r in tmpl_cols.fetchall()}
            assert "foo" in tmpl_names
            tenant_cols = await conn.execute(
                text("SELECT column_name FROM information_schema.columns "
                     "WHERE table_schema = 'tenant_test_tenant' AND table_name = 'test_table'")
            )
            tenant_names = {r[0] for r in tenant_cols.fetchall()}
            assert "foo" in tenant_names

    async def test_inactive_tenant_schema_still_updated(self, engine, setup_database):
        async with engine.begin() as conn:
            await conn.execute(text(
                "INSERT INTO public.tenants (id, name, slug, status) "
                "VALUES ('inactive-tenant', 'Inactive', 'inactive', 'inactive') "
                "ON CONFLICT (id) DO NOTHING"
            ))
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS tenant_inactive_tenant"))
            await conn.execute(text(
                "CREATE TABLE tenant_inactive_tenant.test_table "
                "(LIKE tenant_template.training_jobs "
                "INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES)"
            ))
        async with engine.begin() as conn:
            _run_tenant_schema_ddl(
                conn,
                "ALTER TABLE {schema}.test_table ADD COLUMN IF NOT EXISTS bar VARCHAR",
            )
        async with engine.begin() as conn:
            inactive_cols = await conn.execute(
                text("SELECT column_name FROM information_schema.columns "
                     "WHERE table_schema = 'tenant_inactive_tenant' AND table_name = 'test_table'")
            )
            names = {r[0] for r in inactive_cols.fetchall()}
            assert "bar" in names

    async def test_re_running_ddl_is_no_op(self, engine, setup_database):
        async with engine.begin() as conn:
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS tenant_noop_tenant"))
            await conn.execute(text(
                "CREATE TABLE tenant_noop_tenant.test_table "
                "(LIKE tenant_template.training_jobs "
                "INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES)"
            ))
        async with engine.begin() as conn:
            _run_tenant_schema_ddl(
                conn,
                "ALTER TABLE {schema}.test_table ADD COLUMN IF NOT EXISTS baz VARCHAR",
            )
            _run_tenant_schema_ddl(
                conn,
                "ALTER TABLE {schema}.test_table ADD COLUMN IF NOT EXISTS baz VARCHAR",
            )
        async with engine.begin() as conn:
            tmpl_cols = await conn.execute(
                text("SELECT column_name FROM information_schema.columns "
                     "WHERE table_schema = 'tenant_template' AND table_name = 'test_table'")
            )
            assert "baz" in {r[0] for r in tmpl_cols.fetchall()}
            tenant_cols = await conn.execute(
                text("SELECT column_name FROM information_schema.columns "
                     "WHERE table_schema = 'tenant_noop_tenant' AND table_name = 'test_table'")
            )
            assert "baz" in {r[0] for r in tenant_cols.fetchall()}


@pytest.mark.asyncio
class TestRemediationMigration:

    async def test_backfill_adds_error_message_to_template_and_tenants(self, engine, setup_database):
        async with engine.begin() as conn:
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS tenant_backfill_tenant"))
            await conn.execute(text(
                "CREATE TABLE tenant_backfill_tenant.training_jobs "
                "(LIKE tenant_template.training_jobs "
                "INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES)"
            ))
        async with engine.begin() as conn:
            _run_tenant_schema_ddl(
                conn,
                "ALTER TABLE {schema}.training_jobs ADD COLUMN IF NOT EXISTS error_message TEXT",
            )
        async with engine.begin() as conn:
            for schema in ("tenant_template", "tenant_backfill_tenant"):
                cols = await conn.execute(
                    text("SELECT column_name FROM information_schema.columns "
                         f"WHERE table_schema = '{schema}' AND table_name = 'training_jobs'")
                )
                names = {r[0] for r in cols.fetchall()}
                assert "error_message" in names, f"{schema}.training_jobs missing error_message"

    async def test_already_matching_tenant_unaffected(self, engine, setup_database):
        async with engine.begin() as conn:
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS tenant_match_tenant"))
            await conn.execute(text(
                "CREATE TABLE tenant_match_tenant.training_jobs "
                "(LIKE tenant_template.training_jobs "
                "INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES)"
            ))
        async with engine.begin() as conn:
            _run_tenant_schema_ddl(
                conn,
                "ALTER TABLE {schema}.training_jobs ADD COLUMN IF NOT EXISTS error_message TEXT",
            )
        verify = await conn.execute(
            text("SELECT column_name FROM information_schema.columns "
                 "WHERE table_schema = 'tenant_template' AND table_name = 'training_jobs' "
                 "AND column_name = 'error_message'")
        )
        assert verify.fetchone() is not None
        verify2 = await conn.execute(
            text("SELECT column_name FROM information_schema.columns "
                 "WHERE table_schema = 'tenant_match_tenant' AND table_name = 'training_jobs' "
                 "AND column_name = 'error_message'")
        )
        assert verify2.fetchone() is not None
        first_run_col_count = await conn.execute(
            text("SELECT COUNT(*) FROM information_schema.columns "
                 "WHERE table_schema = 'tenant_template' AND table_name = 'training_jobs'")
        )
        first_count = first_run_col_count.scalar()
        _run_tenant_schema_ddl(
            conn,
            "ALTER TABLE {schema}.training_jobs ADD COLUMN IF NOT EXISTS error_message TEXT",
        )
        second_run_col_count = await conn.execute(
            text("SELECT COUNT(*) FROM information_schema.columns "
                 "WHERE table_schema = 'tenant_template' AND table_name = 'training_jobs'")
        )
        assert second_run_col_count.scalar() == first_count
