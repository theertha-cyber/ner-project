## ADDED Requirements

### Requirement: Every stored document records which content store produced its reference

The system SHALL persist, alongside a document's storage reference, the kind of the content store that produced it, taken from the value that store declares as its own kind. The recorded kind SHALL be written in the same operation that records the storage reference. A document that carries no storage reference — `source_only` retention, or an `ephemeral` document whose working copy has been deleted — SHALL carry no meaningful backend kind, and its absence SHALL NOT be treated as an error.

The recorded kind SHALL NOT be derived from the document's key, from the reference string, or from the tenant's current profile selection.

#### Scenario: A platform-stored document records the platform kind

- **GIVEN** a tenant served by the platform content store
- **WHEN** a document is stored
- **THEN** the document's recorded content-store kind SHALL be the platform store's declared kind

#### Scenario: A tenant-stored document records the tenant kind

- **GIVEN** a tenant with an active content-store connection
- **WHEN** a document is stored
- **THEN** the document's recorded content-store kind SHALL be the tenant blob store's declared kind

#### Scenario: The kind is recorded with the reference, not afterwards

- **GIVEN** a document being ingested
- **WHEN** its row is first persisted
- **THEN** the storage reference and the content-store kind SHALL both be present
- **AND** neither SHALL require a subsequent write to become correct

### Requirement: Reads and deletes route by the recorded kind, never by current configuration

The system SHALL resolve the content store for an `open` or a `delete` from the kind recorded on that document, and SHALL NOT re-derive it from the tenant's integration profile, its active connections, or its data-plane mode at the time of the operation. A change to a tenant's content-store selection SHALL NOT change where an already-stored document's bytes are looked for.

When a document's recorded kind names a store the system cannot resolve — for example a tenant-backed document whose connection has been retired — the operation SHALL fail with a finite, safe error. The system SHALL NOT attempt the operation against a different backend.

#### Scenario: Activation does not orphan existing documents

- **GIVEN** a tenant with documents stored in the platform content store
- **WHEN** that tenant activates a content-store connection and a pre-existing document's bytes are opened
- **THEN** the bytes SHALL be read from the platform content store
- **AND** they SHALL be the identical bytes originally stored

#### Scenario: New documents after activation read from the tenant container

- **GIVEN** the tenant from the preceding scenario
- **WHEN** a new document is stored and then opened
- **THEN** the bytes SHALL be read from that tenant's container

#### Scenario: Retiring a connection does not redirect existing documents to the platform store

- **GIVEN** a tenant with documents recorded against the tenant blob store kind
- **WHEN** its content-store connection is retired and one of those documents is opened
- **THEN** the operation SHALL fail with a finite safe error
- **AND** the platform content store SHALL NOT be read in its place

#### Scenario: Deletion follows the recorded kind

- **GIVEN** a conversation with attachments stored while a tenant content-store connection was active
- **WHEN** the conversation is deleted
- **THEN** the underlying objects SHALL be deleted from the tenant's container
- **AND** no delete SHALL be attempted against the platform content store for those documents

#### Scenario: A mixed-backend tenant resolves each document independently

- **GIVEN** a tenant with some documents recorded against the platform store kind and others against the tenant blob store kind
- **WHEN** each document's bytes are opened
- **THEN** each SHALL be read from the store named by its own recorded kind

### Requirement: Existing documents carry a backfilled backend kind

The system SHALL treat every document stored before this capability existed as having been produced by the platform content store, and SHALL backfill the recorded kind accordingly so that no stored document lacks one. The backfill SHALL NOT alter any document's storage reference, retention mode, or status.

#### Scenario: Pre-existing documents are readable after the change

- **GIVEN** documents stored before the backend kind was recorded
- **WHEN** the backfill has been applied and their bytes are opened
- **THEN** each SHALL be read from the platform content store
- **AND** the bytes SHALL be identical to those originally stored

#### Scenario: The backfill changes nothing else

- **GIVEN** a document stored before the backend kind was recorded
- **WHEN** its row is compared before and after the backfill
- **THEN** its storage reference, retention mode, and status SHALL be unchanged
