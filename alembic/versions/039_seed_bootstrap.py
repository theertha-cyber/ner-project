"""Schema proposals, batch pre-labeling, and the sampled acceptance record

Five new tenant-schema tables and nothing else. No existing table is altered in either
direction, which is what keeps this change's rollback story the one design.md claims: dropping
these tables leaves every suggestion and every confirmed span exactly as it was, because bulk
promotion writes ordinary rows through the existing span model.

`schema_proposals` / `schema_proposal_candidates` hold a generated proposal and its candidates.
The candidate rows carry a `disposition` and, once approved, the name of the entity type that
was created — but the entity type itself lives where it always has, in
`public.entity_definitions`, written through the entity-config API (design.md Decision 1). No
column here is a substitute for that row.

`prelabel_batches` / `prelabel_batch_documents` are the batch and its per-document outcome. The
per-document table is what makes "9 succeeded, 1 failed" a fact the batch can report rather than
an absence someone has to infer, and its `position` column preserves the submitted order so a
sample drawn later is demonstrably not the first N.

`batch_acceptance_records` is the audit row: which documents were drawn, how many, what rate the
reviewer's dispositions produced, against which threshold, and who decided. `sampled_document_ids`
is stored at selection time rather than recomputed at read time — a re-drawn sample would make
the recorded rate unfalsifiable, which is the whole reason design.md Decision 4 asks for it.

`span_batch_provenance` is a separate table rather than a column on `{schema}.spans`. A
bulk-accepted span must be distinguishable from an individually reviewed one, and a join table
records more than a flag would: it names the batch and the acceptance record whose measured rate
admitted the span, so a quality problem found later is traceable to the decision that let it in.
Absence of a row means individual review, which is what every pre-existing span is.

Additive-only and reversible: `downgrade` drops exactly the six tables `upgrade` creates.

Revision ID: 039
Revises: 038
Create Date: 2026-09-03
"""
from alembic import op
from sqlalchemy import text

revision = "039b"
down_revision = "039"
branch_labels = None
depends_on = None

# Stated here so the migration, the test fixtures that mirror it, and the service constants
# cannot drift apart — the same reason `038` names its source vocabulary.
PROPOSAL_STATUSES = ("queued", "running", "completed", "failed")
CANDIDATE_DISPOSITIONS = ("pending", "approved", "edited", "rejected")
BATCH_STATUSES = ("queued", "running", "completed", "failed")
BATCH_DOCUMENT_STATUSES = ("pending", "succeeded", "failed")
ACCEPTANCE_DECISIONS = ("in_review", "accepted", "rejected")


def _values(vocabulary) -> str:
    return ", ".join("'{}'".format(value) for value in vocabulary)


# Each statement names `{schema}` more than once (the table and its foreign keys), so these are
# formatted against an enumerated schema list rather than run through
# `apply_to_all_tenant_schemas`, whose single `format()` placeholder cannot express that. `038`
# enumerates for the same reason.
_CREATE = [
    """
    CREATE TABLE IF NOT EXISTS {schema}.schema_proposals (
        id VARCHAR PRIMARY KEY,
        status VARCHAR(16) NOT NULL DEFAULT 'queued'
            CHECK (status IN (__PROPOSAL_STATUSES__)),
        seed_document_ids JSONB NOT NULL,
        requested_by VARCHAR,
        error_message TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        completed_at TIMESTAMPTZ
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS {schema}.schema_proposal_candidates (
        id VARCHAR PRIMARY KEY,
        proposal_id VARCHAR NOT NULL
            REFERENCES {schema}.schema_proposals(id) ON DELETE CASCADE,
        name VARCHAR(255) NOT NULL,
        description TEXT,
        -- Every element has been checked against a seed document before it lands here; an
        -- example that would not ground is dropped rather than stored (task 2.3).
        examples JSONB NOT NULL DEFAULT '[]'::jsonb,
        disposition VARCHAR(16) NOT NULL DEFAULT 'pending'
            CHECK (disposition IN (__CANDIDATE_DISPOSITIONS__)),
        created_entity_type VARCHAR(255),
        updated_at TIMESTAMPTZ
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_schema_proposal_candidates_proposal
        ON {schema}.schema_proposal_candidates (proposal_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS {schema}.prelabel_batches (
        id VARCHAR PRIMARY KEY,
        status VARCHAR(16) NOT NULL DEFAULT 'queued'
            CHECK (status IN (__BATCH_STATUSES__)),
        requested_by VARCHAR,
        error_message TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        completed_at TIMESTAMPTZ
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS {schema}.prelabel_batch_documents (
        id VARCHAR PRIMARY KEY,
        batch_id VARCHAR NOT NULL
            REFERENCES {schema}.prelabel_batches(id) ON DELETE CASCADE,
        document_id VARCHAR NOT NULL
            REFERENCES {schema}.documents(id) ON DELETE CASCADE,
        -- Submission order. Kept so a randomly drawn sample can be shown not to be the first N
        -- (design.md Decision 4) rather than merely asserted to be random.
        position INTEGER NOT NULL,
        status VARCHAR(16) NOT NULL DEFAULT 'pending'
            CHECK (status IN (__BATCH_DOCUMENT_STATUSES__)),
        counts JSONB,
        error_message TEXT,
        completed_at TIMESTAMPTZ,
        UNIQUE (batch_id, document_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_prelabel_batch_documents_batch
        ON {schema}.prelabel_batch_documents (batch_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS {schema}.batch_acceptance_records (
        id VARCHAR PRIMARY KEY,
        batch_id VARCHAR NOT NULL
            REFERENCES {schema}.prelabel_batches(id) ON DELETE CASCADE,
        -- Drawn once, at selection time, and read back unchanged. Recomputing this at read
        -- time would make the recorded agreement rate unfalsifiable.
        sampled_document_ids JSONB NOT NULL,
        sample_size INTEGER NOT NULL,
        -- Whether the sample is a subset or the whole batch, recorded per record rather than
        -- read from configuration later: a rate measured under full review and one measured
        -- under sampling are not the same evidence, and configuration changes.
        sampled BOOLEAN NOT NULL,
        agreement_threshold DOUBLE PRECISION NOT NULL,
        agreement_rate DOUBLE PRECISION,
        reviewed_count INTEGER,
        agreed_count INTEGER,
        -- Per-suggestion dispositions as submitted. The gate reads only whether each was an
        -- exact agreement, but the disagreement kind is kept: comparing an exact-match rate
        -- with an overlap-tolerant one on real batches is what the threshold is waiting on.
        dispositions JSONB,
        decision VARCHAR(16) NOT NULL DEFAULT 'in_review'
            CHECK (decision IN (__ACCEPTANCE_DECISIONS__)),
        reviewer VARCHAR,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        decided_at TIMESTAMPTZ
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_batch_acceptance_records_batch
        ON {schema}.batch_acceptance_records (batch_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS {schema}.span_batch_provenance (
        span_id VARCHAR PRIMARY KEY REFERENCES {schema}.spans(id) ON DELETE CASCADE,
        batch_id VARCHAR NOT NULL REFERENCES {schema}.prelabel_batches(id) ON DELETE CASCADE,
        acceptance_id VARCHAR NOT NULL
            REFERENCES {schema}.batch_acceptance_records(id) ON DELETE CASCADE,
        promoted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
]

# The vocabularies are substituted rather than f-string interpolated because every statement
# above also carries `{schema}` placeholders that must survive until `upgrade()` formats them.
_VOCABULARIES = {
    "__PROPOSAL_STATUSES__": PROPOSAL_STATUSES,
    "__CANDIDATE_DISPOSITIONS__": CANDIDATE_DISPOSITIONS,
    "__BATCH_STATUSES__": BATCH_STATUSES,
    "__BATCH_DOCUMENT_STATUSES__": BATCH_DOCUMENT_STATUSES,
    "__ACCEPTANCE_DECISIONS__": ACCEPTANCE_DECISIONS,
}


def _statements() -> list[str]:
    rendered = []
    for statement in _CREATE:
        for placeholder, vocabulary in _VOCABULARIES.items():
            statement = statement.replace(placeholder, _values(vocabulary))
        rendered.append(statement)
    return rendered


_DROP = [
    "DROP TABLE IF EXISTS {schema}.span_batch_provenance",
    "DROP TABLE IF EXISTS {schema}.batch_acceptance_records",
    "DROP TABLE IF EXISTS {schema}.prelabel_batch_documents",
    "DROP TABLE IF EXISTS {schema}.prelabel_batches",
    "DROP TABLE IF EXISTS {schema}.schema_proposal_candidates",
    "DROP TABLE IF EXISTS {schema}.schema_proposals",
]


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
    statements = _statements()
    for schema in _tenant_schemas():
        for statement in statements:
            op.execute(statement.format(schema='"{}"'.format(schema)))


def downgrade() -> None:
    for schema in _tenant_schemas():
        for statement in _DROP:
            op.execute(statement.format(schema='"{}"'.format(schema)))
