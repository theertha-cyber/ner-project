## ADDED Requirements

### Requirement: Formats a browser cannot render are converted to PDF for display

The system SHALL convert an original whose format no browser renders natively into a PDF for viewing, so that the client has exactly one rendering path. The formats requiring conversion SHALL be exactly those the platform accepts at ingestion that are neither PDF nor a browser-renderable image. The conversion SHALL preserve the document's page structure so that a page reference into the original remains meaningful in the rendition.

#### Scenario: A word-processor document is viewable as PDF

- **GIVEN** a retained `.docx` document
- **WHEN** an authorized caller requests its content for display
- **THEN** the response SHALL be a PDF
- **AND** its text content SHALL correspond to the original's

#### Scenario: A spreadsheet-style upload is viewable as PDF

- **GIVEN** a retained `.csv` document
- **WHEN** its content is requested for display
- **THEN** the response SHALL be a PDF

#### Scenario: A multi-page image is viewable as PDF

- **GIVEN** a retained multi-page TIFF
- **WHEN** its content is requested for display
- **THEN** the response SHALL be a PDF
- **AND** it SHALL contain one page per frame of the original

#### Scenario: Natively renderable formats are not converted

- **GIVEN** a retained PDF and a retained PNG
- **WHEN** each is requested for display
- **THEN** neither SHALL be converted
- **AND** each SHALL be served in its own format

### Requirement: A rendition is derived, and never replaces the original

The system SHALL treat a converted PDF as a derived artifact. The original's bytes, its recorded media type, its checksum and its storage reference SHALL be unchanged by any conversion, and a request for the original as a download SHALL yield the original rather than the rendition.

#### Scenario: Conversion does not alter the document record

- **GIVEN** a `.docx` document that has been converted for display
- **WHEN** its document record is inspected
- **THEN** its recorded media type, checksum and storage reference SHALL be unchanged

#### Scenario: The original remains obtainable

- **GIVEN** the document from the preceding scenario
- **WHEN** the original is requested as a download rather than for display
- **THEN** the original bytes SHALL be returned in the original format

### Requirement: A rendition is persisted only where the original is already persisted

The system SHALL persist a rendition only for a document whose retention mode permits its original to be stored durably. For a document under ephemeral or source-only retention, conversion SHALL be performed per request and the rendition SHALL NOT be written to any platform store.

#### Scenario: No rendition is stored for a released original

- **GIVEN** an `ephemeral` document
- **WHEN** it is converted for display
- **THEN** no rendition SHALL be written to any platform store

#### Scenario: No rendition is stored for source-only content

- **GIVEN** a `source_only` document
- **WHEN** it is converted for display
- **THEN** no rendition SHALL be written to any platform store
- **AND** the tenant's choice that no bytes reside in platform storage SHALL still hold afterwards

#### Scenario: A rendition may be reused for a retained document

- **GIVEN** a `platform_blob` document that has been converted once
- **WHEN** it is requested for display again
- **THEN** the system MAY serve the previously produced rendition
- **AND** the bytes served SHALL be equivalent to converting the original again

#### Scenario: Deleting the document removes its rendition

- **GIVEN** a `platform_blob` document with a stored rendition
- **WHEN** the document is hard-deleted
- **THEN** the rendition SHALL also be removed

### Requirement: Conversion is bounded and its failure is reported, never masked

The system SHALL bound a conversion in time and in input size, SHALL report a conversion that fails or exceeds its bound as a distinct outcome, and SHALL NOT fall back to presenting a different document, an empty document, or the unconverted bytes under a PDF media type. A conversion failure SHALL NOT alter the document's processing status.

#### Scenario: A corrupt original fails explicitly

- **GIVEN** a document whose stored bytes cannot be parsed by the converter
- **WHEN** it is requested for display
- **THEN** the response SHALL carry the outcome identifying conversion as failed
- **AND** no PDF SHALL be returned

#### Scenario: A conversion that exceeds its time bound is reported as such

- **GIVEN** a document whose conversion does not complete within the configured bound
- **WHEN** it is requested for display
- **THEN** the conversion SHALL be abandoned
- **AND** the response SHALL report a bounded-conversion failure rather than waiting indefinitely

#### Scenario: Unconverted bytes are never mislabelled

- **GIVEN** any conversion failure
- **WHEN** the response is inspected
- **THEN** it SHALL NOT contain the original's unconverted bytes carrying a PDF media type

#### Scenario: A failed conversion leaves the document untouched

- **GIVEN** a processed document whose conversion fails
- **WHEN** the document is inspected afterwards
- **THEN** its processing status SHALL still be `processed`
- **AND** its text spans and chunks SHALL be unchanged

### Requirement: Conversion runs only where its toolchain belongs

The system SHALL confine the document-conversion toolchain to the runtime image of the service that performs conversion, and SHALL NOT add it to the runtime image of services that do not convert documents.

#### Scenario: Only the converting service carries the toolchain

- **GIVEN** the runtime image definitions for the platform's services
- **WHEN** they are inspected
- **THEN** the conversion toolchain SHALL be present only in the image used by the converting service

#### Scenario: Conversion is observable as shape

- **GIVEN** a conversion that runs
- **WHEN** the emitted telemetry is inspected
- **THEN** it SHALL record an enumerated source-format category, an enumerated outcome and a duration
- **AND** it SHALL contain no filename and no document content
