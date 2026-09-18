## ADDED Requirements

### Requirement: Retrieval excludes superseded and confirmed-missing source documents

All `Retriever` implementations SHALL unconditionally exclude chunks whose document is marked superseded by Azure Blob version replacement or non-retrievable after confirmed source-object deletion, in addition to the existing purpose restriction. This exclusion SHALL NOT be optional or controllable by the caller, and it SHALL be enforced as a database-level predicate with bound parameters.

#### Scenario: Superseded document chunks are excluded

- **GIVEN** a document superseded by a newer synchronized source version
- **WHEN** any `Retriever` implementation queries that tenant schema
- **THEN** no chunk of the superseded document SHALL be returned.

#### Scenario: Confirmed-missing document chunks are excluded

- **GIVEN** a document whose source object is confirmed missing
- **WHEN** any `Retriever` implementation queries that tenant schema
- **THEN** no chunk of that document SHALL be returned
- **AND** the document's provenance SHALL still exist.
