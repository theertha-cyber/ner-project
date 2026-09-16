# Deployment: verify-docker-annotation-fix-20260910 — dev

- Target: docker-compose (local)
- Strategy: `docker compose build`; `docker compose up -d --force-recreate`
- Base URL: http://localhost:3000
- Build: PASS. All Compose images built; portal image `ner-project-portal:latest` was produced (image ID `sha256:b33d0a280131a0eb942e42f0162cfdea236a0bcfba0d079fed54bf8e5f902915`). Compose emitted only the obsolete `version` warning.
- Recreate: PASS. Compose completed and all application services started.
- Health: PASS after startup. Portal HTTP 200; gateway `/health` HTTP 200 with healthy database; annotation `/health` HTTP 200.
- CAP-5 provenance: PASS at source/build provenance level. CAP-5 implementation is present in the repository at commit `99bce39` (`cap-5-single-request-manual-annotation-gestures`), and the portal build completed from the current source context. The image was cache-reused during build (portal image created 2026-09-10T09:43:51Z), so no independent embedded commit label exists.
- Focused portal tests: 21 total, 18 passed, 3 failed. The failures are unrelated layout-control assertions (`layout-btn-3pane`/`layout-btn-focus`); the two CAP-5 request-count tests passed.
- Behavioral browser/API verification: BLOCKED. The deployment is healthy, but no authenticated browser/network trace was captured in this unattended verification; therefore no deployed click/drag behavior pass or failure is claimed.
# CAP-6 Docker Deployment Verification

- Timestamp: 2026-09-11T09:53:44Z
- Commands: `docker compose build`; `docker compose up -d --force-recreate`
- Result: both completed successfully.
- Portal image: `ner-project-portal:latest`
- Image ID: `sha256:0e1cd489ab915b70475c1f4c97d33d8310a5f9ce6ec8e442c408d71b5997b49f`
- Image created: `2026-09-11T09:45:12.50697884Z`
- Compose portal container image: same image ID.
- CAP-5 provenance: rebuilt portal from the workspace containing commit `99bce39 cap-5-single-request-manual-annotation-gestures: prevent duplicate saves`. The final image contains compiled output only and no CAP-5 source marker/labels.
- No application code was modified by CAP-6.
