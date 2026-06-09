"""Sync tenant_{id} schemas with tenant_template.

Clones missing tables and adds missing columns to existing tables.
Safe to re-run — idempotent.

Run:
    python scripts/migrate_existing_tenants.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from src.shared.config import settings


async def main():
    dsn = settings.database_url
    if dsn.startswith("postgresql://"):
        dsn = dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif dsn.startswith("postgresql+psycopg2://"):
        dsn = dsn.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(dsn)
    async with engine.begin() as conn:
        existing = await conn.execute(
            text("SELECT schema_name FROM information_schema.schemata "
                 "WHERE schema_name LIKE 'tenant_%' AND schema_name != 'tenant_template'")
        )
        schemas = [row[0] for row in existing.fetchall()]

        template_tables = await conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'tenant_template'")
        )
        tables = [row[0] for row in template_tables.fetchall()]

        if not schemas:
            print("No existing tenant schemas found. Nothing to do.")
            return

        if not tables:
            print("No tables in tenant_template. Nothing to clone.")
            return

        for schema in schemas:
            for table in tables:
                exists = await conn.execute(
                    text("SELECT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = :s AND tablename = :t)"),
                    {"s": schema, "t": table},
                )
                if not exists.scalar():
                    await conn.execute(
                        text(f"CREATE TABLE {schema}.{table} "
                             f"(LIKE tenant_template.{table} "
                             f"INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES)")
                    )
                    print(f"  [create] {schema}.{table}")
                    continue

                template_cols = await conn.execute(
                    text("SELECT column_name, column_default, is_nullable, "
                         "data_type, character_maximum_length "
                         "FROM information_schema.columns "
                         "WHERE table_schema = 'tenant_template' AND table_name = :t"),
                    {"t": table},
                )
                tenant_cols = await conn.execute(
                    text("SELECT column_name FROM information_schema.columns "
                         "WHERE table_schema = :s AND table_name = :t"),
                    {"s": schema, "t": table},
                )
                tenant_col_names = {row[0] for row in tenant_cols.fetchall()}

                for row in template_cols.fetchall():
                    col = row[0]
                    if col in tenant_col_names:
                        continue

                    nullable = "NULL" if row.is_nullable == "YES" else "NOT NULL"
                    default = f"DEFAULT {row.column_default}" if row.column_default else ""
                    dtype = row.data_type
                    if row.character_maximum_length:
                        dtype = f"{dtype}({row.character_maximum_length})"

                    await conn.execute(
                        text(f"ALTER TABLE {schema}.{table} ADD COLUMN {col} {dtype} {nullable} {default}")
                    )
                    print(f"  [alter] {schema}.{table} — added column {col}")

        print(f"\nDone. {len(schemas)} tenant schema(s) synced.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
