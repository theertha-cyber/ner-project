## Context

The platform uses `pydantic-settings` with `NER_` prefix to load configuration. Three secret-class fields (`jwt_secret`, `minio_access_key`, `minio_secret_key`) have hardcoded fallback strings in `src/shared/config.py`. `docker-compose.yml` repeats those same literal values inline for the services that consume them. The `.env.example` documents these fields but presents them as non-required with weak placeholder values. `AGENTS.md` has no policy entry prohibiting hardcoded secrets.

The risk is twofold: a production deployment that forgets to set `NER_JWT_SECRET` runs with a well-known signing key, and MinIO/MLflow run with default admin credentials that are published in this repository.

## Goals / Non-Goals

**Goals:**
- Secret fields in `Settings` have no default — the application refuses to start if they are absent from the environment
- `docker-compose.yml` resolves all secret values from the developer's `.env` file rather than embedding literals
- `.env.example` is updated to mark secret fields as required and give generation instructions
- `AGENTS.md` gains an explicit invariant prohibiting hardcoded secrets

**Non-Goals:**
- Secrets management infrastructure (Vault, AWS Secrets Manager, etc.) — out of scope
- Rotating or auditing existing deployed secrets
- Changing the secrets used in test files — test fixtures using `os.environ.setdefault()` are scoped, safe, and intentional

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-004: OpenSpec SDD Governance | All changes require proposal → design → spec → tasks pipeline | This document satisfies the design gate |
| ADR-005: OpenCode Agent Boundaries | Agent instructions live in `AGENTS.md`; agents must not take irreversible actions outside their domain | Changes to `AGENTS.md` must be additive and policy-only |

## Decisions

### Decision 1: Remove defaults for secret fields in `Settings`

**Choice:** Remove the default string values from `jwt_secret`, `minio_access_key`, and `minio_secret_key` in `src/shared/config.py`. Leave all other fields with their existing defaults.

**Rationale:** Pydantic-settings raises `ValidationError` at `Settings()` instantiation if a required field has no value and no default. This means the application process itself refuses to start — a hard, early, visible failure rather than a silent misconfiguration. No custom validation logic is needed.

**Alternatives considered:**
- *Keep defaults, add a startup validator that warns* — still allows the application to run with weak secrets; relies on developers reading logs
- *Use `SecretStr` type* — good for masking secrets in repr/logs, orthogonal to this change; can be added later without affecting this work
- *Use `Optional[str] = None` with a validator* — more code for equivalent semantics to just removing the default

### Decision 2: Use `${VAR}` interpolation in `docker-compose.yml`

**Choice:** Replace all inline secret literals in `docker-compose.yml` with `${VAR}` references. Docker Compose automatically reads `.env` from the working directory before interpolation, so developers only need one `.env` file.

**Rationale:** This is Docker Compose's native mechanism for externalising secrets. No new tooling or indirection layer is needed. The same `.env` file that satisfies `pydantic-settings` at runtime also satisfies Compose at `docker compose up` time.

Variables affected:
- `NER_JWT_SECRET` (3 service entries)
- `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` (MinIO service)
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (MLflow service)

**Alternatives considered:**
- *`env_file:` directive per service* — introduces a separate file per service; more files to maintain; no advantage for a monorepo with a single `.env`
- *Docker secrets (Swarm)* — appropriate for production orchestration, not local dev compose

### Decision 3: Extend `.env.example` with docker-compose variables and required markers

**Choice:** Add `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `AWS_ACCESS_KEY_ID`, and `AWS_SECRET_ACCESS_KEY` to `.env.example` (these are not `NER_`-prefixed but are consumed by docker-compose). Mark `NER_JWT_SECRET`, `NER_MINIO_ACCESS_KEY`, and `NER_MINIO_SECRET_KEY` as `REQUIRED` with generation instructions.

**Rationale:** A developer following the `cp .env.example .env` onboarding step should get everything they need for `docker compose up` to work, including the MinIO and MLflow credentials. Without these non-NER vars in `.env.example`, those services silently fail.

### Decision 4: Update `test_settings_fallback_defaults` in `test_env_config.py`

**Choice:** Remove the three assertions that checked for the now-deleted default values (`jwt_secret == "change-me-in-production"`, `minio_access_key == "minioadmin"`, `minio_secret_key == "minioadmin"`). Add a companion test asserting that `Settings()` raises `ValidationError` when secret fields are absent.

**Rationale:** The existing test verified default behaviour that no longer exists. Replacing it with a failure test documents and enforces the new required-field contract.

## Risks / Trade-offs

- [Developers who `git pull` and run tests without a `.env` set will see import-time `ValidationError`] → Mitigated by updating `AGENTS.md` and `.env.example` with clear first-steps instructions, and by the fact that test files already call `os.environ.setdefault()` before any import
- [CI pipelines that do not inject `NER_JWT_SECRET` as an env var will break] → Mitigated by ensuring CI already has these as environment secrets (or a `.env` injected by the pipeline); this change makes a pre-existing implicit requirement explicit

## Migration Plan

1. Update `src/shared/config.py` — remove three defaults
2. Update `docker-compose.yml` — replace literals with `${VAR}` references
3. Update `.env.example` — add required markers, generation instructions, and docker-compose vars
4. Update `AGENTS.md` — add secret-hygiene invariant
5. Update `tests/test_env_config.py` — fix `test_settings_fallback_defaults` and add failure test

No database migrations, no API changes, no inter-service contract changes. Rollback: revert the `config.py` change (restore defaults) and the `docker-compose.yml` change (restore literals).

## Open Questions

- None. The CI assumption (secrets injected as env vars) is standard practice and does not require a code change here.
