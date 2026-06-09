## Context

The platform uses `pydantic-settings` in `src/shared/config.py` with `env_prefix = "NER_"` and `env_file = ".env"` — meaning it already reads from a `.env` file. However, no `.env` file exists in the repo. Developers must set environment variables manually or accept hardcoded defaults that may not reflect their local setup (e.g., `database_url` defaults to `ner_dev` while docker-compose creates `ner`). The test suite sets overrides via `os.environ.setdefault()` in `conftest.py` as a fallback.

This change externalises all configuration into a single `.env` file, documents all supported variables via `.env.example`, and adjusts the default database name to match docker-compose.

## Goals / Non-Goals

**Goals:**
- Create `.env` with development defaults matching `docker-compose.yml` services
- Create `.env.example` documenting every `NER_*` variable with descriptions
- Update `config.py` default `database_url` from `ner_dev` → `ner`
- Add `.env` to `.gitignore`

**Non-Goals:**
- No new settings variables — only document existing ones
- No behavioural changes to any service
- No production secret management — production secrets are out-of-band

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-004 OpenSpec Governance | All changes follow proposal → design → spec → tasks → evidence → archive pipeline | This change follows the pipeline. No spec needed (no functional requirement changes). |

## Decisions

### Decision 1: Single `.env` at project root

**Choice:** A single `.env` file at the project root, loaded by `pydantic-settings` at import time via the `model_config` directive in `Settings`.

**Rationale:** `pydantic-settings` natively supports `.env` files. The `NER_` prefix namespaces all variables. A single file is simpler than per-service `.env` files and matches the current monorepo structure.

**Alternatives considered:**
- Per-service `.env` files (`src/gateway/.env`, etc.) — unnecessary for a monorepo; just adds complexity.
- YAML/JSON config file — would require a separate config loader; pydantic-settings already solves this.

### Decision 2: `.env.example` tracked, `.env` gitignored

**Choice:** `.env.example` is checked into version control as documentation. `.env` is in `.gitignore` so each developer has their own copy.

**Rationale:** Industry standard. `.env.example` documents every variable. Developers copy it to `.env` and adjust values. Secrets never leak into git.

### Decision 3: Test overrides remain in `conftest.py`

**Choice:** The test suite continues using `os.environ.setdefault()` in `conftest.py` rather than a separate `.env.test`.

**Rationale:** Tests need deterministic, isolated configuration that doesn't depend on a developer's `.env` file. `setdefault` sets test values only if not already set, allowing CI to inject via environment variables.

## Risks / Trade-offs

- [Developer forgets to create `.env` after clone] → `pydantic-settings` falls back to defaults, so the app still starts. The error only surfaces when connecting to a non-existent DB (same as today).
- [`.env.example` drifts out of sync with `config.py`] → Mitigation: tasks include checking that every field in `Settings` has a matching entry in `.env.example`.

## Migration Plan

1. Create `.env.example` documenting all `NER_*` variables with descriptions and dummy dev values.
2. Create `.env` with values matching `docker-compose.yml` services.
3. Update `config.py`: change `database_url` default from `ner_dev` → `ner`.
4. Add `.env` to `.gitignore`.
5. Verify: run `uvicorn src.gateway.main:app` and confirm startup logs no database connection errors.
6. Verify: run `pytest tests/ -v` and confirm all tests pass.

## Open Questions

None.
