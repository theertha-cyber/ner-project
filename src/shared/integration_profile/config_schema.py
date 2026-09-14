"""Typed, allowlisted profile configuration.

A value is rejected because it fails a *declared shape*, never because something guessed
it looked like a credential. Heuristic credential detection both misses real secrets and
rejects innocent strings; a closed key set with declared types is enforceable, and a
secret-reference grammar makes "this field holds a reference, not a value" checkable.
"""

import re

# The schemes that name a *secret source*. A bare `<scheme>://<path>` grammar is not
# enough: `postgres://user:hunter2@db.internal:5432/app` satisfies it while carrying a live
# credential inline, which is precisely the leak this field exists to prevent. Restricting
# the scheme to a declared set keeps the check schema-based — the value is rejected because
# `postgres` is not a secret source, not because something guessed what it looked like.
SECRET_REFERENCE_SCHEMES = frozenset(
    {"env", "vault", "aws-secretsmanager", "azure-keyvault", "gcp-secretmanager", "file"}
)

# <scheme>://<path>. The path is opaque to us and is stored exactly as supplied, so an
# operator can audit what a tenant was pointed at.
SECRET_REFERENCE_RE = re.compile(
    r"^(?:" + "|".join(re.escape(s) for s in sorted(SECRET_REFERENCE_SCHEMES)) + r")://[^\s]+$"
)


class ProfileValidationError(Exception):
    """A profile write that does not match the declared schema."""


class UnknownConfigurationKey(ProfileValidationError):
    def __init__(self, adapter_kind: str, key: str):
        self.adapter_kind = adapter_kind
        self.key = key
        super().__init__(
            f"'{key}' is not a configuration key declared for adapter kind '{adapter_kind}'"
        )


class WrongConfigurationType(ProfileValidationError):
    def __init__(self, key: str, expected: str, actual: str):
        super().__init__(
            f"configuration key '{key}' must be {expected}, got {actual}"
        )


class InvalidSecretReference(ProfileValidationError):
    def __init__(self, key: str):
        self.key = key
        # The offending value is never echoed: it is precisely the case where the field
        # may be carrying a live credential.
        super().__init__(
            f"secret-reference field '{key}' must match '<scheme>://<path>' with a "
            f"declared secret-source scheme ({', '.join(sorted(SECRET_REFERENCE_SCHEMES))}); "
            f"a literal credential value is not accepted"
        )


# Per adapter kind: the closed set of permitted configuration keys and their types, plus
# the fields declared to hold secret references. Absent from every entry: any key that
# could hold a credential value.
CONFIGURATION_SCHEMA: dict[str, dict] = {
    "platform_upload": {"config": {}, "secrets": frozenset()},
    "platform_minio": {"config": {}, "secrets": frozenset()},
    "platform_postgresql": {"config": {}, "secrets": frozenset()},
    "platform_pgvector": {"config": {}, "secrets": frozenset()},
    "keka": {
        "config": {"base_url": str, "page_size": int},
        "secrets": frozenset({"api_token_ref"}),
    },
    "s3": {
        "config": {"bucket": str, "region": str, "prefix": str},
        "secrets": frozenset({"access_key_ref", "secret_key_ref"}),
    },
    "azure_blob": {
        "config": {"account": str, "container": str, "prefix": str},
        "secrets": frozenset({"connection_string_ref"}),
    },
    "sharepoint": {
        "config": {"site_url": str, "drive": str},
        "secrets": frozenset({"client_secret_ref"}),
    },
    "tenant_s3": {
        "config": {"bucket": str, "region": str, "endpoint": str},
        "secrets": frozenset({"access_key_ref", "secret_key_ref"}),
    },
    "tenant_azure_blob": {
        "config": {"account": str, "container": str},
        "secrets": frozenset({"connection_string_ref"}),
    },
    "tenant_postgresql": {
        "config": {"host": str, "port": int, "database": str, "sslmode": str},
        "secrets": frozenset({"password_ref"}),
    },
    "tenant_pgvector": {
        "config": {"host": str, "port": int, "database": str},
        "secrets": frozenset({"password_ref"}),
    },
    "external_index": {
        "config": {"endpoint": str, "collection": str},
        "secrets": frozenset({"api_key_ref"}),
    },
}

_TYPE_NAMES = {str: "a string", int: "an integer", bool: "a boolean", float: "a number"}


def declared_secret_fields(adapter_kind: str) -> frozenset:
    entry = CONFIGURATION_SCHEMA.get(adapter_kind)
    return entry["secrets"] if entry else frozenset()


def validate_configuration(adapter_kind: str, configuration: dict | None) -> dict:
    """Check one adapter's non-secret configuration against its declared key set."""
    configuration = configuration or {}
    entry = CONFIGURATION_SCHEMA.get(adapter_kind)
    if entry is None:
        raise ProfileValidationError(f"unknown adapter kind '{adapter_kind}'")

    declared = entry["config"]
    for key, value in configuration.items():
        if key not in declared:
            raise UnknownConfigurationKey(adapter_kind, key)
        expected = declared[key]
        # bool is a subclass of int; an adapter that declared an integer did not mean a flag.
        if expected is int and isinstance(value, bool):
            raise WrongConfigurationType(key, _TYPE_NAMES[int], "a boolean")
        if not isinstance(value, expected):
            raise WrongConfigurationType(
                key, _TYPE_NAMES.get(expected, str(expected)), type(value).__name__
            )
    return configuration


def validate_secret_references(adapter_kind: str, references: dict | None) -> dict:
    """Check that every declared secret field holds a reference and nothing else."""
    references = references or {}
    declared = declared_secret_fields(adapter_kind)
    for key, value in references.items():
        if key not in declared:
            raise UnknownConfigurationKey(adapter_kind, key)
        if not isinstance(value, str) or not SECRET_REFERENCE_RE.match(value):
            raise InvalidSecretReference(key)
    return references
