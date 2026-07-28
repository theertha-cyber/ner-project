from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://ner:ner@localhost:5432/ner_dev?ssl=disable"
    database_url_sync: str = "postgresql://ner:ner@localhost:5432/ner_dev?sslmode=disable"
    redis_url: str = "redis://localhost:6379/0"
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

    chat_use_graph: bool = True

    chat_agentic_retrieval: bool = False
    agentic_max_iterations: int = 3
    agentic_max_iterations_complex: int = 5
    agentic_max_tool_calls: int = 6
    agentic_deadline_seconds: float = 8.0
    agentic_observation_char_limit: int = 4000

    context_token_budget: int = 6000
    context_max_chunks: int | None = None
    conversation_history_turns: int = 5

    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:3000"]
    cors_origin_regex: str = r"http://(localhost|127\.0\.0\.1)(:\d+)?"
    cors_allow_private_network: bool = True

    model_config = {"env_prefix": "NER_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
