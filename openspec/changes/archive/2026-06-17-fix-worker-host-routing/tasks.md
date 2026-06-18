## 1. Settings & Configuration

- [x] 1.1 Add `document_service_url: str = "http://localhost:8001"` to `Settings` in `src/shared/config.py` (using `Field` with env var `NER_DOCUMENT_SERVICE_URL`)
- [x] 1.2 Confirm `model_serving_url` already exists in `Settings` and supports `NER_MODEL_SERVING_URL` env override

## 2. Worker URL Replacement

- [x] 2.1 Replace hardcoded `http://document_service:8001` in `src/extraction_service/worker.py` with `settings.document_service_url`

## 3. Docker Compose Updates

- [x] 3.1 Add `extra_hosts: ["host.docker.internal:host-gateway"]` to `celery_worker_extraction` service in `docker-compose.yml`
- [x] 3.2 Add environment variables `NER_DOCUMENT_SERVICE_URL=http://host.docker.internal:8001` and `NER_MODEL_SERVING_URL=http://host.docker.internal:8004` to `celery_worker_extraction` service in `docker-compose.yml`

## 4. Build & Test

- [x] 4.1 Rebuild Docker image with `docker compose build celery_worker_extraction --no-cache`
- [x] 4.2 Trigger a batch extraction with a valid document while host services (document_service, model_serving) are running
- [ ] 4.3 GET the extraction run status to confirm `processed_count=1` and `failed_count=0`

## 5. Verification & Evidence

- [ ] 5.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 5.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 5.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 5.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 5.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [ ] 5.6 Run `openspec validate fix-worker-host-routing --type change --strict` and confirm it exits clean before archive.
