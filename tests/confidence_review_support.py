"""Fixtures shared by the `test_confidence_routing` / `test_review_queue` / `test_review_outcomes`
/ `test_audit_sampling` / `test_accumulation_reporting` files.

Not a test module — pytest collects `test_*.py`, so this is imported rather than run.

The DDL below mirrors migration `040` (and the `039`/`004` tables this change joins against) for
the tables these tests touch. Duplicated from the migration rather than derived from it for the
same reason `seed_bootstrap_support.py` duplicates its own: these tests build and drop a
throwaway schema per test, and running the whole migration chain per test would trade a few
seconds of clarity for several minutes of runtime. The migration remains the source of truth; a
divergence between the two is a defect these tests are meant to make visible when they stop
passing against a real schema.
"""

import uuid

from sqlalchemy import text

# A document whose entities sit at offsets a test can state literally, so an assertion about
# "45-53" is checkable by eye against the string rather than by running the code that produced it.
#
#          1         2         3         4         5         6
# 0123456789012345678901234567890123456789012345678901234567890
# Jane Roe works as a Data Analyst at Acme Corp in Chennai today.
#                                     ^45      ^53
DOCUMENT_TEXT = "Jane Roe works as a Data Analyst at Acme Corp in Chennai today."

# The offsets the spec's own scenarios use. Asserted here so a test that drifts from the spec's
# numbers fails at import rather than passing against different ones.
ORG_START = 36
ORG_END = 45
assert DOCUMENT_TEXT[ORG_START:ORG_END] == "Acme Corp", DOCUMENT_TEXT[ORG_START:ORG_END]


def make_token(tenant_id, role="tenant_admin"):
    from src.shared.auth import create_access_token

    return create_access_token(tenant_id=tenant_id, user_id="test-reviewer", role=role)


def auth_header(tenant_id, role="tenant_admin") -> dict:
    return {"Authorization": "Bearer " + make_token(tenant_id, role)}


_TENANTS_SQL = """
    CREATE TABLE IF NOT EXISTS public.tenants (
        id VARCHAR PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        slug VARCHAR(63) NOT NULL UNIQUE,
        status VARCHAR(20) DEFAULT 'active',
        max_users INTEGER DEFAULT 10,
        max_documents INTEGER DEFAULT 1000,
        max_storage_gb INTEGER DEFAULT 5,
        max_model_versions INTEGER DEFAULT 10,
        storage_used_bytes BIGINT DEFAULT 0,
        review_policy VARCHAR(8) NOT NULL DEFAULT 'human',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
"""


def tenant_tables_sql(schema: str) -> list[str]:
    """Every tenant table these tests touch, in dependency order."""
    return [
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.documents (
                id VARCHAR PRIMARY KEY,
                tenant_id VARCHAR NOT NULL,
                filename VARCHAR(255) NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                purpose VARCHAR(20) NOT NULL DEFAULT 'query',
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.document_text_spans (
                id VARCHAR PRIMARY KEY,
                document_id VARCHAR NOT NULL,
                span_index INTEGER,
                "text" TEXT,
                char_start INTEGER,
                char_end INTEGER,
                page_number INTEGER,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.extraction_runs (
                id VARCHAR PRIMARY KEY,
                tenant_id VARCHAR NOT NULL,
                document_id VARCHAR NOT NULL REFERENCES {schema}.documents(id) ON DELETE CASCADE,
                model_version VARCHAR,
                status VARCHAR(20) DEFAULT 'queued',
                started_at TIMESTAMPTZ,
                completed_at TIMESTAMPTZ
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.model_versions (
                id VARCHAR PRIMARY KEY,
                tenant_id VARCHAR NOT NULL,
                -- Nullable, as `018` left it. `version` is the original column from `002`;
                -- `018` added `version_number`, backfilled it, and dropped the NOT NULL, and
                -- the training worker has written only `version_number` since. A fixture that
                -- kept `version` mandatory could not represent a version this platform
                -- actually produces.
                version INTEGER,
                version_number INTEGER,
                artifact_uri VARCHAR(500),
                artifact_path TEXT,
                training_job_id VARCHAR,
                metrics JSONB,
                status VARCHAR(20) DEFAULT 'candidate',
                active_flag BOOLEAN DEFAULT false,
                promoted_by VARCHAR,
                promoted_at TIMESTAMPTZ,
                archived_at TIMESTAMPTZ,
                mlflow_run_id VARCHAR,
                run_number INTEGER,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """,
        # From `005`. Present so a test can put a job in flight, approve one, or reject one
        # against the same schema the surfaces read.
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.training_jobs (
                id VARCHAR PRIMARY KEY,
                tenant_id VARCHAR NOT NULL,
                status VARCHAR(30) NOT NULL DEFAULT 'pending_approval',
                source_scope VARCHAR(16),
                hyperparams JSONB,
                celery_task_id VARCHAR,
                current_epoch INTEGER,
                current_loss DOUBLE PRECISION,
                metrics JSONB,
                error_message TEXT,
                model_version_id VARCHAR,
                mlflow_run_id VARCHAR,
                mlflow_run_url TEXT,
                run_number INTEGER,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                started_at TIMESTAMPTZ,
                completed_at TIMESTAMPTZ,
                failed_at TIMESTAMPTZ
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.extracted_entities (
                id VARCHAR PRIMARY KEY,
                run_id VARCHAR NOT NULL REFERENCES {schema}.extraction_runs(id) ON DELETE CASCADE,
                entity_id VARCHAR NOT NULL,
                value TEXT,
                confidence FLOAT,
                review_status VARCHAR(20) DEFAULT 'unreviewed',
                corrected_value TEXT,
                corrected_by VARCHAR,
                document_id VARCHAR
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.spans (
                id VARCHAR PRIMARY KEY,
                document_id VARCHAR NOT NULL REFERENCES {schema}.documents(id) ON DELETE CASCADE,
                entity_type VARCHAR(255) NOT NULL,
                char_start INTEGER NOT NULL,
                char_end INTEGER NOT NULL,
                text_content VARCHAR NOT NULL,
                confidence FLOAT NOT NULL DEFAULT 1.0,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ,
                bio_tags TEXT[]
            )
        """,
        # From `039`. Present so a test can create a batch-accepted span and show it is
        # distinguishable from a production-review one (spec row 17).
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.prelabel_batches (
                id VARCHAR PRIMARY KEY,
                status VARCHAR(16) NOT NULL DEFAULT 'queued',
                annotator_review_status VARCHAR(32),
                training_eligible_at TIMESTAMPTZ,
                requested_by VARCHAR,
                error_message TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                completed_at TIMESTAMPTZ
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.annotation_tasks (
                id VARCHAR PRIMARY KEY,
                document_id VARCHAR,
                annotator_user_id VARCHAR,
                status VARCHAR(20) DEFAULT 'unannotated',
                training_eligible_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.annotation_imports (
                source_file VARCHAR PRIMARY KEY,
                row_count INTEGER NOT NULL DEFAULT 0,
                type_map JSONB,
                training_eligible_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.batch_acceptance_records (
                id VARCHAR PRIMARY KEY,
                batch_id VARCHAR NOT NULL
                    REFERENCES {schema}.prelabel_batches(id) ON DELETE CASCADE,
                sampled_document_ids JSONB NOT NULL,
                sample_size INTEGER NOT NULL,
                sampled BOOLEAN NOT NULL,
                agreement_threshold DOUBLE PRECISION NOT NULL,
                agreement_rate DOUBLE PRECISION,
                reviewed_count INTEGER,
                agreed_count INTEGER,
                dispositions JSONB,
                decision VARCHAR(16) NOT NULL DEFAULT 'in_review',
                reviewer VARCHAR,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                decided_at TIMESTAMPTZ
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.span_batch_provenance (
                span_id VARCHAR PRIMARY KEY REFERENCES {schema}.spans(id) ON DELETE CASCADE,
                batch_id VARCHAR NOT NULL
                    REFERENCES {schema}.prelabel_batches(id) ON DELETE CASCADE,
                acceptance_id VARCHAR NOT NULL
                    REFERENCES {schema}.batch_acceptance_records(id) ON DELETE CASCADE,
                promoted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """,
        # --- migration 040 ---
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.routed_predictions (
                id VARCHAR PRIMARY KEY,
                run_id VARCHAR NOT NULL
                    REFERENCES {schema}.extraction_runs(id) ON DELETE CASCADE,
                document_id VARCHAR NOT NULL
                    REFERENCES {schema}.documents(id) ON DELETE CASCADE,
                entity_type VARCHAR(255) NOT NULL,
                value TEXT NOT NULL,
                confidence DOUBLE PRECISION NOT NULL,
                char_start INTEGER NOT NULL,
                char_end INTEGER NOT NULL,
                model_version VARCHAR NOT NULL,
                served_by_base_model BOOLEAN NOT NULL DEFAULT false,
                below_business_threshold BOOLEAN NOT NULL DEFAULT false,
                disposition VARCHAR(16) NOT NULL
                    CHECK (disposition IN ('accepted', 'queued')),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.review_outcomes (
                id VARCHAR PRIMARY KEY,
                prediction_id VARCHAR NOT NULL,
                document_id VARCHAR NOT NULL
                    REFERENCES {schema}.documents(id) ON DELETE CASCADE,
                outcome VARCHAR(16) NOT NULL
                    CHECK (outcome IN ('confirmed', 'corrected', 'rejected')),
                route VARCHAR(8) NOT NULL CHECK (route IN ('human', 'llm')),
                entity_type VARCHAR(255) NOT NULL,
                char_start INTEGER NOT NULL,
                char_end INTEGER NOT NULL,
                predicted_entity_type VARCHAR(255) NOT NULL,
                predicted_char_start INTEGER NOT NULL,
                predicted_char_end INTEGER NOT NULL,
                predicted_confidence DOUBLE PRECISION,
                model_version VARCHAR NOT NULL,
                served_by_base_model BOOLEAN NOT NULL DEFAULT false,
                origin VARCHAR(16) NOT NULL DEFAULT 'queue'
                    CHECK (origin IN ('queue', 'audit')),
                reviewer VARCHAR,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.span_review_provenance (
                span_id VARCHAR PRIMARY KEY REFERENCES {schema}.spans(id) ON DELETE CASCADE,
                outcome_id VARCHAR NOT NULL
                    REFERENCES {schema}.review_outcomes(id) ON DELETE CASCADE,
                model_version VARCHAR NOT NULL,
                served_by_base_model BOOLEAN NOT NULL DEFAULT false,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.span_training_consumption (
                span_id VARCHAR PRIMARY KEY REFERENCES {schema}.spans(id) ON DELETE CASCADE,
                model_version VARCHAR NOT NULL,
                training_job_id VARCHAR,
                recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.audit_samples (
                id VARCHAR PRIMARY KEY,
                model_version VARCHAR NOT NULL,
                population_size INTEGER NOT NULL,
                sample_size INTEGER NOT NULL,
                sampled_prediction_ids JSONB NOT NULL,
                agreement_rate DOUBLE PRECISION,
                reviewed_count INTEGER,
                agreed_count INTEGER,
                dispositions JSONB,
                status VARCHAR(16) NOT NULL DEFAULT 'in_review'
                    CHECK (status IN ('in_review', 'completed')),
                reviewer VARCHAR,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                completed_at TIMESTAMPTZ
            )
        """,
    ]


async def make_tenant(engine, review_policy="human"):
    """A throwaway tenant with its own schema and catalog row."""
    tid = uuid.uuid4().hex
    schema = f"tenant_{tid}"
    async with engine.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        await conn.execute(text(_TENANTS_SQL))
        # A pre-existing `public.tenants` may predate `040`; add the column rather than assume it.
        await conn.execute(
            text(
                "ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS review_policy "
                "VARCHAR(8) NOT NULL DEFAULT 'human'"
            )
        )
        for ddl in tenant_tables_sql(schema):
            await conn.execute(text(ddl))
        # The tenant-context middleware resolves the JWT's tenant against this table before any
        # handler runs, so a schema without a row here is a 404 rather than the request under test.
        await conn.execute(
            text(
                "INSERT INTO public.tenants (id, name, slug, status, review_policy) "
                "VALUES (:id, :name, :slug, 'active', :policy) ON CONFLICT (id) DO NOTHING"
            ),
            {
                "id": tid,
                "name": f"Review {tid[:8]}",
                "slug": f"conf-review-{tid[:8]}",
                "policy": review_policy,
            },
        )
    return {"tid": tid, "schema": schema}


async def add_document(engine, tenant, document_text=DOCUMENT_TEXT, purpose="query"):
    """A processed document with text.

    `purpose` defaults to `query` because that is the only purpose extraction runs on —
    `_get_documents_to_process` filters on `status = 'processed' AND purpose = 'query'`. A
    routed prediction therefore always belongs to a query-purpose document, and a test that
    created a `training` one would be constructing a state routing never produces.
    """
    doc_id = str(uuid.uuid4())
    schema = tenant["schema"]
    async with engine.begin() as conn:
        await conn.execute(
            text(
                f"INSERT INTO {schema}.documents (id, tenant_id, filename, status, purpose) "
                "VALUES (:id, :tid, 'review-test.txt', 'processed', :purpose)"
            ),
            {"id": doc_id, "tid": tenant["tid"], "purpose": purpose},
        )
        await conn.execute(
            text(
                f'INSERT INTO {schema}.document_text_spans '
                '(id, document_id, span_index, "text", char_start, char_end, page_number) '
                "VALUES (:sid, :doc_id, 0, :txt, 0, :length, 1)"
            ),
            {
                "sid": str(uuid.uuid4()),
                "doc_id": doc_id,
                "txt": document_text,
                "length": len(document_text),
            },
        )
    return doc_id


async def add_run(engine, tenant, doc_id, model_version="3"):
    run_id = str(uuid.uuid4())
    schema = tenant["schema"]
    async with engine.begin() as conn:
        await conn.execute(
            text(
                f"INSERT INTO {schema}.extraction_runs "
                "(id, tenant_id, document_id, model_version, status) "
                "VALUES (:id, :tid, :doc_id, :mv, 'completed')"
            ),
            {"id": run_id, "tid": tenant["tid"], "doc_id": doc_id, "mv": model_version},
        )
    return run_id


async def add_prediction(
    engine,
    tenant,
    run_id,
    doc_id,
    entity_type="organization",
    value="Acme Corp",
    confidence=0.62,
    char_start=ORG_START,
    char_end=ORG_END,
    model_version="3",
    served_by_base_model=False,
    below_business_threshold=False,
    disposition="queued",
):
    """One `routed_predictions` row, written directly.

    Written directly rather than by running the extraction worker: these tests are about what
    happens to a routed prediction, and going through inference to obtain one would make them
    depend on a model's output for numbers they need to state exactly.
    """
    pred_id = str(uuid.uuid4())
    schema = tenant["schema"]
    async with engine.begin() as conn:
        await conn.execute(
            text(
                f"INSERT INTO {schema}.routed_predictions "
                "(id, run_id, document_id, entity_type, value, confidence, char_start, char_end, "
                " model_version, served_by_base_model, below_business_threshold, disposition) "
                "VALUES (:id, :run_id, :doc_id, :etype, :value, :conf, :cs, :ce, :mv, :base, "
                "        :below, :disp)"
            ),
            {
                "id": pred_id,
                "run_id": run_id,
                "doc_id": doc_id,
                "etype": entity_type,
                "value": value,
                "conf": confidence,
                "cs": char_start,
                "ce": char_end,
                "mv": model_version,
                "base": served_by_base_model,
                "below": below_business_threshold,
                "disp": disposition,
            },
        )
    return pred_id


async def drop_test_schemas(engine):
    """Drop only the schemas this module created.

    Scoped by the tenant's own slug rather than by a `tenant_%` wildcard. The wildcard also
    matched the baseline schemas `conftest.pytest_sessionstart` provisions — `tenant_test_tenant`
    and friends — so one module's teardown removed tables the rest of the suite depends on, and
    deadlocked against any still-open connection while doing it.
    """
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT 'tenant_' || id FROM public.tenants WHERE slug LIKE 'conf-review-%'"
            )
        )
        schemas = [row[0] for row in rows]
        for schema in schemas:
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await conn.execute(
            text("DELETE FROM public.tenants WHERE slug LIKE 'conf-review-%'")
        )
