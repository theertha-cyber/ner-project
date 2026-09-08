# QA Report — add-doc-docx-upload-support

## Deployment Under Test
- Base URL: **None** — no deployment record exists; testing the built tree directly.
- Environment: N/A
- Target: N/A
- Deployment record: N/A
- Deployment health at landing: N/A

## Authentication
- Mode: none — public surface only (no running application)
- Account: N/A
- Authenticated surface covered: no — no application running

## Scope
- Commit range: `CAP-1` (add-doc-docx-upload-support)
- Components: document service (OCR worker, API endpoint), portal upload component, spec, tests
- C4 containers: N/A (no deployment)
- NFR authority: requirement document (fall-through — raise as a condition)
- Degradations applied: unit tests could not run (PostgreSQL unavailable); smoke/security/load/accessibility/performance tests not applicable (no deployed URL)

## Results By Test Type
| Test Type | Status | Report |
| --- | --- | --- |
| Smoke | not run — no deployed URL | N/A |
| Sanity | not run — no deployed URL | N/A |
| Regression | not run — no deployed URL | N/A |
| Integration | not run — PostgreSQL unavailable | N/A |
| Unit | not run — PostgreSQL unavailable | [unit.md](./unit.md) |
| Security | not run — no deployed URL | N/A |
| Performance | not run — no deployed URL | N/A |
| Load | not run — no deployed URL | N/A |
| Accessibility | not run — no deployed URL | N/A |
| Demo & Fixture Hygiene | not run — no deployed URL | N/A |
| Code Quality | run | [code-quality.md](./code-quality.md) |

## Evidence
- Combined visual dashboard: not applicable — non-browser target
- All run evidence: `qa/evidences/add-doc-docx-upload-support/` (none generated)

## Release Gate
- Decision: **conditional pass**
- Blocking issues: none
- Conditional approvals:
  1. Unit tests could not run due to missing PostgreSQL database. Run `pytest tests/test_document_ingestion.py -v` against a PostgreSQL instance to verify.
  2. Integration tests could not run due to missing PostgreSQL. Verify the extraction functions work with real DOC/DOCX files when the database is available.
  3. No smoke/security/load/accessibility/performance tests could be run because no deployment exists. If a deployment is later created, run the full QA programme against it.

## Follow-Up Work
| Item | Owner | Priority | Required Before |
| --- | --- | --- | --- |
| Run unit tests against PostgreSQL | QA | high | Deployment to any environment |
| Verify DOC/DOCX extraction with real files | QA | medium | Deployment to any environment |
| Run full QA programme against a deployed instance | QA | high | Production deployment |
