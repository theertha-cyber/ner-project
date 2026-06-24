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
    openai_api_key: str
    chat_api_port: int = 8006
    chat_api_url: str = "http://localhost:8006"

    azure_openai_endpoint: str | None = None
    azure_openai_api_version: str = "2024-12-01-preview"
    azure_openai_chat_deployment: str = "gpt-4o-mini"
    azure_openai_embedding_deployment: str = "text-embedding-3-small"

    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:3000"]
    cors_origin_regex: str = r"http://(localhost|127\.0\.0\.1)(:\d+)?"
    cors_allow_private_network: bool = True

    model_config = {"env_prefix": "NER_", "env_file": ".env"}


settings = Settings()
