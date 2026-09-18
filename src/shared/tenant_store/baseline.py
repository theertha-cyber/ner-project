"""The tenant-store schema baseline (ADR-017, Design D5).

`statements(schema)` reproduces `tenant_template` exactly as it exists at Alembic head
043 — the same tables, the generated `chunk_tsv` column, the HNSW index, the four
analytics materialized views, and the `platform_store_meta` identity table — as a list
of idempotent SQL statements parameterised by schema name. It is generated from
`pg_dump --schema=tenant_template --schema-only` against a database at head 043 (see
`openspec/changes/tenant-postgresql-data-plane/tenant_template_dump.sql`), not
transcribed from the 43 migrations that produced that shape, and verified against them
by `tests/test_tenant_store_parity.py`.

Applying this to an empty schema and applying it to a schema that already has the full
shape must both succeed with no error and no change on the second run — every statement
is `IF NOT EXISTS`, or, for constraints (which Postgres has no `ADD CONSTRAINT IF NOT
EXISTS` for), guarded by a `pg_constraint` existence check.
"""

from __future__ import annotations

BASELINE_REVISION = 1

# --- Tables, in an order that never forward-references another table via a column
# default or inline CHECK (FKs are added separately, after every table exists). ---
_TABLE_DDL: dict[str, str] = {
    "annotation_labels": """
        id character varying NOT NULL,
        task_id character varying NOT NULL,
        entity_id character varying NOT NULL,
        token_start integer,
        token_end integer,
        value text,
        confidence double precision,
        corrected_flag boolean DEFAULT false,
        created_at timestamp with time zone DEFAULT now(),
        PRIMARY KEY (id)
    """,
    "annotation_tasks": """
        id character varying NOT NULL,
        document_id character varying NOT NULL,
        assignee character varying,
        status character varying(20) DEFAULT 'unannotated'::character varying,
        reviewer character varying,
        dataset_version integer,
        created_at timestamp with time zone DEFAULT now(),
        annotator_user_id character varying,
        updated_at timestamp with time zone,
        PRIMARY KEY (id)
    """,
    "audit_log": """
        id character varying NOT NULL,
        tenant_id character varying NOT NULL,
        actor_id character varying,
        action character varying(100) NOT NULL,
        resource_type character varying(100),
        resource_id character varying,
        details jsonb,
        ip_address character varying(45),
        "timestamp" timestamp with time zone DEFAULT now(),
        PRIMARY KEY (id)
    """,
    "azure_blob_hidden_documents": """
        document_id character varying NOT NULL,
        connection_id character varying NOT NULL,
        cause character varying(32) NOT NULL,
        hidden_at timestamp with time zone DEFAULT now() NOT NULL,
        PRIMARY KEY (document_id)
    """,
    "azure_blob_source_objects": """
        connection_id character varying NOT NULL,
        object_identity character varying(1024) NOT NULL,
        source_version character varying(256),
        document_id character varying,
        missing_sightings integer DEFAULT 0 NOT NULL,
        confirmed_missing boolean DEFAULT false NOT NULL,
        last_seen_at timestamp with time zone,
        PRIMARY KEY (connection_id, object_identity)
    """,
    "azure_blob_sync_leases": """
        connection_id character varying NOT NULL,
        run_id character varying NOT NULL,
        acquired_at timestamp with time zone DEFAULT now() NOT NULL,
        expires_at timestamp with time zone NOT NULL,
        PRIMARY KEY (connection_id)
    """,
    "azure_blob_sync_runs": """
        id character varying NOT NULL,
        tenant_id character varying(64) NOT NULL,
        connection_id character varying NOT NULL,
        trigger character varying(32) NOT NULL,
        outcome character varying(32) DEFAULT 'started'::character varying NOT NULL,
        reason character varying(64) DEFAULT 'none'::character varying NOT NULL,
        objects_seen integer DEFAULT 0 NOT NULL,
        objects_ingested integer DEFAULT 0 NOT NULL,
        objects_skipped integer DEFAULT 0 NOT NULL,
        objects_failed integer DEFAULT 0 NOT NULL,
        started_at timestamp with time zone DEFAULT now() NOT NULL,
        completed_at timestamp with time zone,
        PRIMARY KEY (id)
    """,
    "chat_message_feedback": """
        id character varying NOT NULL,
        message_id character varying NOT NULL,
        tenant_id character varying NOT NULL,
        user_id character varying NOT NULL,
        rating text NOT NULL,
        created_at timestamp with time zone DEFAULT now(),
        PRIMARY KEY (id),
        UNIQUE (message_id),
        CONSTRAINT chat_message_feedback_rating_check
            CHECK ((rating = ANY (ARRAY['up'::text, 'down'::text])))
    """,
    "chat_messages": """
        id character varying NOT NULL,
        conversation_id character varying NOT NULL,
        role character varying(20) NOT NULL,
        content text NOT NULL,
        sources jsonb,
        created_at timestamp with time zone DEFAULT now(),
        answer_kind text DEFAULT 'answer'::text NOT NULL,
        model_version text,
        response_time_ms integer,
        PRIMARY KEY (id)
    """,
    "conversation_entity_state": """
        conversation_id character varying NOT NULL,
        pending_original_message text,
        pending_mention text,
        pending_candidates jsonb,
        pending_reask_count integer DEFAULT 0 NOT NULL,
        resolved_document_id character varying,
        resolved_entity_value text,
        updated_at timestamp with time zone DEFAULT now() NOT NULL,
        PRIMARY KEY (conversation_id)
    """,
    "conversations": """
        id character varying NOT NULL,
        tenant_id character varying NOT NULL,
        user_id character varying NOT NULL,
        title character varying(255),
        created_at timestamp with time zone DEFAULT now(),
        updated_at timestamp with time zone DEFAULT now(),
        PRIMARY KEY (id)
    """,
    "document_chunks": """
        id character varying NOT NULL,
        document_id character varying NOT NULL,
        chunk_index integer NOT NULL,
        chunk_text text NOT NULL,
        embedding public.vector(1536),
        created_at timestamp with time zone DEFAULT now(),
        page_number integer,
        char_start integer,
        char_end integer,
        purpose character varying(20),
        uploaded_by character varying,
        ingested_by_kind character varying(32),
        chunk_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english'::regconfig, chunk_text)) STORED,
        PRIMARY KEY (id)
    """,
    "document_entities": """
        id character varying NOT NULL,
        document_id character varying NOT NULL,
        entity_type text NOT NULL,
        entity_value text NOT NULL,
        normalized_value text NOT NULL,
        confidence double precision NOT NULL,
        page_number integer,
        char_start integer,
        char_end integer,
        created_at timestamp with time zone DEFAULT now() NOT NULL,
        value_kind text,
        value_number double precision,
        value_number_high double precision,
        value_unit text,
        value_date date,
        value_date_high date,
        source_entity_value text,
        source_entity_type text,
        postprocess_status text DEFAULT 'not_applied'::text NOT NULL,
        postprocess_model text,
        postprocess_prompt_version text,
        postprocess_at timestamp with time zone,
        extraction_schema_version integer DEFAULT 1 NOT NULL,
        occurrence_count integer DEFAULT 1 NOT NULL,
        PRIMARY KEY (id)
    """,
    "document_text_spans": """
        id character varying NOT NULL,
        document_id character varying NOT NULL,
        page_no integer,
        block_no integer,
        text text,
        start_offset integer,
        end_offset integer,
        ocr_confidence double precision,
        span_index integer,
        char_start integer,
        char_end integer,
        page_number integer,
        created_at timestamp with time zone DEFAULT now(),
        PRIMARY KEY (id)
    """,
    "documents": """
        id character varying NOT NULL,
        tenant_id character varying NOT NULL,
        filename character varying(255) NOT NULL,
        mime_type character varying(100),
        file_size_bytes bigint,
        checksum character varying(64),
        storage_uri character varying(500),
        status character varying(20) DEFAULT 'uploaded'::character varying,
        ocr_applied_flag boolean DEFAULT false,
        error_message text,
        created_at timestamp with time zone DEFAULT now(),
        content_type character varying(255),
        file_size bigint,
        blob_path character varying(500),
        updated_at timestamp with time zone DEFAULT now(),
        uploaded_by character varying(64),
        origin character varying(32) DEFAULT 'push'::character varying NOT NULL,
        source_type character varying(64) DEFAULT 'platform_upload'::character varying NOT NULL,
        source_id character varying(128) DEFAULT 'platform-upload'::character varying NOT NULL,
        external_id character varying(512),
        source_version character varying(256),
        source_created_at timestamp with time zone,
        source_modified_at timestamp with time zone,
        origin_metadata jsonb,
        retention_mode character varying(32) DEFAULT 'platform_blob'::character varying NOT NULL,
        ingested_by_kind character varying(32) DEFAULT 'human'::character varying NOT NULL,
        purpose character varying(20) DEFAULT 'query'::character varying NOT NULL,
        PRIMARY KEY (id),
        CONSTRAINT documents_retention_mode_check CHECK (
            ((retention_mode)::text = ANY ((ARRAY[
                'platform_blob'::character varying,
                'ephemeral'::character varying,
                'source_only'::character varying
            ])::text[]))
        )
    """,
    "external_pg_schema_index": """
        connection_id character varying NOT NULL,
        contract_version integer NOT NULL,
        relation_name character varying(256) NOT NULL,
        entry_text text NOT NULL,
        updated_at timestamp with time zone DEFAULT now() NOT NULL,
        PRIMARY KEY (connection_id, contract_version, relation_name)
    """,
    "extracted_entities": """
        id character varying NOT NULL,
        run_id character varying NOT NULL,
        entity_id character varying NOT NULL,
        value text,
        confidence double precision,
        normalized_value text,
        source_span_id character varying,
        review_status character varying(20) DEFAULT 'unreviewed'::character varying,
        corrected_value text,
        corrected_by character varying,
        correction_notes text,
        document_id character varying,
        PRIMARY KEY (id)
    """,
    "extraction_runs": """
        id character varying NOT NULL,
        tenant_id character varying NOT NULL,
        document_id character varying,
        model_version character varying,
        status character varying(20) DEFAULT 'queued'::character varying,
        started_at timestamp with time zone,
        processing_mode character varying(32) DEFAULT 'bert_only'::character varying NOT NULL,
        postprocess_model text,
        postprocess_prompt_version text,
        postprocess_degraded boolean DEFAULT false NOT NULL,
        completed_at timestamp with time zone,
        total_documents integer DEFAULT 0 NOT NULL,
        processed_count integer DEFAULT 0 NOT NULL,
        skipped_count integer DEFAULT 0 NOT NULL,
        failed_count integer DEFAULT 0 NOT NULL,
        PRIMARY KEY (id)
    """,
    "imported_annotations": """
        id character varying NOT NULL,
        tokens text[] NOT NULL,
        tags text[] NOT NULL,
        source_file character varying NOT NULL,
        row_index integer NOT NULL,
        created_at timestamp with time zone DEFAULT now(),
        reviewed boolean DEFAULT false NOT NULL,
        reviewed_at timestamp with time zone,
        reviewed_by character varying,
        PRIMARY KEY (id)
    """,
    "model_versions": """
        id character varying NOT NULL,
        tenant_id character varying NOT NULL,
        version integer,
        artifact_uri character varying(500),
        training_job_id character varying,
        metrics jsonb,
        status character varying(20) DEFAULT 'candidate'::character varying,
        active_flag boolean DEFAULT false,
        promoted_by character varying,
        promoted_at timestamp with time zone,
        mlflow_run_id character varying,
        created_at timestamp with time zone DEFAULT now(),
        version_number integer,
        artifact_path text,
        run_number integer,
        PRIMARY KEY (id)
    """,
    "spans": """
        id character varying NOT NULL,
        document_id character varying NOT NULL,
        entity_type character varying(255) NOT NULL,
        char_start integer NOT NULL,
        char_end integer NOT NULL,
        text_content character varying NOT NULL,
        confidence double precision DEFAULT 1.0 NOT NULL,
        created_at timestamp with time zone DEFAULT now(),
        updated_at timestamp with time zone,
        bio_tags text[],
        PRIMARY KEY (id)
    """,
    "suggested_spans": """
        id character varying NOT NULL,
        document_id character varying NOT NULL,
        entity_type character varying(255) NOT NULL,
        char_start integer NOT NULL,
        char_end integer NOT NULL,
        text_content character varying NOT NULL,
        confidence double precision NOT NULL,
        created_at timestamp with time zone DEFAULT now(),
        PRIMARY KEY (id)
    """,
    "training_jobs": """
        id character varying NOT NULL,
        tenant_id character varying NOT NULL,
        dataset_version integer,
        base_model character varying(255),
        hyperparameters jsonb,
        status character varying(20) DEFAULT 'queued'::character varying,
        metrics_uri character varying(500),
        started_at timestamp with time zone,
        completed_at timestamp with time zone,
        mlflow_run_id character varying,
        mlflow_run_url text,
        metrics jsonb,
        hyperparams jsonb,
        current_epoch integer,
        current_loss double precision,
        celery_task_id character varying,
        model_version_id character varying,
        created_at timestamp with time zone DEFAULT now(),
        failed_at timestamp with time zone,
        error_message text,
        run_number integer,
        PRIMARY KEY (id)
    """,
    # ADR-017: store identity + applied schema revision. Not part of `tenant_template`
    # before migration 043; part of the baseline from here on.
    "platform_store_meta": """
        store_id uuid NOT NULL,
        tenant_id character varying(64) NOT NULL,
        schema_revision integer NOT NULL,
        provisioned_at timestamp with time zone DEFAULT now() NOT NULL
    """,
}

# Foreign keys, added after every table exists. (table, constraint_name, ddl_after_ADD_CONSTRAINT)
_FOREIGN_KEYS: list[tuple[str, str, str]] = [
    ("annotation_labels", "annotation_labels_task_id_fkey",
     "FOREIGN KEY (task_id) REFERENCES {schema}.annotation_tasks(id) ON DELETE CASCADE"),
    ("annotation_tasks", "annotation_tasks_document_id_fkey",
     "FOREIGN KEY (document_id) REFERENCES {schema}.documents(id) ON DELETE CASCADE"),
    ("chat_message_feedback", "chat_message_feedback_message_id_fkey",
     "FOREIGN KEY (message_id) REFERENCES {schema}.chat_messages(id) ON DELETE CASCADE"),
    ("chat_messages", "chat_messages_conversation_id_fkey",
     "FOREIGN KEY (conversation_id) REFERENCES {schema}.conversations(id) ON DELETE CASCADE"),
    ("document_chunks", "document_chunks_document_id_fkey",
     "FOREIGN KEY (document_id) REFERENCES {schema}.documents(id) ON DELETE CASCADE"),
    ("document_text_spans", "document_text_spans_document_id_fkey",
     "FOREIGN KEY (document_id) REFERENCES {schema}.documents(id) ON DELETE CASCADE"),
    ("extracted_entities", "extracted_entities_run_id_fkey",
     "FOREIGN KEY (run_id) REFERENCES {schema}.extraction_runs(id) ON DELETE CASCADE"),
    ("extracted_entities", "extracted_entities_source_span_id_fkey",
     "FOREIGN KEY (source_span_id) REFERENCES {schema}.document_text_spans(id)"),
    ("extraction_runs", "extraction_runs_document_id_fkey",
     "FOREIGN KEY (document_id) REFERENCES {schema}.documents(id) ON DELETE CASCADE"),
    ("model_versions", "model_versions_training_job_id_fkey",
     "FOREIGN KEY (training_job_id) REFERENCES {schema}.training_jobs(id)"),
    ("spans", "spans_document_id_fkey",
     "FOREIGN KEY (document_id) REFERENCES {schema}.documents(id) ON DELETE CASCADE"),
    ("suggested_spans", "suggested_spans_document_id_fkey",
     "FOREIGN KEY (document_id) REFERENCES {schema}.documents(id) ON DELETE CASCADE"),
]

# Indexes. `CREATE [UNIQUE] INDEX IF NOT EXISTS` is natively idempotent.
_INDEXES: list[str] = [
    "CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw "
    "ON {schema}.document_chunks USING hnsw (embedding public.vector_cosine_ops)",
    "CREATE INDEX IF NOT EXISTS idx_document_chunks_tsv "
    "ON {schema}.document_chunks USING gin (chunk_tsv)",
    "CREATE INDEX IF NOT EXISTS idx_document_entities_template_document_id "
    "ON {schema}.document_entities USING btree (document_id)",
    "CREATE INDEX IF NOT EXISTS idx_document_entities_template_entity_type "
    "ON {schema}.document_entities USING btree (entity_type)",
    "CREATE INDEX IF NOT EXISTS idx_document_entities_template_normalized_value "
    "ON {schema}.document_entities USING btree (normalized_value)",
    "CREATE INDEX IF NOT EXISTS idx_document_entities_template_postprocess_status "
    "ON {schema}.document_entities USING btree (postprocess_status) "
    "WHERE (postprocess_status <> 'not_applied'::text)",
    "CREATE INDEX IF NOT EXISTS idx_document_entities_template_value_date "
    "ON {schema}.document_entities USING btree (entity_type, value_date) "
    "WHERE (value_date IS NOT NULL)",
    "CREATE INDEX IF NOT EXISTS idx_document_entities_template_value_number "
    "ON {schema}.document_entities USING btree (entity_type, value_number) "
    "WHERE (value_number IS NOT NULL)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_model_versions_tenant_promoted "
    "ON {schema}.model_versions USING btree (tenant_id) WHERE ((status)::text = 'promoted'::text)",
    "CREATE INDEX IF NOT EXISTS idx_model_versions_tenant_status "
    "ON {schema}.model_versions USING btree (tenant_id, status)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_confidence_distribution_bucket "
    "ON {schema}.mv_confidence_distribution USING btree (bucket)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_document_entity_counts_type "
    "ON {schema}.mv_document_entity_counts USING btree (entity_type)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_entity_coverage_type "
    "ON {schema}.mv_entity_coverage USING btree (entity_type)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_extraction_volume_date "
    "ON {schema}.mv_extraction_volume USING btree (extraction_date)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_task_active_document "
    "ON {schema}.annotation_tasks USING btree (document_id) "
    "WHERE ((status)::text = ANY ((ARRAY['unannotated'::character varying, "
    "'in-progress'::character varying])::text[]))",
    "CREATE INDEX IF NOT EXISTS idx_training_jobs_tenant_status "
    "ON {schema}.training_jobs USING btree (tenant_id, status)",
    "CREATE INDEX IF NOT EXISTS ix_blob_sync_runs_conn "
    "ON {schema}.azure_blob_sync_runs USING btree (connection_id, started_at DESC)",
    "CREATE INDEX IF NOT EXISTS ix_documents_checksum "
    "ON {schema}.documents USING btree (checksum)",
]

# Materialized views. `CREATE MATERIALIZED VIEW IF NOT EXISTS` is natively idempotent
# (PostgreSQL 9.5+). `WITH NO DATA` matches migrations 011/015 — populated by refresh,
# not at creation.
_MATERIALIZED_VIEWS: list[str] = [
    """
    CREATE MATERIALIZED VIEW IF NOT EXISTS {schema}.mv_confidence_distribution AS
     SELECT
            CASE
                WHEN ((confidence >= (0.0)::double precision) AND (confidence < (0.2)::double precision)) THEN '0.0-0.2'::text
                WHEN ((confidence >= (0.2)::double precision) AND (confidence < (0.4)::double precision)) THEN '0.2-0.4'::text
                WHEN ((confidence >= (0.4)::double precision) AND (confidence < (0.6)::double precision)) THEN '0.4-0.6'::text
                WHEN ((confidence >= (0.6)::double precision) AND (confidence < (0.8)::double precision)) THEN '0.6-0.8'::text
                WHEN ((confidence >= (0.8)::double precision) AND (confidence <= (1.0)::double precision)) THEN '0.8-1.0'::text
                ELSE NULL::text
            END AS bucket,
        count(*) AS count
       FROM {schema}.extracted_entities
      GROUP BY
            CASE
                WHEN ((confidence >= (0.0)::double precision) AND (confidence < (0.2)::double precision)) THEN '0.0-0.2'::text
                WHEN ((confidence >= (0.2)::double precision) AND (confidence < (0.4)::double precision)) THEN '0.2-0.4'::text
                WHEN ((confidence >= (0.4)::double precision) AND (confidence < (0.6)::double precision)) THEN '0.4-0.6'::text
                WHEN ((confidence >= (0.6)::double precision) AND (confidence < (0.8)::double precision)) THEN '0.6-0.8'::text
                WHEN ((confidence >= (0.8)::double precision) AND (confidence <= (1.0)::double precision)) THEN '0.8-1.0'::text
                ELSE NULL::text
            END
      ORDER BY
            CASE
                WHEN ((confidence >= (0.0)::double precision) AND (confidence < (0.2)::double precision)) THEN '0.0-0.2'::text
                WHEN ((confidence >= (0.2)::double precision) AND (confidence < (0.4)::double precision)) THEN '0.2-0.4'::text
                WHEN ((confidence >= (0.4)::double precision) AND (confidence < (0.6)::double precision)) THEN '0.4-0.6'::text
                WHEN ((confidence >= (0.6)::double precision) AND (confidence < (0.8)::double precision)) THEN '0.6-0.8'::text
                WHEN ((confidence >= (0.8)::double precision) AND (confidence <= (1.0)::double precision)) THEN '0.8-1.0'::text
                ELSE NULL::text
            END
      WITH NO DATA
    """,
    """
    CREATE MATERIALIZED VIEW IF NOT EXISTS {schema}.mv_document_entity_counts AS
     SELECT entity_id AS entity_type,
        (avg(entity_count))::double precision AS avg_per_document
       FROM ( SELECT extracted_entities.entity_id,
                extracted_entities.document_id,
                count(*) AS entity_count
               FROM {schema}.extracted_entities
              GROUP BY extracted_entities.entity_id, extracted_entities.document_id) e
      GROUP BY entity_id
      WITH NO DATA
    """,
    """
    CREATE MATERIALIZED VIEW IF NOT EXISTS {schema}.mv_entity_coverage AS
     SELECT e.entity_id AS entity_type,
        (((count(DISTINCT e.document_id))::double precision / (NULLIF(count(DISTINCT d.id), 0))::double precision) * (100)::double precision) AS coverage_pct
       FROM ({schema}.extracted_entities e
         CROSS JOIN {schema}.documents d)
      GROUP BY e.entity_id
      WITH NO DATA
    """,
    """
    CREATE MATERIALIZED VIEW IF NOT EXISTS {schema}.mv_extraction_volume AS
     SELECT date(r.started_at) AS extraction_date,
        count(*) AS count
       FROM ({schema}.extracted_entities e
         JOIN {schema}.extraction_runs r ON (((r.id)::text = (e.run_id)::text)))
      WHERE (r.started_at >= (now() - '30 days'::interval))
      GROUP BY (date(r.started_at))
      ORDER BY (date(r.started_at))
      WITH NO DATA
    """,
]


def _guarded_add_constraint(schema: str, table: str, name: str, ddl: str) -> str:
    """`ALTER TABLE ... ADD CONSTRAINT` has no `IF NOT EXISTS` in PostgreSQL; guard with
    an existence check against `pg_constraint` instead."""
    return f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = '{name}'
                  AND connamespace = '{schema}'::regnamespace
            ) THEN
                ALTER TABLE {schema}.{table} ADD CONSTRAINT {name} {ddl.format(schema=schema)};
            END IF;
        END $$;
    """


def statements(schema: str) -> list[str]:
    """Idempotent DDL that produces `tenant_template` at head 043 inside `schema`.

    Order: tables (inline PRIMARY KEY/UNIQUE/CHECK), materialized views, foreign keys,
    then indexes — every foreign key's target table already exists by the time its
    `ADD CONSTRAINT` runs, and every materialized view's index runs after its view.
    """
    out: list[str] = [f"CREATE SCHEMA IF NOT EXISTS {schema}"]
    for table, body in _TABLE_DDL.items():
        out.append(f"CREATE TABLE IF NOT EXISTS {schema}.{table} ({body})")
    for mv in _MATERIALIZED_VIEWS:
        out.append(mv.format(schema=schema))
    for table, name, ddl in _FOREIGN_KEYS:
        out.append(_guarded_add_constraint(schema, table, name, ddl))
    for index in _INDEXES:
        out.append(index.format(schema=schema))
    return out
