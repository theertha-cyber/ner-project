## Verification Plan

- Build/recreate commands: `docker compose build`; `docker compose up -d --force-recreate`.
- Health evidence: portal `http://localhost:3000`, gateway `http://localhost:8000/health`, annotation service `http://localhost:8005/health`.
- Provenance evidence: running portal image ID, image labels/history, and CAP-5 source/test marker where available.
- Focused source corroboration: `src/portal/src/components/annotation/AnnotationPage.test.tsx`, especially the two CAP-5 tests at lines 584-626.
- Behavioral evidence: authenticated same-token click and multi-token drag request/network traces and resulting confirmed-span counts.
- Required output files: deployment record, health-check, sanity, integration, and summary artifacts under the paths named by the decomposition.

## Disposition Rules

- Any missing health endpoint or unproven CAP-5 portal image is an environment/image-provenance blocker.
- Unrelated layout-control failures and the known Next.js page export type error are recorded separately and are not fixed by CAP-6.
- No behavior is reported as passed when the deployed target cannot be authenticated or observed.
