"""Tenant-scoped Azure connection control plane (CAP-2, ADR-011)."""

from src.shared.data_sources.lifecycle import (
    ACTIVATION_EVIDENCE_GOVERNANCE,
    ACTIVATION_EVIDENCE_NETWORK,
    REQUIRED_ACTIVATION_EVIDENCE,
    STATUSES,
    LifecycleRejected,
)
from src.shared.data_sources.providers import (
    PROVIDER_AZURE_BLOB,
    PROVIDER_AZURE_POSTGRESQL,
    PROVIDERS,
    ConnectionValidationError,
    validate_configuration,
    validate_provider,
    validate_secret_references,
)
from src.shared.data_sources.resolver import (
    active_connection,
    executable_providers,
    is_selection_executable,
)
from src.shared.data_sources.service import (
    activate_connection as activate_connection,
    create_connection as create_connection,
    get_connection as get_connection,
    list_connections as list_connections,
    pause_connection as pause_connection,
    replace_connection as replace_connection,
    retire_connection as retire_connection,
    test_connection as test_connection,
    update_connection as update_connection,
)
from src.shared.data_sources.store import (
    CONNECTIONS_TABLE,
    IDEMPOTENCY_TABLE,
    to_connection_dict,
)
from src.shared.data_sources.testing import (
    SecureTestResult,
    register_tester,
    run_secure_test,
)

__all__ = [
    "ACTIVATION_EVIDENCE_GOVERNANCE",
    "ACTIVATION_EVIDENCE_NETWORK",
    "CONNECTIONS_TABLE",
    "IDEMPOTENCY_TABLE",
    "PROVIDER_AZURE_BLOB",
    "PROVIDER_AZURE_POSTGRESQL",
    "PROVIDERS",
    "REQUIRED_ACTIVATION_EVIDENCE",
    "STATUSES",
    "ConnectionValidationError",
    "LifecycleRejected",
    "SecureTestResult",
    "activate_connection",
    "active_connection",
    "create_connection",
    "executable_providers",
    "get_connection",
    "is_selection_executable",
    "list_connections",
    "pause_connection",
    "register_tester",
    "replace_connection",
    "retire_connection",
    "run_secure_test",
    "test_connection",
    "to_connection_dict",
    "update_connection",
    "validate_configuration",
    "validate_provider",
    "validate_secret_references",
]
