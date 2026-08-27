"""Projects a document's final entity list into the tenant's generated relational tables.

**One write point.** These tables are written here and nowhere else, inside the single
per-document transaction that already persists `extracted_entities` and `document_entities`
(`worker.py`). Either everything for that document commits or nothing does, so the relational
surface is never partially written and never needs reconciling by a second job. There is no
background job, no trigger, and no refresh mechanism — adding one would reintroduce exactly the
staleness window this arrangement exists to remove.

**It consumes the in-memory list.** The entities projected are the same
`list[NormalizedEntity]` object handed to `insert_document_entities`, after post-processing and
the final `collapse_duplicates`. This module issues no `SELECT` against `document_entities`.
Reading back would add a round trip, would couple the projection to the EAV write landing in a
particular shape, and would make "just run the projection separately" look like a small
refactor when it is the thing that breaks the consistency guarantee.

**It emits no DDL.** Every table and column it writes into is created by
`reconcile_entity_tables`, once per run before the document loop. A missing relation or column
therefore means the catalog and the physical schema genuinely disagree, and the right response
is to let the error propagate: the document fails, the transaction rolls back, `failed_count`
rises, and the run continues. Repairing it here would mean DDL inside a per-document
transaction, holding schema locks for the length of one document's writes.

**The builders are pure.** `build_projection_statements` and `build_relational_delete_statements`
return `list[tuple[str, dict]]` and execute nothing, mirroring `build_role_statements`. That is
not tidiness: the extraction worker holds a sync `Connection` and `document_service`'s delete
endpoint holds an `AsyncSession`, and duplicated statement logic between the write path and the
delete path is precisely how a document ends up half-deleted. One builder, two thin executors,
and a test that asserts the two callers' statement lists are equal.

Routing
-------

Entities are routed to definitions by **entity-type literal**, never by equality against the
definition `name`. Per ADR-008 the shared base model is the default, and on that path
`document_entities.entity_type` holds a CoNLL label (`PER`, `ORG`, `NUM`, ...) rather than the
tenant's own entity name; `base_label_mapping` is the bridge. A name-equality comparison
compiles, passes every test written with fine-tuned fixtures, and produces **empty tables for
every base-model tenant** — which reads downstream as "no entities found" rather than as an
error. The index is built from `entity_type_literals`, the same helper the DDL generator uses,
so routing and schema cannot disagree about which entity belongs where.

Identifier safety rides on the pure/executor split. Every identifier comes from
`entity_definitions.sql_identifier` and is re-validated against `^e_[a-z0-9][a-z0-9_]*$` before
it enters a statement; a definition with a NULL identifier is skipped, never slugged at read
time. Entity-type literals are *values* and never appear in these statements at all — routing
happens in Python, so the only tenant-derived text reaching the database does so as a bound
parameter.
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from src.shared.entity_views import (
    CARDINALITY_MULTI,
    CARDINALITY_SINGLE,
    CHILD_VALUE_COLUMNS,
    GENERATED_IDENTIFIER_RE,
    SUBJECT_TABLE_NAME,
    EntityDefinitionSpec,
    InvalidIdentifierError,
    checked_identifier,
    entity_type_literals,
    list_existing_generated_tables_sync,
    subject_columns,
    typed_field_for_value_kind,
)

logger = logging.getLogger(__name__)


def _checked_table(identifier: str | None) -> str:
    """Re-validate a catalog identifier before it reaches an identifier position.

    `sql_identifier` is safe by construction — `to_sql_identifier` produced it — but it arrives
    through a database column any future code path could write. Checking it here means a bad
    value fails loudly at statement-build time rather than becoming SQL."""
    if not identifier or not GENERATED_IDENTIFIER_RE.fullmatch(identifier):
        raise InvalidIdentifierError(
            f"sql_identifier '{identifier}' does not match {GENERATED_IDENTIFIER_RE.pattern}"
        )
    return identifier


# --------------------------------------------------------------------------------------------
# Routing
# --------------------------------------------------------------------------------------------


def build_routing_index(
    specs: list[EntityDefinitionSpec],
) -> dict[str, EntityDefinitionSpec]:
    """`uppercased entity_type literal -> the one definition that claims it`.

    Only active definitions with an assigned `sql_identifier` participate: an inactive
    definition keeps its table and its rows (nothing is ever dropped) but stops receiving new
    ones, and a definition with no identifier has no table to receive them.

    Two active definitions claiming the same literal is a catalog misconfiguration rather than
    a data condition, and it is resolved rather than reported-and-skipped: the definition whose
    own uppercased `name` equals the literal wins, and failing that the first by
    `sql_identifier` sort order. One literal never indexes to two definitions — writing the
    entity to both tables would double-count it in every aggregate the LLM computes."""
    claimants: dict[str, list[EntityDefinitionSpec]] = {}
    for spec in sorted(
        (s for s in specs if s.is_active and s.sql_identifier),
        key=lambda s: s.sql_identifier or "",
    ):
        for literal in entity_type_literals(spec):
            claimants.setdefault(literal, []).append(spec)

    index: dict[str, EntityDefinitionSpec] = {}
    for literal, candidates in claimants.items():
        if len(candidates) == 1:
            index[literal] = candidates[0]
            continue

        by_name = [c for c in candidates if (c.name or "").strip().upper() == literal]
        # `candidates` is already in `sql_identifier` order, so both branches are deterministic
        # over the same catalog regardless of the order the caller loaded it in.
        winner = by_name[0] if by_name else candidates[0]
        logger.warning(
            "relational_projection literal_collision literal=%s claimed_by=%s routed_to=%s",
            literal,
            ",".join(sorted(c.sql_identifier or "" for c in candidates)),
            winner.sql_identifier,
        )
        index[literal] = winner

    return index


def route_entities(
    entities: list, specs: list[EntityDefinitionSpec]
) -> dict[str, list]:
    """`sql_identifier -> entities routed to it`, skipping every unroutable entity.

    An entity whose literal no active definition claims is written to `document_entities` and
    skipped here. The EAV store's tolerance for undefined types is deliberate — an entity type
    can be extracted before it is defined — and it must survive this change, so an unroutable
    entity is a debug line and never a document failure."""
    index = build_routing_index(specs)
    routed: dict[str, list] = {}

    for entity in entities:
        literal = (entity.entity_type or "").strip().upper()
        spec = index.get(literal)
        if spec is None:
            logger.debug(
                "relational_projection unrouted entity_type=%s reason=no_active_definition",
                literal,
            )
            continue
        routed.setdefault(spec.sql_identifier, []).append(entity)

    return routed


# --------------------------------------------------------------------------------------------
# Value selection
# --------------------------------------------------------------------------------------------


def select_single_value(entities: list):
    """The one value a `single` definition contributes to the document's `subject` row.

    Sorted by `(-confidence, -occurrence_count, normalized_value)`, first taken.

    The second and third keys are required, not defensive. `collapse_duplicates` sets
    `existing.confidence = min(existing.confidence, entity.confidence)`
    (`entity_normalizer.py`), so confidence ties are the common case rather than the rare one.
    Sorting on confidence alone would make the chosen value depend on list order and change
    between runs over identical input — which is precisely the property a query surface cannot
    have, because nothing downstream would show that it had changed.

    The values not chosen are not lost: they stay in `document_entities`, which remains the
    system of record and is what the document-detail endpoint reads."""
    if not entities:
        return None
    return sorted(
        entities,
        key=lambda e: (
            -(e.confidence or 0.0),
            -(e.occurrence_count or 0),
            e.normalized_value or "",
        ),
    )[0]


def value_for_column(entity, value_kind: str | None):
    """The value a `subject` column receives, decided by the definition's `value_kind`.

    `value_number` for `number`/`money`/`duration`/`boolean`, `value_date` for `date`, the
    surface value otherwise. When a typed kind yields NULL — the normalizer could not parse the
    surface text — the column stays NULL. Falling back to the surface text would put
    `"half a decade"` in a `DOUBLE PRECISION` column's place in the model's mind and make
    `WHERE years_experience > 5` silently *wrong* rather than merely empty."""
    typed_field = typed_field_for_value_kind(value_kind)
    if typed_field:
        return getattr(entity, typed_field, None)
    return entity.entity_value


# --------------------------------------------------------------------------------------------
# Pure statement builders
# --------------------------------------------------------------------------------------------


def _child_insert(schema: str, table: str) -> str:
    columns = ", ".join(CHILD_VALUE_COLUMNS)
    placeholders = ", ".join(f":{column}" for column in CHILD_VALUE_COLUMNS)
    return (
        f"INSERT INTO {schema}.{table} ({columns})\n"
        f"VALUES ({placeholders})\n"
        # A safety net, not the normal path: `collapse_duplicates` has already merged rows
        # sharing a normalized value. Two *source labels* mapped onto one definition can still
        # collide here, and a unique violation would fail a document over a catalog choice.
        f"ON CONFLICT (document_id, normalized_value) DO UPDATE SET\n"
        f"    value = EXCLUDED.value,\n"
        f"    value_number = EXCLUDED.value_number,\n"
        f"    value_number_high = EXCLUDED.value_number_high,\n"
        f"    value_date = EXCLUDED.value_date,\n"
        f"    value_date_high = EXCLUDED.value_date_high,\n"
        f"    value_unit = EXCLUDED.value_unit,\n"
        f"    confidence = GREATEST({schema}.{table}.confidence, EXCLUDED.confidence),\n"
        f"    page_number = COALESCE(EXCLUDED.page_number, {schema}.{table}.page_number),\n"
        f"    occurrence_count = {schema}.{table}.occurrence_count "
        f"+ EXCLUDED.occurrence_count"
    )


def _child_params(document_id: str, entity) -> dict:
    """`confidence` and `page_number` are projected; provenance is not.

    `source_entity_value`, `source_entity_type`, the `postprocess_*` fields,
    `extraction_schema_version`, `char_start`, and `char_end` stay in `document_entities`. They
    widen the schema description in every prompt without answering any user question, and they
    remain joinable from EAV on `(document_id, normalized_value)`."""
    return {
        "document_id": document_id,
        "value": entity.entity_value,
        "normalized_value": entity.normalized_value,
        "value_number": entity.value_number,
        "value_number_high": entity.value_number_high,
        "value_date": entity.value_date,
        "value_date_high": entity.value_date_high,
        "value_unit": entity.value_unit,
        "confidence": entity.confidence,
        "page_number": entity.page_number,
        "occurrence_count": entity.occurrence_count or 1,
    }


def _subject_upsert(schema: str, columns: list[str]) -> str:
    all_columns = ["document_id", "filename", *columns]
    placeholders = ", ".join(f":{column}" for column in all_columns)
    assignments = ",\n    ".join(
        f"{column} = EXCLUDED.{column}" for column in all_columns[1:]
    )
    return (
        f"INSERT INTO {schema}.{SUBJECT_TABLE_NAME} ({', '.join(all_columns)})\n"
        f"VALUES ({placeholders})\n"
        f"ON CONFLICT (document_id) DO UPDATE SET\n"
        f"    {assignments}"
    )


def build_projection_statements(
    schema: str,
    document_id: str,
    filename: str | None,
    entities: list,
    specs: list[EntityDefinitionSpec],
) -> list[tuple[str, dict]]:
    """Every statement that writes this document's relational rows. Executes nothing.

    Always emits the `subject` upsert, even for a document from which the model extracted
    nothing. A zero-entity document with no `subject` row would turn the generated SQL's
    `LEFT JOIN` into a silently truncated answer and make "documents where nothing was found"
    unanswerable; a document that has never been extracted has no row at all, and that is the
    distinction worth keeping. `filename` is written on every projection.

    Emits one child-table insert per routed entity belonging to an active `multi` definition,
    and nothing at all for `single` definitions beyond their `subject` column — a `single`
    definition's whole point is that it is one column on one row."""
    schema_ident = checked_identifier(schema, "schema")
    routed = route_entities(entities, specs)

    statements: list[tuple[str, dict]] = []

    subject_params: dict = {"document_id": document_id, "filename": filename}
    subject_column_names: list[str] = []
    for spec, column_name, _column_type in subject_columns(specs):
        chosen = select_single_value(routed.get(spec.sql_identifier, []))
        subject_column_names.append(column_name)
        subject_params[column_name] = (
            value_for_column(chosen, spec.value_kind) if chosen is not None else None
        )
    statements.append((_subject_upsert(schema_ident, subject_column_names), subject_params))

    for spec in sorted(
        (s for s in specs if s.is_active and s.cardinality == CARDINALITY_MULTI and s.sql_identifier),
        key=lambda s: s.sql_identifier or "",
    ):
        table = _checked_table(spec.sql_identifier)
        insert = _child_insert(schema_ident, table)
        for entity in routed.get(spec.sql_identifier, []):
            statements.append((insert, _child_params(document_id, entity)))

    return statements


def build_relational_delete_statements(
    schema: str,
    document_id: str,
    specs: list[EntityDefinitionSpec],
    existing_tables: set[str] | None = None,
) -> list[tuple[str, dict]]:
    """Clear this document from every **existing** generated table, plus its `subject` row.

    Scoped to every definition with an identifier, active or not — deliberately wider than the
    projection. Scoping the delete to currently-active definitions would strand a deactivated
    definition's rows in a table that reactivation puts straight back on the query surface, so
    a re-extraction would leave the previous generation's values answering questions beside the
    new one's.

    `existing_tables` narrows the list to relations that are actually present. It matters
    because "existing" is not the same as "catalogued": a tenant whose schema has never been
    reconciled has no `subject` table at all, and a definition created inactive never got one —
    and a `DELETE` against a missing relation raises. Deleting a document must not depend on
    whether an extraction run has ever happened for that tenant. Passing `None` emits the full
    list, which is what the pure tests assert on.

    Pure, and shared: the extraction worker calls it before re-inserting a document, and
    `document_service`'s delete endpoint calls it when a document is removed. Two callers, one
    statement list, because a delete path that diverges from the write path is how a document
    ends up half-deleted."""
    schema_ident = checked_identifier(schema, "schema")
    statements: list[tuple[str, dict]] = []

    def present(table: str) -> bool:
        return existing_tables is None or table in existing_tables

    for spec in sorted(
        (s for s in specs if s.sql_identifier and s.cardinality == CARDINALITY_MULTI),
        key=lambda s: s.sql_identifier or "",
    ):
        table = _checked_table(spec.sql_identifier)
        if not present(table):
            continue
        statements.append(
            (
                f"DELETE FROM {schema_ident}.{table} WHERE document_id = :document_id",
                {"document_id": document_id},
            )
        )

    if present(SUBJECT_TABLE_NAME):
        statements.append(
            (
                f"DELETE FROM {schema_ident}.{SUBJECT_TABLE_NAME} "
                "WHERE document_id = :document_id",
                {"document_id": document_id},
            )
        )
    return statements


# --------------------------------------------------------------------------------------------
# Executors
# --------------------------------------------------------------------------------------------
#
# Thin by design. Everything that decides *what* is written lives above this line; these two
# only decide *when*, on a connection the caller already owns and inside a transaction the
# caller already opened. Neither opens a connection, begins a transaction, or commits — that is
# what lets the projection share the extraction worker's per-document transaction.


def project_document_entities(
    conn,
    schema: str,
    document_id: str,
    filename: str | None,
    entities: list,
    specs: list[EntityDefinitionSpec],
) -> None:
    """Write the document's relational rows on the caller's connection.

    A missing table or column raises rather than being caught. Run-start reconciliation makes
    that unreachable in normal operation, so reaching it means the catalog and the physical
    schema genuinely disagree — a condition an operator needs to see as `failed_count`, not one
    to paper over into a run that reports success while writing an incomplete query surface."""
    for statement, params in build_projection_statements(
        schema, document_id, filename, entities, specs
    ):
        conn.execute(text(statement), params)


def delete_relational_entities(
    conn, schema: str, document_id: str, specs: list[EntityDefinitionSpec]
) -> None:
    """Clear the document's relational rows on the caller's connection.

    Resolves which generated tables the schema actually holds first: a definition created
    inactive never got a table, and a tenant that has never been reconciled has none at all."""
    existing = list_existing_generated_tables_sync(conn, schema)
    for statement, params in build_relational_delete_statements(
        schema, document_id, specs, existing
    ):
        conn.execute(text(statement), params)


# `CARDINALITY_SINGLE` is re-exported so a caller reasoning about which relation a definition
# writes into does not have to import from two modules to find out.
__all__ = [
    "CARDINALITY_MULTI",
    "CARDINALITY_SINGLE",
    "build_projection_statements",
    "build_relational_delete_statements",
    "build_routing_index",
    "delete_relational_entities",
    "project_document_entities",
    "route_entities",
    "select_single_value",
    "value_for_column",
]
