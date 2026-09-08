# Secret Hygiene

## Purpose

Defines the rules and practices that prevent secret values from being hardcoded, committed, or leaked in the codebase, ensuring all credentials are loaded exclusively from environment sources.

---

## Requirements

### Requirement: No Hardcoded Secrets in Codebase

The system SHALL prohibit hardcoded secret values (API keys, signing secrets, passwords, access tokens) anywhere in committed source files. All such values SHALL be loaded exclusively from environment variables or a `.env` file that is excluded from version control.

#### Scenario: AGENTS.md documents the no-hardcoded-secrets invariant

- **GIVEN** the `AGENTS.md` file at the project root is read
- **WHEN** it is searched for guidance on secrets
- **THEN** it SHALL contain an explicit statement that secrets MUST NOT be hardcoded in source files, configuration files, or committed `.env` files

#### Scenario: Source code contains no plaintext secret defaults

- **GIVEN** `src/shared/config.py` is read
- **WHEN** the `Settings` class fields for `jwt_secret`, `minio_access_key`, and `minio_secret_key` are examined
- **THEN** none of them SHALL have a default string value

### Requirement: Test Fixtures Use Isolated Env Injection

Test files that require secret values SHALL inject them via `os.environ.setdefault()` before module imports so that they do not override real environment values when present. Test fixture secrets SHALL be clearly labelled as non-production values.

#### Scenario: Test secrets use setdefault and cannot override real env

- **GIVEN** `NER_JWT_SECRET` is already set in the process environment
- **WHEN** a test file calls `os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")`
- **THEN** the existing value SHALL be preserved and the test fixture value SHALL NOT replace it

### Requirement: Per-Tenant Integration Credentials Are References Only

The system SHALL store per-tenant integration credentials as typed references to an external secret source, never as values. A secret reference SHALL be a declared field in the profile schema whose value matches a `<scheme>://<path>` grammar; a credential value SHALL be rejected because it fails that declared shape, not because it was heuristically recognised. No credential value, API token, connection string, or pre-signed URL SHALL be written to any database row, any committed configuration file, or any source file. A credential SHALL be resolved from its reference at run time and SHALL exist only in process memory for the duration of the operation that needs it.

#### Scenario: No credential value is persisted

- **GIVEN** a tenant integration profile configured with a secret reference
- **WHEN** every column of the stored row is inspected
- **THEN** no column SHALL contain a credential value
- **AND** the reference SHALL be stored in plain form so that it is auditable

#### Scenario: A value in a secret field is rejected by schema, not by heuristic

- **GIVEN** a profile write whose declared secret-reference field carries a literal credential
- **WHEN** the write is validated
- **THEN** it SHALL be rejected for failing the reference grammar
- **AND** the rejection SHALL NOT depend on inspecting whether the value resembles a secret

#### Scenario: Resolved credentials do not outlive the operation

- **GIVEN** an operation that resolves a tenant credential
- **WHEN** the operation completes
- **THEN** the resolved value SHALL NOT have been written to any database row, cache, or file

#### Scenario: Credential resolution is not reachable from adapter code

- **GIVEN** a source or content-store adapter
- **WHEN** its dependencies are inspected
- **THEN** it SHALL receive already-resolved values
- **AND** it SHALL NOT receive a secret reference or a resolver

### Requirement: Runtime Credential Resolution Failure Is Explicit

The system SHALL surface an unresolvable per-tenant credential reference as an explicit configuration failure that moves the owning integration profile to its `error` status with an operator-visible reason. This is an acknowledged deviation from the startup fail-fast rule for secret-class settings: per-tenant references are created at run time and cannot be enumerated at process start, so the process SHALL NOT fail to boot because one tenant's reference is unresolvable.

#### Scenario: An unresolvable reference errors the profile, not the process

- **GIVEN** a running service and a tenant profile whose secret reference cannot be resolved
- **WHEN** resolution is attempted
- **THEN** the profile SHALL move to `error` with a recorded reason
- **AND** the process SHALL continue serving other tenants

#### Scenario: The failure reason carries no credential material

- **GIVEN** a resolution failure for a tenant credential
- **WHEN** the recorded reason and any emitted log record are inspected
- **THEN** they SHALL name the reference and the failure class
- **AND** they SHALL NOT contain any credential value or raw provider payload

#### Scenario: Process-level secret-class settings still fail fast

- **GIVEN** the application configuration with `NER_JWT_SECRET` absent from the environment
- **WHEN** the application starts
- **THEN** startup SHALL fail
- **AND** the per-tenant deviation SHALL NOT weaken this behaviour
