"""Finite lifecycle, test, and activation evidence classes (CAP-2).

Every value the control plane records or returns is drawn from these sets. Outcome
and reason codes are the whole vocabulary: no endpoint, provider diagnostic,
credential, or tenant content is ever persisted as evidence or surfaced in a
response, because there is no field for it and no code outside these sets.
"""

# --- Lifecycle statuses (shared with the profile status model) ------------------------

STATUS_DRAFT = "draft"
STATUS_VALIDATED = "validated"
STATUS_ACTIVE = "active"
STATUS_PAUSED = "paused"
STATUS_ERROR = "error"
STATUS_RETIRED = "retired"

STATUSES = (
    STATUS_DRAFT,
    STATUS_VALIDATED,
    STATUS_ACTIVE,
    STATUS_PAUSED,
    STATUS_ERROR,
    STATUS_RETIRED,
)

# Statuses a PATCH may start from. An accepted update clears test/activation
# evidence and returns the connection to `draft`.
UPDATABLE_STATUSES = frozenset({STATUS_DRAFT, STATUS_PAUSED, STATUS_ERROR})

# Statuses a connection test may start from.
TESTABLE_STATUSES = frozenset({STATUS_DRAFT, STATUS_PAUSED, STATUS_ERROR})

# Statuses a retirement may start from. An active connection must be paused first;
# `retired` is terminal.
RETIRABLE_STATUSES = frozenset(
    {STATUS_DRAFT, STATUS_VALIDATED, STATUS_PAUSED, STATUS_ERROR}
)

# --- Connection test evidence ----------------------------------------------------------

TEST_OUTCOME_PASSED = "passed"
TEST_OUTCOME_FAILED = "failed"
TEST_OUTCOME_NOT_RUN = "not_run"

TEST_OUTCOMES = frozenset({TEST_OUTCOME_PASSED, TEST_OUTCOME_FAILED, TEST_OUTCOME_NOT_RUN})

TEST_REASON_NONE = "none"
TEST_REASON_VALIDATION_FAILED = "validation_failed"
TEST_REASON_SECRET_UNAVAILABLE = "secret_unavailable"
TEST_REASON_CONNECTION_FAILED = "connection_failed"
TEST_REASON_TLS_VALIDATION_FAILED = "tls_validation_failed"
TEST_REASON_AUTHORIZATION_FAILED = "authorization_failed"
TEST_REASON_PREREQUISITE_MISSING = "prerequisite_missing"

# ADR-017 `azure_postgresql_data_plane` residency-specific test checks (Design D3, D11).
TEST_REASON_SERVER_VERSION_UNSUPPORTED = "server_version_unsupported"
TEST_REASON_VECTOR_EXTENSION_UNAVAILABLE = "vector_extension_unavailable"
TEST_REASON_INSUFFICIENT_PRIVILEGE = "insufficient_privilege"
TEST_REASON_QUERY_ROLE_UNAVAILABLE = "query_role_unavailable"
TEST_REASON_TARGET_SCHEMA_NOT_EMPTY = "target_schema_not_empty"
TEST_REASON_STORE_IDENTITY_MISMATCH = "store_identity_mismatch"

TEST_REASONS = frozenset({
    TEST_REASON_NONE,
    TEST_REASON_VALIDATION_FAILED,
    TEST_REASON_SECRET_UNAVAILABLE,
    TEST_REASON_CONNECTION_FAILED,
    TEST_REASON_TLS_VALIDATION_FAILED,
    TEST_REASON_AUTHORIZATION_FAILED,
    TEST_REASON_PREREQUISITE_MISSING,
    TEST_REASON_SERVER_VERSION_UNSUPPORTED,
    TEST_REASON_VECTOR_EXTENSION_UNAVAILABLE,
    TEST_REASON_INSUFFICIENT_PRIVILEGE,
    TEST_REASON_QUERY_ROLE_UNAVAILABLE,
    TEST_REASON_TARGET_SCHEMA_NOT_EMPTY,
    TEST_REASON_STORE_IDENTITY_MISMATCH,
})

# --- Activation evidence -----------------------------------------------------------------

ACTIVATION_OUTCOME_ACTIVE = "active"
ACTIVATION_OUTCOME_INACTIVE = "inactive"
ACTIVATION_OUTCOME_BLOCKED = "blocked"

ACTIVATION_OUTCOMES = frozenset({
    ACTIVATION_OUTCOME_ACTIVE,
    ACTIVATION_OUTCOME_INACTIVE,
    ACTIVATION_OUTCOME_BLOCKED,
})

ACTIVATION_REASON_NONE = "none"
ACTIVATION_REASON_TEST_REQUIRED = "test_required"
ACTIVATION_REASON_TEST_FAILED = "test_failed"
ACTIVATION_REASON_PREREQUISITE_MISSING = "prerequisite_missing"
ACTIVATION_REASON_ACTIVE_PROVIDER_EXISTS = "active_provider_exists"
ACTIVATION_REASON_SECRET_UNAVAILABLE = "secret_unavailable"
# ADR-017: an azure_postgresql_data_plane connection cannot activate while the
# tenant's integration profile still records platform_blob retention.
ACTIVATION_REASON_RETENTION_MODE_NOT_PERMITTED = "retention_mode_not_permitted"

ACTIVATION_REASONS = frozenset({
    ACTIVATION_REASON_NONE,
    ACTIVATION_REASON_TEST_REQUIRED,
    ACTIVATION_REASON_TEST_FAILED,
    ACTIVATION_REASON_PREREQUISITE_MISSING,
    ACTIVATION_REASON_ACTIVE_PROVIDER_EXISTS,
    ACTIVATION_REASON_SECRET_UNAVAILABLE,
    ACTIVATION_REASON_RETENTION_MODE_NOT_PERMITTED,
})

# The exact attestation set an activation request must carry, once each and no
# others. `network_approved` is validated private connectivity or TLS-public with
# customer-approved platform egress IP allowlisting. `governance_approved` is
# approval of an applicable legal/retention/residency obligation, or a recorded
# determination that none applies.
ACTIVATION_EVIDENCE_NETWORK = "network_approved"
ACTIVATION_EVIDENCE_GOVERNANCE = "governance_approved"

REQUIRED_ACTIVATION_EVIDENCE = frozenset({
    ACTIVATION_EVIDENCE_NETWORK,
    ACTIVATION_EVIDENCE_GOVERNANCE,
})

# --- Sync evidence (Blob only; owned by CAP-3, declared here for shape stability) --------

SYNC_OUTCOME_NEVER_RUN = "never_run"
SYNC_OUTCOME_SUCCEEDED = "succeeded"
SYNC_OUTCOME_FAILED = "failed"
SYNC_OUTCOME_BLOCKED = "blocked"
SYNC_OUTCOME_LEASE_HELD = "lease_held"

SYNC_OUTCOMES = frozenset({
    SYNC_OUTCOME_NEVER_RUN,
    SYNC_OUTCOME_SUCCEEDED,
    SYNC_OUTCOME_FAILED,
    SYNC_OUTCOME_BLOCKED,
    SYNC_OUTCOME_LEASE_HELD,
})

# Blob sync cadence, minutes. Enabled only while the connection is active.
SYNC_CADENCE_MINUTES = 15


class LifecycleRejected(Exception):
    """A lifecycle action the connection's state, evidence, or limits forbid.

    Carries the finite API error `code` so the route layer maps it without
    interpreting messages.
    """

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)
