"""Contract-governed external PostgreSQL query path (CAP-4, ADR-013)."""

from src.shared.external_postgres.capability import (
    is_external_request_executable,
    resolve_external_capability,
)
from src.shared.external_postgres.connector import (
    ROW_CAP,
    STATEMENT_TIMEOUT_MS,
    clamp_limit,
    execute_external_query,
    ExternalExecutionFailed,
)
from src.shared.external_postgres.contract import (
    accepted_contract,
    canonical_fingerprint,
    ContractRejected,
    list_versions,
    publish_version,
    store_draft,
    validate_contract_document,
)
from src.shared.external_postgres.drift import (
    DriftBlocked,
    ExternalDatabase,
    FixtureExternalDatabase,
    check as drift_check,
)
from src.shared.external_postgres.index import (
    clear_connection_entries,
    fetch_entries,
    replace_version_entries,
)
from src.shared.external_postgres.validator import (
    ValidationRejected,
    validate_statement,
)

__all__ = [
    "ROW_CAP",
    "STATEMENT_TIMEOUT_MS",
    "ContractRejected",
    "DriftBlocked",
    "ExternalDatabase",
    "ExternalExecutionFailed",
    "FixtureExternalDatabase",
    "accepted_contract",
    "canonical_fingerprint",
    "clamp_limit",
    "clear_connection_entries",
    "drift_check",
    "execute_external_query",
    "fetch_entries",
    "is_external_request_executable",
    "list_versions",
    "publish_version",
    "replace_version_entries",
    "resolve_external_capability",
    "store_draft",
    "validate_contract_document",
    "validate_statement",
    "ValidationRejected",
]
