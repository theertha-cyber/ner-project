"""The finite approved provider catalog for the tenant control plane (CAP-2).

Only Azure Blob Storage and Azure Database for PostgreSQL are administrable by a
tenant administrator. Every other provider string is rejected here, before any row
is written — the catalog is closed at the boundary, not filtered later.

Configuration follows the existing typed-schema discipline from
`src.shared.integration_profile.config_schema`: a closed key set with declared
types, secret *references* matching the declared `<scheme>://<path>` grammar, and
the offending value never echoed back. What this module adds on top is what the
CAP-2 contract requires: non-empty required fields, an integer port range, and
`sslmode` fixed to `verify-full`.
"""

from src.shared.integration_profile.config_schema import SECRET_REFERENCE_RE

PROVIDER_AZURE_BLOB = "azure_blob"
PROVIDER_AZURE_POSTGRESQL = "azure_postgresql"

PROVIDERS = frozenset({PROVIDER_AZURE_BLOB, PROVIDER_AZURE_POSTGRESQL})

# Map each approved provider to the existing secret-reference schema kind it reuses
# for resolution. Configuration validation below is provider-specific and closed; the
# reference grammar is shared so a future Vault registration applies to both seams.
PROVIDER_SECRET_KIND = {
    PROVIDER_AZURE_BLOB: "tenant_azure_blob",
    PROVIDER_AZURE_POSTGRESQL: "tenant_postgresql",
}

# Required secret-reference fields per provider. The value must be a reference, never
# a literal: validated by grammar, exactly like the profile seam.
PROVIDER_SECRET_FIELDS = {
    PROVIDER_AZURE_BLOB: frozenset({"connection_string_ref"}),
    PROVIDER_AZURE_POSTGRESQL: frozenset({"password_ref"}),
}

# Closed configuration keys per provider. `True` marks a required field.
_BLOB_CONFIG_KEYS = {"account": True, "container": True, "prefix": False}
_POSTGRES_CONFIG_KEYS = {
    "host": True,
    "port": True,
    "database": True,
    "username": True,
    "sslmode": True,
}

PROVIDER_CONFIG_KEYS = {
    PROVIDER_AZURE_BLOB: _BLOB_CONFIG_KEYS,
    PROVIDER_AZURE_POSTGRESQL: _POSTGRES_CONFIG_KEYS,
}


class ConnectionValidationError(Exception):
    """A connection write that does not match the closed provider schema.

    Carries a finite machine-readable `code` (always `INVALID_REQUEST` at the API
    boundary) and a safe message naming the field, never the value.
    """

    def __init__(self, field: str | None, message: str):
        self.field = field
        self.code = "INVALID_REQUEST"
        super().__init__(message)


def _require_non_empty_string(provider: str, field: str, value) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ConnectionValidationError(
            field,
            f"'{field}' is required for provider '{provider}' and must be a "
            f"non-empty string",
        )


def _validate_blob(configuration: dict) -> None:
    for key in configuration:
        if key not in _BLOB_CONFIG_KEYS:
            raise ConnectionValidationError(
                key, f"'{key}' is not a configuration key declared for 'azure_blob'"
            )
    for field in ("account", "container"):
        if field not in configuration:
            raise ConnectionValidationError(
                field, f"'{field}' is required for provider 'azure_blob'"
            )
        _require_non_empty_string("azure_blob", field, configuration[field])
    if "prefix" in configuration and not isinstance(configuration["prefix"], str):
        raise ConnectionValidationError(
            "prefix", "'prefix' for provider 'azure_blob' must be a string"
        )


def _validate_postgres(configuration: dict) -> None:
    for key in configuration:
        if key not in _POSTGRES_CONFIG_KEYS:
            raise ConnectionValidationError(
                key,
                f"'{key}' is not a configuration key declared for 'azure_postgresql'",
            )
    for field in ("host", "database", "username"):
        if field not in configuration:
            raise ConnectionValidationError(
                field, f"'{field}' is required for provider 'azure_postgresql'"
            )
        _require_non_empty_string("azure_postgresql", field, configuration[field])
    if "port" not in configuration:
        raise ConnectionValidationError(
            "port", "'port' is required for provider 'azure_postgresql'"
        )
    port = configuration["port"]
    # bool is a subclass of int; a flag is not a port.
    if isinstance(port, bool) or not isinstance(port, int):
        raise ConnectionValidationError(
            "port", "'port' for provider 'azure_postgresql' must be an integer"
        )
    if not 1 <= port <= 65535:
        raise ConnectionValidationError(
            "port", "'port' for provider 'azure_postgresql' must be 1-65535"
        )
    if "sslmode" not in configuration:
        raise ConnectionValidationError(
            "sslmode", "'sslmode' is required for provider 'azure_postgresql'"
        )
    if configuration["sslmode"] != "verify-full":
        raise ConnectionValidationError(
            "sslmode",
            "'sslmode' for provider 'azure_postgresql' must be exactly 'verify-full'",
        )


def validate_provider(provider: str) -> str:
    """Reject anything outside the two approved providers."""
    if provider not in PROVIDERS:
        raise ConnectionValidationError(
            "provider",
            f"'{provider}' is not an approved connection provider; "
            f"approved providers are {', '.join(sorted(PROVIDERS))}",
        )
    return provider


def validate_configuration(provider: str, configuration: dict | None) -> dict:
    """Check one provider's non-secret configuration against its closed key set."""
    validate_provider(provider)
    configuration = dict(configuration or {})
    if provider == PROVIDER_AZURE_BLOB:
        _validate_blob(configuration)
    else:
        _validate_postgres(configuration)
    return configuration


def validate_secret_references(provider: str, references: dict | None) -> dict:
    """Check that required reference fields hold references and nothing else.

    Unknown keys are rejected, required fields must be present and non-empty, and
    every value must match the declared secret-source grammar. A literal credential
    fails the grammar, which is what makes "references only" enforceable rather
    than advisory. The offending value is never echoed.
    """
    validate_provider(provider)
    references = dict(references or {})
    declared = PROVIDER_SECRET_FIELDS[provider]
    for key in references:
        if key not in declared:
            raise ConnectionValidationError(
                key,
                f"'{key}' is not a secret-reference field declared for '{provider}'",
            )
    for field in sorted(declared):
        value = references.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ConnectionValidationError(
                field, f"'{field}' is required for provider '{provider}'"
            )
        if not SECRET_REFERENCE_RE.match(value):
            raise ConnectionValidationError(
                field,
                f"'{field}' must match '<scheme>://<path>' with a declared "
                f"secret-source scheme; a literal credential value is not accepted",
            )
    return references
