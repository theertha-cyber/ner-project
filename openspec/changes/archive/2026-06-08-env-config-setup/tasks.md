## 1. Environment Configuration Setup

- [x] 1.1 Update `src/shared/config.py`: change `database_url` default from `"postgresql+asyncpg://ner:ner@localhost:5432/ner_dev"` to `"postgresql+asyncpg://ner:ner@localhost:5432/ner"`
- [x] 1.2 Create `.env.example` at project root documenting every `NER_*` variable with descriptions and example values (database, Redis, JWT, MinIO)
- [x] 1.3 Create `.env` at project root with development defaults matching `docker-compose.yml` services (postgres-test, postgres, Redis, MinIO)
- [x] 1.4 Add `.env` to `.gitignore` — add line before any existing entries

## 2. Test & Verification

- [x] 2.1 Create `tests/test_env_config.py` with tests for:
  - `test_settings_load_from_env`: assert settings reads from `.env` when present
  - `test_settings_fallback_defaults`: assert settings uses hardcoded defaults when no `.env` exists
- [x] 2.2 Verify `.env.example` documents every field in `Settings` class — run a manual comparison between `config.py` field names and `NER_*` entries in `.env.example`

## 3. Verification & Evidence

- [x] 3.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 3.2 Collect functional evidence (test output / code review) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 3.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 3.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 3.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 3.6 Run `openspec validate env-config-setup --type change --strict` and confirm it exits clean before archive.
