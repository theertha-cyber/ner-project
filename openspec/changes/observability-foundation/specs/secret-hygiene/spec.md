## MODIFIED Requirements

### Requirement: No Hardcoded Secrets in Codebase

The system SHALL prohibit hardcoded secret values (API keys, signing secrets, passwords, access tokens, hashing peppers) anywhere in committed source files. All such values SHALL be loaded exclusively from environment variables or a `.env` file that is excluded from version control.

#### Scenario: AGENTS.md documents the no-hardcoded-secrets invariant

- **GIVEN** the `AGENTS.md` file at the project root is read
- **WHEN** it is searched for guidance on secrets
- **THEN** it SHALL contain an explicit statement that secrets MUST NOT be hardcoded in source files, configuration files, or committed `.env` files

#### Scenario: Source code contains no plaintext secret defaults

- **GIVEN** `src/shared/config.py` is read
- **WHEN** the `Settings` class fields for `jwt_secret`, `minio_access_key`, `minio_secret_key`, and the telemetry user-hash pepper are examined
- **THEN** none of them SHALL have a default string value

#### Scenario: Startup fails when the telemetry pepper is absent

- **GIVEN** the telemetry user-hash pepper is not present in the environment
- **WHEN** a service starts
- **THEN** startup SHALL fail with an error identifying the missing setting
- **AND** the process SHALL NOT fall back to an empty or built-in pepper value
