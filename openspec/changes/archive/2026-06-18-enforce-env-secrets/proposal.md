## Why

Several secrets — the JWT signing key, MinIO credentials, and MLflow AWS credentials — are hardcoded as literal strings in `src/shared/config.py` defaults and `docker-compose.yml`. This means any developer who clones the repo and runs `docker compose up` is running with publicly-known credentials, and a misconfigured production deployment could silently use the same weak defaults without any warning.

## What Changes

- Remove hardcoded default values for `jwt_secret`, `minio_access_key`, and `minio_secret_key` in `src/shared/config.py` — these fields become required (no default)
- Replace inline literal secrets in `docker-compose.yml` with `${VAR}` references so they are resolved from the `.env` file at runtime
- Update `.env.example` to clearly mark secret fields as required and provide guidance on generating safe values
- Create `agents.md` at the project root documenting the policy that no secrets may be hardcoded anywhere in the codebase

## Capabilities

### New Capabilities

- `secret-hygiene`: Developer-facing policy document (`agents.md`) and enforcement conventions ensuring secrets are never committed as literal values

### Modified Capabilities

- `env-config`: Add a requirement that secret-class settings (`jwt_secret`, `minio_access_key`, `minio_secret_key`) MUST NOT have hardcoded defaults and MUST fail at startup if not supplied via environment

## Impact

- `src/shared/config.py`: Three fields lose their default values — any environment (including CI) that does not provide `NER_JWT_SECRET`, `NER_MINIO_ACCESS_KEY`, `NER_MINIO_SECRET_KEY` will fail at startup with a Pydantic validation error
- `docker-compose.yml`: Secrets become `${NER_JWT_SECRET}`, `${MINIO_ROOT_USER}`, `${MINIO_ROOT_PASSWORD}`, `${AWS_ACCESS_KEY_ID}`, `${AWS_SECRET_ACCESS_KEY}` — the developer must have a `.env` file present before running `docker compose up`
- `tests/conftest.py` and individual test files: Already use `os.environ.setdefault(...)` for test secrets — no change needed, these remain valid test fixtures
- `.env.example`: Updated with required-field markers and generation instructions
- `agents.md`: New file created at project root

## Open Questions

- Should CI pipelines inject these secrets via GitHub Actions secrets, or is a committed `.env.ci` acceptable? (Assumption: CI already has these as environment secrets; no `.env.ci` file will be created here.)
Answer: not yet decided.
- Should the `minio_access_key` / `minio_secret_key` defaults be preserved for local dev convenience (outside Docker) or removed entirely? 
Answer: removed entirely — local dev should use the `.env` file like every other environment.
