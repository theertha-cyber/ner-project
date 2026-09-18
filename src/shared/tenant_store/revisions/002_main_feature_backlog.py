"""Backfills the tenant-store baseline for Alembic migrations 039-048 (main's
automated-annotation guided workflow, confidence-routed review, and chat
export/chart work), landed independently of ADR-017 and never folded into
`baseline.py` before the `external-tenant-data-sources` <-> `main` merge.

Fourteen tenant-scoped tables and seven columns on tables `baseline.py`
already defines. DDL and constraint names taken verbatim from
`pg_dump --schema-only --schema=tenant_template` against a database at
Alembic head 052 -- same provenance discipline as `baseline.py` itself, not
transcribed from the migrations, and verified against them by
`tests/test_tenant_store_parity.py`.

A single revision rather than one per originating migration (039/040/041/042/
045/046/047/048): this is a one-time backlog catch-up landing in one PR, not
incremental work arriving alongside each migration -- the convention in
`revisions/__init__.py` exists for the latter.
"""

from __future__ import annotations

REVISION = 2

# --- New tables, in an order that never forward-references another new table via a
# column default or inline CHECK (FKs -- including to baseline.py's tables -- are
# added separately below, after every table here exists). ---
_TABLE_DDL: dict[str, str] = {
    "prelabel_batches": """
        id character varying NOT NULL,
        status character varying(16) DEFAULT 'queued'::character varying NOT NULL,
        requested_by character varying,
        error_message text,
        created_at timestamp with time zone DEFAULT now() NOT NULL,
        completed_at timestamp with time zone,
        annotator_review_status character varying(32),
        training_eligible_at timestamp with time zone,
        batch_kind character varying(16) DEFAULT 'large'::character varying NOT NULL,
        state character varying(24),
        PRIMARY KEY (id),
        CONSTRAINT prelabel_batches_status_check
            CHECK (((status)::text = ANY ((ARRAY['queued'::character varying,
                'running'::character varying, 'completed'::character varying,
                'failed'::character varying])::text[])))
    """,
    "schema_proposals": """
        id character varying NOT NULL,
        status character varying(16) DEFAULT 'queued'::character varying NOT NULL,
        seed_document_ids jsonb NOT NULL,
        requested_by character varying,
        error_message text,
        created_at timestamp with time zone DEFAULT now() NOT NULL,
        completed_at timestamp with time zone,
        qa_pair_document_id character varying,
        PRIMARY KEY (id),
        CONSTRAINT schema_proposals_status_check
            CHECK (((status)::text = ANY ((ARRAY['queued'::character varying,
                'running'::character varying, 'completed'::character varying,
                'failed'::character varying])::text[])))
    """,
    "review_outcomes": """
        id character varying NOT NULL,
        prediction_id character varying NOT NULL,
        document_id character varying NOT NULL,
        outcome character varying(16) NOT NULL,
        route character varying(8) NOT NULL,
        entity_type character varying(255) NOT NULL,
        char_start integer NOT NULL,
        char_end integer NOT NULL,
        predicted_entity_type character varying(255) NOT NULL,
        predicted_char_start integer NOT NULL,
        predicted_char_end integer NOT NULL,
        predicted_confidence double precision,
        model_version character varying NOT NULL,
        served_by_base_model boolean DEFAULT false NOT NULL,
        origin character varying(16) DEFAULT 'queue'::character varying NOT NULL,
        reviewer character varying,
        created_at timestamp with time zone DEFAULT now() NOT NULL,
        PRIMARY KEY (id),
        CONSTRAINT review_outcomes_origin_check
            CHECK (((origin)::text = ANY ((ARRAY['queue'::character varying,
                'audit'::character varying])::text[]))),
        CONSTRAINT review_outcomes_outcome_check
            CHECK (((outcome)::text = ANY ((ARRAY['confirmed'::character varying,
                'corrected'::character varying, 'rejected'::character varying])::text[]))),
        CONSTRAINT review_outcomes_route_check
            CHECK (((route)::text = ANY ((ARRAY['human'::character varying,
                'llm'::character varying])::text[])))
    """,
    "routed_predictions": """
        id character varying NOT NULL,
        run_id character varying NOT NULL,
        document_id character varying NOT NULL,
        entity_type character varying(255) NOT NULL,
        value text NOT NULL,
        confidence double precision NOT NULL,
        char_start integer NOT NULL,
        char_end integer NOT NULL,
        model_version character varying NOT NULL,
        served_by_base_model boolean DEFAULT false NOT NULL,
        below_business_threshold boolean DEFAULT false NOT NULL,
        disposition character varying(16) NOT NULL,
        created_at timestamp with time zone DEFAULT now() NOT NULL,
        PRIMARY KEY (id),
        CONSTRAINT routed_predictions_disposition_check
            CHECK (((disposition)::text = ANY ((ARRAY['accepted'::character varying,
                'queued'::character varying])::text[])))
    """,
    "audit_samples": """
        id character varying NOT NULL,
        model_version character varying NOT NULL,
        population_size integer NOT NULL,
        sample_size integer NOT NULL,
        sampled_prediction_ids jsonb NOT NULL,
        agreement_rate double precision,
        reviewed_count integer,
        agreed_count integer,
        dispositions jsonb,
        status character varying(16) DEFAULT 'in_review'::character varying NOT NULL,
        reviewer character varying,
        created_at timestamp with time zone DEFAULT now() NOT NULL,
        completed_at timestamp with time zone,
        PRIMARY KEY (id),
        CONSTRAINT audit_samples_status_check
            CHECK (((status)::text = ANY ((ARRAY['in_review'::character varying,
                'completed'::character varying])::text[])))
    """,
    "annotation_imports": """
        source_file character varying NOT NULL,
        row_count integer DEFAULT 0 NOT NULL,
        type_map jsonb,
        training_eligible_at timestamp with time zone,
        created_at timestamp with time zone DEFAULT now() NOT NULL,
        PRIMARY KEY (source_file)
    """,
    "llm_prelabel_jobs": """
        id character varying NOT NULL,
        document_id character varying NOT NULL,
        status character varying(16) DEFAULT 'queued'::character varying NOT NULL,
        content_hash character varying(64) NOT NULL,
        config_version character varying(64) NOT NULL,
        served_from_cache boolean DEFAULT false NOT NULL,
        spans jsonb,
        counts jsonb,
        error_message text,
        created_at timestamp with time zone DEFAULT now(),
        completed_at timestamp with time zone,
        PRIMARY KEY (id)
    """,
    "batch_acceptance_records": """
        id character varying NOT NULL,
        batch_id character varying NOT NULL,
        sampled_document_ids jsonb NOT NULL,
        sample_size integer NOT NULL,
        sampled boolean NOT NULL,
        agreement_threshold double precision NOT NULL,
        agreement_rate double precision,
        reviewed_count integer,
        agreed_count integer,
        dispositions jsonb,
        decision character varying(16) DEFAULT 'in_review'::character varying NOT NULL,
        reviewer character varying,
        created_at timestamp with time zone DEFAULT now() NOT NULL,
        decided_at timestamp with time zone,
        PRIMARY KEY (id),
        CONSTRAINT batch_acceptance_records_decision_check
            CHECK (((decision)::text = ANY ((ARRAY['in_review'::character varying,
                'accepted'::character varying, 'rejected'::character varying])::text[])))
    """,
    "prelabel_batch_documents": """
        id character varying NOT NULL,
        batch_id character varying NOT NULL,
        document_id character varying NOT NULL,
        "position" integer NOT NULL,
        status character varying(16) DEFAULT 'pending'::character varying NOT NULL,
        counts jsonb,
        error_message text,
        completed_at timestamp with time zone,
        PRIMARY KEY (id),
        UNIQUE (batch_id, document_id),
        CONSTRAINT prelabel_batch_documents_status_check
            CHECK (((status)::text = ANY ((ARRAY['pending'::character varying,
                'succeeded'::character varying, 'failed'::character varying])::text[])))
    """,
    "prelabel_batch_guidance": """
        id character varying NOT NULL,
        batch_id character varying NOT NULL,
        document_id character varying NOT NULL,
        corrected_spans jsonb,
        note text,
        created_at timestamp with time zone DEFAULT now() NOT NULL,
        PRIMARY KEY (id),
        UNIQUE (batch_id, document_id)
    """,
    "schema_proposal_candidates": """
        id character varying NOT NULL,
        proposal_id character varying NOT NULL,
        name character varying(255) NOT NULL,
        description text,
        examples jsonb DEFAULT '[]'::jsonb NOT NULL,
        disposition character varying(16) DEFAULT 'pending'::character varying NOT NULL,
        created_entity_type character varying(255),
        updated_at timestamp with time zone,
        PRIMARY KEY (id),
        CONSTRAINT schema_proposal_candidates_disposition_check
            CHECK (((disposition)::text = ANY ((ARRAY['pending'::character varying,
                'approved'::character varying, 'edited'::character varying,
                'rejected'::character varying])::text[])))
    """,
    "span_batch_provenance": """
        span_id character varying NOT NULL,
        batch_id character varying NOT NULL,
        acceptance_id character varying NOT NULL,
        promoted_at timestamp with time zone DEFAULT now() NOT NULL,
        PRIMARY KEY (span_id)
    """,
    "span_review_provenance": """
        span_id character varying NOT NULL,
        outcome_id character varying NOT NULL,
        model_version character varying NOT NULL,
        served_by_base_model boolean DEFAULT false NOT NULL,
        created_at timestamp with time zone DEFAULT now() NOT NULL,
        PRIMARY KEY (span_id)
    """,
    "span_training_consumption": """
        span_id character varying NOT NULL,
        model_version character varying NOT NULL,
        training_job_id character varying,
        recorded_at timestamp with time zone DEFAULT now() NOT NULL,
        PRIMARY KEY (span_id)
    """,
}

# New columns on tables `baseline.py` already defines.
_COLUMN_ADDS: list[str] = [
    "ALTER TABLE {schema}.annotation_tasks "
    "ADD COLUMN IF NOT EXISTS training_eligible_at timestamp with time zone",
    "ALTER TABLE {schema}.chat_messages "
    "ADD COLUMN IF NOT EXISTS export_rows jsonb, "
    "ADD COLUMN IF NOT EXISTS export_row_count integer, "
    "ADD COLUMN IF NOT EXISTS chart jsonb",
    "ALTER TABLE {schema}.imported_annotations "
    "ADD COLUMN IF NOT EXISTS pending_mapping boolean DEFAULT false NOT NULL",
    "ALTER TABLE {schema}.suggested_spans "
    "ADD COLUMN IF NOT EXISTS source character varying(16) "
    "DEFAULT 'keyword'::character varying NOT NULL",
    "ALTER TABLE {schema}.training_jobs "
    "ADD COLUMN IF NOT EXISTS source_scope character varying(16)",
]

# New CHECK constraints on tables `baseline.py` already defines (guarded like
# `baseline.py`'s own `_FOREIGN_KEYS`: no `ADD CONSTRAINT IF NOT EXISTS` in Postgres).
_COLUMN_CHECKS: list[tuple[str, str, str]] = [
    ("suggested_spans", "ck_suggested_spans_source",
     "CHECK (((source)::text = ANY ((ARRAY['keyword'::character varying, "
     "'llm'::character varying])::text[])))"),
    ("training_jobs", "training_jobs_source_scope_check",
     "CHECK (((source_scope IS NULL) OR ((source_scope)::text = "
     "ANY ((ARRAY['manual'::character varying, 'automated'::character varying, "
     "'import'::character varying])::text[]))))"),
]

# Foreign keys -- from a new table to another new table, or to a `baseline.py` table.
# (table, constraint_name, ddl_after_ADD_CONSTRAINT)
_FOREIGN_KEYS: list[tuple[str, str, str]] = [
    ("review_outcomes", "review_outcomes_document_id_fkey",
     "FOREIGN KEY (document_id) REFERENCES {schema}.documents(id) ON DELETE CASCADE"),
    ("routed_predictions", "routed_predictions_document_id_fkey",
     "FOREIGN KEY (document_id) REFERENCES {schema}.documents(id) ON DELETE CASCADE"),
    ("routed_predictions", "routed_predictions_run_id_fkey",
     "FOREIGN KEY (run_id) REFERENCES {schema}.extraction_runs(id) ON DELETE CASCADE"),
    ("llm_prelabel_jobs", "llm_prelabel_jobs_document_id_fkey",
     "FOREIGN KEY (document_id) REFERENCES {schema}.documents(id) ON DELETE CASCADE"),
    ("batch_acceptance_records", "batch_acceptance_records_batch_id_fkey",
     "FOREIGN KEY (batch_id) REFERENCES {schema}.prelabel_batches(id) ON DELETE CASCADE"),
    ("prelabel_batch_documents", "prelabel_batch_documents_batch_id_fkey",
     "FOREIGN KEY (batch_id) REFERENCES {schema}.prelabel_batches(id) ON DELETE CASCADE"),
    ("prelabel_batch_documents", "prelabel_batch_documents_document_id_fkey",
     "FOREIGN KEY (document_id) REFERENCES {schema}.documents(id) ON DELETE CASCADE"),
    ("prelabel_batch_guidance", "prelabel_batch_guidance_batch_id_fkey",
     "FOREIGN KEY (batch_id) REFERENCES {schema}.prelabel_batches(id) ON DELETE CASCADE"),
    ("prelabel_batch_guidance", "prelabel_batch_guidance_document_id_fkey",
     "FOREIGN KEY (document_id) REFERENCES {schema}.documents(id) ON DELETE CASCADE"),
    ("schema_proposal_candidates", "schema_proposal_candidates_proposal_id_fkey",
     "FOREIGN KEY (proposal_id) REFERENCES {schema}.schema_proposals(id) ON DELETE CASCADE"),
    ("span_batch_provenance", "span_batch_provenance_span_id_fkey",
     "FOREIGN KEY (span_id) REFERENCES {schema}.spans(id) ON DELETE CASCADE"),
    ("span_batch_provenance", "span_batch_provenance_batch_id_fkey",
     "FOREIGN KEY (batch_id) REFERENCES {schema}.prelabel_batches(id) ON DELETE CASCADE"),
    ("span_batch_provenance", "span_batch_provenance_acceptance_id_fkey",
     "FOREIGN KEY (acceptance_id) REFERENCES {schema}.batch_acceptance_records(id) ON DELETE CASCADE"),
    ("span_review_provenance", "span_review_provenance_span_id_fkey",
     "FOREIGN KEY (span_id) REFERENCES {schema}.spans(id) ON DELETE CASCADE"),
    ("span_review_provenance", "span_review_provenance_outcome_id_fkey",
     "FOREIGN KEY (outcome_id) REFERENCES {schema}.review_outcomes(id) ON DELETE CASCADE"),
    ("span_training_consumption", "span_training_consumption_span_id_fkey",
     "FOREIGN KEY (span_id) REFERENCES {schema}.spans(id) ON DELETE CASCADE"),
]

# Indexes. `CREATE [UNIQUE] INDEX IF NOT EXISTS` is natively idempotent.
_INDEXES: list[str] = [
    "CREATE INDEX IF NOT EXISTS idx_batch_acceptance_records_batch "
    "ON {schema}.batch_acceptance_records USING btree (batch_id)",
    "CREATE INDEX IF NOT EXISTS idx_llm_prelabel_jobs_cache_key "
    "ON {schema}.llm_prelabel_jobs USING btree (document_id, content_hash, config_version) "
    "WHERE ((status)::text = 'completed'::text)",
    "CREATE INDEX IF NOT EXISTS idx_prelabel_batch_documents_batch "
    "ON {schema}.prelabel_batch_documents USING btree (batch_id)",
    "CREATE INDEX IF NOT EXISTS idx_prelabel_batch_guidance_batch "
    "ON {schema}.prelabel_batch_guidance USING btree (batch_id)",
    "CREATE INDEX IF NOT EXISTS idx_review_outcomes_prediction "
    "ON {schema}.review_outcomes USING btree (prediction_id)",
    "CREATE INDEX IF NOT EXISTS idx_routed_predictions_disposition "
    "ON {schema}.routed_predictions USING btree (disposition, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_routed_predictions_document "
    "ON {schema}.routed_predictions USING btree (document_id)",
    "CREATE INDEX IF NOT EXISTS idx_schema_proposal_candidates_proposal "
    "ON {schema}.schema_proposal_candidates USING btree (proposal_id)",
    "CREATE INDEX IF NOT EXISTS idx_span_review_provenance_version "
    "ON {schema}.span_review_provenance USING btree (model_version)",
]


def _guarded_add_constraint(schema: str, table: str, name: str, ddl: str) -> str:
    """Same guard as `baseline.py`'s: no `ADD CONSTRAINT IF NOT EXISTS` in Postgres."""
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
    """Idempotent DDL, applied after `baseline.py`'s (and in the same order it uses):
    new tables (inline PRIMARY KEY/UNIQUE/CHECK), column adds + checks on existing
    tables, foreign keys, then indexes."""
    out: list[str] = []
    for table, body in _TABLE_DDL.items():
        out.append(f"CREATE TABLE IF NOT EXISTS {schema}.{table} ({body})")
    for statement in _COLUMN_ADDS:
        out.append(statement.format(schema=schema))
    for table, name, ddl in _COLUMN_CHECKS:
        out.append(_guarded_add_constraint(schema, table, name, ddl))
    for table, name, ddl in _FOREIGN_KEYS:
        out.append(_guarded_add_constraint(schema, table, name, ddl))
    for index in _INDEXES:
        out.append(index.format(schema=schema))
    return out
