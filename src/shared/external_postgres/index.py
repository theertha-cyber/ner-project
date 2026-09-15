"""Tenant-isolated schema-index representations (CAP-4, ADR-013).

The index helps retrieve schema context for chat prompts; it never authorizes
access — the canonical contract plus the live fingerprint do. Entries live in
the tenant's own schema (``tenant_<id>.external_pg_schema_index``), keyed by
connection and contract version. Publish replaces the version's entries;
retirement clears the connection's entries.
"""

from __future__ import annotations

from sqlalchemy import text


def _index_table(schema: str) -> str:
    if not schema.replace("_", "").isalnum():
        raise ValueError("unsafe schema")
    return f"{schema}.external_pg_schema_index"


def entry_text_for_relation(relation: str, relation_def: dict,
                            joins: list[dict]) -> str:
    """Bounded context text for one relation: its description, columns (each
    with an optional description), and its join keys (design.md Decision 2)."""
    columns = relation_def.get("columns", [])
    description = relation_def.get("description")
    column_descriptions = relation_def.get("column_descriptions") or {}
    header = f"table {relation}"
    if description:
        header += f" — {description}"
    lines = [header, "columns:"]
    for column in sorted(columns):
        col_description = column_descriptions.get(column)
        if col_description:
            lines.append(f"  {column} — {col_description}")
        else:
            lines.append(f"  {column}")
    for join in joins:
        if join.get("left") == relation:
            lines.append(
                f"join {relation}.{join['left_key']} = "
                f"{join['right']}.{join['right_key']}"
            )
        elif join.get("right") == relation:
            lines.append(
                f"join {relation}.{join['right_key']} = "
                f"{join['left']}.{join['left_key']}"
            )
    return "\n".join(lines)


async def replace_version_entries(session, schema: str, connection_id: str,
                                  version: int, canonical: dict) -> int:
    """Replace one version's index entries; returns the entry count."""
    table = _index_table(schema)
    await session.execute(
        text(f"DELETE FROM {table} "
             "WHERE connection_id = :cid AND contract_version = :v"),
        {"cid": connection_id, "v": version},
    )
    relations = canonical.get("relations", {})
    joins = canonical.get("joins", [])
    count = 0
    for relation, rel_def in relations.items():
        rel_def = rel_def if isinstance(rel_def, dict) else {}
        await session.execute(
            text(f"INSERT INTO {table} "
                 "(connection_id, contract_version, relation_name, entry_text) "
                 "VALUES (:cid, :v, :rel, :entry) "
                 "ON CONFLICT (connection_id, contract_version, relation_name) "
                 "DO UPDATE SET entry_text = EXCLUDED.entry_text, "
                 "updated_at = NOW()"),
            {"cid": connection_id, "v": version, "rel": relation,
             "entry": entry_text_for_relation(relation, rel_def, joins)},
        )
        count += 1
    return count


async def clear_connection_entries(session, schema: str, connection_id: str) -> None:
    """Remove every index entry for one connection (retirement path)."""
    table = _index_table(schema)
    await session.execute(
        text(f"DELETE FROM {table} WHERE connection_id = :cid"),
        {"cid": connection_id},
    )


async def fetch_entries(session, schema: str, connection_id: str,
                        version: int) -> list[dict]:
    """Tenant-scoped read of one version's entries (context only)."""
    table = _index_table(schema)
    result = await session.execute(
        text(f"SELECT relation_name, entry_text FROM {table} "
             "WHERE connection_id = :cid AND contract_version = :v "
             "ORDER BY relation_name"),
        {"cid": connection_id, "v": version},
    )
    return [{"relation": r.relation_name, "entry": r.entry_text}
            for r in result.fetchall()]
