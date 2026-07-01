## 1. src/shared/config.py — Remove secret defaults

- [x] 1.1 Remove the default value `"change-me-in-production"` from the `jwt_secret` field in `src/shared/config.py` (line 8) — field becomes required with no fallback
- [x] 1.2 Remove the default value `"minioadmin"` from the `minio_access_key` field in `src/shared/config.py` (line 16)
- [x] 1.3 Remove the default value `"minioadmin"` from the `minio_secret_key` field in `src/shared/config.py` (line 17)

## 2. docker-compose.yml — Replace hardcoded literals with interpolation

- [x] 2.1 Replace `NER_JWT_SECRET: "dev-secret-do-not-use-in-prod"` with `NER_JWT_SECRET: "${NER_JWT_SECRET}"` in the `training_service` service block
- [x] 2.2 Replace `NER_JWT_SECRET: "dev-secret-do-not-use-in-prod"` with `NER_JWT_SECRET: "${NER_JWT_SECRET}"` in the `celery_worker` service block
- [x] 2.3 Replace `NER_JWT_SECRET: "dev-secret-do-not-use-in-prod"` with `NER_JWT_SECRET: "${NER_JWT_SECRET}"` in the `celery_worker_extraction` service block
- [x] 2.4 Replace `MINIO_ROOT_USER: minioadmin` with `MINIO_ROOT_USER: "${MINIO_ROOT_USER}"` in the `minio` service block
- [x] 2.5 Replace `MINIO_ROOT_PASSWORD: minioadmin` with `MINIO_ROOT_PASSWORD: "${MINIO_ROOT_PASSWORD}"` in the `minio` service block
- [x] 2.6 Replace `AWS_ACCESS_KEY_ID: minioadmin` with `AWS_ACCESS_KEY_ID: "${AWS_ACCESS_KEY_ID}"` in the `mlflow` service block
- [x] 2.7 Replace `AWS_SECRET_ACCESS_KEY: minioadmin` with `AWS_SECRET_ACCESS_KEY: "${AWS_SECRET_ACCESS_KEY}"` in the `mlflow` service block

## 3. .env.example — Add required markers and docker-compose vars

- [x] 3.1 Add a `# REQUIRED — generate with: openssl rand -hex 32` comment above `NER_JWT_SECRET` and remove the `change-me-in-production` placeholder value (leave the key with an empty value or a `<generate>` marker)
- [x] 3.2 Add `# REQUIRED` comments above `NER_MINIO_ACCESS_KEY` and `NER_MINIO_SECRET_KEY` entries
- [x] 3.3 Add a new `# --- docker-compose service credentials ---` section with entries for `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` — each marked `# REQUIRED` with a note explaining they are consumed directly by docker-compose (not NER_-prefixed)

## 4. AGENTS.md — Add secret-hygiene invariant

- [x] 4.1 Add a new invariant entry to section 2 of `AGENTS.md`: **"No secret may be hardcoded in source code, configuration files, or committed `.env` files. All secrets MUST be loaded from environment variables sourced from a developer's local `.env` file (not tracked in version control). Defaults for secret-class settings in `Settings` MUST NOT be present."**

## 5. tests/test_env_config.py — Update for removed defaults

- [x] 5.1 Remove the three assertions from `test_settings_fallback_defaults` that reference the now-deleted defaults: `settings.jwt_secret == "change-me-in-production"`, `settings.minio_access_key == "minioadmin"`, `settings.minio_secret_key == "minioadmin"`
- [x] 5.2 Add a new test `test_settings_fail_without_jwt_secret` that clears all NER_ env vars and asserts `pytest.raises(pydantic.ValidationError)` when `Settings(_env_file=None)` is called
- [x] 5.3 Add `test_settings_fail_without_minio_access_key` with the same pattern, providing jwt_secret and minio_secret_key but omitting minio_access_key
- [x] 5.4 Add `test_settings_fail_without_minio_secret_key` with the same pattern, providing jwt_secret and minio_access_key but omitting minio_secret_key

## 6. Verification & Evidence

- [x] 6.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass (`pytest tests/test_env_config.py -v`)
- [x] 6.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log
- [x] 6.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register
- [x] 6.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance
- [x] 6.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent)
- [x] 6.6 Run `openspec validate enforce-env-secrets --type change --strict` and confirm it exits clean before archive
