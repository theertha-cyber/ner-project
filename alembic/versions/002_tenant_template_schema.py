"""create tenant_template schema with tenant-scoped tables

Revision ID: 002
Revises: 001
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

TENANT_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS tenant_template.documents (
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

CREATE TABLE IF NOT EXISTS tenant_template.document_text_spans (
    id VARCHAR PRIMARY KEY,
    document_id VARCHAR NOT NULL REFERENCES tenant_template.documents(id) ON DELETE CASCADE,
    page_no INTEGER,
    block_no INTEGER,
    text TEXT,
    start_offset INTEGER,
    end_offset INTEGER,
    ocr_confidence FLOAT
);

CREATE TABLE IF NOT EXISTS tenant_template.annotation_tasks (
    id VARCHAR PRIMARY KEY,
    document_id VARCHAR NOT NULL REFERENCES tenant_template.documents(id) ON DELETE CASCADE,
    assignee VARCHAR,
    status VARCHAR(20) DEFAULT 'open',
    reviewer VARCHAR,
    dataset_version INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tenant_template.annotation_labels (
    id VARCHAR PRIMARY KEY,
    task_id VARCHAR NOT NULL REFERENCES tenant_template.annotation_tasks(id) ON DELETE CASCADE,
    entity_id VARCHAR NOT NULL,
    token_start INTEGER,
    token_end INTEGER,
    value TEXT,
    confidence FLOAT,
    corrected_flag BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tenant_template.training_jobs (
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

CREATE TABLE IF NOT EXISTS tenant_template.model_versions (
    id VARCHAR PRIMARY KEY,
    tenant_id VARCHAR NOT NULL,
    version INTEGER NOT NULL,
    artifact_uri VARCHAR(500),
    training_job_id VARCHAR REFERENCES tenant_template.training_jobs(id),
    metrics JSONB,
    status VARCHAR(20) DEFAULT 'candidate',
    active_flag BOOLEAN DEFAULT false,
    promoted_by VARCHAR,
    promoted_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS tenant_template.extraction_runs (
    id VARCHAR PRIMARY KEY,
    tenant_id VARCHAR NOT NULL,
    document_id VARCHAR NOT NULL REFERENCES tenant_template.documents(id) ON DELETE CASCADE,
    model_version VARCHAR,
    status VARCHAR(20) DEFAULT 'queued',
    started_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS tenant_template.extracted_entities (
    id VARCHAR PRIMARY KEY,
    run_id VARCHAR NOT NULL REFERENCES tenant_template.extraction_runs(id) ON DELETE CASCADE,
    entity_id VARCHAR NOT NULL,
    value TEXT,
    confidence FLOAT,
    normalized_value TEXT,
    source_span_id VARCHAR REFERENCES tenant_template.document_text_spans(id),
    review_status VARCHAR(20) DEFAULT 'unreviewed',
    corrected_value TEXT,
    corrected_by VARCHAR,
    correction_notes TEXT
);

CREATE TABLE IF NOT EXISTS tenant_template.audit_log (
    id VARCHAR PRIMARY KEY,
    tenant_id VARCHAR NOT NULL,
    actor_id VARCHAR,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id VARCHAR,
    details JSONB,
    ip_address VARCHAR(45),
    timestamp TIMESTAMPTZ DEFAULT NOW()
);
"""


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS tenant_template")
    for statement in TENANT_TABLES_SQL.split(";"):
        stmt = statement.strip()
        if stmt:
            op.execute(stmt + ";")


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS tenant_template CASCADE")
