"""Provision the least-privilege role that generated chat SQL executes under, then
smoke-check it against every tenant schema.

Grants are derived from `WHITELISTED_TABLES`, so this is the one place that has to run
after the whitelist changes or a tenant is added. Idempotent — safe to re-run.

Run before enabling `NER_SQL_EXECUTION_ROLE_ENABLED`:

    python scripts/provision_sql_execution_role.py
    python scripts/provision_sql_execution_role.py --check-only
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine

from src.chat_api.services.sql_execution_role import (
    list_tenant_schemas,
    provision_role,
    smoke_check_schema,
)
from src.shared.config import settings


def _async_dsn(dsn: str) -> str:
    if dsn.startswith("postgresql://"):
        return dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
    if dsn.startswith("postgresql+psycopg2://"):
        return dsn.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    return dsn


async def main(check_only: bool) -> int:
    role = settings.sql_execution_role_name
    engine = create_async_engine(_async_dsn(settings.database_url))
    failures: list[str] = []

    try:
        async with engine.begin() as conn:
            schemas = [s for s in await list_tenant_schemas(conn) if s != "tenant_template"]
            if not schemas:
                print("No tenant schemas found. Nothing to grant.")
                return 0
            if check_only:
                print(f"Skipping provisioning; checking role '{role}' as it stands.")
            else:
                await provision_role(conn, role, schemas)
                print(f"Provisioned role '{role}' over {len(schemas)} tenant schema(s).")

        # Each smoke check runs in its own connection so an aborted transaction from a
        # missing grant cannot mask the next schema's result.
        for schema in schemas:
            async with engine.connect() as conn:
                try:
                    await smoke_check_schema(conn, role, schema)
                    print(f"  OK   {schema}")
                except Exception as exc:  # noqa: BLE001 - reported, not swallowed
                    failures.append(f"{schema}: {type(exc).__name__}: {exc}")
                    print(f"  FAIL {schema}: {type(exc).__name__}: {exc}")
    finally:
        await engine.dispose()

    if failures:
        print(
            f"\n{len(failures)} schema(s) failed the smoke check. "
            "Do NOT enable NER_SQL_EXECUTION_ROLE_ENABLED until they pass."
        )
        return 1

    print(f"\nAll schemas readable under '{role}'. Safe to enable the toggle.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Run the smoke check without creating or re-granting anything.",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.check_only)))
