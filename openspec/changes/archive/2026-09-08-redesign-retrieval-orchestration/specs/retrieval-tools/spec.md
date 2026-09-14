## ADDED Requirements

### Requirement: Single semantic retrieval capability with internal scope

The system SHALL expose exactly one semantic retrieval capability, named `semantic_retrieval`, that accepts a natural-language `query`, an optional `top_k`, and an optional `scope` object. The `scope` object SHALL select the search extent internally: `{"type": "tenant"}` searches all of the requesting tenant's chunks and is the default when `scope` is omitted; `{"type": "document", "document_ids": [...]}` restricts the search to the listed documents. The scope shape SHALL be extensible to further scope types without adding a new capability. Callers SHALL NOT be able to select a scope outside the requesting tenant.

#### Scenario: Tenant scope is the default

- **GIVEN** a `semantic_retrieval` invocation with only a `query`
- **WHEN** the capability executes
- **THEN** the retriever SHALL be called with no metadata filter
- **AND** the results SHALL be ranked chunks from across the tenant's corpus

#### Scenario: Document scope restricts results

- **GIVEN** a tenant with chunks in documents `D1` and `D2`
- **WHEN** `semantic_retrieval` is invoked with `scope = {"type": "document", "document_ids": ["D1"]}`
- **THEN** every returned chunk SHALL have `document_id == "D1"`

#### Scenario: Document scope accepts multiple documents

- **GIVEN** a tenant with chunks in documents `D1`, `D2`, and `D3`
- **WHEN** `semantic_retrieval` is invoked with `scope = {"type": "document", "document_ids": ["D1", "D2"]}`
- **THEN** returned chunks SHALL come only from `D1` and `D2`
- **AND** the document id values SHALL be passed as bound query parameters, never interpolated into SQL text

#### Scenario: Unknown scope type is rejected

- **GIVEN** an invocation with `scope = {"type": "galaxy"}`
- **WHEN** arguments are validated
- **THEN** the invocation SHALL be rejected without issuing a query
- **AND** the error SHALL name the unsupported scope type

#### Scenario: top_k is clamped to the configured maximum

- **GIVEN** a configured maximum top-K
- **WHEN** `semantic_retrieval` is invoked with a `top_k` above that maximum
- **THEN** the retriever SHALL be called with the configured maximum

#### Scenario: Retriever failure returns an error result, not an exception

- **GIVEN** a retriever that raises
- **WHEN** `semantic_retrieval` is invoked
- **THEN** the invocation SHALL return an error result carrying the failure message
- **AND** no exception SHALL propagate to the orchestrator

### Requirement: Exactly two retrieval capabilities are exposed

The default registry SHALL contain exactly two capabilities: `semantic_retrieval` and `structured_retrieval`. `structured_retrieval` SHALL answer a natural-language question against extracted structured entity data, delegating SQL generation, validation, and execution to the injected `sql_search` callable. No capability SHALL be registered that differs from another only by search scope.

#### Scenario: Registry exposes two capabilities

- **GIVEN** the default registry
- **WHEN** its exported schemas are inspected
- **THEN** they SHALL contain exactly the names `semantic_retrieval` and `structured_retrieval`

#### Scenario: Capability descriptions state retrieval intent

- **GIVEN** the exported schema for each capability
- **WHEN** its description is inspected
- **THEN** the description SHALL describe what kind of information the capability retrieves
- **AND** SHALL NOT describe the underlying implementation or index

## REMOVED Requirements

### Requirement: Document retrieval tools

**Reason**: `search_documents` and `lookup_document` both perform semantic retrieval and differ only in search scope. Exposing both forced the orchestration layer to reason about retrieval implementations rather than retrieval intent.

**Migration**: Both are replaced by `semantic_retrieval`. `search_documents(query, top_k)` becomes `semantic_retrieval(query, top_k)`; `lookup_document(query, document_id, top_k)` becomes `semantic_retrieval(query, top_k, scope={"type": "document", "document_ids": [document_id]})`. Callers holding tool names directly (the eval harness) must be updated; there are no external API consumers of these names.

### Requirement: Entity retrieval tool

**Reason**: Renamed to align the capability vocabulary with the orchestration layer.

**Migration**: `search_entities` is renamed to `structured_retrieval`. Arguments and behaviour are unchanged.
