"""Fixtures shared by the four `test_seed_bootstrap_*` files.

Not a test module — pytest collects `test_*.py`, so this is imported rather than run.

The DDL below mirrors migrations `038` and `039` for the tables this change touches. It is
duplicated from the migrations rather than derived from them for the same reason
`test_llm_prelabel_api.py` duplicates its own: these tests build and drop a throwaway schema per
test, and running the whole migration chain per test would trade a few seconds of clarity for
several minutes of runtime. The migration remains the source of truth; a divergence between the
two is a defect these tests are meant to make visible when they stop passing against a real
schema.
"""

import uuid

from sqlalchemy import text

# One resume-shaped document, used wherever a test needs text with recognisable entities in it.
DOCUMENT_TEXT = (
    "John Doe works as a Senior Engineer at Acme Corp and studied at "
    "Vellore Institute of Technology. "
    "Jane Roe works as a Data Analyst at Globex and studied at Anna University."
)


def make_token(tenant_id, role="tenant_admin"):
    from src.shared.auth import create_access_token

    return create_access_token(tenant_id=tenant_id, user_id="test-user", role=role)


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
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
"""

_NOTIFICATIONS_SQL = """
    CREATE TABLE IF NOT EXISTS public.notifications (
        id VARCHAR PRIMARY KEY,
        tenant_id VARCHAR NOT NULL,
        recipient_role VARCHAR(50),
        recipient_user_id VARCHAR,
        kind VARCHAR(64) NOT NULL,
        title VARCHAR(255) NOT NULL,
        body TEXT,
        resource_type VARCHAR(64),
        resource_id VARCHAR,
        read_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
"""

# The full shape, not the reduced one the change 1 tests use: approval runs the real
# `EntityService.create_entity_type`, which assigns `sql_identifier` and reads `cardinality`.
_ENTITY_DEFINITIONS_SQL = """
    CREATE TABLE IF NOT EXISTS public.entity_definitions (
        id VARCHAR PRIMARY KEY,
        tenant_id VARCHAR NOT NULL,
        name VARCHAR(255) NOT NULL,
        description TEXT,
        examples JSON,
        qa_examples JSONB,
        validation_rule VARCHAR(500),
        target_table VARCHAR(255),
        base_label_mapping JSON,
        value_kind VARCHAR(32),
        value_unit VARCHAR(32),
        cardinality VARCHAR(16) NOT NULL DEFAULT 'multi',
        sql_identifier VARCHAR(63),
        version INTEGER NOT NULL DEFAULT 1,
        required_flag BOOLEAN DEFAULT false,
        is_active BOOLEAN DEFAULT true,
        provenance VARCHAR(16) NOT NULL DEFAULT 'manual',
        provenance_ref VARCHAR(255),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
"""


def tenant_tables_sql(schema: str) -> list[str]:
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
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.suggested_spans (
                id VARCHAR PRIMARY KEY,
                document_id VARCHAR NOT NULL REFERENCES {schema}.documents(id) ON DELETE CASCADE,
                entity_type VARCHAR(255) NOT NULL,
                char_start INTEGER NOT NULL,
                char_end INTEGER NOT NULL,
                text_content VARCHAR NOT NULL,
                confidence FLOAT NOT NULL,
                source VARCHAR(16) NOT NULL DEFAULT 'keyword',
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.schema_proposals (
                id VARCHAR PRIMARY KEY,
                status VARCHAR(16) NOT NULL DEFAULT 'queued',
                seed_document_ids JSONB NOT NULL,
                qa_pair_document_id VARCHAR,
                requested_by VARCHAR,
                error_message TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                completed_at TIMESTAMPTZ
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.schema_proposal_candidates (
                id VARCHAR PRIMARY KEY,
                proposal_id VARCHAR NOT NULL
                    REFERENCES {schema}.schema_proposals(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                examples JSONB NOT NULL DEFAULT '[]'::jsonb,
                disposition VARCHAR(16) NOT NULL DEFAULT 'pending',
                created_entity_type VARCHAR(255),
                updated_at TIMESTAMPTZ
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.prelabel_batches (
                id VARCHAR PRIMARY KEY,
                status VARCHAR(16) NOT NULL DEFAULT 'queued',
                batch_kind VARCHAR(16) NOT NULL DEFAULT 'large',
                state VARCHAR(24),
                annotator_review_status VARCHAR(32),
                training_eligible_at TIMESTAMPTZ,
                requested_by VARCHAR,
                error_message TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                completed_at TIMESTAMPTZ
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.prelabel_batch_guidance (
                id VARCHAR PRIMARY KEY,
                batch_id VARCHAR NOT NULL
                    REFERENCES {schema}.prelabel_batches(id) ON DELETE CASCADE,
                document_id VARCHAR NOT NULL
                    REFERENCES {schema}.documents(id) ON DELETE CASCADE,
                corrected_spans JSONB,
                note TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (batch_id, document_id)
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.prelabel_batch_documents (
                id VARCHAR PRIMARY KEY,
                batch_id VARCHAR NOT NULL
                    REFERENCES {schema}.prelabel_batches(id) ON DELETE CASCADE,
                document_id VARCHAR NOT NULL
                    REFERENCES {schema}.documents(id) ON DELETE CASCADE,
                position INTEGER NOT NULL,
                status VARCHAR(16) NOT NULL DEFAULT 'pending',
                counts JSONB,
                error_message TEXT,
                completed_at TIMESTAMPTZ,
                UNIQUE (batch_id, document_id)
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
    ]


async def make_tenant(engine, entity_types=("person_name", "institute")):
    """A throwaway tenant with its own schema, catalog row, and entity types."""
    tid = uuid.uuid4().hex
    schema = f"tenant_{tid}"
    async with engine.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        await conn.execute(text(_TENANTS_SQL))
        await conn.execute(text(_ENTITY_DEFINITIONS_SQL))
        await conn.execute(text(_NOTIFICATIONS_SQL))
        for ddl in tenant_tables_sql(schema):
            await conn.execute(text(ddl))
        # The tenant-context middleware resolves the JWT's tenant against this table before any
        # handler runs, so a schema without a row here is a 404 rather than the request under
        # test.
        await conn.execute(
            text(
                "INSERT INTO public.tenants (id, name, slug, status) "
                "VALUES (:id, :name, :slug, 'active') ON CONFLICT (id) DO NOTHING"
            ),
            {"id": tid, "name": f"Seed {tid[:8]}", "slug": f"seed-bootstrap-{tid[:8]}"},
        )
        for name in entity_types or ():
            await conn.execute(
                text(
                    "INSERT INTO public.entity_definitions "
                    "(id, tenant_id, name, description, examples, is_active, version, "
                    " cardinality) "
                    "VALUES (:id, :tid, :name, :description, :examples, true, 1, 'multi')"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "tid": tid,
                    "name": name,
                    "description": f"A {name}",
                    "examples": "[]",
                },
            )
    return {"tid": tid, "schema": schema}


async def add_document(engine, tenant, document_text=DOCUMENT_TEXT, purpose="training"):
    doc_id = str(uuid.uuid4())
    schema = tenant["schema"]
    async with engine.begin() as conn:
        await conn.execute(
            text(
                f"INSERT INTO {schema}.documents (id, tenant_id, filename, status, purpose) "
                "VALUES (:id, :tid, 'test.txt', 'processed', :purpose)"
            ),
            {"id": doc_id, "tid": tenant["tid"], "purpose": purpose},
        )
        if document_text is not None:
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


async def drop_test_schemas(engine):
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name LIKE 'tenant_%'"
            )
        )
        for row in rows:
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {row[0]} CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS public.entity_definitions CASCADE"))
        await conn.execute(
            text("DELETE FROM public.tenants WHERE slug LIKE 'seed-bootstrap-%'")
        )
