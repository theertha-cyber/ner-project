"""Emit a schema-contract skeleton for selected tables of a live PostgreSQL
database (design.md Decision 8).

Reads every visible column of the named tables via the same
`information_schema.columns WHERE table_schema = 'public'` predicate
`AzureExternalDatabase.introspect` uses, so the emitted `columns` list matches
the drift gate's fingerprint exactly — a contract missing even one live
column blocks every query with `drift_mismatch`. Primary keys come from
`table_constraints`/`key_column_usage`; foreign keys between the selected
tables become `joins`. Every relation gets an empty `description` and a
`column_descriptions` entry per column, for an administrator to fill in.

The DSN is read only from `EXTERNAL_PG_DSN` — never a CLI argument — so the
password never lands in shell history.

    EXTERNAL_PG_DSN=postgresql://role:pass@host:5432/db \\
        python scripts/external_pg_contract_skeleton.py \\
        --tables fisc_user_profile,fisc_user_role --version 1 > contract.json
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg


async def _introspect_columns(conn: asyncpg.Connection, tables: list[str]) -> dict[str, list[str]]:
    rows = await conn.fetch(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = ANY($1::text[]) "
        "ORDER BY table_name, ordinal_position",
        tables,
    )
    columns: dict[str, list[str]] = {name: [] for name in tables}
    for row in rows:
        columns[row["table_name"]].append(row["column_name"])
    return columns


async def _introspect_primary_keys(conn: asyncpg.Connection, tables: list[str]) -> dict[str, str]:
    rows = await conn.fetch(
        "SELECT tc.table_name, kcu.column_name "
        "FROM information_schema.table_constraints tc "
        "JOIN information_schema.key_column_usage kcu "
        "  ON tc.constraint_name = kcu.constraint_name "
        "  AND tc.table_schema = kcu.table_schema "
        "WHERE tc.table_schema = 'public' AND tc.constraint_type = 'PRIMARY KEY' "
        "  AND tc.table_name = ANY($1::text[]) "
        "ORDER BY kcu.ordinal_position",
        tables,
    )
    primary_keys: dict[str, str] = {}
    for row in rows:
        # First column of a composite key only — the contract's `primary_key`
        # field is a single column; a composite key still gets its `columns`
        # entry right, which is what the drift fingerprint compares.
        primary_keys.setdefault(row["table_name"], row["column_name"])
    return primary_keys


async def _introspect_foreign_keys(conn: asyncpg.Connection, tables: list[str]) -> list[dict]:
    rows = await conn.fetch(
        "SELECT tc.table_name AS left_table, kcu.column_name AS left_key, "
        "       ccu.table_name AS right_table, ccu.column_name AS right_key "
        "FROM information_schema.table_constraints tc "
        "JOIN information_schema.key_column_usage kcu "
        "  ON tc.constraint_name = kcu.constraint_name "
        "  AND tc.table_schema = kcu.table_schema "
        "JOIN information_schema.constraint_column_usage ccu "
        "  ON tc.constraint_name = ccu.constraint_name "
        "  AND tc.table_schema = ccu.table_schema "
        "WHERE tc.table_schema = 'public' AND tc.constraint_type = 'FOREIGN KEY' "
        "  AND tc.table_name = ANY($1::text[]) AND ccu.table_name = ANY($1::text[])",
        tables,
    )
    joins = []
    for row in rows:
        joins.append({
            "left": row["left_table"], "right": row["right_table"],
            "left_key": row["left_key"], "right_key": row["right_key"],
        })
    return joins


def _build_contract(tables: list[str], version: int, columns: dict[str, list[str]],
                    primary_keys: dict[str, str], joins: list[dict]) -> dict:
    relations = {}
    for table in tables:
        table_columns = columns.get(table, [])
        relation: dict = {"columns": table_columns, "description": ""}
        if table in primary_keys:
            relation["primary_key"] = primary_keys[table]
        relation["column_descriptions"] = {column: "" for column in table_columns}
        relations[table] = relation
    return {"version": version, "relations": relations, "joins": joins}


async def main(tables: list[str], version: int) -> int:
    dsn = os.environ.get("EXTERNAL_PG_DSN")
    if not dsn:
        print("EXTERNAL_PG_DSN is not set.", file=sys.stderr)
        return 1

    conn = await asyncpg.connect(dsn)
    try:
        columns = await _introspect_columns(conn, tables)
        missing = [table for table in tables if not columns.get(table)]
        if missing:
            print(f"No visible columns for: {', '.join(missing)}", file=sys.stderr)
            return 1
        primary_keys = await _introspect_primary_keys(conn, tables)
        joins = await _introspect_foreign_keys(conn, tables)
    finally:
        await conn.close()

    contract = _build_contract(tables, version, columns, primary_keys, joins)
    print(json.dumps(contract, indent=2))
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tables", required=True, help="Comma-separated table names.")
    parser.add_argument("--version", type=int, required=True, help="Contract version number.")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    table_names = [t.strip() for t in args.tables.split(",") if t.strip()]
    sys.exit(asyncio.run(main(table_names, args.version)))
