## ADDED Requirements

### Requirement: A document's original bytes are retrievable over HTTP

The system SHALL expose an operation that returns a document's original bytes to an authorized caller, presented for display rather than download. The bytes SHALL be resolved from the store implied by the document's recorded retention mode, using the same content resolution the processing pipeline uses, and SHALL NOT be re-derived from the storage reference's shape.

#### Scenario: A retained original is returned byte for byte

- **GIVEN** a document whose retention mode is `platform_blob` and whose bytes are in the durable store
- **WHEN** an authorized caller requests its content
- **THEN** the response SHALL carry the identical bytes that were stored
- **AND** the response SHALL indicate inline presentation rather than an attachment download

#### Scenario: The response discloses no storage detail

- **GIVEN** any successful content response
- **WHEN** its status, headers and body are inspected
- **THEN** no bucket name, container name, endpoint, region, credential or redirect to a storage service SHALL be present

#### Scenario: Resolution follows the recorded retention mode

- **GIVEN** two documents matching in every respect except that one is `platform_blob` and one is `ephemeral` with its working copy still present
- **WHEN** each document's content is requested
- **THEN** each SHALL be read from the store its recorded retention mode implies

### Requirement: Source-only content is re-read from its originating source

The system SHALL obtain the bytes of a `source_only` document by asking the adapter registered for that document's source type, and SHALL NOT require a platform copy to exist. The registry of source adapters SHALL be populated in every process that serves content, so that a document whose source is reopenable is never reported as unreadable because of how a process was started.

#### Scenario: A source-only document is viewable

- **GIVEN** a `source_only` document whose source type has a registered adapter that can supply its bytes
- **WHEN** an authorized caller requests its content
- **THEN** the bytes SHALL be returned
- **AND** no platform store SHALL have been read

#### Scenario: The serving process has its adapters registered

- **GIVEN** the content-serving application as it is started in production
- **WHEN** the registry of source adapters is inspected after startup
- **THEN** the adapter for the platform's supported pull source SHALL be present

#### Scenario: A missing adapter degrades rather than failing startup

- **GIVEN** a deployment where the adapter's own dependencies are unavailable
- **WHEN** the application starts
- **THEN** startup SHALL succeed
- **AND** a request for a `source_only` document SHALL report that its source cannot be re-read

#### Scenario: No bytes are retained after a source-only view

- **GIVEN** a `source_only` document that has just been viewed
- **WHEN** the platform's stores are inspected
- **THEN** no copy of its bytes SHALL have been written to any of them

### Requirement: An availability probe answers before bytes are transferred

The system SHALL expose an operation that reports, without transferring the document, whether the original can currently be produced, how it should be rendered, its size, and — when it cannot be produced — which of the enumerated reasons applies. The probe SHALL NOT be the only place authorization is enforced.

#### Scenario: The probe describes a viewable document

- **GIVEN** a retained, natively renderable document
- **WHEN** an authorized caller probes it
- **THEN** the response SHALL report that it is available, its render mode, and its size
- **AND** no document bytes SHALL have been read from any store

#### Scenario: The probe reports a released original without transferring anything

- **GIVEN** an `ephemeral` document whose working copy has been released
- **WHEN** an authorized caller probes it
- **THEN** the response SHALL report that it is unavailable with the reason identifying the original as not retained

#### Scenario: The probe reports that conversion is required

- **GIVEN** a retained document in a format that is not natively renderable
- **WHEN** an authorized caller probes it
- **THEN** the response SHALL report a render mode indicating the original will be converted for display

### Requirement: The served media type is determined by the system, never echoed from stored input

The system SHALL determine a content response's media type by resolving the document's type and mapping it through a closed allow-list of servable types, SHALL serve anything outside that list as an opaque binary type, and SHALL instruct the client not to re-interpret the declared type. The uploader-declared media type recorded on the document SHALL NOT be echoed to a client.

#### Scenario: A stored active-content type is not served as active content

- **GIVEN** a document whose recorded media type is a script-bearing type such as HTML
- **WHEN** its content is requested
- **THEN** the response's media type SHALL NOT be that type
- **AND** it SHALL be an opaque binary type that a browser downloads rather than renders

#### Scenario: Content-type sniffing is disabled

- **GIVEN** any content response
- **WHEN** its headers are inspected
- **THEN** they SHALL instruct the client not to infer a type other than the one declared

#### Scenario: A supported format is served as itself

- **GIVEN** a stored PDF
- **WHEN** its content is requested
- **THEN** the response's media type SHALL be the PDF media type

### Requirement: Content access applies the same visibility rules as every other answer channel

The system SHALL restrict content access to documents the requesting user may see, applying the same uploader-visibility rule the document listing and the chat answer channels apply, from one shared definition. A conversation-owned document SHALL additionally be accessible only to the user who attached it. Both checks SHALL be expressible within the tenant's own schema, without reading any control-plane table and without joining the conversations relation.

#### Scenario: A user opens a document they may see

- **GIVEN** a document the requesting non-administrative user ingested
- **WHEN** they request its content
- **THEN** the bytes SHALL be returned

#### Scenario: A user cannot open another user's document

- **GIVEN** a document ingested by a different human
- **WHEN** a non-administrative user requests its content
- **THEN** the request SHALL be refused
- **AND** no bytes SHALL be transferred

#### Scenario: A user opens their own attachment

- **GIVEN** a conversation-owned document the requesting user attached
- **WHEN** they request its content
- **THEN** the bytes SHALL be returned

#### Scenario: Another user cannot open someone's attachment

- **GIVEN** the attachment from the preceding scenario
- **WHEN** a different user of the same tenant requests its content
- **THEN** the request SHALL be refused

#### Scenario: Another tenant's document is not reachable

- **GIVEN** a document belonging to a different tenant
- **WHEN** its content is requested with this tenant's credentials
- **THEN** the request SHALL be refused as not found

#### Scenario: Authorization reaches no control-plane table

- **GIVEN** the statements executed while authorizing a content request
- **WHEN** they are inspected
- **THEN** none SHALL reference a control-plane table
- **AND** none SHALL reference the conversations relation

#### Scenario: The rule has one definition

- **GIVEN** the content routes and the document listing
- **WHEN** their visibility predicates are inspected
- **THEN** both SHALL derive from the same shared definition

### Requirement: Every failure outcome is distinct and actionable

The system SHALL distinguish the reasons a document's content cannot be returned, using a closed set of machine-readable outcomes, so that a permanent consequence of the tenant's own retention policy is never presented as a transient error. At minimum the system SHALL distinguish: the document does not exist; the caller may not see it; the original was released and will not return; the stored original is missing; the source cannot be re-read at all; the source is temporarily unreachable; and conversion for display failed.

#### Scenario: A released original is permanent and says so

- **GIVEN** an `ephemeral` document whose working copy has been released
- **WHEN** its content is requested
- **THEN** the response SHALL carry the outcome identifying the original as not retained
- **AND** that outcome SHALL be distinct from the one used for a temporarily unreachable source

#### Scenario: An unreachable source is transient and says so

- **GIVEN** a `source_only` document whose source adapter is registered but currently fails to supply bytes
- **WHEN** its content is requested
- **THEN** the response SHALL carry the outcome identifying the source as temporarily unreachable
- **AND** it SHALL be distinguishable from a document whose source has no adapter at all

#### Scenario: A missing document is not confused with a forbidden one

- **GIVEN** a document id that does not exist in the tenant
- **WHEN** content is requested for it
- **THEN** the outcome SHALL identify it as not found
- **AND** SHALL differ from the outcome returned for a document that exists but may not be seen

#### Scenario: Existing derived data survives a failed view

- **GIVEN** any document whose content request fails for any reason
- **WHEN** the document is inspected afterwards
- **THEN** its status, its text spans and its chunks SHALL be unchanged
- **AND** its recorded retention mode SHALL be unchanged

### Requirement: Content access is observable without recording document content

The system SHALL record content-access outcomes using enumerated categories and counts only. No log record, span attribute or metric label SHALL contain a filename, a storage reference, document bytes, or an extracted value.

#### Scenario: An access is recorded as shape

- **GIVEN** a content request that succeeds
- **WHEN** the emitted telemetry is inspected
- **THEN** it SHALL identify the retention mode and an enumerated outcome
- **AND** it SHALL contain no filename, storage reference or document content

#### Scenario: Metric labels are finite and declared

- **GIVEN** the metric family recording content access
- **WHEN** its label keys and value sets are inspected
- **THEN** every value set SHALL be finite and enumerated at declaration
- **AND** no label SHALL carry a media type drawn from stored input
