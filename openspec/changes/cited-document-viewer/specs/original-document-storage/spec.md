## ADDED Requirements

### Requirement: A document's bytes reach a client only by passing through the application

The system SHALL deliver a document's bytes to a client only in the body of a response the application itself produces, after the application has authorized the request. The system SHALL NOT disclose to a client any value that would let it fetch those bytes from the underlying store directly — including a bucket or container name, an endpoint, a region, a credential, a pre-authorized URL, or a redirect to a storage service.

This is the consequence of the content-store boundary exposing exactly three operations. A pre-authorized URL would require a fourth, and it is unimplementable for a document whose bytes live in no platform store at all. Stating the property here makes it enforceable by test rather than held only by the absence of code.

#### Scenario: No pre-authorized URL is minted

- **GIVEN** the content-store boundary and every caller of it
- **WHEN** their operations are inspected
- **THEN** none SHALL produce a URL from which a client could fetch a document's bytes

#### Scenario: A content response carries bytes, not a location

- **GIVEN** any response by which a client obtains a document's bytes
- **WHEN** its status and headers are inspected
- **THEN** it SHALL NOT be a redirect
- **AND** it SHALL carry no header naming a storage location

#### Scenario: Authorization precedes delivery

- **GIVEN** a request for a document's bytes from a caller who may not see it
- **WHEN** the request is handled
- **THEN** no bytes SHALL be read from any store
- **AND** no bytes SHALL be transferred

### Requirement: Content resolution is shared by every reader of a document's bytes

The system SHALL resolve a document's bytes from its recorded retention mode in one place, used by every component that reads them, whether for processing or for delivery to a user. That resolution SHALL remain importable without loading the processing pipeline, so that a request path is not obliged to construct processing machinery to read a file.

#### Scenario: Processing and delivery resolve identically

- **GIVEN** a document under any retention mode
- **WHEN** its bytes are resolved for processing and for delivery to a user
- **THEN** both SHALL use the same resolution
- **AND** both SHALL read from the same store

#### Scenario: Reading bytes does not require the processing pipeline

- **GIVEN** the module that resolves content
- **WHEN** it is imported
- **THEN** the chunking and embedding components SHALL NOT be required for the import to succeed

#### Scenario: Existing callers are unaffected by the extraction

- **GIVEN** components that resolved content before this change, including the source-adapter registration performed by the pull-source integration
- **WHEN** they are exercised
- **THEN** they SHALL behave as they did before
