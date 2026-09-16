## Context

CAP-5 fixed duplicate manual annotation requests in `AnnotationPage.tsx`. CAP-6 is a verification-only change: the source and deployment definitions are not to be modified.

## Verification Approach

1. Run `docker compose build` and capture the portal build result and image ID.
2. Run `docker compose up -d --force-recreate`, wait for dependencies, and capture portal, gateway, and annotation health responses.
3. Inspect the running portal image metadata/content and source revision evidence to establish that CAP-5 is present; a reused image or failed provenance check blocks behavioral acceptance.
4. Run `npm test --workspace=src/portal` and distinguish CAP-5 assertions from unrelated failures.
5. Authenticate against the local portal when possible and capture network/API evidence for one same-token click and one multi-token drag, including request count, inclusive range, and confirmed-span count.
6. Write the requested deployment and QA evidence files. If a prerequisite is unavailable, write a blocker disposition and do not claim gesture behavior passed or failed.

## Scope Guard

No changes to `AnnotationPage.tsx`, APIs, database schema, Docker manifests, historical data, or unrelated tests.
