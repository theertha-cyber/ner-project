## Purpose

This capability covers the annotation-mode selector in the document upload flow: how users choose between Manual and Automated annotation for training uploads, when the Automated option is available, how Automated mode triggers LLM pre-labeling per uploaded document, and how the batch outcome is reported.

## Requirements

### Requirement: Annotation Mode Selector Visibility

The system SHALL render an annotation-mode selector with exactly two options, "Manual" and "Automated", within the document upload flow when `purpose` is `"training"`. The system SHALL NOT render the selector when `purpose` is `"query"`. The selector's initial selection SHALL be "Manual" unless the caller seeds a different initial selection (e.g. a deep link opened via the Automated flow's own upload entry point), and SHALL reset to "Manual" after a batch completes regardless of how it started — a mode that persisted across batches would silently send a later, unrelated batch through Automated by accident.

#### Scenario: Selector is shown for training uploads

- **GIVEN** the upload zone is rendered with `purpose: "training"`
- **WHEN** the page loads
- **THEN** an annotation-mode selector SHALL be visible with options "Manual" and "Automated"
- **AND** "Manual" SHALL be selected

#### Scenario: Selector is not shown for query uploads

- **GIVEN** the upload zone is rendered with `purpose: "query"`
- **WHEN** the page loads
- **THEN** no annotation-mode selector SHALL be rendered

#### Scenario: Selector resets to Manual after a batch completes

- **GIVEN** the user selected "Automated" and completed an upload batch
- **WHEN** the batch finishes and the upload zone returns to its idle state
- **THEN** the selector SHALL show "Manual" selected

#### Scenario: Selector seeds its initial selection from the caller

- **GIVEN** the upload zone is rendered with `purpose: "training"` and a seeded initial
  selection of "Automated"
- **WHEN** the page loads
- **THEN** the selector SHALL show "Automated" selected

#### Scenario: A seeded Automated selection still resets to Manual after a batch

- **GIVEN** the upload zone was seeded with an initial selection of "Automated" and the user
  completed an upload batch without changing it
- **WHEN** the batch finishes and the upload zone returns to its idle state
- **THEN** the selector SHALL show "Manual" selected

### Requirement: Automated Option Gating

The system SHALL disable the "Automated" option and display an explanatory hint when the tenant has zero active entity types. The system SHALL keep "Automated" enabled when the tenant has at least one active entity type, regardless of whether any entity type has `qa_examples` configured.

#### Scenario: Automated is disabled with no active entity types

- **GIVEN** the tenant has zero active entity types
- **WHEN** the upload zone is rendered with `purpose: "training"`
- **THEN** the "Automated" option SHALL be disabled
- **AND** a hint SHALL be shown directing the user to configure entity types
- **AND** "Manual" SHALL remain selectable

#### Scenario: Automated is enabled when entity types exist without QA pairs

- **GIVEN** the tenant has 2 active entity types and neither has any `qa_examples`
- **WHEN** the upload zone is rendered with `purpose: "training"`
- **THEN** the "Automated" option SHALL be enabled

### Requirement: Manual Mode Performs No Pre-labeling

The system SHALL NOT issue any pre-labeling request when "Manual" is selected. Upload behaviour in Manual mode SHALL be identical to the behaviour before this change.

#### Scenario: Manual upload issues no pre-label request

- **GIVEN** the annotation-mode selector is set to "Manual"
- **WHEN** the user uploads 3 valid training documents
- **THEN** 3 upload requests SHALL be issued
- **AND** no request SHALL be issued to any `/prelabel/llm` endpoint

### Requirement: Automated Mode Triggers Pre-labeling Per Uploaded Document

The system SHALL, after the upload batch completes and only when "Automated" is selected, issue one `POST /api/v1/documents/{doc_id}/prelabel/llm` request per successfully uploaded document, sequentially. The system SHALL NOT issue a pre-label request for a document whose upload failed or was rejected by client-side validation.

#### Scenario: Automated upload triggers one pre-label request per document

- **GIVEN** the annotation-mode selector is set to "Automated"
- **WHEN** the user uploads 3 valid training documents and all 3 uploads succeed
- **THEN** 3 pre-label requests SHALL be issued, one per uploaded document id
- **AND** each request SHALL target `POST /api/v1/documents/{doc_id}/prelabel/llm`

#### Scenario: Failed uploads are not pre-labeled

- **GIVEN** the annotation-mode selector is set to "Automated"
- **AND** a batch of 3 documents in which 1 upload fails with a server error
- **WHEN** the batch completes
- **THEN** pre-label requests SHALL be issued only for the 2 documents that uploaded successfully

#### Scenario: Client-side rejected files are not pre-labeled

- **GIVEN** the annotation-mode selector is set to "Automated"
- **AND** a batch containing 2 valid PDFs and 1 `.exe` file rejected by client-side validation
- **WHEN** the batch completes
- **THEN** pre-label requests SHALL be issued only for the 2 valid PDFs

#### Scenario: Pre-label requests are issued after uploads, not interleaved

- **GIVEN** the annotation-mode selector is set to "Automated"
- **WHEN** the user uploads 2 valid training documents
- **THEN** both upload requests SHALL complete before the first pre-label request is issued

### Requirement: Pre-labeling Failure Does Not Affect Uploads

The system SHALL treat a failed pre-label trigger as independent of the upload it relates to. A failed pre-label request SHALL NOT mark the corresponding upload as failed, SHALL NOT remove or alter the uploaded document, and SHALL NOT prevent pre-label requests for the remaining documents in the batch.

#### Scenario: One failed pre-label trigger does not stop the rest

- **GIVEN** an Automated batch of 3 successfully uploaded documents
- **AND** the pre-label request for the second document returns a 500
- **WHEN** the trigger phase runs
- **THEN** a pre-label request SHALL still be issued for the third document
- **AND** all 3 documents SHALL remain listed as successfully uploaded

#### Scenario: Pre-label failure leaves the document usable

- **GIVEN** an Automated batch in which a document uploaded successfully but its pre-label request failed
- **WHEN** the batch outcome is displayed
- **THEN** the document SHALL be reported as uploaded
- **AND** the document SHALL NOT be reported as an upload failure

### Requirement: Batch Outcome Reporting

The system SHALL report the pre-labeling trigger outcome for an Automated batch separately from the upload outcome, stating how many documents were queued for pre-labeling and identifying any documents that failed to queue. The system SHALL display trigger-phase progress while the pre-label requests are in flight.

#### Scenario: Successful Automated batch reports queued count

- **GIVEN** an Automated batch of 3 documents where all uploads and all pre-label triggers succeed
- **WHEN** the batch completes
- **THEN** the summary SHALL report 3 documents uploaded
- **AND** the summary SHALL report 3 documents queued for pre-labeling

#### Scenario: Partial trigger failure is reported distinctly

- **GIVEN** an Automated batch of 3 successfully uploaded documents where 1 pre-label trigger fails
- **WHEN** the batch completes
- **THEN** the summary SHALL report 3 documents uploaded
- **AND** the summary SHALL report 2 documents queued for pre-labeling and 1 that failed to queue
- **AND** the failed document SHALL be identified by name

#### Scenario: Trigger phase shows progress

- **GIVEN** an Automated batch of 5 successfully uploaded documents
- **WHEN** the pre-label trigger phase is running
- **THEN** a progress indicator SHALL show the current position within the trigger phase
- **AND** the indicator SHALL be distinguishable from the upload progress indicator

#### Scenario: Manual batch reports no pre-labeling outcome

- **GIVEN** a Manual batch of 3 successfully uploaded documents
- **WHEN** the batch completes
- **THEN** the summary SHALL report 3 documents uploaded
- **AND** the summary SHALL NOT mention pre-labeling
