"""Per-tenant integration credentials are references only — verification.md rows 93-99.

`AGENTS.md` invariant 3 says no secret may be hardcoded in source, configuration, or a
committed `.env`, and that secret-class settings carry no defaults. Per-tenant references
are created at run time and cannot be enumerated at process start, so this change carries
one acknowledged deviation — an unresolvable reference errors that tenant's profile rather
than failing the boot. Row 99 is what stops that deviation from widening: the existing
process-level fail-fast still applies, unmodified.
"""

import inspect
import os
import pathlib

import pytest

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from src.shared.config import Settings
from src.shared.integration_profile import config_schema, secrets
from src.shared.integration_profile.config_schema import (
    CONFIGURATION_SCHEMA,
    SECRET_REFERENCE_RE,
    InvalidSecretReference,
    validate_secret_references,
)
from src.shared.integration_profile.secrets import (
    SecretResolutionError,
    TenantSecretContext,
    resolve_for_tenant,
    sanitised_reason,
)
from src.shared.integration_profile.store import IntegrationProfile

pytestmark = [pytest.mark.verification]

SRC_ROOT = pathlib.Path(__file__).resolve().parents[2] / "src"

CREDENTIAL_LITERALS = [
    "sk-live-51H8xQwErTyUiOpAsDfGhJkL",
    "AKIAIOSFODNN7EXAMPLE",
    "postgres://user:hunter2@db.internal:5432/app",
    "hunter2",
    "-----BEGIN PRIVATE KEY-----",
]


def profile_with(references: dict) -> IntegrationProfile:
    return IntegrationProfile(tenant_id="t-1", secret_references=references)


# --- Row 93: no credential value is persisted ------------------------------------------


def test_row_93_the_profile_schema_has_no_column_for_a_credential_value():
    migration = (
        SRC_ROOT.parent / "alembic" / "versions" / "039_tenant_integration_profiles.py"
    ).read_text(encoding="utf-8")

    # `secret_references` is the only secret-adjacent column, and it is named for what it
    # holds. There is no `password`, `token`, `api_key`, or `connection_string` column for
    # a value to land in.
    for forbidden in ("password ", "api_key ", "api_token ", "connection_string ", "secret_value"):
        assert forbidden not in migration, f"the profile table declares {forbidden.strip()}"
    assert "secret_references" in migration


def test_row_93_a_reference_is_stored_in_plain_form_so_it_stays_auditable():
    reference = "vault://tenants/acme/keka/api-token"
    validated = validate_secret_references("keka", {"api_token_ref": reference})
    assert validated["api_token_ref"] == reference, "the reference was transformed"


# --- Row 94: rejection is by declared schema, not by heuristic -------------------------


@pytest.mark.parametrize("literal", CREDENTIAL_LITERALS)
def test_row_94_a_literal_in_a_secret_field_is_rejected_by_grammar(literal):
    with pytest.raises(InvalidSecretReference) as excinfo:
        validate_secret_references("keka", {"api_token_ref": literal})
    # The rejection cites the grammar, and never echoes the value it refused.
    assert "<scheme>://<path>" in str(excinfo.value)
    assert literal not in str(excinfo.value)


def test_row_94_rejection_does_not_depend_on_the_value_resembling_a_secret():
    """A connection-string-shaped value in a *reference* field is accepted when it matches
    the grammar, and an innocent-looking one is rejected when it does not. Neither outcome
    turns on what the value looks like."""
    assert validate_secret_references(
        "tenant_postgresql", {"password_ref": "vault://a/b"}
    )
    with pytest.raises(InvalidSecretReference):
        validate_secret_references("tenant_postgresql", {"password_ref": "correct-horse"})

    # And the validator contains no value-inspection heuristic. Code lines only: the
    # module's own prose explains why heuristics are refused, which is not an offence.
    code = [
        line
        for line in inspect.getsource(config_schema).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    code = chr(10).join(code)
    for heuristic in ("looks_like", "entropy", "is_secret", "SECRET_PATTERNS", "resembles"):
        assert heuristic not in code, f"validation uses a heuristic: {heuristic}"


def test_the_reference_grammar_is_scheme_then_path():
    assert SECRET_REFERENCE_RE.match("env://NER_SOMETHING")
    assert SECRET_REFERENCE_RE.match("vault://tenants/acme/keka/api-token")
    assert SECRET_REFERENCE_RE.match("aws-secretsmanager://prod/keka")
    for invalid in (
        "plain-value",
        "://no-scheme",
        "vault:/single-slash",
        "vault://",
        "://",
        # A connection string satisfies a bare <scheme>://<path> grammar while carrying a
        # live credential inline. The scheme allowlist is what refuses it.
        "postgres://user:hunter2@db.internal:5432/app",
        "https://example.com/token",
    ):
        assert not SECRET_REFERENCE_RE.match(invalid), invalid


# --- Row 95: resolved values do not outlive the operation ------------------------------


def test_row_95_a_resolved_value_lives_only_in_the_returned_context(monkeypatch):
    monkeypatch.setenv("NER_HYGIENE_SECRET", "the-resolved-credential")
    profile = profile_with({"keka": {"api_token_ref": "env://NER_HYGIENE_SECRET"}})

    context = resolve_for_tenant(profile, "keka")
    assert context.values["api_token_ref"] == "the-resolved-credential"

    # Nothing was written back onto the profile, and the module holds no cache.
    assert profile.secret_references == {
        "keka": {"api_token_ref": "env://NER_HYGIENE_SECRET"}
    }
    module_state = {
        name: value
        for name, value in vars(secrets).items()
        if not name.startswith("__") and isinstance(value, (dict, list, set))
    }
    for name, value in module_state.items():
        assert "the-resolved-credential" not in str(value), f"{name} retained the value"


def test_row_95_the_context_is_immutable_and_tenant_bound():
    context = TenantSecretContext(tenant_id="t-1", values={"api_token_ref": "v"})
    assert context.tenant_id == "t-1"
    with pytest.raises(Exception):
        context.tenant_id = "t-2"  # frozen dataclass


# --- Row 96: adapters hold no resolver -------------------------------------------------


def test_row_96_adapters_receive_values_and_never_a_reference_or_a_resolver():
    from src.document_service.content_store import minio_store
    from src.document_service.ingestion import service as ingestion_service

    for module in (minio_store, ingestion_service):
        source = inspect.getsource(module)
        for forbidden in (
            "resolve_for_tenant",
            "resolve_all_for_tenant",
            "SecretResolutionError",
            "secret_references",
            "EnvironmentSecretResolver",
        ):
            assert forbidden not in source, (
                f"{module.__name__} can reach {forbidden}: an adapter must receive "
                f"already-resolved values"
            )

    # The context handed to an adapter carries values, a tenant, and nothing callable.
    assert set(TenantSecretContext.__dataclass_fields__) == {"tenant_id", "values"}


def test_no_adapter_configuration_schema_declares_a_value_field():
    """Every secret field in every adapter's schema is a `_ref` field."""
    for adapter_kind, entry in CONFIGURATION_SCHEMA.items():
        for field in entry["secrets"]:
            assert field.endswith("_ref"), f"{adapter_kind}.{field} is not a reference field"
        # And no non-secret key is named for a credential.
        for key in entry["config"]:
            assert not any(
                token in key for token in ("password", "secret", "token", "api_key")
            ), f"{adapter_kind}.{key} names a credential in a non-secret field"


# --- Rows 97 and 98: the profile errors, the process does not ---------------------------


def test_row_97_an_unresolvable_reference_raises_a_typed_error_not_a_process_failure(
    monkeypatch,
):
    monkeypatch.delenv("NER_ABSENT_HYGIENE_SECRET", raising=False)
    profile = profile_with({"keka": {"api_token_ref": "env://NER_ABSENT_HYGIENE_SECRET"}})

    with pytest.raises(SecretResolutionError) as excinfo:
        resolve_for_tenant(profile, "keka")

    assert excinfo.value.failure_class == "not_found"
    # It is an ordinary exception a caller handles, not SystemExit — the process keeps
    # serving every other tenant.
    assert not isinstance(excinfo.value, SystemExit)


def test_row_98_the_failure_reason_names_the_reference_and_the_class_only(monkeypatch):
    monkeypatch.setenv("NER_HYGIENE_SECRET", "must-not-appear-anywhere")
    reference = "env://NER_HYGIENE_SECRET"

    error = SecretResolutionError(reference, "unauthorised")
    reason = sanitised_reason(error)

    assert reference in reason
    assert "unauthorised" in reason
    assert "must-not-appear-anywhere" not in reason
    # No raw provider payload either.
    assert "{" not in reason and "Traceback" not in reason


def test_a_declared_scheme_with_no_registered_resolver_is_a_failure_class():
    """`vault` is a declared secret source but this change ships only the `env` resolver.
    A profile pointed at it fails with a named class, not a crash."""
    profile = profile_with({"keka": {"api_token_ref": "vault://tenants/acme/token"}})
    with pytest.raises(SecretResolutionError) as excinfo:
        resolve_for_tenant(profile, "keka")
    assert excinfo.value.failure_class == "unknown_scheme"


def test_a_scheme_outside_the_declared_set_never_reaches_resolution():
    """It is refused at the grammar, before anything tries to resolve it."""
    profile = profile_with({"keka": {"api_token_ref": "madeup://a/b"}})
    with pytest.raises(SecretResolutionError) as excinfo:
        resolve_for_tenant(profile, "keka")
    assert excinfo.value.failure_class == "malformed_reference"


# --- Row 99: process-level fail-fast is unweakened --------------------------------------


def test_row_99_process_level_secret_settings_still_have_no_default():
    """The per-tenant deviation must not become a general licence."""
    for field in ("jwt_secret", "minio_access_key", "minio_secret_key", "telemetry_pepper"):
        assert Settings.model_fields[field].is_required(), (
            f"`{field}` gained a default — the per-tenant runtime-resolution deviation "
            f"does not extend to process-level secret-class settings"
        )


def test_row_99_the_existing_startup_fail_fast_test_is_unmodified():
    """The `NER_JWT_SECRET` fail-fast case lives in its own file and must still assert
    what it always did."""
    existing = (
        pathlib.Path(__file__).parent / "test_config_secret_hygiene.py"
    ).read_text(encoding="utf-8")
    assert "SECRET_FIELDS" in existing
    assert '"jwt_secret"' in existing
    assert "is_required()" in existing
