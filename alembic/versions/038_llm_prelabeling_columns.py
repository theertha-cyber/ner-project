"""qa_examples on entity_definitions, source on suggested_spans

Two additive columns for LLM-assisted pre-labeling.

`public.entity_definitions.qa_examples` holds question/answer pairs a tenant supplies as few-shot
context for the pre-labeling prompt. Nullable with no backfill: absent is the honest representation
of "this tenant configured none", and an entity type without QA pairs is still fully eligible for
extraction, so there is nothing to default it to. JSONB rather than TEXT because prompt construction
reads it as structured data, not as an opaque blob.

`{tenant_schema}.suggested_spans.source` records which mechanism produced a suggestion. NOT NULL
with a `'keyword'` default, and that default is what backfills existing rows: every suggestion that
exists before this migration came from the keyword matcher, so `'keyword'` is a statement of fact
about that data rather than a placeholder. Applied through `apply_to_all_tenant_schemas`, which
covers `tenant_template` — and since `TenantService.create_tenant` clones new schemas from
`tenant_template` with `LIKE ... INCLUDING DEFAULTS`, every tenant provisioned after this migration
gets the column and its default with no separate provisioning change.

VARCHAR + CHECK rather than an ENUM, matching `036` and `037`: a BERT-backed source is planned for a
later change in this same plan, and adding a value to a Postgres ENUM is itself a migration.

Additive-only and reversible: `downgrade` drops exactly what `upgrade` added and touches no other
column, so no pre-existing `suggested_spans` row is at risk in either direction.

Revision ID: 038
Revises: 037
Create Date: 2026-09-03
"""
from alembic import op
from sqlalchemy import text

from tenant_schema_ddl import apply_to_all_tenant_schemas

revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None

# The vocabulary lives here so the migration, the DDL the test fixtures mirror, and the service
# constant cannot drift apart silently.
SUGGESTION_SOURCES = ("keyword", "llm")
DEFAULT_SUGGESTION_SOURCE = "keyword"

_SOURCE_VALUES = ", ".join(f"'{value}'" for value in SUGGESTION_SOURCES)

_ADD_SOURCE = (
    "ALTER TABLE {schema}.suggested_spans "
    f"ADD COLUMN IF NOT EXISTS source VARCHAR(16) NOT NULL DEFAULT '{DEFAULT_SUGGESTION_SOURCE}'"
)

# Drop-then-add in one statement rather than a DO block: the helper interpolates the schema
# through a single `format()` placeholder, so a template naming `{schema}` twice would need
# positional specifiers to work at all.
_ADD_SOURCE_CHECK = (
    "ALTER TABLE {schema}.suggested_spans "
    "DROP CONSTRAINT IF EXISTS ck_suggested_spans_source, "
    f"ADD CONSTRAINT ck_suggested_spans_source CHECK (source IN ({_SOURCE_VALUES}))"
)

_DROP_SOURCE_CHECK = (
    "ALTER TABLE {schema}.suggested_spans DROP CONSTRAINT IF EXISTS ck_suggested_spans_source"
)

_DROP_SOURCE = "ALTER TABLE {schema}.suggested_spans DROP COLUMN IF EXISTS source"

# One table serving two purposes, because they are the same fact recorded once. A row is the
# job — what the async trigger returns a handle to, and what the status endpoint reads — and it
# is also the cache entry: `content_hash` plus `config_version` is the key, and `spans` is the
# grounded result. A separate cache would need its own invalidation story; this one expires by
# construction, because a document edit or a configuration change produces a different key.
#
# `spans` is stored rather than recomputed so a cache hit can re-materialise the suggestions.
# The prior job's rows in `suggested_spans` may be gone by then — a keyword pre-label run
# replaces every suggestion for the document — and "served from cache" has to mean the
# suggestions are there, not that they once were.
#
# Not written through `apply_to_all_tenant_schemas`: that helper interpolates the schema through
# a single `format()` placeholder, and this DDL names it twice (the table and its foreign key).
# The schemas are enumerated in Python instead, the way `037` enumerates rows to backfill.
_CREATE_JOBS_TABLE = """
    CREATE TABLE IF NOT EXISTS {schema}.llm_prelabel_jobs (
        id VARCHAR PRIMARY KEY,
        document_id VARCHAR NOT NULL REFERENCES {schema}.documents(id) ON DELETE CASCADE,
        status VARCHAR(16) NOT NULL DEFAULT 'queued',
        content_hash VARCHAR(64) NOT NULL,
        config_version VARCHAR(64) NOT NULL,
        served_from_cache BOOLEAN NOT NULL DEFAULT false,
        spans JSONB,
        counts JSONB,
        error_message TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        completed_at TIMESTAMPTZ
    )
"""

# The cache lookup: newest completed job for this document under this exact key.
_CREATE_JOBS_INDEX = """
    CREATE INDEX IF NOT EXISTS idx_llm_prelabel_jobs_cache_key
        ON {schema}.llm_prelabel_jobs (document_id, content_hash, config_version)
        WHERE status = 'completed'
"""

_DROP_JOBS_TABLE = "DROP TABLE IF EXISTS {schema}.llm_prelabel_jobs"


def _tenant_schemas() -> list[str]:
    """Every tenant schema, `tenant_template` included.

    The template is not optional: `TenantService.create_tenant` clones new schemas from it, so a
    table missing there is a table missing from every tenant provisioned afterwards."""
    conn = op.get_bind()
    rows = conn.execute(
        text(
            "SELECT nspname FROM pg_namespace "
            "WHERE nspname = 'tenant_template' OR nspname LIKE 'tenant\\_%' "
            "ORDER BY nspname"
        )
    ).fetchall()
    return [row[0] for row in rows]


def upgrade() -> None:
    op.execute("ALTER TABLE public.entity_definitions ADD COLUMN IF NOT EXISTS qa_examples JSONB")
    apply_to_all_tenant_schemas(op, _ADD_SOURCE)
    apply_to_all_tenant_schemas(op, _ADD_SOURCE_CHECK)
    for schema in _tenant_schemas():
        op.execute(_CREATE_JOBS_TABLE.format(schema=f'"{schema}"'))
        op.execute(_CREATE_JOBS_INDEX.format(schema=f'"{schema}"'))


def downgrade() -> None:
    for schema in _tenant_schemas():
        op.execute(_DROP_JOBS_TABLE.format(schema=f'"{schema}"'))
    apply_to_all_tenant_schemas(op, _DROP_SOURCE_CHECK)
    apply_to_all_tenant_schemas(op, _DROP_SOURCE)
    op.execute("ALTER TABLE public.entity_definitions DROP COLUMN IF EXISTS qa_examples")
