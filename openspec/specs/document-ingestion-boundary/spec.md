# Document Ingestion Boundary

## Purpose

Defines the application-owned ingestion contract: the normalized document a source
adapter submits, the declared content-acquisition capability, what the ingestion
use case owns versus what an adapter owns, platform upload as the first adapter,
dispatch that carries no content, and the prohibition on source-specific behaviour
downstream of ingestion.

---

## Requirements


### Requirement: Single application-owned ingestion entry point

The system SHALL provide one application-owned document ingestion operation that accepts a normalized document and SHALL make it the only code path permitted to create a row in `tenant_{tid}.documents`. The operation SHALL own platform document-id generation, file-type and size validation, checksum computation, duplicate identification, resolution of the retention mode and content resolution, the metadata row write, and processing dispatch. The operation SHALL NOT reference HTTP request objects, multipart types, object-storage clients, provider APIs, or credentials.

#### Scenario: Upload creates a document through the ingestion operation

- **GIVEN** an authenticated tenant user with a valid JWT
- **WHEN** they POST a PDF to `/api/v1/documents`
- **THEN** the `tenant_{tid}.documents` row SHALL be created by the ingestion operation and not by the route handler
- **AND** the response SHALL have status 201 with the same body fields the route returned before this change

#### Scenario: No second writer of the documents table exists

- **GIVEN** the application source tree
- **WHEN** all statements that INSERT into a `documents` relation are enumerated outside of tests and migrations
- **THEN** exactly one such statement SHALL exist
- **AND** it SHALL reside in the ingestion operation

#### Scenario: The ingestion operation is callable without an HTTP request

- **GIVEN** a normalized document constructed with no FastAPI request, no `UploadFile`, and no HTTP context
- **WHEN** the ingestion operation is invoked with it
- **THEN** a document SHALL be created and processing SHALL be dispatched
- **AND** no exception SHALL be raised

### Requirement: Normalized document contract

The system SHALL define a normalized document contract carrying: trusted tenant identity, filename, content access, purpose, an ingesting actor, a source reference, and optional declared media type and declared size. The source reference SHALL carry a source type, a `source_id` naming the configured document source, and optional external identity, source version, source-created and source-modified timestamps, and opaque source metadata. The tenant identity SHALL be taken from authenticated context and SHALL NOT be accepted from an adapter payload. Retention mode and content resolution SHALL be decided by the ingestion operation from the tenant's integration profile and SHALL NOT be fields an adapter supplies.

#### Scenario: Purpose is carried on the contract

- **GIVEN** a normalized document whose purpose is `training`
- **WHEN** it is ingested and processing completes
- **THEN** the document's stored `purpose` SHALL be `training`
- **AND** no chunks or embeddings SHALL be produced for it

#### Scenario: Optional source metadata is absent without error

- **GIVEN** a normalized document with no external identity, no source version, and no source timestamps
- **WHEN** it is ingested
- **THEN** ingestion SHALL succeed
- **AND** the corresponding stored fields SHALL be NULL

#### Scenario: Source timestamps are never synthesised

- **GIVEN** a normalized document whose source supplies no modified timestamp
- **WHEN** it is ingested
- **THEN** the stored source-modified timestamp SHALL be NULL
- **AND** it SHALL NOT be set to the ingestion time

#### Scenario: An adapter cannot assert a tenant identity

- **GIVEN** a normalized document whose source metadata contains a tenant identifier differing from the authenticated tenant
- **WHEN** it is ingested
- **THEN** the document SHALL be written to the authenticated tenant's schema
- **AND** the value carried in source metadata SHALL have no effect on tenant resolution

### Requirement: Declared content-acquisition capability

The normalized document contract SHALL carry a declared content-acquisition capability with exactly one of two values: `single_use`, meaning the bytes exist only for the duration of the submitting call and cannot be obtained again from the source; or `reopenable`, meaning the source adapter can be asked for the same bytes again after the submitting call has ended. Platform upload SHALL declare `single_use`. The ingestion operation SHALL use this declaration, together with the tenant's configured retention mode, to decide how the processing pipeline will obtain bytes, and SHALL record the outcome on the document as its retention mode.

#### Scenario: Platform upload declares single-use content

- **GIVEN** the platform upload adapter
- **WHEN** it constructs a normalized document
- **THEN** the declared content-acquisition capability SHALL be `single_use`

#### Scenario: A single-use source is never assigned source-only retention

- **GIVEN** a tenant whose profile requests `source_only` retention
- **WHEN** a document declaring `single_use` content acquisition is submitted
- **THEN** ingestion SHALL be rejected with a reason naming the incompatible combination
- **AND** no document row SHALL be created
- **AND** no bytes SHALL be written to any store

#### Scenario: Content resolution is decided once and recorded

- **GIVEN** a tenant profile selecting `ephemeral` retention and a `single_use` upload
- **WHEN** the document is ingested
- **THEN** the document's recorded `retention_mode` SHALL be `ephemeral`
- **AND** subsequent processing SHALL obtain bytes according to that recorded value without re-deriving it

#### Scenario: Checksum is computed by the platform over the bytes it read

- **GIVEN** a normalized document whose source declares a version string that is not a SHA-256 digest
- **WHEN** it is ingested
- **THEN** the stored checksum SHALL be the platform-computed SHA-256 of the bytes actually read
- **AND** the source-declared version SHALL be stored separately and SHALL NOT be used as the checksum

### Requirement: Platform upload is an adapter over the ingestion contract

The system SHALL implement the platform upload route as an adapter that translates an HTTP multipart request into the normalized document contract. The route SHALL retain responsibility for tenant and role resolution, the role-to-purpose policy, multipart handling, and HTTP status mapping, and SHALL NOT construct storage keys, write to any content store, insert document rows, or dispatch processing directly. Platform upload SHALL be recorded with `source_type` of `platform_upload` and the reserved `source_id` value `platform-upload`, which SHALL be stable for the life of a tenant and SHALL NOT be issued to any configured document source.

#### Scenario: Upload behaviour is unchanged

- **GIVEN** the existing document ingestion test suite
- **WHEN** it is executed against the refactored upload route, with edits to those tests confined to mock patch targets and fixture DDL and none to a `GIVEN`, a `WHEN`, or an asserted outcome
- **THEN** every test SHALL pass

#### Scenario: Uploaded documents record the reserved platform source

- **GIVEN** an authenticated tenant user
- **WHEN** they upload a document
- **THEN** the stored `source_type` SHALL be `platform_upload`
- **AND** the stored `source_id` SHALL be exactly `platform-upload`

#### Scenario: The reserved source identifier is stable across uploads

- **GIVEN** the same tenant uploading two documents at different times
- **WHEN** both rows are read
- **THEN** their `source_id` values SHALL be identical
- **AND** neither SHALL be a generated identifier

#### Scenario: The reserved identifier cannot be claimed by a configured source

- **GIVEN** an attempt to register a document source whose `source_id` is `platform-upload`
- **WHEN** the registration is written
- **THEN** it SHALL be rejected as reserved

#### Scenario: Role-to-purpose policy remains at the HTTP boundary

- **GIVEN** a user whose role is `business_user`
- **WHEN** they POST a document with `purpose=training`
- **THEN** the response SHALL have status 403
- **AND** no document row SHALL be created

#### Scenario: The route does not reference the content store

- **GIVEN** the upload route module
- **WHEN** its imports and references are inspected
- **THEN** it SHALL NOT reference any object-storage client type
- **AND** it SHALL NOT construct any storage key

### Requirement: Injectable processing dispatch

The system SHALL dispatch post-ingestion processing through an injectable dispatcher rather than a hard-coded call. The default dispatcher SHALL preserve the current in-process behaviour. The dispatcher SHALL carry only the document identity and tenant identity; it SHALL NOT carry bytes, a storage reference, or a media type, so that a dispatch is replayable from persisted state alone.

#### Scenario: Default dispatch is unchanged

- **GIVEN** an application configured with the default dispatcher
- **WHEN** a document is uploaded
- **THEN** processing SHALL be scheduled in-process exactly as before this change

#### Scenario: Dispatch carries no content

- **GIVEN** the dispatcher contract
- **WHEN** its parameters are inspected
- **THEN** they SHALL comprise the document identity and tenant identity only

#### Scenario: A test dispatcher observes dispatch without executing it

- **GIVEN** an ingestion operation configured with a recording dispatcher
- **WHEN** a document is ingested
- **THEN** the dispatcher SHALL have recorded exactly one dispatch for that document id
- **AND** no OCR SHALL have executed

### Requirement: The processing pipeline contains no source-specific behaviour

The system SHALL keep OCR, chunking, embedding, extraction, retrieval, and chatbot logic free of conditionals on document source type, source identity, or storage adapter kind. Behaviour that must differ SHALL differ through the recorded retention mode and media type only.

#### Scenario: No source conditionals exist downstream of ingestion

- **GIVEN** the OCR worker, the chunking module, the embedding service, the extraction service, the retrieval modules, and the chat API
- **WHEN** their statements are inspected
- **THEN** none SHALL branch on `source_type`, `source_id`, or a storage adapter kind

#### Scenario: Two documents from different sources follow one path

- **GIVEN** one document ingested through the platform upload adapter and one ingested by invoking the ingestion operation directly with a different source type, both with the same content and purpose
- **WHEN** both are processed
- **THEN** their text spans SHALL be equivalent
- **AND** their chunk counts SHALL be equal
