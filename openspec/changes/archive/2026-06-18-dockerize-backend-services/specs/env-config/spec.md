## MODIFIED Requirements

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
