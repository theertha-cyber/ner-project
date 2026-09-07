"""Secret-class settings must have no default, including the new telemetry pepper.

Verification rows 30 and 31.

The pepper keys the user hash that keeps raw user identity out of the log store. A
default value — even a "clearly fake" one committed to make tests pass — would mean every
deployment that forgot to set it shares one publicly-known key, and an HMAC under a known
key over a tenant's user list is reversible by enumeration. That puts identity straight
back into telemetry while the field still looks hashed.

So the pepper is treated exactly like `jwt_secret`: absent means startup fails, loudly,
naming the setting.
"""

import os
from contextlib import contextmanager

import pytest
from pydantic import ValidationError

from src.shared.config import Settings

pytestmark = [pytest.mark.verification]

# Every field that must be supplied by the environment. `telemetry_pepper` joins the
# three that predate this change.
SECRET_FIELDS = ("jwt_secret", "minio_access_key", "minio_secret_key", "telemetry_pepper")

# The non-secret required fields, so a test isolating one secret does not fail on another.
_OTHER_REQUIRED = {
    "NER_JWT_SECRET": "test-jwt-secret",
    "NER_MINIO_ACCESS_KEY": "test-minio-access-key",
    "NER_MINIO_SECRET_KEY": "test-minio-secret-key",
    "NER_OPENAI_API_KEY": "test-openai-key",
    "NER_TELEMETRY_PEPPER": "test-telemetry-pepper",
}


@contextmanager
def clean_ner_environment():
    """Run with no `NER_` variables set, restoring them afterwards.

    The suite's own conftest exports several of these, so a test that reads the real
    environment would pass whether or not the field has a default.
    """
    saved = {key: os.environ.pop(key) for key in [k for k in os.environ if k.startswith("NER_")]}
    try:
        yield
    finally:
        os.environ.update(saved)


class TestSecretFieldsHaveNoDefault:
    """Row 30 — no plaintext secret defaults in `src/shared/config.py`."""

    @pytest.mark.parametrize("field", SECRET_FIELDS)
    def test_field_is_required(self, field):
        assert Settings.model_fields[field].is_required(), (
            f"`{field}` has a default. A secret-class setting with a default is a "
            "committed secret that no reviewer will notice."
        )


class TestStartupFailsWithoutThePepper:
    """Row 31 — absent pepper fails startup, naming the setting."""

    def test_missing_pepper_raises_naming_the_field(self):
        with clean_ner_environment():
            for key, value in _OTHER_REQUIRED.items():
                if key != "NER_TELEMETRY_PEPPER":
                    os.environ[key] = value

            with pytest.raises(ValidationError) as excinfo:
                # `_env_file=None`: the repository's own `.env` supplies the pepper, and
                # reading it here would test the developer's machine, not the code.
                Settings(_env_file=None)

        assert "telemetry_pepper" in str(excinfo.value)

    def test_pepper_present_allows_construction(self):
        with clean_ner_environment():
            os.environ.update(_OTHER_REQUIRED)
            settings = Settings(_env_file=None)

        assert settings.telemetry_pepper == "test-telemetry-pepper"

    def test_no_fallback_pepper_is_used_by_the_hash(self):
        """The hash must key off the setting, not off a constant in the module."""
        import inspect

        from src.shared.observability import identity

        source = inspect.getsource(identity)
        assert "settings.telemetry_pepper" in source
        assert "hmac" in source, "an unkeyed digest is reversible over a small user set"
