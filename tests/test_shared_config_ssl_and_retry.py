import importlib
import os


def _fresh_settings(env: dict):
    # conftest.py sets NER_DATABASE_URL/NER_DATABASE_URL_SYNC via setdefault for the
    # test database — clear them here unless the test explicitly wants to exercise
    # them, so "no override" tests observe the real Settings() field defaults.
    tracked_keys = set(env) | {"NER_DATABASE_URL", "NER_DATABASE_URL_SYNC"}
    old = {k: os.environ.get(k) for k in tracked_keys}
    for k in tracked_keys:
        os.environ.pop(k, None)
    os.environ.setdefault("NER_OPENAI_API_KEY", "test-openai-key")
    os.environ.update(env)
    try:
        from src.shared import config as config_module
        importlib.reload(config_module)
        # Bypass .env (which pins its own NER_DATABASE_URL/_SYNC for local dev) so
        # these tests observe class-default/env-var behavior in isolation.
        return config_module.Settings(_env_file=None)
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_default_ssl_mode_matches_pre_change_behavior():
    s = _fresh_settings({})
    assert s.database_ssl_mode == "disable"
    assert "ssl=disable" in s.database_url
    assert "sslmode=disable" in s.database_url_sync


def test_database_ssl_mode_override_updates_default_urls_without_full_url_override():
    s = _fresh_settings({"NER_DATABASE_SSL_MODE": "require"})
    assert s.database_ssl_mode == "require"
    assert "ssl=require" in s.database_url
    assert "sslmode=require" in s.database_url_sync


def test_explicit_database_url_override_is_not_rewritten_by_ssl_mode():
    custom_url = "postgresql+asyncpg://ner:ner@postgres-test:5432/ner_dev?ssl=disable"
    s = _fresh_settings({"NER_DATABASE_URL": custom_url, "NER_DATABASE_SSL_MODE": "require"})
    assert s.database_url == custom_url


def test_default_cors_and_service_urls_unchanged_without_overrides():
    s = _fresh_settings({})
    assert s.cors_origins == ["http://localhost:3000"]
    assert s.cors_origin_regex == r"http://(localhost|127\.0\.0\.1)(:\d+)?"
    assert s.model_serving_url == "http://localhost:8004"


def test_retry_env_override_takes_effect():
    s = _fresh_settings({"NER_RETRY_MAX_TOTAL_SECONDS": "60"})
    assert s.retry_max_total_seconds == 60.0


def test_retry_defaults_present():
    s = _fresh_settings({})
    assert s.retry_initial_delay_seconds == 0.5
    assert s.retry_backoff_multiplier == 2.0
    assert s.retry_max_delay_seconds == 10.0
    assert s.retry_max_total_seconds == 30.0
