## ADDED Requirements

### Requirement: Document Content Hashing and Duplicate Identification

The system SHALL compute a deterministic SHA-256 content hash over the raw bytes of every successfully uploaded document and persist it as a 64-character lowercase hex digest in the `checksum` column of `tenant_{tid}.documents`. The hash SHALL depend only on the file's byte content — never on its filename, upload time, uploading user, `purpose`, or document ID — so that byte-identical files always produce the same hash and any difference in bytes produces a different hash.

Before inserting the new document record, the system SHALL look up the earliest existing document in the same tenant schema whose `checksum` equals the newly computed hash and whose `status` is not `deleted`. When such a document exists, the upload response SHALL include `duplicate_of` set to that document's ID; otherwise `duplicate_of` SHALL be `null`. The lookup SHALL be scoped to the caller's tenant schema and SHALL additionally filter on `tenant_id`, so that documents belonging to other tenants can never be reported as duplicates.

A duplicate upload SHALL NOT be rejected, merged, or deduplicated. The upload SHALL still return HTTP 201 with its own new document ID and `status: "pending"`, SHALL store its own blob, and SHALL leave the previously uploaded document's record, ownership, extraction history, and annotations entirely unmodified.

The upload response SHALL include the computed `checksum`, and the document-metadata GET response SHALL include the stored `checksum`.

#### Scenario: Upload persists a SHA-256 content hash

- **GIVEN** an authenticated tenant user
- **WHEN** they POST a PDF file to `/api/v1/documents`
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain a `checksum` that is the 64-character lowercase SHA-256 hex digest of the uploaded bytes
- **AND** the stored `checksum` column for that document SHALL hold the same value

#### Scenario: Identical content produces the same deterministic hash

- **GIVEN** the same file bytes are hashed twice
- **WHEN** the content hash is computed for each
- **THEN** both hashes SHALL be identical
- **AND** the hash SHALL be a 64-character lowercase hex string

#### Scenario: Different filenames with identical content are recognised as identical content

- **GIVEN** an authenticated tenant user has already uploaded a file as `original.pdf`
- **WHEN** they upload the exact same bytes as `renamed-copy.pdf`
- **THEN** the response SHALL have status 201 with a new document ID distinct from the first
- **AND** both documents' stored `checksum` values SHALL be equal
- **AND** the second response's `duplicate_of` SHALL be the first document's ID

#### Scenario: Different content is not reported as a duplicate

- **GIVEN** an authenticated tenant user has already uploaded a file
- **WHEN** they upload a different file whose bytes differ
- **THEN** the two documents' stored `checksum` values SHALL differ
- **AND** the second response's `duplicate_of` SHALL be `null`

#### Scenario: Duplicate upload does not modify the original document

- **GIVEN** an authenticated tenant user has already uploaded a file that is now in `processed` status
- **WHEN** they upload the exact same bytes again
- **THEN** the original document SHALL still exist with its original ID, filename, `uploaded_by`, and status
- **AND** the new document SHALL have its own distinct ID and `status: "pending"`

#### Scenario: Duplicate detection does not cross tenant boundaries

- **GIVEN** tenant A has uploaded a file
- **WHEN** a user of tenant B uploads the exact same bytes
- **THEN** tenant B's response `duplicate_of` SHALL be `null`

#### Scenario: A soft-deleted document is not reported as a duplicate

- **GIVEN** an authenticated tenant user uploaded a file and then deleted it, leaving it in `deleted` status
- **WHEN** they upload the exact same bytes again
- **THEN** the response `duplicate_of` SHALL be `null`

#### Scenario: Document metadata exposes the stored checksum

- **GIVEN** a document that was uploaded after content hashing was introduced
- **WHEN** a tenant user GETs `/api/v1/documents/{doc_id}`
- **THEN** the response's `document` object SHALL include the stored `checksum`
