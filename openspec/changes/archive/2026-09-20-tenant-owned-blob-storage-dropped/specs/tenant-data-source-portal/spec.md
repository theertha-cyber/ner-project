## ADDED Requirements

### Requirement: Content-store connections are administrable in the portal

The portal SHALL present an `azure_blob_content_store` connection through the same connection collection, detail route, and lifecycle panel as every other approved provider, enforcing its closed schema (account, container, optional prefix, `connection_string_ref`) with inline validation. Its values SHALL be write-only and absent after save, and the detail view SHALL never present configuration values, secret-reference values, endpoint details, connection strings, or provider diagnostics.

Because a content-store connection has no synchronization, its detail route SHALL omit the sync-activity section and the "Sync now" control, as PostgreSQL connections already do.

#### Scenario: A content-store connection is created through the standard form

- **GIVEN** an authenticated tenant administrator on the connection collection
- **WHEN** the administrator creates an `azure_blob_content_store` draft
- **THEN** the form SHALL enforce account, container, optional prefix, and a secret reference
- **AND** the saved values SHALL be absent from the rendered detail view

#### Scenario: The content-store detail route omits sync activity

- **GIVEN** an `azure_blob_content_store` connection
- **WHEN** its detail route renders
- **THEN** no sync-activity section and no "Sync now" control SHALL be present

#### Scenario: A failed write test surfaces only a safe reason class

- **GIVEN** a content-store connection whose secure test failed because the credential cannot write
- **WHEN** the administrator views the lifecycle panel
- **THEN** the panel SHALL show a finite safe reason class
- **AND** SHALL NOT display a provider error payload, container name, or credential

### Requirement: Tenant users can see where their content is stored

The portal SHALL present, to an authenticated tenant administrator, a safe indication of which content store currently serves the tenant's uploads — platform-operated storage or the tenant's own container — derived from the tenant's executable content-store selection rather than from its recorded selection alone. Where a tenant has content recorded against more than one backend, the portal SHALL indicate that earlier content remains in its original location and SHALL NOT imply that activation relocated it.

The indication SHALL name no container, account, endpoint, or credential.

#### Scenario: An active content store is reflected in the portal

- **GIVEN** a tenant with an active `azure_blob_content_store` connection and an executable content-store selection
- **WHEN** a tenant administrator views the data-source area
- **THEN** the portal SHALL indicate that new uploads are stored in the tenant's own storage

#### Scenario: A recorded but unexecutable selection does not claim tenant storage

- **GIVEN** a tenant recording `content_store_adapter = tenant_azure_blob` with no active content-store connection
- **WHEN** a tenant administrator views the data-source area
- **THEN** the portal SHALL indicate that uploads are stored in platform storage

#### Scenario: Earlier content is not implied to have moved

- **GIVEN** a tenant that activated a content-store connection after documents already existed
- **WHEN** a tenant administrator views the data-source area
- **THEN** the portal SHALL indicate that content stored before activation remains in its original location

#### Scenario: The indication discloses no storage configuration

- **GIVEN** any tenant with an active content-store connection
- **WHEN** the storage indication renders
- **THEN** it SHALL NOT contain a container name, account name, endpoint, or credential

### Requirement: Content routes present a safe state when the tenant store is unavailable

When a tenant's content store is unreachable, the portal SHALL present a safe, finite unavailable state on the document and chat-attachment surfaces rather than a generic failure or an empty success, SHALL keep the rest of the portal usable, and SHALL NOT display a provider error payload or any storage configuration.

#### Scenario: Upload surfaces show a safe unavailable state

- **GIVEN** a tenant whose content store is unreachable
- **WHEN** a tenant user opens the document upload surface
- **THEN** the portal SHALL present a finite safe unavailable state
- **AND** SHALL NOT present the upload as having succeeded

#### Scenario: The rest of the portal stays usable

- **GIVEN** the tenant from the preceding scenario
- **WHEN** the user navigates to a surface that does not read document content
- **THEN** that surface SHALL render normally
