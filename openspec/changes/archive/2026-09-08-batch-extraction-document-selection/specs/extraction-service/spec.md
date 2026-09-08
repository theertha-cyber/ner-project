## ADDED Requirements

### Requirement: List documents eligible for batch extraction

The system SHALL expose `GET /api/v1/extract-batch/eligible-documents` returning the tenant's documents in `processed` status. Each document in the response SHALL include an `already_extracted` boolean, computed using the same idempotency rule as batch extraction: `true` when `extracted_entities` already has rows for that `document_id` matching the tenant's current active model version (version 0 when no model is promoted), `false` otherwise. The lookup used to compute `already_extracted` SHALL be the same shared function used by the batch extraction worker to decide which documents to skip, so the two never disagree.

#### Scenario: Eligible documents list marks already-extracted documents

- **GIVEN** a tenant with two `processed` documents, one already extracted under the active model version and one not
- **WHEN** a Tenant Admin GETs `/api/v1/extract-batch/eligible-documents`
- **THEN** the response SHALL have status 200
- **AND** the already-extracted document SHALL have `already_extracted: true`
- **AND** the other document SHALL have `already_extracted: false`

#### Scenario: Eligible documents list excludes non-processed documents

- **GIVEN** a tenant with one `processed` document and one `pending` document
- **WHEN** a Tenant Admin GETs `/api/v1/extract-batch/eligible-documents`
- **THEN** the response SHALL only contain the `processed` document

#### Scenario: Eligible documents list as non-admin

- **GIVEN** an authenticated `business_user`
- **WHEN** the user GETs `/api/v1/extract-batch/eligible-documents`
- **THEN** the response SHALL have status 200

#### Scenario: A document re-extracted under a new model version becomes eligible again

- **GIVEN** a document extracted only under a since-superseded model version
- **WHEN** a Tenant Admin GETs `/api/v1/extract-batch/eligible-documents` after a new model version is promoted
- **THEN** that document SHALL have `already_extracted: false`
