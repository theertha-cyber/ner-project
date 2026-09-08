## ADDED Requirements

### Requirement: Tool results render into bounded LLM observations

`ToolResult` SHALL expose a rendering method producing a plain-text observation suitable for injection into an LLM conversation as a tool-role message. The rendering SHALL include enough per-result identity for a caller to follow up (document id, chunk index, score for chunk results; row content for entity results), SHALL report an error result as an explicit error observation, and SHALL truncate to a caller-supplied character limit. Rendering SHALL NOT mutate `ToolResult.results` — the full results remain available to the caller.

#### Scenario: Chunk results render with follow-up identity

- **GIVEN** a `ToolResult` from `search_documents` holding two `RetrievalResult` items
- **WHEN** it is rendered into an observation
- **THEN** the observation SHALL name each result's `document_id`, `chunk_index`, and score
- **AND** it SHALL include the chunk text

#### Scenario: Error result renders as an error observation

- **GIVEN** a `ToolResult` whose `error` is set and whose `results` are empty
- **WHEN** it is rendered
- **THEN** the observation SHALL state that the tool call failed and SHALL carry the error text

#### Scenario: Rendering respects the character limit and preserves results

- **GIVEN** a `ToolResult` whose rendered form exceeds the supplied limit
- **WHEN** it is rendered with that limit
- **THEN** the returned observation SHALL NOT exceed the limit
- **AND** `ToolResult.results` SHALL still contain every original item

### Requirement: Tool context carries remaining execution budget

`ToolContext` SHALL be able to carry a remaining wall-clock deadline for the calling loop. When a deadline is present and has already passed, a tool call SHALL return an error `ToolResult` without issuing any database query, embedding request, or reranker request.

#### Scenario: Expired deadline denies the call before any I/O

- **GIVEN** a `ToolContext` whose deadline has already passed and a spy retriever
- **WHEN** `search_documents.call` is invoked
- **THEN** the spy retriever SHALL NOT be invoked
- **AND** the returned `ToolResult` SHALL carry an error indicating the budget was exhausted

#### Scenario: Absent deadline preserves existing behaviour

- **GIVEN** a `ToolContext` constructed without a deadline
- **WHEN** any registered tool is called
- **THEN** the tool SHALL execute exactly as it does without budget support
- **AND** existing tool tests SHALL pass unmodified
