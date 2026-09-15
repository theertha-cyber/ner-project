"""Confidence routing, the review queue, review outcomes, and accumulation accounting

Five new tenant-schema tables plus one additive column on `public.tenants`. No existing table
loses a column or a constraint, which is what keeps the rollback story design.md claims: dropping
these tables leaves every span and every extracted entity exactly as it was, because review
outcomes become spans through the ordinary span model.

`routed_predictions` is both halves of Decision 1 in one table. A reconstructed entity from an
extraction run lands here with `disposition` recording which side of the review threshold it fell
on, and `below_business_threshold` recording — separately — whether it also fell below the
business-facing `confidence_threshold`. Two columns rather than one because they answer two
different questions and the whole point of Decision 1 is that those questions have different
right answers. Retaining the below-business-threshold rows here is what stops extraction
discarding them; nothing reads this table into a business-facing response.

`review_outcomes` is what a reviewer — human or LLM — decided. `prediction_id` is deliberately
NOT a foreign key: Decision 11 deletes the `routed_predictions` row once its information has been
extracted into an outcome, and the outcome has to survive that deletion or accumulation
accounting and route-agreement comparison would be destroyed by the cleanup that bounds storage.
The outcome therefore carries its own copy of the document, offsets, type and model version, and
also the *predicted* type and offsets, so "what the model said" and "what the reviewer said"
remain comparable after the prediction row is gone.

`span_review_provenance` is a join table rather than a column on `{schema}.spans`, matching
`span_batch_provenance` from `039` exactly. Together the two tables give the three origins
requirement 'Spans from production review are distinguishable by origin' asks for: a row here
means production review, a row in `span_batch_provenance` means batch acceptance, and neither
means individual manual annotation — which is what every pre-existing span is.

`span_training_consumption` is the record change 6 writes and this change reads. It exists here,
unwritten by any code in this change, because accumulation is *defined* as the spans no training
run has consumed yet (design.md Decision 5) and that definition needs somewhere to point. Change
6 owns its writer; nothing in this change inserts a row. An empty table means nothing has been
trained on, which is exactly right before the first retrain.

`audit_samples` is the accept path's only feedback. Like `039`'s `batch_acceptance_records` it
stores the drawn identities at selection time rather than recomputing them at read time — a
re-drawn sample makes the recorded agreement rate unfalsifiable.

`public.tenants.review_policy` carries Decision 10's per-tenant switch. It defaults to `human`,
so the LLM review route is implemented and tested but enabled for nobody until human-route
agreement data exists to compare it against.

Additive and reversible: `downgrade` drops exactly the five tables and the one column `upgrade`
creates.

Revision ID: 040
Revises: 039
Create Date: 2026-09-07
"""
from alembic import op
from sqlalchemy import text

revision = "040"
down_revision = "039b"
branch_labels = None
depends_on = None

# Stated here so the migration, the fixtures that mirror it, and the service constants cannot
# drift apart — the same reason `038` and `039` name their vocabularies.
DISPOSITIONS = ("accepted", "queued")
REVIEW_OUTCOMES = ("confirmed", "corrected", "rejected")
REVIEW_ROUTES = ("human", "llm")
OUTCOME_ORIGINS = ("queue", "audit")
AUDIT_STATUSES = ("in_review", "completed")
REVIEW_POLICIES = ("human", "llm")


def _values(vocabulary) -> str:
    return ", ".join("'{}'".format(value) for value in vocabulary)


# Each statement names `{schema}` more than once (the table and its foreign keys), so these are
# formatted against an enumerated schema list rather than run through a single-placeholder
# helper. `038` and `039` enumerate for the same reason.
_CREATE = [
    """
    CREATE TABLE IF NOT EXISTS {schema}.routed_predictions (
        id VARCHAR PRIMARY KEY,
        run_id VARCHAR NOT NULL
            REFERENCES {schema}.extraction_runs(id) ON DELETE CASCADE,
        document_id VARCHAR NOT NULL
            REFERENCES {schema}.documents(id) ON DELETE CASCADE,
        entity_type VARCHAR(255) NOT NULL,
        value TEXT NOT NULL,
        -- Min-aggregated across the span's constituent tokens by `aggregate_confidence`
        -- (design.md Decision 8). The queue and the extraction store therefore agree about
        -- the same span's confidence rather than each deriving its own.
        confidence DOUBLE PRECISION NOT NULL,
        char_start INTEGER NOT NULL,
        char_end INTEGER NOT NULL,
        -- Captured from the serving response at routing time, never inferred later
        -- (ADR-003). `served_by_base_model` is stored rather than derived by comparing the
        -- version against a literal, so ADR-008's fallback stays a recorded fact.
        model_version VARCHAR NOT NULL,
        served_by_base_model BOOLEAN NOT NULL DEFAULT false,
        -- Below the business-facing `confidence_threshold`. Distinct from `disposition`,
        -- which is about the review threshold: Decision 1's whole point is that these two
        -- questions are independent and must not share a knob.
        below_business_threshold BOOLEAN NOT NULL DEFAULT false,
        disposition VARCHAR(16) NOT NULL
            CHECK (disposition IN (__DISPOSITIONS__)),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_routed_predictions_disposition
        ON {schema}.routed_predictions (disposition, created_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_routed_predictions_document
        ON {schema}.routed_predictions (document_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS {schema}.review_outcomes (
        id VARCHAR PRIMARY KEY,
        -- Not a foreign key, deliberately. Decision 11 deletes the prediction row once this
        -- outcome exists; a cascade or a NOT NULL reference would make the storage bound
        -- destroy the accounting it is meant to be invisible to.
        prediction_id VARCHAR NOT NULL,
        document_id VARCHAR NOT NULL
            REFERENCES {schema}.documents(id) ON DELETE CASCADE,
        outcome VARCHAR(16) NOT NULL
            CHECK (outcome IN (__REVIEW_OUTCOMES__)),
        route VARCHAR(8) NOT NULL
            CHECK (route IN (__REVIEW_ROUTES__)),
        -- What the reviewer settled on. For a `confirmed` outcome these equal the predicted
        -- columns below; for `corrected` they are the reviewer's offsets and type; for
        -- `rejected` they are the prediction's, since no span is created either way.
        entity_type VARCHAR(255) NOT NULL,
        char_start INTEGER NOT NULL,
        char_end INTEGER NOT NULL,
        -- What the model said, kept alongside so agreement stays measurable after the
        -- prediction row is deleted.
        predicted_entity_type VARCHAR(255) NOT NULL,
        predicted_char_start INTEGER NOT NULL,
        predicted_char_end INTEGER NOT NULL,
        predicted_confidence DOUBLE PRECISION,
        model_version VARCHAR NOT NULL,
        served_by_base_model BOOLEAN NOT NULL DEFAULT false,
        -- Whether this outcome came from working the queue or from an audit draw over the
        -- auto-accepted population. Both use the same resolution path; only the population
        -- they were drawn from differs.
        origin VARCHAR(16) NOT NULL DEFAULT 'queue'
            CHECK (origin IN (__OUTCOME_ORIGINS__)),
        reviewer VARCHAR,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_review_outcomes_prediction
        ON {schema}.review_outcomes (prediction_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS {schema}.span_review_provenance (
        span_id VARCHAR PRIMARY KEY REFERENCES {schema}.spans(id) ON DELETE CASCADE,
        outcome_id VARCHAR NOT NULL
            REFERENCES {schema}.review_outcomes(id) ON DELETE CASCADE,
        -- Copied from the outcome so the accumulation query is one join rather than two,
        -- and so a span stays attributable to the version that predicted it.
        model_version VARCHAR NOT NULL,
        served_by_base_model BOOLEAN NOT NULL DEFAULT false,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_span_review_provenance_version
        ON {schema}.span_review_provenance (model_version)
    """,
    """
    CREATE TABLE IF NOT EXISTS {schema}.span_training_consumption (
        span_id VARCHAR PRIMARY KEY REFERENCES {schema}.spans(id) ON DELETE CASCADE,
        -- The version the run produced, not the version that predicted the span.
        model_version VARCHAR NOT NULL,
        training_job_id VARCHAR,
        recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS {schema}.audit_samples (
        id VARCHAR PRIMARY KEY,
        model_version VARCHAR NOT NULL,
        -- The auto-accepted population the draw was made from, recorded so a rate measured
        -- over 500 predictions is not silently compared with one measured over 12.
        population_size INTEGER NOT NULL,
        sample_size INTEGER NOT NULL,
        -- Drawn once, at selection time, and read back unchanged. Recomputing at read time
        -- would make the recorded rate unfalsifiable — `039` stores its sample for the same
        -- reason.
        sampled_prediction_ids JSONB NOT NULL,
        agreement_rate DOUBLE PRECISION,
        reviewed_count INTEGER,
        agreed_count INTEGER,
        dispositions JSONB,
        status VARCHAR(16) NOT NULL DEFAULT 'in_review'
            CHECK (status IN (__AUDIT_STATUSES__)),
        reviewer VARCHAR,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        completed_at TIMESTAMPTZ
    )
    """,
]

_VOCABULARIES = {
    "__DISPOSITIONS__": DISPOSITIONS,
    "__REVIEW_OUTCOMES__": REVIEW_OUTCOMES,
    "__REVIEW_ROUTES__": REVIEW_ROUTES,
    "__OUTCOME_ORIGINS__": OUTCOME_ORIGINS,
    "__AUDIT_STATUSES__": AUDIT_STATUSES,
}


def _statements() -> list[str]:
    rendered = []
    for statement in _CREATE:
        for placeholder, vocabulary in _VOCABULARIES.items():
            statement = statement.replace(placeholder, _values(vocabulary))
        rendered.append(statement)
    return rendered


_DROP = [
    "DROP TABLE IF EXISTS {schema}.audit_samples",
    "DROP TABLE IF EXISTS {schema}.span_training_consumption",
    "DROP TABLE IF EXISTS {schema}.span_review_provenance",
    "DROP TABLE IF EXISTS {schema}.review_outcomes",
    "DROP TABLE IF EXISTS {schema}.routed_predictions",
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

    # Decision 10's per-tenant route switch. Added with a default rather than backfilled so
    # every existing tenant is human-only the moment this lands, which is the shipped default
    # and the only safe one before any agreement baseline exists.
    op.execute(
        "ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS review_policy "
        "VARCHAR(8) NOT NULL DEFAULT 'human'"
    )
    op.execute(
        "ALTER TABLE public.tenants DROP CONSTRAINT IF EXISTS tenants_review_policy_check"
    )
    op.execute(
        "ALTER TABLE public.tenants ADD CONSTRAINT tenants_review_policy_check "
        "CHECK (review_policy IN ({}))".format(_values(REVIEW_POLICIES))
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE public.tenants DROP CONSTRAINT IF EXISTS tenants_review_policy_check"
    )
    op.execute("ALTER TABLE public.tenants DROP COLUMN IF EXISTS review_policy")
    for schema in _tenant_schemas():
        for statement in _DROP:
            op.execute(statement.format(schema='"{}"'.format(schema)))
