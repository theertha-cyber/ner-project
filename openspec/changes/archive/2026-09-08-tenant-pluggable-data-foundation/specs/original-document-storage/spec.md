## ADDED Requirements

### Requirement: Document content store boundary

The system SHALL define one application-owned boundary for writing, reading, and removing a document's bytes, exposing exactly three operations: put bytes for a given tenant and document, returning an opaque storage reference or nothing; open the bytes at a previously returned reference; and delete the bytes at a reference. The boundary SHALL NOT expose bucket names, container names, endpoints, regions, credentials, or the key-construction rule to any caller. The term for a value returned by this boundary is `storage_reference`; `blob_path` names only the existing physical column in which it is persisted until the named `document-metadata-column-reconciliation` change renames it.

#### Scenario: Storing returns an opaque reference

- **GIVEN** a configured content store
- **WHEN** a document's bytes are put
- **THEN** the operation SHALL return a storage reference
- **AND** opening that reference SHALL yield the identical bytes

#### Scenario: Deleting removes the bytes

- **GIVEN** bytes previously put and a reference to them
- **WHEN** delete is called with that reference
- **THEN** a subsequent open of that reference SHALL NOT return the bytes
- **AND** delete SHALL be safe to call again with the same reference

#### Scenario: The boundary exposes no storage configuration

- **GIVEN** the boundary's contract definition
- **WHEN** its operations and types are inspected
- **THEN** they SHALL NOT name a bucket, container, endpoint, region, or credential

### Requirement: The storage reference is an outcome, never an input

The system SHALL derive a document's storage reference from the content store's return value. No caller SHALL compute, predict, or supply a storage reference before a put is attempted.

#### Scenario: The upload path does not precompute a key

- **GIVEN** the ingestion operation and the upload route
- **WHEN** their statements are inspected
- **THEN** neither SHALL construct a storage path or key
- **AND** the persisted storage reference SHALL be exactly the value the store returned

#### Scenario: Key construction lives inside the platform adapter

- **GIVEN** the platform MinIO adapter
- **WHEN** bytes are put for a tenant
- **THEN** the object key SHALL be constructed inside the adapter
- **AND** the key SHALL be scoped to that tenant's prefix

### Requirement: Retention mode is explicit and determines content resolution

The system SHALL record on every document an explicit `retention_mode` with exactly one of three values, and SHALL NOT infer retention from a NULL storage reference:

- `platform_blob` — the original is written to the durable content store and retained. Bytes are reopened from that store for the life of the document.
- `ephemeral` — the original is written to a working content store under a bounded lifetime, used to complete processing, and deleted when the document reaches a terminal processing state or the lifetime expires, whichever comes first. No durable original is retained.
- `source_only` — no bytes are written to any platform store. Bytes are reopened by asking the originating source adapter for them.

The system SHALL resolve the retention mode from the tenant's integration profile at ingestion time, SHALL record it on the document, and SHALL use the recorded value — never a re-derivation — for every subsequent content resolution.

#### Scenario: Retention mode is stored, not inferred

- **GIVEN** a document ingested under `ephemeral` retention whose working copy has since been deleted
- **WHEN** the document row is read
- **THEN** `retention_mode` SHALL be `ephemeral`
- **AND** the value SHALL NOT change as a result of the storage reference becoming unusable

#### Scenario: Platform retention reopens from the durable store

- **GIVEN** a document ingested under `platform_blob` retention
- **WHEN** processing obtains its bytes
- **THEN** the bytes SHALL be read from the durable content store using the recorded storage reference

#### Scenario: Retention follows tenant configuration, not source type

- **GIVEN** two tenants, one profile selecting `platform_blob` and one selecting `ephemeral`, both receiving a platform upload
- **WHEN** each uploads the same document
- **THEN** the first document's `retention_mode` SHALL be `platform_blob`
- **AND** the second document's `retention_mode` SHALL be `ephemeral`

#### Scenario: An adapter cannot override retention

- **GIVEN** a source adapter that asserts a retention preference in its source metadata
- **WHEN** a document from it is ingested
- **THEN** the retention actually applied SHALL be the one resolved from the tenant's integration profile
- **AND** the value carried in source metadata SHALL have no effect

### Requirement: Ephemeral retention uses a bounded working copy

For a document ingested under `ephemeral` retention, the system SHALL write the bytes to a working content store configured separately from the durable store, SHALL record the resulting reference for the duration of processing, and SHALL delete the working copy when the document reaches `processed` or `failed`. The working store SHALL be configured with an independent expiry so that an abandoned working copy is removed without depending on the application. Once the working copy is deleted, the document's persisted storage reference SHALL be NULL.

This is an explicit privacy statement, not an omission: under `ephemeral` retention the document's bytes **do** transit platform-operated storage for the duration of processing. A tenant that cannot permit that transit cannot use platform upload, and SHALL be configured with `source_only` retention and a reopenable source instead.

#### Scenario: An ephemeral document processes end to end

- **GIVEN** a tenant profile selecting `ephemeral` retention
- **WHEN** a PDF is uploaded and processing completes
- **THEN** the document status SHALL be `processed`
- **AND** text spans SHALL exist for it

#### Scenario: The working copy is deleted on success

- **GIVEN** the document from the preceding scenario
- **WHEN** processing reaches `processed`
- **THEN** the working copy SHALL have been deleted from the working store
- **AND** the document's persisted storage reference SHALL be NULL

#### Scenario: The working copy is deleted on failure

- **GIVEN** a corrupt document ingested under `ephemeral` retention
- **WHEN** processing reaches `failed`
- **THEN** the working copy SHALL have been deleted from the working store
- **AND** the document's persisted storage reference SHALL be NULL

#### Scenario: Nothing is written to the durable store under ephemeral retention

- **GIVEN** a tenant profile selecting `ephemeral` retention and an instrumented durable content store
- **WHEN** a document is uploaded and processed
- **THEN** no put SHALL have been performed against the durable store
- **AND** no open SHALL have been performed against the durable store

#### Scenario: An ephemeral query document becomes retrievable

- **GIVEN** an `ephemeral` document with `purpose='query'`
- **WHEN** processing completes and semantic retrieval runs for text it contains
- **THEN** chunks from that document SHALL be retrievable
- **AND** their content SHALL match the document's extracted text

#### Scenario: A NULL reference is not reported as a failure

- **GIVEN** a successfully processed `ephemeral` document whose working copy has been deleted
- **WHEN** its metadata is retrieved through the documents API
- **THEN** its status SHALL be `processed`
- **AND** no error message SHALL be present

### Requirement: Reprocessability is bounded by retention mode and stated, never silently assumed

The system SHALL treat a document as reprocessable only while its bytes remain resolvable. A `platform_blob` document SHALL be reprocessable for the life of the document. An `ephemeral` document SHALL be reprocessable only until its working copy is deleted. A `source_only` document SHALL be reprocessable only while its originating source can be asked for the bytes. A reprocess request for a document whose bytes are no longer resolvable SHALL fail explicitly, SHALL leave the document's existing derived data intact, and SHALL NOT delete text spans or chunks.

#### Scenario: Reprocessing a retained document succeeds

- **GIVEN** a processed `platform_blob` document
- **WHEN** it is reprocessed
- **THEN** the bytes SHALL be read from the durable store
- **AND** processing SHALL succeed

#### Scenario: Reprocessing an expired ephemeral document fails explicitly

- **GIVEN** a processed `ephemeral` document whose working copy has been deleted
- **WHEN** reprocessing is requested
- **THEN** the request SHALL fail with a reason identifying the bytes as unresolvable
- **AND** the document's existing text spans and chunks SHALL be unchanged
- **AND** the document's status SHALL NOT become `failed`

#### Scenario: Retries within the processing window reuse the recorded resolution

- **GIVEN** an `ephemeral` document whose first processing attempt raised a transient error before reaching a terminal state
- **WHEN** processing is attempted again while the working copy still exists
- **THEN** the bytes SHALL be obtained from the working copy
- **AND** processing SHALL be able to succeed

### Requirement: No consumer parses the storage reference

The system SHALL treat the storage reference as opaque outside the store that produced it. No component SHALL derive a file extension, media type, tenant identity, document identity, or any other semantic value from it.

#### Scenario: OCR does not read the storage reference to choose an extractor

- **GIVEN** the OCR processing path
- **WHEN** its statements are inspected
- **THEN** it SHALL NOT split, parse, or pattern-match the storage reference
- **AND** the extractor selection SHALL be derived from the document's resolved media type

#### Scenario: Processing succeeds for a document with no durable reference

- **GIVEN** an `ephemeral` document being processed for the first time
- **WHEN** the processing worker runs
- **THEN** the bytes SHALL be obtained through the recorded content resolution
- **AND** processing SHALL succeed
