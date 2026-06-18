import os
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.shared.config import Settings


def test_settings_load_from_env():
    env_content = """
NER_DATABASE_URL=postgresql+asyncpg://custom:url@host:5432/custom_db
NER_JWT_SECRET=custom-secret
NER_REDIS_URL=redis://custom:6379/1
NER_MINIO_ACCESS_KEY=custom-minio-user
NER_MINIO_SECRET_KEY=custom-minio-pass
"""
    env_vars = [k for k in os.environ if k.startswith("NER_")]
    backup = {k: os.environ.pop(k) for k in env_vars}

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env.test"
            env_path.write_text(env_content)

            settings = Settings(_env_file=str(env_path))

            assert settings.database_url == "postgresql+asyncpg://custom:url@host:5432/custom_db"
            assert settings.jwt_secret == "custom-secret"
            assert settings.redis_url == "redis://custom:6379/1"
    finally:
        os.environ.update(backup)


def test_settings_fallback_defaults():
    env_vars = [k for k in os.environ if k.startswith("NER_")]
    backup = {k: os.environ.pop(k) for k in env_vars}

    try:
        os.environ["NER_JWT_SECRET"] = "test-jwt-secret"
        os.environ["NER_MINIO_ACCESS_KEY"] = "test-minio-user"
        os.environ["NER_MINIO_SECRET_KEY"] = "test-minio-pass"

        settings = Settings(_env_file=None)

        assert settings.database_url == "postgresql+asyncpg://ner:ner@localhost:5432/ner_dev?ssl=disable"
        assert settings.database_url_sync == "postgresql://ner:ner@localhost:5432/ner_dev?sslmode=disable"
        assert settings.redis_url == "redis://localhost:6379/0"
        assert settings.jwt_algorithm == "HS256"
        assert settings.access_token_ttl_minutes == 15
        assert settings.refresh_token_ttl_days == 7
        assert settings.minio_endpoint == "localhost:9000"
        assert settings.minio_bucket == "ner-platform"
    finally:
        os.environ.update(backup)


def test_settings_fail_without_jwt_secret():
    env_vars = [k for k in os.environ if k.startswith("NER_")]
    backup = {k: os.environ.pop(k) for k in env_vars}

    try:
        with pytest.raises(ValidationError):
            Settings(_env_file=None)
    finally:
        os.environ.update(backup)


def test_settings_fail_without_minio_access_key():
    env_vars = [k for k in os.environ if k.startswith("NER_")]
    backup = {k: os.environ.pop(k) for k in env_vars}

    try:
        os.environ["NER_JWT_SECRET"] = "test-jwt-secret"
        os.environ["NER_MINIO_SECRET_KEY"] = "test-minio-pass"

        with pytest.raises(ValidationError):
            Settings(_env_file=None)
    finally:
        os.environ.update(backup)


def test_settings_fail_without_minio_secret_key():
    env_vars = [k for k in os.environ if k.startswith("NER_")]
    backup = {k: os.environ.pop(k) for k in env_vars}

    try:
        os.environ["NER_JWT_SECRET"] = "test-jwt-secret"
        os.environ["NER_MINIO_ACCESS_KEY"] = "test-minio-user"

        with pytest.raises(ValidationError):
            Settings(_env_file=None)
    finally:
        os.environ.update(backup)
