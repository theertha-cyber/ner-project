"""Canonical schema-contract lifecycle (CAP-4, ADR-013).

A contract declares approved relations, columns, and the explicit join graph
with join keys for one tenant's active PostgreSQL connection::

    {"version": 3,
     "relations": {"orders": {"columns": ["id", "customer_id", "total"],
                              "primary_key": "id"}},
     "joins": [{"left": "orders", "right": "customers",
                "left_key": "customer_id", "right_key": "id"}]}

Validation is structural only (finite reason classes, field-level safe errors);
the canonical fingerprint is SHA-256 over a canonical serialization with sorted
relations, sorted columns, and sorted normalized joins. Live comparison
recomputes the same fingerprint from introspected metadata (drift.py).

Persistence is tenant-bound: every lookup constrains the owning tenant from
authenticated server-side context. Contract *structure* (relation/column/join
names) is authorization metadata, not tenant business rows, and is the only
content these rows hold.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy import text

logger = logging.getLogger(__name__)

CONTRACTS_TABLE = "public.external_pg_contracts"

STATE_DRAFT = "draft"
STATE_VALIDATED = "validated"
STATE_PUBLISHED = "published"

REASON_NONE = "none"
REASON_INVALID_JSON = "invalid_json"
REASON_INVALID_SHAPE = "invalid_shape"
REASON_UNKNOWN_RELATION = "unknown_relation"
REASON_UNDECLARED_JOIN_KEY = "undeclared_join_key"
REASON_DUPLICATE_VERSION = "duplicate_version"
REASON_NOT_ACTIVE_CONNECTION = "not_active_connection"

VALIDATION_REASONS = frozenset(
    {
        REASON_NONE,
        REASON_INVALID_JSON,
        REASON_INVALID_SHAPE,
        REASON_UNKNOWN_RELATION,
        REASON_UNDECLARED_JOIN_KEY,
        REASON_DUPLICATE_VERSION,
        REASON_NOT_ACTIVE_CONNECTION,
    }
)

_MAX_RELATIONS = 100
_MAX_COLUMNS_PER_RELATION = 200
_MAX_JOINS = 200
_MAX_NAME_LEN = 128
_MAX_DESCRIPTION_LEN = 2000

_CANONICAL_RELATION_KEYS = ("columns", "primary_key", "description", "column_descriptions")


@dataclass(frozen=True)
class ContractValidation:
    """Result of validating one candidate contract document."""

    valid: bool
    reason: str
    field_errors: tuple = ()


@dataclass(frozen=True)
class CanonicalContract:
    """An accepted canonical contract: version, relations, joins, fingerprint."""

    version: int
    relations: dict
    joins: tuple
    fingerprint: str


def validate_contract_document(document: dict) -> ContractValidation:
    """Validate the structure of one candidate contract document."""
    errors: list[str] = []
    if not isinstance(document, dict):
        return ContractValidation(False, REASON_INVALID_SHAPE, ("document",))
    relations = document.get("relations")
    joins = document.get("joins", [])
    version = document.get("version")
    if not isinstance(version, int) or version < 1:
        errors.append("version")
    if not isinstance(relations, dict) or not relations:
        errors.append("relations")
    elif len(relations) > _MAX_RELATIONS:
        errors.append("relations")
    else:
        for name, rel in relations.items():
            if not _is_safe_name(name):
                errors.append(f"relations.{name}")
                continue
            if not isinstance(rel, dict):
                errors.append(f"relations.{name}")
                continue
            columns = rel.get("columns")
            if not isinstance(columns, list) or not columns:
                errors.append(f"relations.{name}.columns")
            elif len(columns) > _MAX_COLUMNS_PER_RELATION:
                errors.append(f"relations.{name}.columns")
            else:
                for col in columns:
                    if not _is_safe_name(col):
                        errors.append(f"relations.{name}.columns.{col}")
            pk = rel.get("primary_key")
            if pk is not None and pk not in (columns or []):
                errors.append(f"relations.{name}.primary_key")
            description = rel.get("description")
            if description is not None and not (
                isinstance(description, str) and len(description) <= _MAX_DESCRIPTION_LEN
            ):
                errors.append(f"relations.{name}.description")
            column_descriptions = rel.get("column_descriptions")
            if column_descriptions is not None:
                if not isinstance(column_descriptions, dict):
                    errors.append(f"relations.{name}.column_descriptions")
                else:
                    declared_columns = set(columns or [])
                    for col_name, col_description in column_descriptions.items():
                        if col_name not in declared_columns:
                            errors.append(
                                f"relations.{name}.column_descriptions.{col_name}"
                            )
                        elif not (
                            isinstance(col_description, str)
                            and len(col_description) <= _MAX_DESCRIPTION_LEN
                        ):
                            errors.append(
                                f"relations.{name}.column_descriptions.{col_name}"
                            )
    if not isinstance(joins, list) or len(joins) > _MAX_JOINS:
        errors.append("joins")
    else:
        for i, join in enumerate(joins):
            if not isinstance(join, dict):
                errors.append(f"joins[{i}]")
                continue
            left, right = join.get("left"), join.get("right")
            left_key, right_key = join.get("left_key"), join.get("right_key")
            if left not in (relations or {}):
                errors.append(f"joins[{i}].left")
            if right not in (relations or {}):
                errors.append(f"joins[{i}].right")
            if (
                isinstance(relations, dict)
                and left in relations
                and left_key not in (relations[left].get("columns") or [])
            ):
                errors.append(f"joins[{i}].left_key")
            if (
                isinstance(relations, dict)
                and right in relations
                and right_key not in (relations[right].get("columns") or [])
            ):
                errors.append(f"joins[{i}].right_key")
    if errors:
        reason = (
            REASON_UNDECLARED_JOIN_KEY
            if any(".left_key" in e or ".right_key" in e for e in errors)
            else REASON_INVALID_SHAPE
        )
        # Field paths only: never echo values.
        return ContractValidation(False, reason, tuple(errors))
    return ContractValidation(True, REASON_NONE, ())


def _normalize_relations(relations: dict) -> dict:
    """Keeps only the canonical relation keys before persistence, so an unknown
    key never reaches storage regardless of what the accidental pass-through
    used to allow (design.md Decision 1, Risk 4)."""
    normalized = {}
    for name, rel in relations.items():
        entry = {"columns": list(rel.get("columns", []))}
        if rel.get("primary_key") is not None:
            entry["primary_key"] = rel["primary_key"]
        if rel.get("description") is not None:
            entry["description"] = rel["description"]
        if rel.get("column_descriptions") is not None:
            entry["column_descriptions"] = dict(rel["column_descriptions"])
        normalized[name] = entry
    return normalized


def _is_safe_name(name: object) -> bool:
    return (
        isinstance(name, str)
        and 1 <= len(name) <= _MAX_NAME_LEN
        and name.replace("_", "").isalnum()
        and not name[0].isdigit()
    )


def canonical_fingerprint(relations: dict, joins: list | tuple) -> str:
    """Deterministic fingerprint over sorted relations/columns/normalized joins."""
    normalized_joins = sorted(
        [
            (j["left"], j["right"], j["left_key"], j["right_key"])
            for j in joins
        ]
    )
    canonical = json.dumps(
        {
            "relations": {
            name: sorted(relations[name].get("columns", []))
            for name in sorted(relations)
            },
            "joins": [list(j) for j in normalized_joins],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def fingerprint_of_metadata(relation_columns: dict[str, list[str]], joins: list | tuple) -> str:
    """Fingerprint over live introspected metadata using the same canonical form."""
    relations = {name: {"columns": cols} for name, cols in relation_columns.items()}
    return canonical_fingerprint(relations, joins)


async def store_draft(session, tenant_id: str, connection_id: str, document: dict) -> dict:
    """Validate and store one draft version; raises ContractRejected on invalid."""
    validation = validate_contract_document(document)
    if not validation.valid:
        raise ContractRejected(validation.reason, validation.field_errors)
    relations = _normalize_relations(document["relations"])
    joins = document.get("joins", [])
    fingerprint = canonical_fingerprint(relations, joins)
    existing = await session.execute(
        text(
            f"SELECT version FROM {CONTRACTS_TABLE} "
            "WHERE tenant_id = :tid AND connection_id = :cid AND version = :v"
        ),
        {"tid": tenant_id, "cid": connection_id, "v": document["version"]},
    )
    if existing.fetchone() is not None:
        raise ContractRejected(REASON_DUPLICATE_VERSION, ("version",))
    row_id = str(uuid.uuid4())
    await session.execute(
        text(
            f"INSERT INTO {CONTRACTS_TABLE} "
            "(id, tenant_id, connection_id, version, canonical, fingerprint, "
            " validation_state, validation_reason, published) "
            "VALUES (:id, :tid, :cid, :v, CAST(:canonical AS JSONB), :fp, "
            " 'validated', 'none', FALSE)"
        ),
        {
            "id": row_id,
            "tid": tenant_id,
            "cid": connection_id,
            "v": document["version"],
            "canonical": json.dumps(
                {"version": document["version"], "relations": relations, "joins": joins}
            ),
            "fp": fingerprint,
        },
    )
    logger.info(
        "external_pg_contract_stored",
        extra={"tenant": tenant_id, "version": document["version"], "state": "validated"},
    )
    return {"id": row_id, "version": document["version"], "fingerprint": fingerprint,
            "validation_state": "validated", "validation_reason": REASON_NONE}


async def publish_version(session, tenant_id: str, connection_id: str, version: int) -> dict:
    """Mark one validated version published; earlier versions unpublish atomically."""
    result = await session.execute(
        text(
            f"UPDATE {CONTRACTS_TABLE} SET published = FALSE "
            "WHERE tenant_id = :tid AND connection_id = :cid AND published = TRUE"
        ),
        {"tid": tenant_id, "cid": connection_id},
    )
    updated = await session.execute(
        text(
            f"UPDATE {CONTRACTS_TABLE} SET published = TRUE, "
            "validation_state = 'published', published_at = NOW() "
            "WHERE tenant_id = :tid AND connection_id = :cid AND version = :v "
            "AND validation_state IN ('validated', 'published')"
        ),
        {"tid": tenant_id, "cid": connection_id, "v": version},
    )
    if updated.rowcount == 0:
        raise ContractRejected(REASON_INVALID_SHAPE, ("version",))
    row = await accepted_contract(session, tenant_id, connection_id)
    logger.info(
        "external_pg_contract_published",
        extra={"tenant": tenant_id, "version": version},
    )
    return row


async def accepted_contract(session, tenant_id: str, connection_id: str) -> dict | None:
    """The tenant's published contract for one connection, or None."""
    result = await session.execute(
        text(
            f"SELECT version, canonical, fingerprint FROM {CONTRACTS_TABLE} "
            "WHERE tenant_id = :tid AND connection_id = :cid AND published = TRUE "
            "ORDER BY version DESC LIMIT 1"
        ),
        {"tid": tenant_id, "cid": connection_id},
    )
    row = result.fetchone()
    if row is None:
        return None
    canonical = row.canonical if isinstance(row.canonical, dict) else json.loads(row.canonical)
    return {"version": row.version, "canonical": canonical, "fingerprint": row.fingerprint}


async def list_versions(session, tenant_id: str, connection_id: str,
                        page: int = 1, page_size: int = 20) -> dict:
    """Paginated version history for one tenant-owned connection."""
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    total = (
        await session.execute(
            text(
                f"SELECT COUNT(*) FROM {CONTRACTS_TABLE} "
                "WHERE tenant_id = :tid AND connection_id = :cid"
            ),
            {"tid": tenant_id, "cid": connection_id},
        )
    ).scalar()
    rows = await session.execute(
        text(
            f"SELECT version, fingerprint, validation_state, validation_reason, "
            f"published FROM {CONTRACTS_TABLE} "
            "WHERE tenant_id = :tid AND connection_id = :cid "
            "ORDER BY version DESC LIMIT :lim OFFSET :off"
        ),
        {"tid": tenant_id, "cid": connection_id, "lim": page_size,
         "off": (page - 1) * page_size},
    )
    items = [
        {"version": r.version, "fingerprint": r.fingerprint,
         "validation_state": r.validation_state,
         "validation_reason": r.validation_reason, "published": r.published}
        for r in rows.fetchall()
    ]
    total_pages = (total + page_size - 1) // page_size if total else 0
    return {"items": items, "page": page, "page_size": page_size,
            "total": total, "total_pages": total_pages}


class ContractRejected(Exception):
    """A contract was invalid; carries a finite reason and field paths only."""

    def __init__(self, reason: str, field_errors: tuple = ()):
        super().__init__(reason)
        self.reason = reason
        self.field_errors = tuple(field_errors)
