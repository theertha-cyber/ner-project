"""Verify the live database's schema matches what the Alembic migration chain declares.

Checks three things:
  1. Every `public` table declared by the ORM models (src.gateway.models) has
     the columns those models declare.
  2. `tenant_template` contains every tenant-scoped table any migration's
     upgrade() ever creates.
  3. Every provisioned `tenant_<id>` schema has the same table set as
     `tenant_template`.

Presence-only: this does not check column types, and it never fails on an
object the chain doesn't know about (a developer's scratch table is fine).

Exits non-zero and prints every drifted object if any check fails.
"""
import asyncio
import os
import re
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.gateway.models import Base
from src.shared.config import settings

_VERSIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "alembic", "versions")

_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?tenant_template\.(\w+)",
    re.IGNORECASE,
)


def _declared_public_tables() -> dict[str, set[str]]:
    """Table name -> declared column names, for every ORM model mapped to schema="public"."""
    declared: dict[str, set[str]] = {}
    for table in Base.metadata.tables.values():
        if table.schema == "public":
            declared[table.name] = {c.name for c in table.columns}
    return declared


def _declared_tenant_template_tables() -> set[str]:
    """Union of every table any migration creates in tenant_template.

    Every migration in this chain that creates a tenant_template table does so
    from its upgrade() path (directly or via a module-level SQL constant
    upgrade() executes); none create one from downgrade(). Scanning whole
    files for CREATE TABLE therefore reflects what the forward-applied chain
    declares without needing to isolate function bodies.
    """
    declared: set[str] = set()
    if not os.path.isdir(_VERSIONS_DIR):
        return declared

    for filename in os.listdir(_VERSIONS_DIR):
        if not filename.endswith(".py"):
            continue
        path = os.path.join(_VERSIONS_DIR, filename)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        for m in _CREATE_TABLE_RE.finditer(content):
            declared.add(m.group(1))
    return declared


async def verify(database_url: str | None = None) -> list[str]:
    """Returns a list of human-readable drift descriptions. Empty means clean."""
    url = database_url or settings.database_url
    engine = create_async_engine(url)
    problems: list[str] = []

    try:
        async with engine.connect() as conn:
            # 1. public tables have the columns the ORM models declare.
            declared_public = _declared_public_tables()
            for table_name, declared_columns in declared_public.items():
                result = await conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' AND table_name = :t"
                    ),
                    {"t": table_name},
                )
                existing_columns = {r[0] for r in result.fetchall()}
                if not existing_columns:
                    problems.append(f"public.{table_name}: table is missing entirely")
                    continue
                missing = declared_columns - existing_columns
                for col in sorted(missing):
                    problems.append(f"public.{table_name}: missing column '{col}'")

            # 2. tenant_template has every table the chain ever creates.
            declared_template_tables = _declared_tenant_template_tables()
            result = await conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'tenant_template'")
            )
            template_tables = {r[0] for r in result.fetchall()}
            for table_name in sorted(declared_template_tables - template_tables):
                problems.append(f"tenant_template.{table_name}: missing")

            # 3. every provisioned tenant schema matches tenant_template's table set.
            result = await conn.execute(
                text("SELECT nspname FROM pg_namespace WHERE nspname LIKE 'tenant\\_%' AND nspname != 'tenant_template'")
            )
            tenant_schemas = [r[0] for r in result.fetchall()]
            for schema in tenant_schemas:
                result = await conn.execute(
                    text("SELECT tablename FROM pg_tables WHERE schemaname = :s"),
                    {"s": schema},
                )
                tenant_tables = {r[0] for r in result.fetchall()}
                for table_name in sorted(template_tables - tenant_tables):
                    problems.append(f"{schema}.{table_name}: missing (present in tenant_template)")
    finally:
        await engine.dispose()

    return problems


async def main() -> int:
    problems = await verify()
    if problems:
        print("Schema drift detected:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("Schema verification passed: no drift detected.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
