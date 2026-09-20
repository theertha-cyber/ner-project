## ADDED Requirements

### Requirement: A tenant content store is a distinct write-capable connection

The system SHALL provide a distinct approved connection provider, `azure_blob_content_store`, for a tenant-owned container the platform writes into. It SHALL be separate from the read-only `azure_blob` document-source provider, and an active `azure_blob` source connection SHALL NOT make a tenant content store executable. Its non-secret configuration SHALL be a closed key set of `account`, `container`, and an optional `prefix`, and its credential SHALL be supplied as a secret reference matching the declared `<scheme>://<path>` grammar, never as a literal value.

A tenant's `azure_blob_content_store` connection and its `azure_blob` source connection SHALL NOT share a secret reference, and SHALL NOT name the same container.

#### Scenario: A read-only source connection does not make a content store executable

- **GIVEN** a tenant with an active `azure_blob` source connection and `content_store_adapter = tenant_azure_blob`
- **WHEN** the content-store selection is resolved
- **THEN** it SHALL NOT be executable
- **AND** the tenant's bytes SHALL continue to be served by the platform content store

#### Scenario: A literal credential is rejected

- **GIVEN** an `azure_blob_content_store` draft whose credential field holds a literal connection string
- **WHEN** the draft is saved
- **THEN** the system SHALL reject it with a finite safe validation error naming the field
- **AND** the offending value SHALL NOT be echoed in the response

#### Scenario: An unknown configuration key is rejected

- **GIVEN** an `azure_blob_content_store` draft carrying a configuration key outside the declared set
- **WHEN** the draft is saved
- **THEN** the system SHALL reject it with a finite safe validation error naming the key

#### Scenario: Sharing a secret reference with the source connection is rejected

- **GIVEN** a tenant with an active `azure_blob` source connection using secret reference R
- **WHEN** the tenant administrator saves an `azure_blob_content_store` draft using R
- **THEN** the system SHALL reject it with a finite safe code indicating the reference is shared across purposes

#### Scenario: Naming the source container is rejected

- **GIVEN** a tenant with an active `azure_blob` source connection on container C
- **WHEN** the tenant administrator saves an `azure_blob_content_store` draft naming container C
- **THEN** the system SHALL reject it with a finite safe validation error

### Requirement: One container holds durable and working bytes under separate prefixes

The system SHALL write a tenant's durable originals and its working copies into the single configured container, under distinct prefixes derived inside the storage adapter. The prefix rule SHALL NOT be exposed to any caller, and no caller SHALL construct, predict, or parse a key. Every key the platform writes SHALL be scoped to the owning tenant.

#### Scenario: Key construction stays inside the adapter

- **GIVEN** the tenant blob content-store adapter
- **WHEN** bytes are put for a tenant
- **THEN** the object key SHALL be constructed inside the adapter
- **AND** the key SHALL be scoped to that tenant

#### Scenario: The caller learns nothing about the container

- **GIVEN** a successful put through the tenant blob content store
- **WHEN** the returned storage reference is inspected by a caller
- **THEN** it SHALL NOT be required to contain a container name, account name, or prefix for any caller to use it

### Requirement: Bounded working-copy lifetime is enforced by the tenant's container

The system SHALL require that the tenant's container carry a lifecycle rule scoped to the working prefix that expires objects within the configured working-copy lifetime, so that an abandoned working copy is removed without depending on the platform application reaching a terminal state. The connection test SHALL verify the rule is present and correctly scoped, and activation SHALL be refused with a finite safe reason class when it is absent.

#### Scenario: A missing lifecycle rule blocks activation

- **GIVEN** an `azure_blob_content_store` draft whose container carries no lifecycle rule on the working prefix
- **WHEN** the tenant administrator tests the connection
- **THEN** the outcome SHALL be failed with a finite safe reason class naming the missing expiry rule
- **AND** activation SHALL be blocked

#### Scenario: A correctly scoped rule passes

- **GIVEN** an `azure_blob_content_store` draft whose container expires objects under the working prefix within the configured lifetime
- **WHEN** the tenant administrator tests the connection
- **THEN** the expiry check SHALL pass

### Requirement: Pause and retirement stop content routing without deleting tenant objects

Pausing a tenant's active `azure_blob_content_store` connection SHALL stop the tenant content store being executable, and content operations for documents recorded against it SHALL fail with a finite safe error rather than falling back to platform storage. Retiring it without an activated same-container replacement SHALL have the same effect and SHALL be terminal for access to those documents' bytes.

Pausing and retiring SHALL NOT delete, overwrite, or expire any object in the tenant's container. The response SHALL state that content remaining in the tenant's container is the customer's to delete. Replacing the connection with one naming the same container SHALL restore access to documents already recorded against it.

#### Scenario: Pausing stops new writes from routing to the tenant container

- **GIVEN** a tenant with an active content-store connection
- **WHEN** the tenant administrator pauses it and a document is uploaded
- **THEN** the upload SHALL be served by the platform content store
- **AND** the new document's recorded backend kind SHALL be the platform store's kind

#### Scenario: Retirement leaves tenant objects untouched

- **GIVEN** a tenant with documents stored in its own container
- **WHEN** the tenant administrator retires the content-store connection with confirmation
- **THEN** no delete SHALL be executed against the tenant's container
- **AND** the response SHALL state that remaining content is the customer's to delete

#### Scenario: Same-container replacement restores access

- **GIVEN** a retired content-store connection and documents recorded against the tenant blob store kind
- **WHEN** a replacement connection naming the same container is activated
- **THEN** those documents' bytes SHALL be readable again
