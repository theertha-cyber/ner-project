## 1. Fix Seed Script

- [x] 1.1 Add existence check before the promoted model INSERT in `src/gateway/seed.py` (~line 297): query `SELECT id FROM {schema_name}.model_versions WHERE tenant_id = :tid AND status = 'promoted'` and skip the insert if a row is found
- [x] 1.2 Rebuild and run `db-init`: `docker-compose up -d --build db-init`
- [x] 1.3 Confirm `db-init` exits 0: `docker wait ner-project-db-init-1`
- [x] 1.4 Confirm the extraction service auto-starts: `docker ps --filter "name=extraction_service" --format "{{.Names}} {{.Status}}"`

## 2. Verification & Evidence

- [x] 2.1 Confirm `db-init` logs show no IntegrityError for the model_versions insert — `docker logs ner-project-db-init-1 | Select-String "IntegrityError"` should return nothing
- [x] 2.2 Run a playground extraction and confirm it returns 200 — `Invoke-RestMethod -Uri "http://localhost:8000/api/v1/extract" -Method POST -Body '{"text":"test"}' -ContentType "application/json" -Headers @{Authorization="Bearer <token>"}`
- [x] 2.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register
- [x] 2.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance
- [ ] 2.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent)
- [x] 2.6 Run `openspec validate fix-seed-promoted-model-conflict --type change --strict` and confirm it exits clean before archive
