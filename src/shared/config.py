import re

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://ner:ner@localhost:5432/ner_dev?ssl=disable"
    database_url_sync: str = "postgresql://ner:ner@localhost:5432/ner_dev?sslmode=disable"
    database_ssl_mode: str = "disable"
    redis_url: str = "redis://localhost:6379/0"
    # Root log level. Application loggers emit through the root logger, which Python
    # defaults to WARNING with no handlers — so `logger.info` lines (the generated SQL
    # among them) are discarded before reaching stdout unless this is configured.
    # INFO surfaces the generated SQL in `docker logs`, which includes literals derived
    # from the user's question; drop to WARNING where those logs are retained or shipped.
    log_level: str = "INFO"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    training_device: str = "cpu"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str = "ner-platform"
    mlflow_tracking_uri: str = "http://localhost:5000"
    model_serving_port: int = 8004
    extraction_celery_queue: str = "extraction"
    confidence_threshold: float = 0.50
    model_cache_memory_limit_gb: int = 2
    model_cache_ttl_minutes: int = 30
    model_serving_url: str = "http://localhost:8004"
    # Sliding-window NER inference. Sizes are WordPiece counts, excluding the two
    # special tokens ([CLS]/[SEP]) that the tokenizer adds, so
    # `inference_window_size + 2` must stay under the BERT positional-embedding
    # limit of 512. Overlap is re-inferred context, not new coverage: a token near
    # a window edge sees truncated context and gets an unreliable BIO label, so
    # every token is covered by some window that holds it well away from an edge.
    inference_window_size: int = 400
    inference_window_overlap: int = 50
    extraction_service_url: str = "http://localhost:8002"
    document_service_url: str = "http://localhost:8001"
    training_service_url: str = "http://localhost:8003"
    openai_api_key: str
    chat_api_port: int = 8006
    chat_api_url: str = "http://localhost:8006"
    analytics_service_url: str = "http://localhost:8007"

    azure_openai_endpoint: str | None = None
    azure_openai_api_version: str = "2024-12-01-preview"
    azure_openai_chat_deployment: str = "gpt-4o-mini"
    azure_openai_embedding_deployment: str = "text-embedding-3-small"

    chunk_size: int = 512
    chunk_overlap: int = 128
    retrieval_top_k: int = 5
    embedding_model: str = "text-embedding-3-small"

    reranker_enabled: bool = True
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    rerank_candidate_count: int = 20
    # Loading the cross-encoder on first use takes far longer than scoring with it.
    # model_serving warms it at startup, so this only has to cover a genuinely slow
    # scoring call — but it must still exceed a cold load, or the very first query
    # after a restart races the warm-up and silently falls back to unranked results.
    rerank_timeout_seconds: float = 30.0

    orchestrator_max_invocations: int = 3
    retrieval_deadline_seconds: float = 8.0
    candidate_document_filtering_enabled: bool = False
    # A structured-only plan that finds nothing gets exactly one semantic retry, but
    # only with this much of the retrieval deadline left. Inferred from observed
    # latencies (planner 1.0-3.0s, structured attempt 1.7-2.8s of an 8s window):
    # recovery must never be the reason a turn misses the ADR-007 P95 target.
    retrieval_recovery_min_budget_seconds: float = 2.0

    # Generated SQL runs under a dedicated least-privilege role holding SELECT on the
    # whitelisted tables in tenant schemas and nothing at all in `public`. It is
    # defence in depth behind `validate_sql`, so a future gap in table-reference
    # resolution degrades into a permission error rather than a cross-tenant read.
    # The role is chosen here and nowhere else — never from a tool argument, the
    # question, or the generated statement. Disabling the toggle restores the
    # connection role without a redeploy; the role itself is left provisioned.
    sql_execution_role_enabled: bool = False
    sql_execution_role_name: str = "ner_chat_sql"

    # Bounded SQL recovery. `sql_max_attempts = 1` restores the pre-existing
    # one-shot behaviour and is the config-only rollback for the retry loop.
    sql_max_attempts: int = 3
    sql_entity_sample_values_per_type: int = 8
    sql_entity_sample_max_values: int = 120

    entity_resolution_enabled: bool = True
    entity_resolution_max_candidates: int = 5
    # Entity types that hold people's names. Must cover what the tenant's own label
    # schema actually calls them: a fine-tuned model emits its own label set, and a
    # tenant whose name type is `NAME` resolves nothing against a `PER,PERSON` list.
    entity_resolution_person_types: str = "PER,PERSON,NAME,CANDIDATE_NAME,PERSON_NAME"
    entity_resolution_max_skills: int = 3

    # --- Entity quality: reconstruction, validity, and provenance ---
    # Words that may sit between an entity's tokens and still belong to it. Model
    # serving drops every `O` prediction before responding, so a labelled word two
    # positions later arrives adjacent in the list. Requiring a strict `word_index + 1`
    # split "Having two and a half years of experience" into `two` and `half years`,
    # which then typed as 2.0 and 0.5 instead of 2.5. The bound plus the same-page
    # requirement keeps the cross-page stitching this guard was written to prevent.
    max_entity_word_gap: int = 2
    # Canonical values shorter than this are extraction artifacts, not facts — the dev
    # tenant persisted two rows whose value was the empty string. Types naming genuine
    # short codes (`C`, `R`, `Go`) are exempted by name rather than by a character rule,
    # because "short and meaningful" is a property of the type, not of the string.
    min_entity_value_length: int = 2
    entity_short_value_types: str = "PROGRAMMING_LANGUAGE"
    # Bumped whenever the deterministic pipeline changes in a way that makes new rows
    # incomparable with old ones. Version 1 is the pre-calibration pipeline: raw-logit
    # confidence, untrimmed spans, no validity gate, one row per mention.
    extraction_schema_version: int = 2

    # --- Entity post-processing (optional LLM layer over BERT output) ---
    # Off by default: it costs tokens, adds an external dependency to extraction, and
    # is only offered as a processing mode once it clears the evaluation gate.
    postprocess_enabled: bool = False
    # Compared against a calibrated probability. Only rows stamped with the current
    # `extraction_schema_version` are eligible — a raw logit is not on this scale.
    postprocess_confidence_threshold: float = 0.60
    postprocess_timeout_seconds: float = 20.0
    postprocess_context_chars: int = 1200
    postprocess_token_budget: int = 200_000
    postprocess_prompt_version: str = "v1"
    # Types whose values are normally multi-token, so a single-token extraction is
    # suspect enough to be worth a look.
    postprocess_multi_token_types: str = "NAME,COMPANY,INSTITUTION,ADDRESS"

    context_token_budget: int = 6000
    # Four independent caps on what used to be governed by one value and one literal.
    # `retrieval_top_k` bounds a single retrieval invocation; a plan with three semantic
    # invocations could therefore produce 15 unique chunks, of which the prompt admitted
    # 5 and the citations 3 — two thirds discarded silently, and the two counts
    # disagreeing in both directions. Each stage now names its own cap.
    #   retrieval_top_k             per-invocation retrieval depth (declared above)
    #   retrieval_merge_max_chunks  retained after cross-invocation merge
    #   context_max_chunks          admitted into the generation prompt
    #   citation_max_chunks         returned to the user as citations
    retrieval_merge_max_chunks: int = 10
    context_max_chunks: int = 8
    citation_max_chunks: int = 8
    conversation_history_turns: int = 5

    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:3000"]
    cors_origin_regex: str = r"http://(localhost|127\.0\.0\.1)(:\d+)?"
    cors_allow_private_network: bool = True

    retry_initial_delay_seconds: float = 0.5
    retry_backoff_multiplier: float = 2.0
    retry_max_delay_seconds: float = 10.0
    retry_max_total_seconds: float = 30.0

    model_config = {"env_prefix": "NER_", "env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def _apply_database_ssl_mode(self) -> "Settings":
        """Inject database_ssl_mode into the default connection URLs when the
        URLs themselves were not explicitly overridden, so operators can
        toggle SSL via one env var instead of reconstructing the whole URL."""
        fields_set = self.model_fields_set
        if "database_url" not in fields_set:
            self.database_url = re.sub(r"ssl=[^&]*", f"ssl={self.database_ssl_mode}", self.database_url)
        if "database_url_sync" not in fields_set:
            self.database_url_sync = re.sub(
                r"sslmode=[^&]*", f"sslmode={self.database_ssl_mode}", self.database_url_sync
            )
        return self


settings = Settings()
