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


def test_reranking_defaults_with_no_env_overrides():
    """Covers scenario 12: task 1.2."""
    env_vars = [k for k in os.environ if k.startswith("NER_RERANK")]
    backup = {k: os.environ.pop(k) for k in env_vars}

    try:
        os.environ["NER_JWT_SECRET"] = "test-jwt-secret"
        os.environ["NER_MINIO_ACCESS_KEY"] = "test-minio-user"
        os.environ["NER_MINIO_SECRET_KEY"] = "test-minio-pass"
        os.environ["NER_OPENAI_API_KEY"] = "test-openai-key"

        settings = Settings(_env_file=None)

        assert settings.reranker_enabled is True
        assert settings.rerank_candidate_count == 20
        assert settings.reranker_model == "cross-encoder/ms-marco-MiniLM-L-6-v2"
    finally:
        os.environ.update(backup)


def test_context_assembly_defaults_with_no_env_overrides():
    """Covers scenario 15: task 1.2."""
    env_vars = [k for k in os.environ if k.startswith("NER_CONTEXT") or k.startswith("NER_CONVERSATION")]
    backup = {k: os.environ.pop(k) for k in env_vars}

    try:
        os.environ["NER_JWT_SECRET"] = "test-jwt-secret"
        os.environ["NER_MINIO_ACCESS_KEY"] = "test-minio-user"
        os.environ["NER_MINIO_SECRET_KEY"] = "test-minio-pass"
        os.environ["NER_OPENAI_API_KEY"] = "test-openai-key"

        settings = Settings(_env_file=None)

        assert settings.context_token_budget == 6000
        assert settings.conversation_history_turns == 5
    finally:
        os.environ.update(backup)


def test_new_chunk_cap_defaults_match_design():
    """verification.md row 80. One value used to govern per-invocation retrieval, the
    prompt admission, and (via a hardcoded literal) the citations, so a multi-invocation
    plan discarded most of what it retrieved without any of it being visible. Defaults
    are recorded in design.md Decision 9."""
    env_vars = [
        k for k in os.environ
        if k.startswith("NER_CONTEXT") or k.startswith("NER_RETRIEVAL") or k.startswith("NER_CITATION")
    ]
    backup = {k: os.environ.pop(k) for k in env_vars}

    try:
        os.environ["NER_JWT_SECRET"] = "test-jwt-secret"
        os.environ["NER_MINIO_ACCESS_KEY"] = "test-minio-user"
        os.environ["NER_MINIO_SECRET_KEY"] = "test-minio-pass"
        os.environ["NER_OPENAI_API_KEY"] = "test-openai-key"

        settings = Settings(_env_file=None)

        assert settings.retrieval_top_k == 5
        assert settings.retrieval_merge_max_chunks == 10
        assert settings.context_max_chunks == 8
        assert settings.citation_max_chunks == 8
        # No cap silently derives from another.
        assert settings.context_max_chunks != settings.retrieval_top_k
        assert settings.retrieval_recovery_min_budget_seconds == 2.0
    finally:
        os.environ.update(backup)


def test_reranker_enabled_false_via_env_var():
    """Covers scenario 13: task 1.3."""
    env_vars = [k for k in os.environ if k.startswith("NER_RERANK")]
    backup = {k: os.environ.pop(k) for k in env_vars}

    try:
        os.environ["NER_JWT_SECRET"] = "test-jwt-secret"
        os.environ["NER_MINIO_ACCESS_KEY"] = "test-minio-user"
        os.environ["NER_MINIO_SECRET_KEY"] = "test-minio-pass"
        os.environ["NER_OPENAI_API_KEY"] = "test-openai-key"
        os.environ["NER_RERANKER_ENABLED"] = "false"

        settings = Settings(_env_file=None)

        assert settings.reranker_enabled is False
    finally:
        os.environ.update(backup)
