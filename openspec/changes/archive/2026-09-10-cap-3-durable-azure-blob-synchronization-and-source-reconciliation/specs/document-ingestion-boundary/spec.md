## ADDED Requirements

### Requirement: Azure Blob sync submits through the common ingestion boundary

The Azure Blob synchronization runtime SHALL act as a configured pull source that submits each eligible object as a `NormalizedDocument` with a `SourceReference` identifying the Azure Blob source, `REOPENABLE` acquisition while its temporary working bytes exist, and `source_system` actor kind. The ingestion operation SHALL treat such documents exactly like any other pull-source document: retention is resolved from the tenant's profile, the checksum is computed over the bytes read, duplicates are identified but never rejected, and no source conditional SHALL exist downstream of ingestion.

#### Scenario: Sync document enters through the common boundary

- **GIVEN** a Blob object acquired by the sync runtime for an authenticated tenant
- **WHEN** it is submitted as a `NormalizedDocument` to `DocumentIngestionService.ingest()`
- **THEN** a document row SHALL be created with the Azure Blob source identity recorded
- **AND** no Azure-specific branch SHALL execute in OCR, NER, chunking, extraction, or retrieval.

#### Scenario: Sync documents cannot assert tenant identity

- **GIVEN** a `NormalizedDocument` submitted by the sync runtime
- **WHEN** the ingestion operation resolves the tenant
- **THEN** it SHALL use only the authenticated tenant on the document
- **AND** any tenant identifier in source metadata SHALL have no effect.
