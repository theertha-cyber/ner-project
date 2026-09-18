## 1. Tenant-schema sync ledger and migration

- [x] 1.1 Add tenant-schema sync run/object-version/lease tables via an additive alembic migration with tenant-scoped indexes.
- [x] 1.2 Add ledger/lease domain operations with atomic lease acquire/release and version compare-and-set.

## 2. Contained provider runtime and durable sync job

- [x] 2.1 Implement the contained Azure Blob provider seam (enumeration, opaque identity/version, byte acquisition, error mapping) with a fixture/fake for tests.
- [x] 2.2 Implement one tenant-bound Celery sync task for manual, scheduled, retry, and catch-up triggers with identity-only payloads.
- [x] 2.3 Implement the 15-minute scheduler evaluation with one missed-schedule catch-up and inactive-connection gating.

## 3. Reconciliation, retention, and compatibility

- [x] 3.1 Implement unchanged-skip, atomic changed-replace via the common ingestion pipeline, and two-confirmation missing handling.
- [x] 3.2 Implement temporary working-storage byte handling with deletion on every terminal path.
- [x] 3.3 Enforce retrieval exclusion of superseded and confirmed-missing documents in all retrievers.
- [x] 3.4 Remediate touched OCR failure telemetry to safe structured error classes.

## 4. Verification & Evidence

- [x] 4.1 Add executable manual, scheduled, catch-up, retry, lease-overlap, unchanged, changed, missing, single-absence, listing-failure, temporary-cleanup, tenant-isolation, retrieval-exclusion, status-shape, and boundary-contract tests for every delta-spec scenario.
- [x] 4.2 Run the configured test command and record evidence in verification.md.
- [x] 4.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 4.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [x] 4.5 Complete Audit Record sign-off in verification.md § Audit Record.
- [x] 4.6 Run `openspec validate cap-3-durable-azure-blob-synchronization-and-source-reconciliation --strict` and resolve all findings.
