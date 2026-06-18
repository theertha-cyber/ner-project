## 1. Docker Compose — Add Extraction Worker Service

- [x] 1.1 Add `celery_worker_extraction` service to `docker-compose.yml` — copy the existing `celery_worker` block with these changes:
  - Service name: `celery_worker_extraction`
  - Command: `celery -A src.extraction_service.celery_app worker -Q extraction --pool=solo --loglevel=info`
  - Remove env vars not needed by extraction worker: `NER_TRAINING_DEVICE`, `NER_MINIO_ENDPOINT`, `NER_MLFLOW_TRACKING_URI`
  - Keep `NER_DATABASE_URL`, `NER_DATABASE_URL_SYNC`, `NER_CELERY_BROKER_URL`, `NER_CELERY_RESULT_BACKEND`, `NER_JWT_SECRET`
  - Add `depends_on` for `redis` and `postgres-test`

## 2. Verification & Evidence

- [x] 2.1 Verify worker starts: `docker-compose up celery_worker_extraction` and confirm log shows `celery@... ready.` with `extraction` queue subscription
- [x] 2.2 Verify batch extraction flow: trigger `POST /api/v1/extract-batch` with a document ID, then poll `GET /api/v1/extract-batch/{run_id}` until status is `"completed"`
- [x] 2.3 Collect functional evidence for each scenario in verification.md § Spec Alignment — record entries in verification.md § Evidence Log
- [x] 2.4 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register
- [x] 2.5 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance
- [x] 2.6 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent)
- [x] 2.7 Run `openspec validate add-celery-extraction-worker --type change --strict` and confirm it exits clean before archive
