## MODIFIED Requirements

### Requirement: Retention mode is explicit and determines content resolution

The system SHALL record on every document an explicit `retention_mode` with exactly one of three values, and SHALL NOT infer retention from a NULL storage reference:

- `platform_blob` — the original is written to the durable content store and retained. Bytes are reopened from that store for the life of the document.
- `ephemeral` — the original is written to a working content store under a bounded lifetime, used to complete processing, and deleted when the document reaches a terminal processing state or the lifetime expires, whichever comes first. No durable original is retained.
- `source_only` — no bytes are written to any platform store. Bytes are reopened by asking the originating source adapter for them.

Retention mode SHALL determine *whether and for how long* an original is retained. It SHALL NOT determine *which backend* retains it: the durable and working content stores are resolved per tenant under `tenant-content-store-routing`, and for a tenant routed to its own container both are that container. The name `platform_blob` therefore denotes platform-*managed* retention, not platform-*operated* storage.

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

#### Scenario: Retention mode does not select the backend

- **GIVEN** two tenants both selecting `platform_blob` retention, one routed to its own container and one served by the platform content store
- **WHEN** each uploads a document
- **THEN** both documents' `retention_mode` SHALL be `platform_blob`
- **AND** the first document's bytes SHALL be in the tenant's container
- **AND** the second document's bytes SHALL be in platform storage

### Requirement: Ephemeral retention uses a bounded working copy

For a document ingested under `ephemeral` retention, the system SHALL write the bytes to a working content store configured separately from the durable store, SHALL record the resulting reference for the duration of processing, and SHALL delete the working copy when the document reaches `processed` or `failed`. The working store SHALL be configured with an independent expiry so that an abandoned working copy is removed without depending on the application. Once the working copy is deleted, the document's persisted storage reference SHALL be NULL.

"Configured separately" SHALL mean that the expiry applies to working copies and to nothing else. It SHALL NOT mandate a particular physical separation: the platform content store realises it as a separate bucket, and a tenant-routed content store realises it as a separate prefix carrying a prefix-scoped expiry rule. In both cases the expiry SHALL be enforced by the object store rather than by the application reaching a terminal state.

This is an explicit privacy statement, not an omission: under `ephemeral` retention the document's bytes **do** transit storage for the duration of processing. For a tenant served by the platform content store, that storage is platform-operated, and a tenant that cannot permit that transit SHALL be configured either with `source_only` retention and a reopenable source, or with a tenant-routed content store under `tenant-content-store-routing`, in which case the transit occurs entirely within the tenant's own container.

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

#### Scenario: A routed tenant's ephemeral bytes never reach platform storage

- **GIVEN** a tenant routed to its own container and selecting `ephemeral` retention, with an instrumented platform working store
- **WHEN** a document is uploaded and processed
- **THEN** no put SHALL have been performed against the platform working store
- **AND** the working copy SHALL have been written to and deleted from the tenant's container

## ADDED Requirements

### Requirement: A storage reference is accompanied by its producing store

The system SHALL treat a document's storage reference as meaningful only together with the recorded kind of the content store that produced it, as governed by `content-store-backend-attribution`. No component SHALL resolve bytes from a storage reference alone once more than one content-store backend is registered.

#### Scenario: Resolving bytes requires both values

- **GIVEN** a document whose storage reference is recorded without a content-store kind
- **WHEN** its bytes are resolved
- **THEN** the operation SHALL fail explicitly
- **AND** SHALL NOT guess a backend

#### Scenario: The boundary still exposes no storage configuration

- **GIVEN** the content-store contract definition after a second backend exists
- **WHEN** its operations and types are inspected
- **THEN** they SHALL NOT name a bucket, container, endpoint, region, or credential
