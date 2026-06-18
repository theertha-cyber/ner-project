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
