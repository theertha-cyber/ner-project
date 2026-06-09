## Why

The platform has no `.env` file. `src/shared/config.py` uses pydantic-settings (`NER_` prefix, `.env` support) but falls back to hardcoded defaults when no `.env` exists. Developers must either manually set environment variables or accept defaults that may not match their local setup. This creates friction for onboarding, makes the dev database URL point to a non-existent `ner_dev` DB, and leaves production secrets undocumented.

## What Changes

- Create `.env` with development defaults (postgres-test, Redis, MinIO, JWT secret)
- Create `.env.example` documenting all supported variables (without secrets)
- Remove hardcoded default in `config.py` for `database_url` that points to `ner_dev` — switch default to `ner` to match docker-compose
- Ensure all services load config exclusively from `settings` object (already the case: `database.py`, `auth.py`, `seed.py` all use `settings`)
- Add `.env` to `.gitignore`

## Capabilities

### New Capabilities

- `env-config`: Platform-wide environment variable configuration. Defines the source of truth for all configurable settings (database, Redis, JWT, MinIO, etc.) via a single `.env` file, loaded by `pydantic-settings` at import time.

### Modified Capabilities

None — this change introduces no new application features or behavioural changes. It only externalises existing configuration defaults into a checked-in file.

## Impact

- `src/shared/config.py`: Adjust `database_url` default from `ner_dev` → `ner` to match `docker-compose.yml`
- Root `.env` created (git-ignored) with all settings
- `.env.example` created (tracked) as documentation
- `.gitignore` updated to exclude `.env`
- No API or behavioural changes — all consumers already use `settings`

## Open Questions

- Should `.env.example` include dummy values or empty keys for secrets? Decision: include dummy dev values for documentation completeness; production secrets are managed out-of-band.
