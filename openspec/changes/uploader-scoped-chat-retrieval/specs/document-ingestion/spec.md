## MODIFIED Requirements

### Requirement: Document visibility by ingesting actor

The system SHALL record an ingesting actor on every document, distinguishing a human user from a source system. Listing SHALL restrict a non-administrative user to documents ingested by that user **only when the ingesting actor is a human**. A document whose ingesting actor is a source system SHALL be visible to every user of that tenant, so that document listing and chat retrieval agree on what a user may see.

That agreement SHALL hold in both directions. A document a non-administrative user may not list SHALL NOT be citable, countable, or nameable in that user's chat answers, through any answer channel over the platform's own tenant data.

#### Scenario: A user sees their own uploads

- **GIVEN** a non-administrative user who has uploaded a document
- **WHEN** they list documents
- **THEN** their own document SHALL be listed

#### Scenario: A user does not see another user's upload

- **GIVEN** two non-administrative users in one tenant, each having uploaded a document
- **WHEN** the first lists documents
- **THEN** the second user's document SHALL NOT be listed

#### Scenario: A system-ingested document is visible tenant-wide

- **GIVEN** a document whose ingesting actor is a source system rather than a human
- **WHEN** a non-administrative user lists documents
- **THEN** that document SHALL be listed

#### Scenario: Listing and retrieval agree

- **GIVEN** a `purpose='query'` document whose ingesting actor is a source system, and a non-administrative user
- **WHEN** that user asks a question whose answer cites that document
- **THEN** the cited document SHALL also be listable by that user

#### Scenario: Listing and retrieval agree in the other direction

- **GIVEN** a `purpose='query'` document ingested by a human other than the requesting non-administrative user
- **WHEN** that user asks a question whose content matches that document
- **THEN** the document SHALL NOT be cited in the answer
- **AND** the document SHALL also not be listable by that user

#### Scenario: Administrators are unaffected

- **GIVEN** a user whose role is `tenant_admin`
- **WHEN** they list documents
- **THEN** every non-deleted document in the tenant SHALL be listed regardless of ingesting actor

## ADDED Requirements

### Requirement: Chunks carry their document's ingesting actor

The system SHALL denormalize a document's ingesting actor and uploading user onto every chunk it writes, in the same write that records the chunk's `purpose` and conversation ownership, so that an answer channel ranking chunks can apply the uploader-visibility rule from the chunk row alone. The denormalized values SHALL be those recorded on the document at ingestion and SHALL NOT be re-derived at query time.

#### Scenario: A newly written chunk carries the actor

- **GIVEN** a document ingested by a human user and processed to completion
- **WHEN** its chunks are written
- **THEN** each chunk SHALL record that document's ingesting actor kind and uploading user

#### Scenario: A source-system document's chunks are marked as such

- **GIVEN** a document whose ingesting actor is a source system, processed to completion
- **WHEN** its chunks are written
- **THEN** each chunk's recorded ingesting actor kind SHALL be the source-system value

#### Scenario: Existing chunks are backfilled

- **GIVEN** a tenant schema holding chunks written before this change
- **WHEN** the migration that adds the denormalized columns has run
- **THEN** every existing chunk SHALL carry the ingesting actor and uploading user of its own document
- **AND** no chunk SHALL be left with an absent ingesting actor kind

#### Scenario: The denormalized value agrees with the document

- **GIVEN** any chunk in a tenant schema
- **WHEN** its denormalized ingesting actor and uploading user are compared with its document's
- **THEN** they SHALL be equal
