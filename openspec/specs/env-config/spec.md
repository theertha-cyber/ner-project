# Environment Configuration

## Purpose

Defines how the platform loads, documents, and protects environment-specific configuration using `pydantic-settings` and `.env` files.

---

## Requirements

### Requirement: Environment Configuration Loading

The system SHALL load all configurable settings from a `.env` file at the project root using `pydantic-settings` with the `NER_` prefix. Secret-class settings (`jwt_secret`, `minio_access_key`, `minio_secret_key`) SHALL have no hardcoded default value; the application SHALL fail at startup with a `ValidationError` if any of these fields are absent from the environment. Non-secret settings MAY retain hardcoded defaults for local-dev convenience.

#### Scenario: Settings load from .env file

- **GIVEN** a `.env` file exists at the project root with `NER_DATABASE_URL=postgresql+asyncpg://custom:url@host:5432/db`
- **WHEN** `settings.database_url` is accessed
- **THEN** the value SHALL be `"postgresql+asyncpg://custom:url@host:5432/db"`

#### Scenario: Settings fall back to defaults when .env missing

- **GIVEN** no `.env` file exists at the project root
- **WHEN** `settings.database_url` is accessed
- **THEN** the value SHALL be the hardcoded default `"postgresql+asyncpg://ner:ner@localhost:5432/ner"`

#### Scenario: Settings fail at startup when NER_JWT_SECRET is absent

- **GIVEN** no `NER_JWT_SECRET` is set in the environment and no `.env` file provides it
- **WHEN** `Settings()` is instantiated
- **THEN** a `pydantic.ValidationError` SHALL be raised

#### Scenario: Settings fail at startup when NER_MINIO_ACCESS_KEY is absent

- **GIVEN** no `NER_MINIO_ACCESS_KEY` is set in the environment and no `.env` file provides it
- **WHEN** `Settings()` is instantiated
- **THEN** a `pydantic.ValidationError` SHALL be raised

#### Scenario: Settings fail at startup when NER_MINIO_SECRET_KEY is absent

- **GIVEN** no `NER_MINIO_SECRET_KEY` is set in the environment and no `.env` file provides it
- **WHEN** `Settings()` is instantiated
- **THEN** a `pydantic.ValidationError` SHALL be raised

### Requirement: Environment Variable Documentation

The system SHALL provide a `.env.example` file at the project root that documents every configurable `NER_*` environment variable and every docker-compose variable consumed from the `.env` file. Secret-class fields SHALL be marked as `# REQUIRED` with inline generation instructions. This file SHALL be tracked in version control. The `.env.example` SHALL additionally document all inter-service URL variables introduced by the containerised stack (`NER_DOCUMENT_SERVICE_URL`, `NER_MODEL_SERVING_URL`), noting that these default to `localhost` addresses for bare-metal runs and should be overridden to Docker service names when running inside the compose network.

#### Scenario: .env.example documents all settings

- **GIVEN** the `Settings` class defines fields `database_url`, `redis_url`, `jwt_secret`, `jwt_algorithm`, `access_token_ttl_minutes`, `refresh_token_ttl_days`, `minio_endpoint`, `minio_access_key`, `minio_secret_key`, `minio_bucket`
- **WHEN** `.env.example` is read
- **THEN** every field name SHALL appear as `NER_<UPPER_CASE_FIELD_NAME>` with a descriptive comment and example value

#### Scenario: .env.example marks secret fields as required

- **GIVEN** the `.env.example` file is read
- **WHEN** the entries for `NER_JWT_SECRET`, `NER_MINIO_ACCESS_KEY`, `NER_MINIO_SECRET_KEY`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` are examined
- **THEN** each SHALL have a `# REQUIRED` comment and a generation hint (e.g. `openssl rand -hex 32`)

#### Scenario: .env.example includes docker-compose variables

- **GIVEN** the `.env.example` file is read
- **WHEN** it is searched for `MINIO_ROOT_USER` and `AWS_ACCESS_KEY_ID`
- **THEN** both SHALL appear as documented entries

#### Scenario: .env.example documents inter-service URL variables

- **GIVEN** the `.env.example` file is read
- **WHEN** it is searched for `NER_DOCUMENT_SERVICE_URL` and `NER_MODEL_SERVING_URL`
- **THEN** both SHALL appear with comments explaining that docker-compose overrides them to container service names

### Requirement: docker-compose Uses Environment Interpolation for Secrets

The system's `docker-compose.yml` SHALL reference all secret values via `${VAR}` interpolation rather than inline literal strings, so that secrets are resolved from the developer's `.env` file at `docker compose up` time.

#### Scenario: docker-compose resolves NER_JWT_SECRET from .env

- **GIVEN** the `.env` file contains `NER_JWT_SECRET=my-local-secret`
- **WHEN** `docker compose config` is run
- **THEN** the resolved `NER_JWT_SECRET` value in every service that consumes it SHALL be `my-local-secret`, not a hardcoded literal

#### Scenario: docker-compose.yml contains no hardcoded secret literals

- **GIVEN** `docker-compose.yml` is read
- **WHEN** it is searched for the strings `dev-secret-do-not-use`, `minioadmin`
- **THEN** no matches SHALL be found

### Requirement: .env Excluded from Version Control

The system SHALL exclude `.env` from version control via `.gitignore`. Only `.env.example` SHALL be tracked.

#### Scenario: .env is gitignored

- **GIVEN** a fresh clone of the repository
- **WHEN** `git check-ignore .env` is run
- **THEN** the exit code SHALL be 0 (file is ignored)
