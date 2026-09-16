## Why

CAP-5's prior QA run could not verify the deployed portal because Docker Compose was unavailable and the portal image had been reused after a failed rebuild. This verification establishes image provenance and validates the single-request click/drag behavior at the deployed portal/API boundary without changing application behavior.

## What Changes

- Rebuild and recreate the Docker Compose target, then capture service health evidence.
- Prove the portal image contains the CAP-5 implementation.
- Run focused portal tests and record their disposition.
- Exercise or capture evidence for same-token click and multi-token drag request counts, inclusive range, and confirmed-span results.
- Add deployment and QA evidence artifacts only; no application, API, schema, or Compose implementation changes.

## Capabilities

### New Capabilities

- `docker-annotation-verification`: Evidence-only verification of CAP-5 in the recreated Docker deployment.

### Modified Capabilities

None. This change verifies existing CAP-5 behavior and does not alter requirements.

## Impact

Affected artifacts are `docs/deploy/verify-docker-annotation-fix-20260910-dev.md` and the four `qa/verify-docker-annotation-fix/` evidence files. Docker, the local Compose deployment, the portal focused test suite, and the CAP-5 portal/API boundary are exercised. No source files are intended to change.

## Open Questions

- Whether the local environment has credentials and seeded data sufficient for authenticated browser gestures; if not, record an environment/image-provenance blocker rather than infer a behavior result.
- The focused test suite may retain unrelated pre-existing layout/type failures; disposition them separately from CAP-5 request-count assertions.
