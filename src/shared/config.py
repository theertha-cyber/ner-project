from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://ner:ner@localhost:5432/ner_dev"
    database_url_sync: str = "postgresql://ner:ner@localhost:5432/ner_dev"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "ner-platform"

    model_config = {"env_prefix": "NER_", "env_file": ".env"}


settings = Settings()
