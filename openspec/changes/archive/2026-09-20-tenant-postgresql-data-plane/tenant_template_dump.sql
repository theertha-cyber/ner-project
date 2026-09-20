--
-- PostgreSQL database dump
--

\restrict Up4WohSoN43b9c0K4FqeBCXUlKZSAQRwZfrwYbxt9PtjKFLF9alRmLkhem3nF6g

-- Dumped from database version 16.14 (Debian 16.14-1.pgdg12+1)
-- Dumped by pg_dump version 16.14 (Debian 16.14-1.pgdg12+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: tenant_template; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA tenant_template;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: annotation_labels; Type: TABLE; Schema: tenant_template; Owner: -
--

CREATE TABLE tenant_template.annotation_labels (
    id character varying NOT NULL,
    task_id character varying NOT NULL,
    entity_id character varying NOT NULL,
    token_start integer,
    token_end integer,
    value text,
    confidence double precision,
    corrected_flag boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: annotation_tasks; Type: TABLE; Schema: tenant_template; Owner: -
--

CREATE TABLE tenant_template.annotation_tasks (
    id character varying NOT NULL,
    document_id character varying NOT NULL,
    assignee character varying,
    status character varying(20) DEFAULT 'unannotated'::character varying,
    reviewer character varying,
    dataset_version integer,
    created_at timestamp with time zone DEFAULT now(),
    annotator_user_id character varying,
    updated_at timestamp with time zone
);


--
-- Name: audit_log; Type: TABLE; Schema: tenant_template; Owner: -
--

CREATE TABLE tenant_template.audit_log (
    id character varying NOT NULL,
    tenant_id character varying NOT NULL,
    actor_id character varying,
    action character varying(100) NOT NULL,
    resource_type character varying(100),
    resource_id character varying,
    details jsonb,
    ip_address character varying(45),
    "timestamp" timestamp with time zone DEFAULT now()
);


--
-- Name: azure_blob_hidden_documents; Type: TABLE; Schema: tenant_template; Owner: -
--

CREATE TABLE tenant_template.azure_blob_hidden_documents (
    document_id character varying NOT NULL,
    connection_id character varying NOT NULL,
    cause character varying(32) NOT NULL,
    hidden_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: azure_blob_source_objects; Type: TABLE; Schema: tenant_template; Owner: -
--

CREATE TABLE tenant_template.azure_blob_source_objects (
    connection_id character varying NOT NULL,
    object_identity character varying(1024) NOT NULL,
    source_version character varying(256),
    document_id character varying,
    missing_sightings integer DEFAULT 0 NOT NULL,
    confirmed_missing boolean DEFAULT false NOT NULL,
    last_seen_at timestamp with time zone
);


--
-- Name: azure_blob_sync_leases; Type: TABLE; Schema: tenant_template; Owner: -
--

CREATE TABLE tenant_template.azure_blob_sync_leases (
    connection_id character varying NOT NULL,
    run_id character varying NOT NULL,
    acquired_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL
);


--
-- Name: azure_blob_sync_runs; Type: TABLE; Schema: tenant_template; Owner: -
--

CREATE TABLE tenant_template.azure_blob_sync_runs (
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
    completed_at timestamp with time zone
);


--
-- Name: chat_message_feedback; Type: TABLE; Schema: tenant_template; Owner: -
--

CREATE TABLE tenant_template.chat_message_feedback (
    id character varying NOT NULL,
    message_id character varying NOT NULL,
    tenant_id character varying NOT NULL,
    user_id character varying NOT NULL,
    rating text NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT chat_message_feedback_rating_check CHECK ((rating = ANY (ARRAY['up'::text, 'down'::text])))
);


--
-- Name: chat_messages; Type: TABLE; Schema: tenant_template; Owner: -
--

CREATE TABLE tenant_template.chat_messages (
    id character varying NOT NULL,
    conversation_id character varying NOT NULL,
    role character varying(20) NOT NULL,
    content text NOT NULL,
    sources jsonb,
    created_at timestamp with time zone DEFAULT now(),
    answer_kind text DEFAULT 'answer'::text NOT NULL,
    model_version text,
    response_time_ms integer
);


--
-- Name: conversation_entity_state; Type: TABLE; Schema: tenant_template; Owner: -
--

CREATE TABLE tenant_template.conversation_entity_state (
    conversation_id character varying NOT NULL,
    pending_original_message text,
    pending_mention text,
    pending_candidates jsonb,
    pending_reask_count integer DEFAULT 0 NOT NULL,
    resolved_document_id character varying,
    resolved_entity_value text,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: conversations; Type: TABLE; Schema: tenant_template; Owner: -
--

CREATE TABLE tenant_template.conversations (
    id character varying NOT NULL,
    tenant_id character varying NOT NULL,
    user_id character varying NOT NULL,
    title character varying(255),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: document_chunks; Type: TABLE; Schema: tenant_template; Owner: -
--

CREATE TABLE tenant_template.document_chunks (
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
    chunk_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english'::regconfig, chunk_text)) STORED
);


--
-- Name: document_entities; Type: TABLE; Schema: tenant_template; Owner: -
--

CREATE TABLE tenant_template.document_entities (
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
    occurrence_count integer DEFAULT 1 NOT NULL
);


--
-- Name: document_text_spans; Type: TABLE; Schema: tenant_template; Owner: -
--

CREATE TABLE tenant_template.document_text_spans (
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
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: documents; Type: TABLE; Schema: tenant_template; Owner: -
--

CREATE TABLE tenant_template.documents (
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
    CONSTRAINT documents_retention_mode_check CHECK (((retention_mode)::text = ANY ((ARRAY['platform_blob'::character varying, 'ephemeral'::character varying, 'source_only'::character varying])::text[])))
);


--
-- Name: external_pg_schema_index; Type: TABLE; Schema: tenant_template; Owner: -
--

CREATE TABLE tenant_template.external_pg_schema_index (
    connection_id character varying NOT NULL,
    contract_version integer NOT NULL,
    relation_name character varying(256) NOT NULL,
    entry_text text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: extracted_entities; Type: TABLE; Schema: tenant_template; Owner: -
--

CREATE TABLE tenant_template.extracted_entities (
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
    document_id character varying
);


--
-- Name: extraction_runs; Type: TABLE; Schema: tenant_template; Owner: -
--

CREATE TABLE tenant_template.extraction_runs (
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
    failed_count integer DEFAULT 0 NOT NULL
);


--
-- Name: imported_annotations; Type: TABLE; Schema: tenant_template; Owner: -
--

CREATE TABLE tenant_template.imported_annotations (
    id character varying NOT NULL,
    tokens text[] NOT NULL,
    tags text[] NOT NULL,
    source_file character varying NOT NULL,
    row_index integer NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: model_versions; Type: TABLE; Schema: tenant_template; Owner: -
--

CREATE TABLE tenant_template.model_versions (
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
    artifact_path text
);


--
-- Name: mv_confidence_distribution; Type: MATERIALIZED VIEW; Schema: tenant_template; Owner: -
--

CREATE MATERIALIZED VIEW tenant_template.mv_confidence_distribution AS
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
   FROM tenant_template.extracted_entities
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
  WITH NO DATA;


--
-- Name: mv_document_entity_counts; Type: MATERIALIZED VIEW; Schema: tenant_template; Owner: -
--

CREATE MATERIALIZED VIEW tenant_template.mv_document_entity_counts AS
 SELECT entity_id AS entity_type,
    (avg(entity_count))::double precision AS avg_per_document
   FROM ( SELECT extracted_entities.entity_id,
            extracted_entities.document_id,
            count(*) AS entity_count
           FROM tenant_template.extracted_entities
          GROUP BY extracted_entities.entity_id, extracted_entities.document_id) e
  GROUP BY entity_id
  WITH NO DATA;


--
-- Name: mv_entity_coverage; Type: MATERIALIZED VIEW; Schema: tenant_template; Owner: -
--

CREATE MATERIALIZED VIEW tenant_template.mv_entity_coverage AS
 SELECT e.entity_id AS entity_type,
    (((count(DISTINCT e.document_id))::double precision / (NULLIF(count(DISTINCT d.id), 0))::double precision) * (100)::double precision) AS coverage_pct
   FROM (tenant_template.extracted_entities e
     CROSS JOIN tenant_template.documents d)
  GROUP BY e.entity_id
  WITH NO DATA;


--
-- Name: mv_extraction_volume; Type: MATERIALIZED VIEW; Schema: tenant_template; Owner: -
--

CREATE MATERIALIZED VIEW tenant_template.mv_extraction_volume AS
 SELECT date(r.started_at) AS extraction_date,
    count(*) AS count
   FROM (tenant_template.extracted_entities e
     JOIN tenant_template.extraction_runs r ON (((r.id)::text = (e.run_id)::text)))
  WHERE (r.started_at >= (now() - '30 days'::interval))
  GROUP BY (date(r.started_at))
  ORDER BY (date(r.started_at))
  WITH NO DATA;


--
-- Name: spans; Type: TABLE; Schema: tenant_template; Owner: -
--

CREATE TABLE tenant_template.spans (
    id character varying NOT NULL,
    document_id character varying NOT NULL,
    entity_type character varying(255) NOT NULL,
    char_start integer NOT NULL,
    char_end integer NOT NULL,
    text_content character varying NOT NULL,
    confidence double precision DEFAULT 1.0 NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone,
    bio_tags text[]
);


--
-- Name: suggested_spans; Type: TABLE; Schema: tenant_template; Owner: -
--

CREATE TABLE tenant_template.suggested_spans (
    id character varying NOT NULL,
    document_id character varying NOT NULL,
    entity_type character varying(255) NOT NULL,
    char_start integer NOT NULL,
    char_end integer NOT NULL,
    text_content character varying NOT NULL,
    confidence double precision NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: training_jobs; Type: TABLE; Schema: tenant_template; Owner: -
--

CREATE TABLE tenant_template.training_jobs (
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
    failed_at timestamp with time zone
);


--
-- Name: annotation_labels annotation_labels_pkey; Type: CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.annotation_labels
    ADD CONSTRAINT annotation_labels_pkey PRIMARY KEY (id);


--
-- Name: annotation_tasks annotation_tasks_pkey; Type: CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.annotation_tasks
    ADD CONSTRAINT annotation_tasks_pkey PRIMARY KEY (id);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- Name: azure_blob_hidden_documents azure_blob_hidden_documents_pkey; Type: CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.azure_blob_hidden_documents
    ADD CONSTRAINT azure_blob_hidden_documents_pkey PRIMARY KEY (document_id);


--
-- Name: azure_blob_source_objects azure_blob_source_objects_pkey; Type: CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.azure_blob_source_objects
    ADD CONSTRAINT azure_blob_source_objects_pkey PRIMARY KEY (connection_id, object_identity);


--
-- Name: azure_blob_sync_leases azure_blob_sync_leases_pkey; Type: CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.azure_blob_sync_leases
    ADD CONSTRAINT azure_blob_sync_leases_pkey PRIMARY KEY (connection_id);


--
-- Name: azure_blob_sync_runs azure_blob_sync_runs_pkey; Type: CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.azure_blob_sync_runs
    ADD CONSTRAINT azure_blob_sync_runs_pkey PRIMARY KEY (id);


--
-- Name: chat_message_feedback chat_message_feedback_message_id_key; Type: CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.chat_message_feedback
    ADD CONSTRAINT chat_message_feedback_message_id_key UNIQUE (message_id);


--
-- Name: chat_message_feedback chat_message_feedback_pkey; Type: CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.chat_message_feedback
    ADD CONSTRAINT chat_message_feedback_pkey PRIMARY KEY (id);


--
-- Name: chat_messages chat_messages_pkey; Type: CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.chat_messages
    ADD CONSTRAINT chat_messages_pkey PRIMARY KEY (id);


--
-- Name: conversation_entity_state conversation_entity_state_pkey; Type: CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.conversation_entity_state
    ADD CONSTRAINT conversation_entity_state_pkey PRIMARY KEY (conversation_id);


--
-- Name: conversations conversations_pkey; Type: CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.conversations
    ADD CONSTRAINT conversations_pkey PRIMARY KEY (id);


--
-- Name: document_chunks document_chunks_pkey; Type: CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.document_chunks
    ADD CONSTRAINT document_chunks_pkey PRIMARY KEY (id);


--
-- Name: document_entities document_entities_pkey; Type: CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.document_entities
    ADD CONSTRAINT document_entities_pkey PRIMARY KEY (id);


--
-- Name: document_text_spans document_text_spans_pkey; Type: CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.document_text_spans
    ADD CONSTRAINT document_text_spans_pkey PRIMARY KEY (id);


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);


--
-- Name: external_pg_schema_index external_pg_schema_index_pkey; Type: CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.external_pg_schema_index
    ADD CONSTRAINT external_pg_schema_index_pkey PRIMARY KEY (connection_id, contract_version, relation_name);


--
-- Name: extracted_entities extracted_entities_pkey; Type: CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.extracted_entities
    ADD CONSTRAINT extracted_entities_pkey PRIMARY KEY (id);


--
-- Name: extraction_runs extraction_runs_pkey; Type: CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.extraction_runs
    ADD CONSTRAINT extraction_runs_pkey PRIMARY KEY (id);


--
-- Name: imported_annotations imported_annotations_pkey; Type: CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.imported_annotations
    ADD CONSTRAINT imported_annotations_pkey PRIMARY KEY (id);


--
-- Name: model_versions model_versions_pkey; Type: CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.model_versions
    ADD CONSTRAINT model_versions_pkey PRIMARY KEY (id);


--
-- Name: spans spans_pkey; Type: CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.spans
    ADD CONSTRAINT spans_pkey PRIMARY KEY (id);


--
-- Name: suggested_spans suggested_spans_pkey; Type: CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.suggested_spans
    ADD CONSTRAINT suggested_spans_pkey PRIMARY KEY (id);


--
-- Name: training_jobs training_jobs_pkey; Type: CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.training_jobs
    ADD CONSTRAINT training_jobs_pkey PRIMARY KEY (id);


--
-- Name: idx_document_chunks_embedding_hnsw; Type: INDEX; Schema: tenant_template; Owner: -
--

CREATE INDEX idx_document_chunks_embedding_hnsw ON tenant_template.document_chunks USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_document_chunks_tsv; Type: INDEX; Schema: tenant_template; Owner: -
--

CREATE INDEX idx_document_chunks_tsv ON tenant_template.document_chunks USING gin (chunk_tsv);


--
-- Name: idx_document_entities_template_document_id; Type: INDEX; Schema: tenant_template; Owner: -
--

CREATE INDEX idx_document_entities_template_document_id ON tenant_template.document_entities USING btree (document_id);


--
-- Name: idx_document_entities_template_entity_type; Type: INDEX; Schema: tenant_template; Owner: -
--

CREATE INDEX idx_document_entities_template_entity_type ON tenant_template.document_entities USING btree (entity_type);


--
-- Name: idx_document_entities_template_normalized_value; Type: INDEX; Schema: tenant_template; Owner: -
--

CREATE INDEX idx_document_entities_template_normalized_value ON tenant_template.document_entities USING btree (normalized_value);


--
-- Name: idx_document_entities_template_postprocess_status; Type: INDEX; Schema: tenant_template; Owner: -
--

CREATE INDEX idx_document_entities_template_postprocess_status ON tenant_template.document_entities USING btree (postprocess_status) WHERE (postprocess_status <> 'not_applied'::text);


--
-- Name: idx_document_entities_template_value_date; Type: INDEX; Schema: tenant_template; Owner: -
--

CREATE INDEX idx_document_entities_template_value_date ON tenant_template.document_entities USING btree (entity_type, value_date) WHERE (value_date IS NOT NULL);


--
-- Name: idx_document_entities_template_value_number; Type: INDEX; Schema: tenant_template; Owner: -
--

CREATE INDEX idx_document_entities_template_value_number ON tenant_template.document_entities USING btree (entity_type, value_number) WHERE (value_number IS NOT NULL);


--
-- Name: idx_model_versions_tenant_promoted; Type: INDEX; Schema: tenant_template; Owner: -
--

CREATE UNIQUE INDEX idx_model_versions_tenant_promoted ON tenant_template.model_versions USING btree (tenant_id) WHERE ((status)::text = 'promoted'::text);


--
-- Name: idx_model_versions_tenant_status; Type: INDEX; Schema: tenant_template; Owner: -
--

CREATE INDEX idx_model_versions_tenant_status ON tenant_template.model_versions USING btree (tenant_id, status);


--
-- Name: idx_mv_confidence_distribution_bucket; Type: INDEX; Schema: tenant_template; Owner: -
--

CREATE UNIQUE INDEX idx_mv_confidence_distribution_bucket ON tenant_template.mv_confidence_distribution USING btree (bucket);


--
-- Name: idx_mv_document_entity_counts_type; Type: INDEX; Schema: tenant_template; Owner: -
--

CREATE UNIQUE INDEX idx_mv_document_entity_counts_type ON tenant_template.mv_document_entity_counts USING btree (entity_type);


--
-- Name: idx_mv_entity_coverage_type; Type: INDEX; Schema: tenant_template; Owner: -
--

CREATE UNIQUE INDEX idx_mv_entity_coverage_type ON tenant_template.mv_entity_coverage USING btree (entity_type);


--
-- Name: idx_mv_extraction_volume_date; Type: INDEX; Schema: tenant_template; Owner: -
--

CREATE UNIQUE INDEX idx_mv_extraction_volume_date ON tenant_template.mv_extraction_volume USING btree (extraction_date);


--
-- Name: idx_task_active_document; Type: INDEX; Schema: tenant_template; Owner: -
--

CREATE UNIQUE INDEX idx_task_active_document ON tenant_template.annotation_tasks USING btree (document_id) WHERE ((status)::text = ANY ((ARRAY['unannotated'::character varying, 'in-progress'::character varying])::text[]));


--
-- Name: idx_training_jobs_tenant_status; Type: INDEX; Schema: tenant_template; Owner: -
--

CREATE INDEX idx_training_jobs_tenant_status ON tenant_template.training_jobs USING btree (tenant_id, status);


--
-- Name: ix_blob_sync_runs_conn; Type: INDEX; Schema: tenant_template; Owner: -
--

CREATE INDEX ix_blob_sync_runs_conn ON tenant_template.azure_blob_sync_runs USING btree (connection_id, started_at DESC);


--
-- Name: ix_documents_checksum; Type: INDEX; Schema: tenant_template; Owner: -
--

CREATE INDEX ix_documents_checksum ON tenant_template.documents USING btree (checksum);


--
-- Name: annotation_labels annotation_labels_task_id_fkey; Type: FK CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.annotation_labels
    ADD CONSTRAINT annotation_labels_task_id_fkey FOREIGN KEY (task_id) REFERENCES tenant_template.annotation_tasks(id) ON DELETE CASCADE;


--
-- Name: annotation_tasks annotation_tasks_document_id_fkey; Type: FK CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.annotation_tasks
    ADD CONSTRAINT annotation_tasks_document_id_fkey FOREIGN KEY (document_id) REFERENCES tenant_template.documents(id) ON DELETE CASCADE;


--
-- Name: chat_message_feedback chat_message_feedback_message_id_fkey; Type: FK CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.chat_message_feedback
    ADD CONSTRAINT chat_message_feedback_message_id_fkey FOREIGN KEY (message_id) REFERENCES tenant_template.chat_messages(id) ON DELETE CASCADE;


--
-- Name: chat_messages chat_messages_conversation_id_fkey; Type: FK CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.chat_messages
    ADD CONSTRAINT chat_messages_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES tenant_template.conversations(id) ON DELETE CASCADE;


--
-- Name: document_chunks document_chunks_document_id_fkey; Type: FK CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.document_chunks
    ADD CONSTRAINT document_chunks_document_id_fkey FOREIGN KEY (document_id) REFERENCES tenant_template.documents(id) ON DELETE CASCADE;


--
-- Name: document_text_spans document_text_spans_document_id_fkey; Type: FK CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.document_text_spans
    ADD CONSTRAINT document_text_spans_document_id_fkey FOREIGN KEY (document_id) REFERENCES tenant_template.documents(id) ON DELETE CASCADE;


--
-- Name: extracted_entities extracted_entities_run_id_fkey; Type: FK CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.extracted_entities
    ADD CONSTRAINT extracted_entities_run_id_fkey FOREIGN KEY (run_id) REFERENCES tenant_template.extraction_runs(id) ON DELETE CASCADE;


--
-- Name: extracted_entities extracted_entities_source_span_id_fkey; Type: FK CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.extracted_entities
    ADD CONSTRAINT extracted_entities_source_span_id_fkey FOREIGN KEY (source_span_id) REFERENCES tenant_template.document_text_spans(id);


--
-- Name: extraction_runs extraction_runs_document_id_fkey; Type: FK CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.extraction_runs
    ADD CONSTRAINT extraction_runs_document_id_fkey FOREIGN KEY (document_id) REFERENCES tenant_template.documents(id) ON DELETE CASCADE;


--
-- Name: model_versions model_versions_training_job_id_fkey; Type: FK CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.model_versions
    ADD CONSTRAINT model_versions_training_job_id_fkey FOREIGN KEY (training_job_id) REFERENCES tenant_template.training_jobs(id);


--
-- Name: spans spans_document_id_fkey; Type: FK CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.spans
    ADD CONSTRAINT spans_document_id_fkey FOREIGN KEY (document_id) REFERENCES tenant_template.documents(id) ON DELETE CASCADE;


--
-- Name: suggested_spans suggested_spans_document_id_fkey; Type: FK CONSTRAINT; Schema: tenant_template; Owner: -
--

ALTER TABLE ONLY tenant_template.suggested_spans
    ADD CONSTRAINT suggested_spans_document_id_fkey FOREIGN KEY (document_id) REFERENCES tenant_template.documents(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict Up4WohSoN43b9c0K4FqeBCXUlKZSAQRwZfrwYbxt9PtjKFLF9alRmLkhem3nF6g

