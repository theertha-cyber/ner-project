## ADDED Requirements

### Requirement: Touched OCR failure paths emit safe structured error classes

The document-processing failure paths touched by this change SHALL record only a declared finite error class and correlation metadata in logs, document error fields, metrics, and traces. They SHALL NOT emit tracebacks, interpolated exception messages, or exception objects from storage, provider, or model calls; a driver or provider error SHALL be represented by its type name and the finite class it maps to.

#### Scenario: OCR failure records a class, not a payload

- **GIVEN** a document whose chunking, embedding, or terminal processing step raises
- **WHEN** the failure is recorded
- **THEN** the stored and logged record SHALL contain only the finite error class and correlation metadata
- **AND** no traceback SHALL be printed and no exception message SHALL be interpolated.
