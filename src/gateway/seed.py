"""Seed script: create bootstrap System Admin user and demo tenant with dashboard data."""
import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from src.shared.auth import hash_password

_TENANT_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS {schema}.documents (
    id VARCHAR PRIMARY KEY,
    tenant_id VARCHAR NOT NULL,
    filename VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100),
    file_size_bytes BIGINT,
    checksum VARCHAR(64),
    storage_uri VARCHAR(500),
    status VARCHAR(20) DEFAULT 'uploaded',
    ocr_applied_flag BOOLEAN DEFAULT false,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS {schema}.document_text_spans (
    id VARCHAR PRIMARY KEY,
    document_id VARCHAR NOT NULL REFERENCES {schema}.documents(id) ON DELETE CASCADE,
    page_no INTEGER,
    block_no INTEGER,
    text TEXT,
    start_offset INTEGER,
    end_offset INTEGER,
    ocr_confidence FLOAT
);
CREATE TABLE IF NOT EXISTS {schema}.annotation_tasks (
    id VARCHAR PRIMARY KEY,
    document_id VARCHAR NOT NULL REFERENCES {schema}.documents(id) ON DELETE CASCADE,
    annotator_user_id VARCHAR,
    assignee VARCHAR,
    status VARCHAR(20) DEFAULT 'unannotated',
    reviewer VARCHAR,
    dataset_version INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS {schema}.spans (
    id VARCHAR PRIMARY KEY,
    document_id VARCHAR NOT NULL REFERENCES {schema}.documents(id) ON DELETE CASCADE,
    entity_type VARCHAR(255) NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    text_content VARCHAR NOT NULL,
    confidence FLOAT NOT NULL DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS {schema}.suggested_spans (
    id VARCHAR PRIMARY KEY,
    document_id VARCHAR NOT NULL REFERENCES {schema}.documents(id) ON DELETE CASCADE,
    entity_type VARCHAR(255) NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    text_content VARCHAR NOT NULL,
    confidence FLOAT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS {schema}.training_jobs (
    id VARCHAR PRIMARY KEY,
    tenant_id VARCHAR NOT NULL,
    dataset_version INTEGER,
    base_model VARCHAR(255),
    hyperparameters JSONB,
    status VARCHAR(20) DEFAULT 'queued',
    metrics_uri VARCHAR(500),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS {schema}.model_versions (
    id VARCHAR PRIMARY KEY,
    tenant_id VARCHAR NOT NULL,
    version INTEGER NOT NULL,
    artifact_uri VARCHAR(500),
    training_job_id VARCHAR,
    metrics JSONB,
    status VARCHAR(20) DEFAULT 'candidate',
    active_flag BOOLEAN DEFAULT false,
    promoted_by VARCHAR,
    promoted_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS {schema}.extraction_runs (
    id VARCHAR PRIMARY KEY,
    tenant_id VARCHAR NOT NULL,
    document_id VARCHAR,
    model_version VARCHAR,
    status VARCHAR(20) DEFAULT 'queued',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS {schema}.extracted_entities (
    id VARCHAR PRIMARY KEY,
    run_id VARCHAR NOT NULL REFERENCES {schema}.extraction_runs(id) ON DELETE CASCADE,
    entity_id VARCHAR NOT NULL,
    value TEXT,
    confidence FLOAT,
    normalized_value TEXT,
    source_span_id VARCHAR,
    review_status VARCHAR(20) DEFAULT 'unreviewed',
    corrected_value TEXT,
    corrected_by VARCHAR,
    correction_notes TEXT,
    document_id VARCHAR
);
"""


async def seed():
    from src.shared.config import settings
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        system_tenant_id = "system"
        tenant_result = await db.execute(
            text("SELECT id FROM public.tenants WHERE id = :id"),
            {"id": system_tenant_id},
        )
        if not tenant_result.fetchone():
            await db.execute(
                text("""
                    INSERT INTO public.tenants (id, name, slug, status)
                    VALUES (:id, 'System', 'system', 'active')
                """),
                {"id": system_tenant_id},
            )
            print("Created system tenant")

        admin_id = str(uuid.uuid4())
        admin_email = "admin@nerplatform.io"
        admin_password = hash_password("Admin123!")

        result = await db.execute(
            text("SELECT id FROM public.tenant_users WHERE email = :email AND role = 'system_admin'"),
            {"email": admin_email},
        )
        if not result.fetchone():
            await db.execute(
                text("""
                    INSERT INTO public.tenant_users (id, tenant_id, email, password_hash, role, status)
                    VALUES (:id, 'system', :email, :pwd, 'system_admin', 'active')
                """),
                {"id": admin_id, "email": admin_email, "pwd": admin_password},
            )
            print(f"Created System Admin: {admin_email} / Admin123!")
        else:
            print("System Admin already exists")

        await db.commit()

    demo_tenant_id = "demo-tenant"
    schema_name = f"tenant_{demo_tenant_id.replace('-', '_')}"

    async with session_factory() as db:
        tenant_result = await db.execute(
            text("SELECT id FROM public.tenants WHERE id = :id"),
            {"id": demo_tenant_id},
        )
        if not tenant_result.fetchone():
            await db.execute(
                text("""
                    INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, max_storage_gb, max_model_versions)
                    VALUES (:id, 'Demo Corp', 'demo-corp', 'active', 25, 5000, 20, 10)
                """),
                {"id": demo_tenant_id},
            )
            print("Created demo tenant: Demo Corp")
        else:
            print("Demo tenant already exists")

        tenant_admin_id = str(uuid.uuid4())
        demo_email = "admin@democorp.io"
        demo_password = hash_password("Demo123!")

        result = await db.execute(
            text("SELECT id FROM public.tenant_users WHERE email = :email AND tenant_id = :tid"),
            {"email": demo_email, "tid": demo_tenant_id},
        )
        existing = result.fetchone()
        if not existing:
            await db.execute(
                text("""
                    INSERT INTO public.tenant_users (id, tenant_id, email, password_hash, role, status)
                    VALUES (:id, :tid, :email, :pwd, 'tenant_admin', 'active')
                """),
                {"id": tenant_admin_id, "tid": demo_tenant_id, "email": demo_email, "pwd": demo_password},
            )
            print(f"Created Tenant Admin: {demo_email} / Demo123!")
        else:
            tenant_admin_id = existing[0]
            print("Demo tenant admin already exists")

        annotator_id = str(uuid.uuid4())
        annotator_email = "annotator@democorp.io"
        annotator_password = hash_password("Demo123!")

        result = await db.execute(
            text("SELECT id FROM public.tenant_users WHERE email = :email AND tenant_id = :tid"),
            {"email": annotator_email, "tid": demo_tenant_id},
        )
        existing = result.fetchone()
        if not existing:
            await db.execute(
                text("""
                    INSERT INTO public.tenant_users (id, tenant_id, email, password_hash, role, status)
                    VALUES (:id, :tid, :email, :pwd, 'annotator', 'active')
                """),
                {"id": annotator_id, "tid": demo_tenant_id, "email": annotator_email, "pwd": annotator_password},
            )
            print(f"Created Annotator: {annotator_email} / Demo123!")
        else:
            annotator_id = existing[0]
            print("Demo annotator already exists")

        biz_user_id = str(uuid.uuid4())
        biz_email = "bizuser@democorp.io"
        biz_password = hash_password("Demo123!")

        result = await db.execute(
            text("SELECT id FROM public.tenant_users WHERE email = :email AND tenant_id = :tid"),
            {"email": biz_email, "tid": demo_tenant_id},
        )
        if not result.fetchone():
            await db.execute(
                text("""
                    INSERT INTO public.tenant_users (id, tenant_id, email, password_hash, role, status)
                    VALUES (:id, :tid, :email, :pwd, 'business_user', 'active')
                """),
                {"id": biz_user_id, "tid": demo_tenant_id, "email": biz_email, "pwd": biz_password},
            )
            print(f"Created Business User: {biz_email} / Demo123!")
        else:
            print("Demo business user already exists")

        await db.commit()

    async with session_factory() as db:
        await db.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
        for stmt in _TENANT_TABLES_SQL.split(";"):
            s = stmt.strip().format(schema=schema_name)
            if s:
                await db.execute(text(s + ";"))
        await db.commit()

    async with session_factory() as db:
        doc_names = [
            ("Q3-Report.pdf", "processed"),
            ("Contract-NDA.pdf", "annotated"),
            ("Invoice-2024.pdf", "annotated"),
            ("Meeting-Notes.docx", "annotated"),
            ("Research-Paper.pdf", "processing"),
            ("Financial-Statement.xlsx", "processed"),
            ("Email-Thread.pdf", "annotated"),
            ("Legal-Opinion.docx", "uploaded"),
            ("Press-Release.pdf", "processed"),
            ("Internal-Memo.docx", "uploaded"),
        ]
        doc_ids = []
        for i, (name, status) in enumerate(doc_names):
            doc_id = str(uuid.uuid4())
            doc_ids.append(doc_id)
            await db.execute(
                text(f"""
                    INSERT INTO {schema_name}.documents (id, tenant_id, filename, mime_type, file_size_bytes, status, created_at)
                    VALUES (:id, :tid, :fn, :mime, :size, :st, NOW() - interval '{i} hours')
                    ON CONFLICT (id) DO NOTHING
                """),
                {
                    "id": doc_id, "tid": demo_tenant_id, "fn": name,
                    "mime": "application/pdf" if name.endswith(".pdf") else "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "size": 102400 + i * 50000, "st": status,
                },
            )
        print(f"Seeded {len(doc_names)} demo documents")

        for i, doc_id in enumerate(doc_ids[:5]):
            task_id = str(uuid.uuid4())
            task_status = "completed" if i < 3 else "pending"
            await db.execute(
                text(f"""
                    INSERT INTO {schema_name}.annotation_tasks (id, document_id, annotator_user_id, status, created_at)
                    VALUES (:id, :did, :uid, :st, NOW() - interval '{i} hours')
                    ON CONFLICT (id) DO NOTHING
                """),
                {"id": task_id, "did": doc_id, "uid": annotator_id, "st": task_status},
            )
        print("Seeded 5 annotation tasks (3 completed, 2 pending, assigned to annotator)")

        entity_types = ["PER", "ORG", "LOC", "DATE", "MONEY"]
        for i in range(75):
            span_id = str(uuid.uuid4())
            doc_id = doc_ids[i % 5]
            etype = entity_types[i % len(entity_types)]
            await db.execute(
                text(f"""
                    INSERT INTO {schema_name}.spans (id, document_id, entity_type, char_start, char_end, text_content, confidence)
                    VALUES (:id, :did, :et, :cs, :ce, :txt, :conf)
                    ON CONFLICT (id) DO NOTHING
                """),
                {
                    "id": span_id, "did": doc_id, "et": etype,
                    "cs": i * 10, "ce": i * 10 + 5,
                    "txt": f"Entity{i}", "conf": 0.85 + (i * 0.002),
                },
            )
        print("Seeded 75 spans")

        for i in range(20):
            sugg_id = str(uuid.uuid4())
            doc_id = doc_ids[i % 5]
            etype = entity_types[i % len(entity_types)]
            conf = round(0.55 + i * 0.0125, 3)
            await db.execute(
                text(f"""
                    INSERT INTO {schema_name}.suggested_spans (id, document_id, entity_type, char_start, char_end, text_content, confidence)
                    VALUES (:id, :did, :et, :cs, :ce, :txt, :conf)
                    ON CONFLICT (id) DO NOTHING
                """),
                {
                    "id": sugg_id, "did": doc_id, "et": etype,
                    "cs": i * 15, "ce": i * 15 + 7,
                    "txt": f"Suggested{i}", "conf": conf,
                },
            )
        print("Seeded 20 suggested spans")

        model_id = str(uuid.uuid4())
        await db.execute(
            text(f"""
                INSERT INTO {schema_name}.model_versions (id, tenant_id, version, metrics, status, promoted_at)
                VALUES (:id, :tid, 3, :met, 'promoted', NOW() - interval '2 days')
                ON CONFLICT (id) DO NOTHING
            """),
            {
                "id": model_id, "tid": demo_tenant_id,
                "met": '{"f1": 0.872, "precision": 0.91, "recall": 0.85, "loss": 0.12}',
            },
        )
        print("Seeded promoted model (F1=87.2)")

        training_statuses = [
            ("completed", 3),
            ("completed", 2),
            ("running", 1),
            ("queued", None),
        ]
        for status, days_ago in training_statuses:
            job_id = str(uuid.uuid4())
            started_at_expr = f"NOW() - interval '{days_ago} days'" if days_ago else "NULL"
            await db.execute(
                text(f"""
                    INSERT INTO {schema_name}.training_jobs (id, tenant_id, dataset_version, base_model, status, started_at)
                    VALUES (:id, :tid, :dv, 'dslim/bert-base-NER', :st, {started_at_expr})
                    ON CONFLICT (id) DO NOTHING
                """),
                {"id": job_id, "tid": demo_tenant_id, "dv": (days_ago or 0) + 1, "st": status},
            )
        print("Seeded 4 training jobs")

        extraction_docs = doc_ids[5:9]
        for i, doc_id in enumerate(extraction_docs):
            run_id = str(uuid.uuid4())
            await db.execute(
                text(f"""
                    INSERT INTO {schema_name}.extraction_runs (id, tenant_id, document_id, model_version, status, started_at, completed_at)
                    VALUES (:id, :tid, :did, 'v3', 'completed', NOW() - interval '{i} hours', NOW() - interval '{i - 0.5} hours')
                    ON CONFLICT (id) DO NOTHING
                """),
                {"id": run_id, "tid": demo_tenant_id, "did": doc_id},
            )
            for j in range(8 + i * 3):
                ee_id = str(uuid.uuid4())
                etype = entity_types[j % len(entity_types)]
                conf = 0.7 + (j * 0.03)
                rs = "auto_cleared" if conf > 0.85 else "unreviewed"
                await db.execute(
                    text(f"""
                        INSERT INTO {schema_name}.extracted_entities (id, run_id, entity_id, value, confidence, review_status, document_id)
                        VALUES (:id, :rid, :eid, :val, :conf, :rs, :did)
                        ON CONFLICT (id) DO NOTHING
                    """),
                    {
                        "id": ee_id, "rid": run_id, "eid": etype,
                        "val": f"Value{j}", "conf": conf, "rs": rs, "did": doc_id,
                    },
                )
        print("Seeded 4 extraction runs with entities")

        await db.commit()

    await engine.dispose()
    print("Seed complete")
    print()
    print("Demo credentials:")
    print(f"  System Admin:   admin@nerplatform.io / Admin123!")
    print(f"  Tenant Admin:   admin@democorp.io / Demo123!")
    print(f"  Annotator:      annotator@democorp.io / Demo123!")
    print(f"  Business User:  bizuser@democorp.io / Demo123!")
    print()
    print("All roles have seeded data — run each login to verify the dashboard.")


if __name__ == "__main__":
    asyncio.run(seed())
