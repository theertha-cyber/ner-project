"""Generated per-tenant relational tables over the EAV entity store.

Extracted entities live in one EAV table per tenant schema, `tenant_<slug>.document_entities`:
one row per extracted fact, keyed by `entity_type`, surface text in `entity_value`, typed
values in `value_number` / `value_date` / `value_unit`. That shape is deliberate — tenant
admins add entity types at runtime, and this is what lets a new entity type exist without a
storage migration.

The cost lands on the read side. A Text-to-SQL LLM querying `document_entities` directly has
to self-join it once per entity type and filter each join on `entity_type`, and every
additional tenant-defined type widens the surface it must reason about. This module keeps EAV
as the **write** model and generates a **read** model beside it: one `subject` table per tenant
(one row per extracted document, single-valued facts as columns) and one `e_<entity>` child
table per multi-valued entity type. Adding an entity type then emits cheap, idempotent table
DDL instead of migrating storage.

The generated relations are **physical tables**, not views, and they are written by the
extraction worker rather than derived on read (see `relational_projection.py`). Three problems
collapse at once by making them tables:

1. `CREATE OR REPLACE VIEW` cannot add, rename, or reorder a column, so every new `single`
   definition forced `DROP VIEW ... CASCADE` + `CREATE VIEW` on `subject`. On a table,
   `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` with **no default** is metadata-only in
   PostgreSQL 11+ — no rewrite, no cascade, and no window in which a reader sees a missing
   relation.
2. `build_role_statements` (`src/chat_api/services/sql_execution_role.py`) guards each grant
   with `IF EXISTS (SELECT 1 FROM pg_tables ...)`. `pg_tables` excludes views but matches
   physical tables directly, so the grant guard needs no special case.
3. A table can carry `PRIMARY KEY (document_id, normalized_value)`, which gives the projection
   an `ON CONFLICT` target and makes concurrent writers last-writer-wins instead of
   duplicate-accumulating.

Nothing here executes DDL as a side effect of generating it. `build_entity_table_statements`
follows the same contract as `build_role_statements`: take plain data, return a `list[str]` of
idempotent statements, execute nothing. That is what makes the whole layer assertable in tests
with no database, which matters because the failure modes here are silent — a missing table
returns an error, but a missing *row* returns a confident wrong answer.

Design decisions, and what breaks without them
----------------------------------------------

**Nothing generated here is ever dropped.** `entity_definitions` has no hard delete:
`soft_delete_entity_type` sets `is_active = false` and `toggle_entity_type` flips the same flag
in both directions. When the generated object was a view it held no rows, so dropping it on
deactivation was free. A generated table *is* the rows, so dropping it turns an undo button
into a data-loss event. `is_active = false` therefore means: keep the table, stop projecting
into it, and exclude it from the execution role's grants and from `validate_sql`'s whitelist.
Reactivation resumes projection over data that was never destroyed. A table whose definition
has vanished from the catalog entirely is logged and left in place — removing genuinely dead
tables is a manual operator action. This module emits no `DROP`, `DELETE`, or `TRUNCATE`, and
`tests/test_entity_views_generator.py` asserts that directly rather than trusting review.

A cardinality change is that same rule seen from the other side. Reconciliation is
**tenant-wide** -- every write path reloads the whole catalog and rebuilds the whole schema --
so the first definition edited after a tenant's tables are absent recreates a child table for
every definition that is `multi` *at that moment*, which after migration `037`'s backfill is all
of them. Flipping one to `single` afterwards adds its `subject` column and leaves that child
table standing. Keeping it is correct: on a definition that was `multi` long enough to collect
rows, dropping it destroys the only copy of them. Keeping it *queryable* is not -- the
projection stopped writing to it at the flip, so it answers every question with zero rows. Hence
the split below between what the reconciler maintains (`expected_table_names`, which is also the
query surface) and what any definition merely claims (`catalogued_table_names`, which only
decides whether a table is called an orphan).

**Entity type matching is case-insensitive and includes base-model labels.** The obvious
comparison, `entity_type == definition.name`, is wrong twice over. First, nothing in this
codebase compares entity types case-exactly: `load_entity_type_config` keys on `name.lower()`,
while the extraction worker, the post-processor, the entity resolver and the SQL generator all
uppercase before comparing. Second, on the base-model path — the default per ADR-008 — the
label vocabulary is CoNLL (`PER`/`ORG`/`LOC`/`MISC`), not the tenant's entity names, and
`base_label_mapping` is what ties a definition to those labels. A name-only match is silently
empty for every tenant that has not trained its own model yet, which is the worst failure shape
available: it looks exactly like "no entities found". `entity_type_literals` is public so the
DDL generator, the projection router, and the query-surface resolver all derive the same set
from one implementation and cannot disagree about which entity belongs where.

**The child column list is fixed, and does not vary with `value_kind`.** A child table declares
every typed column whether or not the definition's kind populates it. Deriving the column list
from `value_kind` would turn a later kind change, or the introduction of a new kind, into an
`ALTER` on a populated table; with a fixed shape the columns are already there and simply stay
NULL.

**`subject` gets exactly one column per `single` definition, typed by `value_kind`.** A typed
column is the entire point: the LLM must be able to write `WHERE years_experience > 5` without
a cast. When a typed kind yields NULL because the surface text was unparseable, the column
stays NULL — falling back to surface text in a numeric column makes comparisons *wrong* rather
than merely empty, which is worse. The paired `<name>_text` companion column the view design
projected is gone for the same reason it existed: the surface text is one join away in
`document_entities`, and doubling the column count doubles what every prompt must describe.

**`filename` is denormalized onto `subject`.** It removes a join the LLM must otherwise get
right, and the worker already holds the value at projection time.

**Tenant text never reaches an identifier position.** `entity_definitions.name` is free text.
`to_sql_identifier` slugs it down to a fixed character class rather than quoting it, so
injection safety is a property of the grammar checked in one place rather than of escaping
applied correctly everywhere forever. Entity-type literals are *values*, and the projection
passes them as bound parameters; this module no longer puts them into SQL at all.

Reconciliation
--------------

`reconcile_entity_tables` (async, for `gateway`'s `AsyncSession`) and
`reconcile_entity_tables_sync` (for the extraction worker's sync `Connection`) are thin
executors over the same pure builders, mirroring the pure/executor split in
`relational_projection.py`. Two call idioms, one statement list, so the two can never drift.

`TenantService.create_tenant()` clones the tenant template with
`SELECT tablename FROM pg_tables WHERE schemaname = 'tenant_template'` followed by
`CREATE TABLE ... (LIKE ...)`, and the template carries no generated tables — so a newly
provisioned tenant starts with **zero** of them. Run-start reconciliation in
`run_batch_extraction` is what covers that case, which is why it is not optional.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

TENANT_SCHEMA_PREFIX = "tenant_"

# Postgres truncates identifiers past NAMEDATALEN-1 silently, which would turn two distinct
# entity types into one table. Everything generated here is bounded to the limit explicitly so
# truncation is this module's decision, never the server's.
MAX_IDENTIFIER_LENGTH = 63

# Every generated table name carries this prefix. It does three jobs at once: it guarantees the
# identifier starts with a letter (so a tenant type named "2024 Revenue" is legal unquoted), it
# makes every Postgres reserved word safe without quoting ("select" -> "e_select"), and it
# namespaces generated tables away from real tables in the same schema.
IDENTIFIER_PREFIX = "e_"

# A name that slugs to nothing — "", "---", or a name written entirely in a non-Latin script —
# still has to produce a usable table name. Raising instead would abort the `037` backfill on
# data already in the database, which cannot be corrected before the migration runs.
FALLBACK_SLUG = "unnamed"

SUBJECT_TABLE_NAME = "subject"
# The view-era name, kept so an existing import does not break on the rename.
SUBJECT_VIEW_NAME = SUBJECT_TABLE_NAME

CARDINALITY_SINGLE = "single"
CARDINALITY_MULTI = "multi"
CARDINALITIES = frozenset({CARDINALITY_SINGLE, CARDINALITY_MULTI})

# The grammar every generated identifier satisfies. A digit is allowed immediately after the
# `e_` prefix because the prefix already guarantees a legal leading character, and forbidding it
# would mangle a perfectly readable `e_2024_revenue` for no safety gain.
GENERATED_IDENTIFIER_RE = re.compile(r"^e_[a-z0-9][a-z0-9_]*$")

# Schema and table names are interpolated into DDL, so they are checked against the identifier
# grammar first. They come from `pg_namespace` or from server configuration, never from a
# request — this guards against a typo becoming a syntax injection, it is not a substitute for
# slugging tenant input. Mirrors `_IDENTIFIER_RE` in
# `src/chat_api/services/sql_execution_role.py`.
_BARE_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z_0-9$]*")

_NON_IDENTIFIER_CHARS_RE = re.compile(r"[^a-z0-9]+")


class InvalidIdentifierError(ValueError):
    """Raised when a schema or table name is not a bare SQL identifier."""


def checked_identifier(value: str, kind: str) -> str:
    """Gate for a schema or table name before it is interpolated into a statement.

    Public because `relational_projection` validates the schema string it is handed by exactly
    the same rule — a second copy of the grammar is a second place for it to drift."""
    if not value or not _BARE_IDENTIFIER_RE.fullmatch(value):
        raise InvalidIdentifierError(f"{kind} '{value}' is not a bare SQL identifier")
    return value


_checked_identifier = checked_identifier


def _slug_base(name: str) -> str:
    """The identifier body, before the prefix, the length bound, and collision resolution.

    Accents are folded rather than dropped, so "Café" reads back as `cafe` instead of `caf_`.
    Everything outside `[a-z0-9]` collapses to a single `_`, which is what makes the output
    grammar a property of this function rather than of the caller's input."""
    folded = unicodedata.normalize("NFKD", name or "")
    ascii_only = folded.encode("ascii", "ignore").decode("ascii").lower()
    collapsed = _NON_IDENTIFIER_CHARS_RE.sub("_", ascii_only).strip("_")
    return collapsed or FALLBACK_SLUG


def to_sql_identifier(name: str, taken: set[str]) -> str:
    """Deterministic, collision-free, <=63 chars, matches `^e_[a-z0-9][a-z0-9_]*$`.

    Total by construction: degenerate input falls back to `e_unnamed` rather than raising,
    because this runs both in the `037` migration backfill (where a raise aborts the migration
    for every tenant) and, from the entity-CRUD wiring onward, on a user request (where a raise
    turns a legal tenant-chosen name into a 500).

    `taken` is read, never mutated — the caller decides when a returned identifier becomes
    committed. Determinism matters beyond tidiness: the migration backfill and the runtime
    generator must agree on the same name for the same inputs, or the migration records one
    identifier while the generator creates a table under another and orphans it.

    The length bound is applied to the base *before* any collision suffix, so a suffixed
    identifier still fits rather than being truncated back into a collision by the server."""
    base = _slug_base(name)
    candidate = f"{IDENTIFIER_PREFIX}{base}"[:MAX_IDENTIFIER_LENGTH]
    if candidate not in taken:
        return candidate

    suffix_number = 2
    while True:
        suffix = f"_{suffix_number}"
        candidate = f"{IDENTIFIER_PREFIX}{base}"[: MAX_IDENTIFIER_LENGTH - len(suffix)] + suffix
        if candidate not in taken:
            return candidate
        suffix_number += 1


def schema_for_tenant(tenant_id: str) -> str:
    """The tenant schema name for a `entity_definitions.tenant_id`.

    One direction only, and deliberately so: `tenant_id` -> schema is total, whereas the reverse
    is ambiguous (`demo-tenant` and `demo_tenant` both map to `tenant_demo_tenant`). Every
    caller that needs the pairing therefore starts from the catalog row, never from the schema
    name. Mirrors `_schema` in the extraction worker and in `document_service`."""
    return f"{TENANT_SCHEMA_PREFIX}{tenant_id.replace('-', '_')}"


@dataclass
class EntityDefinitionSpec:
    """The subset of `public.entity_definitions` the generated layer needs, as plain data.

    Deliberately not the ORM model: the generator has to be callable from a migration, from
    `gateway`, from the extraction worker, and from tests that have no database, so it takes a
    value object rather than a session-bound row."""

    name: str
    sql_identifier: str | None
    cardinality: str = CARDINALITY_MULTI
    value_kind: str | None = None
    is_active: bool = True
    # Maps a base-model label (`PER`, `ORG`, ...) to this tenant's own entity type. Present only
    # for tenants whose extraction ran on the shared base model rather than a fine-tuned one.
    base_label_mapping: dict | None = field(default=None)
    # Tenant-authored semantics, carried so a consumer describing the surface can say what a
    # relation or column *means* rather than only what it is called. Default `None` so every
    # existing construction site — migration `037`, the sync loader, the projection tests —
    # keeps working unchanged; a definition with no description simply describes itself by name.
    description: str | None = None
    examples: list | None = None
    value_unit: str | None = None


# --------------------------------------------------------------------------------------------
# DDL generation
# --------------------------------------------------------------------------------------------

# Which typed field on a `NormalizedEntity` (and column on `document_entities`) holds the useful
# value for a declared kind. This mirrors the parser table in `semantic_normalizer.PARSERS` and
# is duplicated rather than imported: `src/shared` must not depend on a service package, and
# this module is imported by `gateway`, by the extraction service, and by the `037` migration.
# A kind absent here (`text`, NULL, or anything added later without a column) projects the
# surface text.
_TYPED_FIELD_BY_VALUE_KIND = {
    "number": "value_number",
    "money": "value_number",
    "duration": "value_number",
    "boolean": "value_number",
    "date": "value_date",
}

# The `subject` column type each typed field needs. Derived from the field rather than restated
# per kind, so a kind added to `_TYPED_FIELD_BY_VALUE_KIND` cannot be given a column type here
# that disagrees with the value the projection writes into it.
_COLUMN_TYPE_BY_TYPED_FIELD = {
    "value_number": "DOUBLE PRECISION",
    "value_date": "DATE",
}

SUBJECT_TEXT_COLUMN_TYPE = "TEXT"

# How each type above spells itself in `information_schema.columns.data_type`, which is the only
# way to ask the server what a column actually is. Kept beside the types themselves: a type added
# to `_COLUMN_TYPE_BY_TYPED_FIELD` without a spelling here would compare unequal against every
# real column, and the reconciler would answer that by retyping — and so blanking — every column
# on every run. `tests/test_entity_views_generator.py` asserts this map is total over
# `subject_column_type`'s range rather than leaving that to review.
_INFORMATION_SCHEMA_TYPE = {
    SUBJECT_TEXT_COLUMN_TYPE: "text",
    "DOUBLE PRECISION": "double precision",
    "DATE": "date",
}

# The child-table shape. Fixed rather than derived from the definition: a `value_kind` change,
# or a new kind introduced later, then never requires an `ALTER` on a populated child table —
# the column is already there and stays NULL. `(document_id, normalized_value)` is a real
# primary key, which is what gives the projection an `ON CONFLICT` target.
_CHILD_TABLE_COLUMNS = (
    "document_id VARCHAR NOT NULL",
    "value TEXT NOT NULL",
    "normalized_value TEXT NOT NULL",
    "value_number DOUBLE PRECISION",
    "value_number_high DOUBLE PRECISION",
    "value_date DATE",
    "value_date_high DATE",
    "value_unit TEXT",
    "confidence DOUBLE PRECISION NOT NULL",
    "page_number INTEGER",
    "occurrence_count INTEGER NOT NULL DEFAULT 1",
)

# The value columns a child row carries, in the order `relational_projection` binds them. Kept
# beside the DDL so the insert and the table cannot drift apart.
CHILD_VALUE_COLUMNS = (
    "document_id",
    "value",
    "normalized_value",
    "value_number",
    "value_number_high",
    "value_date",
    "value_date_high",
    "value_unit",
    "confidence",
    "page_number",
    "occurrence_count",
)

# Columns `subject` always carries. A pivot column may not shadow one of these — an entity type
# legitimately named "Filename" slugs to `e_filename`, whose stripped form would collide.
SUBJECT_IDENTITY_COLUMNS = ("document_id", "filename")
_SUBJECT_IDENTITY_COLUMNS = SUBJECT_IDENTITY_COLUMNS


def _checked_generated_identifier(value: str | None) -> str:
    """Gate between the catalog and an identifier position in DDL.

    `sql_identifier` is produced by `to_sql_identifier` and is supposed to be safe by
    construction, but it arrives here through a database column that any future code path could
    write. Re-checking it against the grammar here means a bad value fails loudly at generation
    time instead of becoming DDL."""
    if not value or not GENERATED_IDENTIFIER_RE.fullmatch(value):
        raise InvalidIdentifierError(
            f"sql_identifier '{value}' does not match {GENERATED_IDENTIFIER_RE.pattern}"
        )
    return value


def entity_type_literals(definition: "EntityDefinitionSpec") -> list[str]:
    """Every stored `entity_type` value that means this definition, uppercased and sorted.

    Public because three callers need exactly this set and must not each derive their own: the
    DDL generator, the projection router in
    `src/extraction_service/services/relational_projection.py`, and the query-surface resolver.
    A second implementation would eventually disagree, and the symptom would be an empty table
    rather than an error.

    The definition's own name covers a tenant running its own fine-tuned model, where the label
    set was built from annotation tags seeded by that name. The `base_label_mapping` keys cover
    the base-model path, where `entity_type` holds a CoNLL label (`PER`, `ORG`, ...) instead —
    the same bridge `entity_resolver` and `rag_orchestrator` already use."""
    literals: set[str] = set()

    name = (definition.name or "").strip().upper()
    if name:
        literals.add(name)

    mapping = definition.base_label_mapping
    if isinstance(mapping, dict):
        for key in mapping:
            label = str(key).strip().upper()
            if label:
                literals.add(label)

    return sorted(literals)


# The view-era private name, kept so an existing import does not break on the rename.
_entity_type_literals = entity_type_literals


def _unique_column(candidate: str, taken: set[str]) -> str:
    """Deterministic disambiguation for a projected column name, same rule as identifiers."""
    if candidate not in taken:
        return candidate[:MAX_IDENTIFIER_LENGTH]
    suffix_number = 2
    while True:
        suffix = f"_{suffix_number}"
        disambiguated = candidate[: MAX_IDENTIFIER_LENGTH - len(suffix)] + suffix
        if disambiguated not in taken:
            return disambiguated
        suffix_number += 1


def _ordered(definitions: list["EntityDefinitionSpec"]) -> list["EntityDefinitionSpec"]:
    """Stable order so repeated generation is byte-identical."""
    return sorted(definitions, key=lambda d: ((d.sql_identifier or ""), (d.name or "")))


def _active(
    definitions: list["EntityDefinitionSpec"], cardinality: str
) -> list["EntityDefinitionSpec"]:
    return [
        d
        for d in _ordered(definitions)
        if d.is_active and d.cardinality == cardinality and d.sql_identifier
    ]


def typed_field_for_value_kind(value_kind: str | None) -> str | None:
    """The `NormalizedEntity` field a declared kind parses into, or None for surface text.

    Shared with the projection so the column `subject` declares and the value written into it
    are decided by one table."""
    return _TYPED_FIELD_BY_VALUE_KIND.get(value_kind or "")


def subject_column_type(value_kind: str | None) -> str:
    """`DOUBLE PRECISION` for the numeric kinds, `DATE` for dates, `TEXT` for everything else."""
    typed_field = typed_field_for_value_kind(value_kind)
    return _COLUMN_TYPE_BY_TYPED_FIELD.get(typed_field or "", SUBJECT_TEXT_COLUMN_TYPE)


def subject_columns(
    definitions: list["EntityDefinitionSpec"],
) -> list[tuple["EntityDefinitionSpec", str, str]]:
    """`(definition, column_name, column_type)` for every active `single` definition.

    The single source of the `subject` column layout. The DDL generator emits an
    `ADD COLUMN IF NOT EXISTS` from it and the projection builds its upsert from it, so the
    column a definition owns is decided once. Deriving the name twice is how a projection ends
    up writing a column the DDL never added — an error at run time, and one that fails the whole
    document."""
    taken = set(SUBJECT_IDENTITY_COLUMNS)
    columns: list[tuple["EntityDefinitionSpec", str, str]] = []

    for definition in _active(definitions, CARDINALITY_SINGLE):
        identifier = _checked_generated_identifier(definition.sql_identifier)
        base = identifier[len(IDENTIFIER_PREFIX) :] or FALLBACK_SLUG
        column_name = _unique_column(base, taken)
        taken.add(column_name)
        columns.append((definition, column_name, subject_column_type(definition.value_kind)))

    return columns


def child_index_name(identifier: str) -> str:
    """`idx_<identifier>_normalized_value`, bounded to the identifier length limit.

    Two identifiers long enough to be truncated into the same index name would leave the second
    index uncreated (`CREATE INDEX IF NOT EXISTS` matches on the name alone). That costs a scan,
    never a row, which is why the bound is applied here rather than being worked around."""
    return f"idx_{identifier}_normalized_value"[:MAX_IDENTIFIER_LENGTH]


def build_child_table_statements(schema: str, definition: "EntityDefinitionSpec") -> list[str]:
    """`CREATE TABLE IF NOT EXISTS` plus its `normalized_value` index, for one `multi` type."""
    schema_ident = _checked_identifier(schema, "schema")
    table = _checked_generated_identifier(definition.sql_identifier)
    columns = ",\n    ".join(_CHILD_TABLE_COLUMNS)
    return [
        (
            f"CREATE TABLE IF NOT EXISTS {schema_ident}.{table} (\n"
            f"    {columns},\n"
            f"    PRIMARY KEY (document_id, normalized_value)\n"
            f")"
        ),
        (
            f"CREATE INDEX IF NOT EXISTS {child_index_name(table)} "
            f"ON {schema_ident}.{table} (normalized_value)"
        ),
    ]


def build_subject_table_statements(
    schema: str, definitions: list["EntityDefinitionSpec"]
) -> list[str]:
    """The `subject` table, then one `ADD COLUMN IF NOT EXISTS` per active `single` definition.

    Never a drop-and-recreate: `ADD COLUMN IF NOT EXISTS` with no default is metadata-only in
    PostgreSQL 11+, so adding the tenth `single` definition costs the same as the first and
    existing rows keep their values with NULL in the new column."""
    schema_ident = _checked_identifier(schema, "schema")

    statements = [
        (
            f"CREATE TABLE IF NOT EXISTS {schema_ident}.{SUBJECT_TABLE_NAME} (\n"
            f"    document_id VARCHAR PRIMARY KEY,\n"
            f"    filename TEXT\n"
            f")"
        )
    ]
    for _definition, column_name, column_type in subject_columns(definitions):
        statements.append(
            f"ALTER TABLE {schema_ident}.{SUBJECT_TABLE_NAME} "
            f"ADD COLUMN IF NOT EXISTS {column_name} {column_type}"
        )
    return statements


def diverging_subject_columns(
    definitions: list["EntityDefinitionSpec"], actual_types: dict[str, str]
) -> list[tuple[str, str, str]]:
    """`(column, actual type, declared type)` for every `subject` column that disagrees.

    `ADD COLUMN IF NOT EXISTS` creates a column at the type its definition's `value_kind`
    declared *at the time the column first appeared*, and does nothing ever after. A later
    `value_kind` edit therefore moves the catalog and leaves the column behind, while every
    consumer keeps trusting the catalog: the projection writes the representation the new kind
    implies, and the query surface tells the SQL generator the new type. This function is how
    that divergence stops being invisible.

    Only columns an **active** `single` definition owns are reported. A column left behind by a
    deactivation or by a flip to `multi` is off the query surface exactly as a retained child
    table is: nothing projects into it, nothing may query it, and its rows are the only copy of
    that projection. It rejoins the surface — and is converged then — if its definition comes
    back.

    A column that does not exist yet is not a divergence: the `ADD COLUMN` in the same statement
    list creates it at the declared type."""
    diverging: list[tuple[str, str, str]] = []

    for _definition, column_name, declared in subject_columns(definitions):
        actual = actual_types.get(column_name)
        if actual is None:
            continue
        if actual.lower() == _INFORMATION_SCHEMA_TYPE.get(declared, declared).lower():
            continue
        diverging.append((column_name, actual, declared))

    return diverging


def build_subject_column_type_statements(
    schema: str,
    definitions: list["EntityDefinitionSpec"],
    actual_types: dict[str, str],
) -> list[str]:
    """One `ALTER COLUMN ... TYPE` per diverging `subject` column, clearing what it held.

    `USING NULL::<type>` rather than a value-preserving cast, for two independent reasons.

    The column is a *projection* of an entity, computed by `value_for_column(entity, kind)` —
    `document_entities` is the system of record. Under a new kind the correct value is a
    different projection of the same entity, never a cast of the old one: `'5 years'` under
    `text` must become `5.0` under `number`, and `5.0` must become `'5 years'` going back. A
    cast that succeeds is therefore still wrong, which is worse than one that fails. The values
    are not lost — they are re-derived by the projection at the next extraction of each
    document.

    And it always works. PostgreSQL refuses `TEXT -> DOUBLE PRECISION` and `TEXT -> DATE`
    outright without a `USING` clause (a property of the type pair, not of the data — an empty
    table is refused too), provides no cast at all between `DOUBLE PRECISION` and `DATE`, and
    aborts a casting `USING` on the first unparseable row. That last one matters most: this DDL
    runs inside the transaction of an entity-definition edit and at the start of every
    extraction run, so a conversion that can fail on data is a conversion that can brick both
    for data nobody chose."""
    schema_ident = _checked_identifier(schema, "schema")

    return [
        f"ALTER TABLE {schema_ident}.{SUBJECT_TABLE_NAME} "
        f"ALTER COLUMN {column_name} TYPE {declared} USING NULL::{declared}"
        for column_name, _actual, declared in diverging_subject_columns(definitions, actual_types)
    ]


def build_entity_table_statements(
    schema: str, definitions: list["EntityDefinitionSpec"]
) -> list[str]:
    """The full, idempotent table script for one tenant schema.

    Returned rather than executed so it can be inspected, diffed, and asserted on without a
    database. Every statement is safe to re-run, and the same inputs always produce the same
    list in the same order.

    Contains no `DROP`, `DELETE`, or `TRUNCATE` — not as an accident of the current definition
    set, but for every possible one, including definitions that are inactive or absent from the
    catalog. See the module docstring on why deactivation must not destroy rows."""
    schema_ident = _checked_identifier(schema, "schema")

    statements: list[str] = []
    for definition in _active(definitions, CARDINALITY_MULTI):
        statements.extend(build_child_table_statements(schema_ident, definition))

    statements.extend(build_subject_table_statements(schema_ident, definitions))
    return statements


def expected_table_names(definitions: list["EntityDefinitionSpec"]) -> set[str]:
    """Every table `build_entity_table_statements` would create or extend.

    `subject`, plus the child table of each active `multi` definition -- and nothing else. An
    active `single` definition owns a *column* on `subject`, not a table, so it contributes no
    name here. This doubles as the tenant's query surface, which is why `generated_table_names`
    is defined as this function rather than restated beside it."""
    names = {SUBJECT_TABLE_NAME}
    names.update(d.sql_identifier for d in _active(definitions, CARDINALITY_MULTI))
    return names


def catalogued_table_names(definitions: list["EntityDefinitionSpec"]) -> set[str]:
    """Every table name any supplied definition claims, active or not.

    Wider than `expected_table_names` on purpose, and in two directions: an inactive
    definition's table is retained, and so is the child table a definition keeps after its
    cardinality moves to `single`. Neither is an orphan. Only a table no definition claims at
    all is."""
    names = {SUBJECT_TABLE_NAME}
    names.update(d.sql_identifier for d in definitions if d.sql_identifier)
    return names


def generated_table_names(definitions: list["EntityDefinitionSpec"]) -> set[str]:
    """The tenant's query surface: `subject` plus every active `multi` definition's table.

    This is the set the execution role is granted `SELECT` on and the set `validate_sql`
    accepts, resolved from one function so the two cannot drift. It *is* `expected_table_names`
    -- the surface is exactly what the reconciler maintains -- and delegating rather than
    restating it is what keeps a table off the whitelist that the reconciler would never
    create.

    Three exclusions, each for its own reason:

    - An **inactive** definition: its table is retained, but deactivation means "stop answering
      questions from it".
    - A definition with **no `sql_identifier`**: no table was ever created for it.
    - An active **`single`** definition: its values live in a `subject` column and it has no
      table of its own. It may nonetheless still *have* one, because a definition that was
      `multi` when any reconcile ran got a child table, and the never-drop rule keeps that
      table and its rows forever. Listing its identifier here put a permanently empty relation
      on the surface: the projection stopped writing to it at the flip, so
      `SELECT ... FROM e_name` returns nothing and the model answers confidently from nothing.
      That is the silent-wrong-answer failure this module exists to avoid, so the retained
      table stays on disk and off the surface."""
    return expected_table_names(definitions)


# --------------------------------------------------------------------------------------------
# Reconciliation
# --------------------------------------------------------------------------------------------
#
# Thin wrappers around the pure functions above, mirroring `provision_role()` /
# `list_tenant_schemas()` in `src/chat_api/services/sql_execution_role.py`. Everything that
# decides *what* the DDL should be lives above this line; everything below only decides *when*
# to run it — and there are two of everything below only because the extraction worker holds a
# sync `Connection` while `gateway` holds an `AsyncSession`.


_SCHEMAS_QUERY = "SELECT nspname FROM pg_namespace WHERE nspname LIKE :prefix ORDER BY nspname"

_HAS_ENTITY_STORE_QUERY = (
    "SELECT 1 FROM information_schema.tables "
    "WHERE table_schema = :schema AND table_name = 'document_entities'"
)

# `pg_tables` rather than `information_schema.tables`: it matches physical tables only, which is
# exactly the set this module creates, and it is the same catalog the grant guard consults.
_EXISTING_TABLES_QUERY = "SELECT tablename FROM pg_tables WHERE schemaname = :schema"

# What `subject`'s columns physically are, which is the only question `pg_tables` cannot answer
# and the one a `value_kind` edit changes the answer to. `information_schema` rather than
# `pg_attribute` here because it reports the SQL-standard type name directly, and comparing
# spellings is the whole job.
_SUBJECT_COLUMN_TYPES_QUERY = (
    "SELECT column_name, data_type FROM information_schema.columns "
    "WHERE table_schema = :schema AND table_name = :relation"
)


async def list_tenant_schemas(session: AsyncSession) -> list[str]:
    """Every tenant schema, in a stable order.

    Duplicated from `src.chat_api.services.sql_execution_role.list_tenant_schemas` rather than
    imported: that module imports `WHITELISTED_TABLES` from `sql_generator`, so importing it
    here would drag the entire chat stack into `gateway`'s import graph for the sake of one
    `SELECT` against `pg_namespace`."""
    result = await session.execute(
        text(_SCHEMAS_QUERY), {"prefix": f"{TENANT_SCHEMA_PREFIX}%"}
    )
    return [row[0] for row in result.fetchall()]


def _generated_names(names: set[str]) -> set[str]:
    """Names in a schema this module could have created.

    Scoped to `subject` plus anything matching the generated-identifier grammar, so a table a
    tenant or a future migration created by hand is never mistaken for a generated one."""
    return {
        name
        for name in names
        if name == SUBJECT_TABLE_NAME or GENERATED_IDENTIFIER_RE.fullmatch(name)
    }


async def list_existing_generated_tables(session: AsyncSession, schema: str) -> set[str]:
    """The generated tables `schema` actually holds right now.

    The delete paths need this: a tenant whose schema has never been reconciled has no
    `subject` table at all, and a `DELETE` against a missing relation raises. Deleting a
    document must not depend on whether an extraction run has ever happened for that tenant."""
    schema_ident = checked_identifier(schema, "schema")
    result = await session.execute(text(_EXISTING_TABLES_QUERY), {"schema": schema_ident})
    return _generated_names({row[0] for row in result.fetchall()})


def list_existing_generated_tables_sync(conn: Connection, schema: str) -> set[str]:
    """`list_existing_generated_tables` for the extraction worker's sync `Connection`."""
    schema_ident = checked_identifier(schema, "schema")
    rows = conn.execute(text(_EXISTING_TABLES_QUERY), {"schema": schema_ident}).fetchall()
    return _generated_names({row[0] for row in rows})


def _renderable(definitions: list["EntityDefinitionSpec"]) -> list["EntityDefinitionSpec"]:
    """A definition with no `sql_identifier` is skipped rather than slugged here.

    A read-time slug is not stable across processes, so two workers could create tables under
    different names for the same entity type. The identifier is assigned once, in the catalog,
    by `EntityService.create_entity_type`."""
    return [d for d in definitions if d.sql_identifier]


def _log_reconciled(
    schema: str,
    statements: list[str],
    orphans: list[str],
    off_surface: list[str],
    retyped: list[tuple[str, str, str]] | None = None,
) -> None:
    for column_name, actual, declared in retyped or []:
        # One line per column, naming both types and saying plainly that the values are gone.
        # A cleared column is otherwise discovered later with nothing to attribute it to, and
        # "the column is empty" is a much harder thing to diagnose than "the column was
        # retyped, so it was cleared, and re-extraction refills it".
        logger.warning(
            "entity_tables column_retyped schema=%s column=%s from=%s to=%s values_cleared=true "
            "refill=re_extraction",
            schema, column_name, actual, declared,
        )
    if orphans:
        # Never dropped: the definition may be restored, and the rows are the only copy of the
        # projection. Surfaced so an operator can decide, which is the whole cleanup path.
        logger.info(
            "entity_tables orphaned schema=%s tables=%s action=retained",
            schema,
            ",".join(sorted(orphans)),
        )
    if off_surface:
        # Still claimed by a definition, but not something this catalog would create: the
        # definition is inactive, or its cardinality moved to `single` and its values now live
        # in a `subject` column. Kept on disk, written by nothing, queryable by nothing. Logged
        # because it is otherwise invisible -- it is not an orphan, so the line above never
        # names it, and an operator deciding whether a table is dead needs to see that it fell
        # off the surface rather than never having been on it.
        logger.info(
            "entity_tables off_surface schema=%s tables=%s action=retained",
            schema,
            ",".join(sorted(off_surface)),
        )
    logger.info(
        "entity_tables reconciled schema=%s statements=%d orphans_retained=%d "
        "off_surface_retained=%d",
        schema,
        len(statements),
        len(orphans),
        len(off_surface),
    )


def _reconcile_plan(
    schema: str,
    definitions: list["EntityDefinitionSpec"],
    existing: set[str],
    subject_column_types: dict[str, str] | None = None,
) -> tuple[list[str], list[str], list[str], list[tuple[str, str, str]]]:
    """`(statements, orphans, off_surface, retyped)` for one schema. Pure; both executors share it.

    `orphans` are generated tables no definition claims at all. `off_surface` are generated
    tables a definition still claims but that this catalog would not create -- an inactive
    definition's table, or the child table a definition kept when it became `single`. Neither
    set is dropped; they are separated because they call for different operator decisions, and
    because a table that fell off the surface is otherwise reported nowhere.

    `retyped` are the `subject` columns whose physical type no longer matches the type their
    definition's `value_kind` declares. Their `ALTER`s come **after** the create/add-column
    statements, which is what makes the caller's single pre-DDL snapshot valid for the whole
    list: a column this run creates is created at the declared type and is absent from the
    snapshot, so it is never also retyped."""
    renderable = _renderable(definitions)
    present = _generated_names(existing)
    catalogued = catalogued_table_names(renderable)
    active = expected_table_names(renderable)
    orphans = sorted(present - catalogued)
    off_surface = sorted((present & catalogued) - active)

    actual_types = subject_column_types or {}
    statements = build_entity_table_statements(schema, renderable)
    statements.extend(build_subject_column_type_statements(schema, renderable, actual_types))

    return statements, orphans, off_surface, diverging_subject_columns(renderable, actual_types)


async def reconcile_entity_tables(
    session: AsyncSession, schema: str, definitions: list["EntityDefinitionSpec"]
) -> list[str]:
    """Idempotent: bring `schema`'s generated tables in line with `entity_definitions`.

    Handles every state a tenant schema is actually found in — table missing (create), `subject`
    missing a newly-`single` definition's column (add it), a definition deactivated or gone from
    the catalog (leave its table and rows alone, log it), and a tenant with no definitions at all
    (the bare `subject` table). A schema lacking `document_entities` is skipped rather than
    raising, so one legacy tenant cannot abort the run for everyone after it — the same guard
    migrations `029` and `035` apply to their per-schema DDL.

    Executes inside the caller's transaction and never commits, so a caller can reconcile
    several schemas atomically. Returns the statements actually applied."""
    schema_ident = _checked_identifier(schema, "schema")

    has_store = await session.execute(text(_HAS_ENTITY_STORE_QUERY), {"schema": schema_ident})
    if has_store.fetchone() is None:
        logger.info("entity_tables skipped schema=%s reason=missing_document_entities", schema_ident)
        return []

    result = await session.execute(text(_EXISTING_TABLES_QUERY), {"schema": schema_ident})
    existing = {row[0] for row in result.fetchall()}
    types_result = await session.execute(
        text(_SUBJECT_COLUMN_TYPES_QUERY),
        {"schema": schema_ident, "relation": SUBJECT_TABLE_NAME},
    )
    subject_column_types = {row[0]: row[1] for row in types_result.fetchall()}

    statements, orphans, off_surface, retyped = _reconcile_plan(
        schema_ident, definitions, existing, subject_column_types
    )
    for statement in statements:
        await session.execute(text(statement))

    _log_reconciled(schema_ident, statements, orphans, off_surface, retyped)
    return statements


def reconcile_entity_tables_sync(
    conn: Connection, schema: str, definitions: list["EntityDefinitionSpec"]
) -> list[str]:
    """`reconcile_entity_tables` for a synchronous `Connection`.

    The extraction worker holds one, `gateway` holds an `AsyncSession`, and both must apply
    byte-identical DDL. Rather than reimplement the decisions, both executors run the same
    `_reconcile_plan`; only the `execute`/`await execute` differ."""
    schema_ident = _checked_identifier(schema, "schema")

    has_store = conn.execute(text(_HAS_ENTITY_STORE_QUERY), {"schema": schema_ident})
    if has_store.fetchone() is None:
        logger.info("entity_tables skipped schema=%s reason=missing_document_entities", schema_ident)
        return []

    existing = {
        row[0]
        for row in conn.execute(text(_EXISTING_TABLES_QUERY), {"schema": schema_ident}).fetchall()
    }
    subject_column_types = {
        row[0]: row[1]
        for row in conn.execute(
            text(_SUBJECT_COLUMN_TYPES_QUERY),
            {"schema": schema_ident, "relation": SUBJECT_TABLE_NAME},
        ).fetchall()
    }

    statements, orphans, off_surface, retyped = _reconcile_plan(
        schema_ident, definitions, existing, subject_column_types
    )
    for statement in statements:
        conn.execute(text(statement))

    _log_reconciled(schema_ident, statements, orphans, off_surface, retyped)
    return statements


# --------------------------------------------------------------------------------------------
# Query-surface resolution
# --------------------------------------------------------------------------------------------

_QUERY_SURFACE_QUERY = """
    SELECT tenant_id, name, sql_identifier, cardinality, value_kind, value_unit,
           description, examples, is_active, base_label_mapping
    FROM public.entity_definitions
    WHERE sql_identifier IS NOT NULL
"""


_TENANT_DEFINITIONS_QUERY = """
    SELECT name, sql_identifier, cardinality, value_kind, is_active, base_label_mapping
    FROM public.entity_definitions
    WHERE tenant_id = :tid AND sql_identifier IS NOT NULL
    ORDER BY sql_identifier
"""


def _as_mapping(value) -> dict | None:
    """`base_label_mapping` reads back as a dict on JSONB and as text on a TEXT column."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        import json

        try:
            parsed = json.loads(value)
        except ValueError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _as_list(value) -> list | None:
    """`examples` reads back as a list on JSONB and as text on a TEXT column."""
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value:
        import json

        try:
            parsed = json.loads(value)
        except ValueError:
            return None
        return parsed if isinstance(parsed, list) else None
    return None


def _spec_from_row(row) -> "EntityDefinitionSpec":
    # `getattr` on the metadata fields: two queries feed this function and only
    # `_QUERY_SURFACE_QUERY` selects them. A loader that does not need the semantics does not
    # pay for them, and adding them to a row is never required to build a valid spec.
    return EntityDefinitionSpec(
        name=row.name,
        sql_identifier=row.sql_identifier,
        cardinality=row.cardinality or CARDINALITY_MULTI,
        value_kind=getattr(row, "value_kind", None),
        is_active=bool(row.is_active),
        base_label_mapping=_as_mapping(row.base_label_mapping),
        description=getattr(row, "description", None),
        examples=_as_list(getattr(row, "examples", None)),
        value_unit=getattr(row, "value_unit", None),
    )


@dataclass(frozen=True)
class SubjectColumnSpec:
    """One `subject` column, and the definition whose values it holds.

    `name` and `sql_type` come from `subject_columns()` rather than being recomputed, so the
    column a consumer describes is the column the DDL added and the projection writes."""

    name: str
    sql_type: str
    definition: EntityDefinitionSpec


@dataclass(frozen=True)
class QuerySurface:
    """One tenant's readable relational surface: names, columns, and what they mean.

    Three consumers read this: the execution role's grant list, `validate_sql`'s table and
    column whitelist, and the SQL generator's prompt. Every one of them takes its view from
    this object, because the three failure modes of disagreeing are all invisible — a granted
    relation the validator rejects, a validated relation the database refuses, and a relation
    described to the generator that neither will accept.

    Derived, never restated: `table_names` is `generated_table_names()` and `subject_columns`
    is `subject_columns()`, the same two functions the reconciler and the projection use."""

    table_names: set[str]
    subject_columns: list[SubjectColumnSpec] = field(default_factory=list)
    child_tables: dict[str, EntityDefinitionSpec] = field(default_factory=dict)

    def columns_by_relation(self) -> dict[str, set[str]]:
        """`relation -> the columns it declares`, for a caller validating column references.

        `subject` carries its identity columns plus one per active `single` definition; a child
        table carries the fixed shape `_CHILD_TABLE_COLUMNS` creates, which is why it is read
        from `CHILD_VALUE_COLUMNS` rather than derived from the definition."""
        columns: dict[str, set[str]] = {
            SUBJECT_TABLE_NAME: set(SUBJECT_IDENTITY_COLUMNS)
            | {column.name for column in self.subject_columns}
        }
        for identifier in self.child_tables:
            columns[identifier] = set(CHILD_VALUE_COLUMNS)
        return columns


def build_query_surface(definitions: list["EntityDefinitionSpec"]) -> QuerySurface:
    """The surface one tenant's catalog describes. Pure, so it is assertable without a session.

    A child table appears only when it is on `generated_table_names` — which excludes the
    inactive, the identifier-less, and the table an active `single` definition retains from an
    earlier `multi` life. The retained table stays on disk and off the surface: the projection
    stopped writing to it at the flip, so querying it answers every question with zero rows."""
    table_names = generated_table_names(definitions)
    columns = [
        SubjectColumnSpec(name=name, sql_type=sql_type, definition=definition)
        for definition, name, sql_type in subject_columns(definitions)
    ]
    child_tables = {
        d.sql_identifier: d
        for d in _active(definitions, CARDINALITY_MULTI)
        if d.sql_identifier in table_names
    }
    return QuerySurface(
        table_names=table_names, subject_columns=columns, child_tables=child_tables
    )


async def load_definition_specs(
    session: AsyncSession, tenant_id: str
) -> list["EntityDefinitionSpec"]:
    """One tenant's renderable definitions, for an async caller.

    The sync sibling is `load_entity_definition_specs` in `semantic_normalizer.py`, which the
    extraction worker uses. Both skip a NULL `sql_identifier` — a read-time slug is not stable
    across processes — and both order by `sql_identifier`, which is what makes the projection's
    collision tie-break a property of the catalog rather than of row order.

    Inactive definitions are included: they are excluded from projection and from the query
    surface, but the delete path still needs to know their tables exist so a re-extraction or a
    document delete clears their stale rows."""
    result = await session.execute(text(_TENANT_DEFINITIONS_QUERY), {"tid": tenant_id})
    return [_spec_from_row(row) for row in result.fetchall()]


async def resolve_query_surface(
    session: AsyncSession, schemas: list[str]
) -> dict[str, QuerySurface]:
    """`schema -> QuerySurface` for the execution role, `validate_sql`, and the generator.

    One resolver feeds all three. A table present in the grants but absent from the whitelist is
    a query the validator rejects for a table the role can read; the reverse is a query the
    validator accepts and the database refuses; a relation described to the generator that is on
    neither is a query that cannot succeed. None is recoverable at run time, and none is visible
    in review, so they are computed from the same call rather than kept in step by discipline.

    Inactive definitions are excluded even though their tables are retained — that exclusion *is*
    what deactivation means for the query surface. Every requested schema appears in the result,
    carrying at least `subject`, because the reconciler creates it for a tenant with no
    definitions at all."""
    surface: dict[str, QuerySurface] = {
        _checked_identifier(schema, "schema"): build_query_surface([]) for schema in schemas
    }
    if not surface:
        return surface

    result = await session.execute(text(_QUERY_SURFACE_QUERY))
    by_schema: dict[str, list[EntityDefinitionSpec]] = {}
    for row in result.fetchall():
        by_schema.setdefault(schema_for_tenant(row.tenant_id), []).append(_spec_from_row(row))

    for schema, definitions in by_schema.items():
        if schema in surface:
            surface[schema] = build_query_surface(definitions)

    return surface


async def resolve_generated_tables(
    session: AsyncSession, schemas: list[str]
) -> dict[str, set[str]]:
    """`schema -> {generated table names}`, the name-only projection of the query surface.

    Kept as its own function because `build_role_statements` and its tests consume
    `dict[str, set[str]]`; changing that shape would churn a security-relevant path for no
    capability. It is a pure narrowing of one `resolve_query_surface` call, so the granted set
    is by construction the set the validator and the generator see."""
    return {
        schema: surface.table_names
        for schema, surface in (await resolve_query_surface(session, schemas)).items()
    }
