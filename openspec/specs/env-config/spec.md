# Environment Configuration

## Purpose

Defines how the platform loads, documents, and protects environment-specific configuration using `pydantic-settings` and `.env` files.

---

## Requirements

### Requirement: Environment Configuration Loading

The system SHALL load all configurable settings from a `.env` file at the project root using `pydantic-settings` with the `NER_` prefix. If the `.env` file is missing, the system SHALL fall back to hardcoded defaults defined in `Settings`. Every `Settings` field SHALL have a corresponding documented entry in `.env.example`.

#### Scenario: Settings load from .env file

- **GIVEN** a `.env` file exists at the project root with `NER_DATABASE_URL=postgresql+asyncpg://custom:url@host:5432/db`
- **WHEN** `settings.database_url` is accessed
- **THEN** the value SHALL be `"postgresql+asyncpg://custom:url@host:5432/db"`

#### Scenario: Settings fall back to defaults when .env missing

- **GIVEN** no `.env` file exists at the project root
- **WHEN** `settings.database_url` is accessed
- **THEN** the value SHALL be the hardcoded default `"postgresql+asyncpg://ner:ner@localhost:5432/ner"`

### Requirement: Environment Variable Documentation

The system SHALL provide a `.env.example` file at the project root that documents every configurable `NER_*` environment variable with a description and an example value. This file SHALL be tracked in version control.

#### Scenario: .env.example documents all settings

- **GIVEN** the `Settings` class defines fields `database_url`, `redis_url`, `jwt_secret`, `jwt_algorithm`, `access_token_ttl_minutes`, `refresh_token_ttl_days`, `minio_endpoint`, `minio_access_key`, `minio_secret_key`, `minio_bucket`
- **WHEN** `.env.example` is read
- **THEN** every field name SHALL appear as `NER_<UPPER_CASE_FIELD_NAME>` with a descriptive comment and example value

### Requirement: .env Excluded from Version Control

The system SHALL exclude `.env` from version control via `.gitignore`. Only `.env.example` SHALL be tracked.

#### Scenario: .env is gitignored

- **GIVEN** a fresh clone of the repository
- **WHEN** `git check-ignore .env` is run
- **THEN** the exit code SHALL be 0 (file is ignored)
