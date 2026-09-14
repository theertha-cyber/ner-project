## ADDED Requirements

### Requirement: Retrieval tool contract

The system SHALL define a `RetrievalTool` structural protocol exposing `name` (stable snake_case identifier), `description` (natural-language purpose used by an LLM to choose the tool), `args_schema` (a JSON Schema object describing accepted arguments), and `async call(args: dict, context: ToolContext) -> ToolResult`. Every tool implementation SHALL validate `args` against `args_schema` before executing and SHALL reject unknown or malformed arguments without executing a query.

#### Scenario: Tool exposes a complete contract

- **GIVEN** any registered retrieval tool
- **WHEN** its `name`, `description`, and `args_schema` are read
- **THEN** `name` SHALL be a non-empty snake_case string
- **AND** `description` SHALL be a non-empty string
- **AND** `args_schema` SHALL be a JSON Schema object with `type: "object"` and a `properties` map

#### Scenario: Invalid arguments are rejected before execution

- **GIVEN** a tool whose `args_schema` requires a string `query`
- **WHEN** `call({"query": 123}, context)` is invoked
- **THEN** the tool SHALL return a `ToolResult` with `error` set and `results` empty
- **AND** no database query SHALL be executed

#### Scenario: Unknown argument keys are rejected

- **GIVEN** a tool whose `args_schema` declares only `query` and `top_k`
- **WHEN** `call({"query": "invoice total", "schema": "tenant_other"}, context)` is invoked
- **THEN** the tool SHALL return a `ToolResult` with `error` set
- **AND** no database query SHALL be executed

### Requirement: Tool result envelope

The system SHALL return every tool invocation as a `ToolResult` carrying `tool_name`, `results` (a list of typed domain objects — `RetrievalResult` for document tools, structured entity rows for entity tools), `latency_ms`, `degraded` (boolean, true when the tool completed via a fallback path such as reranker failure), and `error` (a string, or `None` on success). A `ToolResult` SHALL be returned for both success and failure — a tool SHALL NOT raise on retrieval failure.

#### Scenario: Successful invocation reports metadata

- **GIVEN** a seeded tenant schema containing chunks matching the query
- **WHEN** `search_documents.call({"query": "<matching text>"}, context)` completes
- **THEN** the `ToolResult` SHALL have `error is None`, `degraded is False`, a positive `latency_ms`, and a non-empty `results` list
- **AND** every item in `results` SHALL be a `RetrievalResult`

#### Scenario: Retrieval failure returns an error result rather than raising

- **GIVEN** the underlying retriever raises an exception
- **WHEN** the tool is invoked
- **THEN** the call SHALL return a `ToolResult` with `error` set to a non-empty string and `results` empty
- **AND** no exception SHALL propagate to the caller

#### Scenario: Degraded retrieval is flagged

- **GIVEN** `search_documents` is backed by a `RerankingRetriever` whose reranker is unavailable
- **WHEN** the tool is invoked and the retriever falls back to unreranked candidates
- **THEN** the `ToolResult` SHALL have `degraded is True`
- **AND** `results` SHALL still contain the fallback candidates

### Requirement: Tenant scope is caller-supplied, never argument-supplied

The system SHALL carry `tenant_id`, `schema`, and the database session in a `ToolContext` constructed by the calling application from authenticated request state. Tool `args_schema` SHALL NOT declare `schema`, `tenant_id`, `purpose`, or any other tenancy or purpose-restriction parameter, so no LLM-generated or user-generated argument can widen the tool's data scope.

#### Scenario: Tool schemas expose no tenancy parameters

- **GIVEN** every tool in the registry
- **WHEN** its `args_schema.properties` keys are inspected
- **THEN** none SHALL be `schema`, `tenant_id`, `tenant`, or `purpose`

#### Scenario: Tool queries the context's schema only

- **GIVEN** two tenant schemas each containing chunks matching the same query
- **WHEN** a tool is invoked with a `ToolContext` for the first schema
- **THEN** every returned result SHALL originate from the first schema
- **AND** no result SHALL originate from the second schema

#### Scenario: Purpose restriction survives the tool layer

- **GIVEN** a tenant schema containing both `purpose='training'` and `purpose='query'` chunks matching the query
- **WHEN** any document retrieval tool is invoked with any argument values
- **THEN** no returned result SHALL come from a `purpose='training'` chunk

### Requirement: Document retrieval tools

The system SHALL provide a `search_documents` tool that executes the application's configured `Retriever` (dense, hybrid, or reranking composition) for a query and returns `RetrievalResult` objects, and a `lookup_document` tool that performs the same retrieval restricted to a single `document_id` via the existing `metadata_filter` mechanism. Neither tool SHALL implement its own retrieval, ranking, or fusion logic.

#### Scenario: search_documents delegates to the configured retriever

- **GIVEN** a `ToolContext` whose configured retriever is a spy implementing the `Retriever` protocol
- **WHEN** `search_documents.call({"query": "q"}, context)` is invoked
- **THEN** the spy's `retrieve` SHALL be called exactly once with `query == "q"`
- **AND** the `ToolResult.results` SHALL be the spy's returned results

#### Scenario: lookup_document restricts results to one document

- **GIVEN** a tenant schema with chunks from two documents, both matching the query
- **WHEN** `lookup_document.call({"query": "q", "document_id": "<doc-a>"}, context)` is invoked
- **THEN** every returned `RetrievalResult` SHALL have `document_id == "<doc-a>"`

#### Scenario: top_k argument bounds the result count

- **GIVEN** a tenant schema with more matching chunks than the requested `top_k`
- **WHEN** `search_documents.call({"query": "q", "top_k": 3}, context)` is invoked
- **THEN** `ToolResult.results` SHALL contain at most 3 items

#### Scenario: top_k is capped against caller-supplied inflation

- **GIVEN** a configured maximum tool `top_k`
- **WHEN** a tool is invoked with a `top_k` exceeding that maximum
- **THEN** the effective `top_k` SHALL be clamped to the maximum
- **AND** the invocation SHALL NOT fail

### Requirement: Entity retrieval tool

The system SHALL provide a `search_entities` tool that answers a natural-language question against extracted entity data using the existing SQL generation and execution path, returning structured rows. The tool SHALL be callable without constructing a `RAGOrchestrator` or importing `chat_api`, and SHALL apply the same SQL validation and tenant-scoping guardrails as the chat SQL source.

#### Scenario: Entity tool returns structured rows

- **GIVEN** a tenant schema containing extracted entities
- **WHEN** `search_entities.call({"query": "how many invoices"}, context)` is invoked
- **THEN** `ToolResult.results` SHALL be a list of row mappings
- **AND** `error` SHALL be `None`

#### Scenario: Entity tool is importable from shared code

- **GIVEN** the codebase after this change
- **WHEN** the module defining `search_entities` is imported
- **THEN** the import SHALL NOT transitively import `src.chat_api`

#### Scenario: Entity tool preserves SQL guardrails

- **GIVEN** a query whose generated SQL would be rejected by the existing SQL validation layer
- **WHEN** `search_entities` is invoked with that query
- **THEN** the SQL SHALL NOT be executed
- **AND** the `ToolResult` SHALL have `error` set

### Requirement: Tool registry and schema export

The system SHALL provide a `ToolRegistry` that registers tools by `name`, rejects duplicate names, resolves a tool by name, lists all registered tools, and exports all tool contracts as a list of JSON tool-calling definitions in the `{"type": "function", "function": {"name", "description", "parameters"}}` shape accepted by OpenAI-compatible and LangChain tool binding.

#### Scenario: Registry resolves tools by name

- **GIVEN** a registry with `search_documents`, `lookup_document`, and `search_entities` registered
- **WHEN** `registry.get("search_documents")` is called
- **THEN** the returned object SHALL be the registered `search_documents` tool

#### Scenario: Unknown tool name is an explicit error

- **GIVEN** a populated registry
- **WHEN** `registry.get("delete_documents")` is called
- **THEN** an explicit lookup error SHALL be raised naming the unknown tool

#### Scenario: Duplicate registration is rejected

- **GIVEN** a registry that already contains `search_documents`
- **WHEN** another tool with `name == "search_documents"` is registered
- **THEN** registration SHALL fail with an explicit error

#### Scenario: Exported schemas are tool-calling shaped

- **GIVEN** a populated registry
- **WHEN** `registry.export_schemas()` is called
- **THEN** each entry SHALL have `type == "function"`
- **AND** `function.name` SHALL equal the tool's `name`, `function.description` the tool's `description`, and `function.parameters` the tool's `args_schema`

### Requirement: Chat runtime behaviour is unchanged by the tool layer

The system SHALL introduce the tool layer additively: the LangGraph chat flow, `RAGOrchestrator`, prompt assembly, citation enrichment, and all HTTP contracts SHALL behave identically to before this change.

#### Scenario: Existing chat tests pass unmodified

- **GIVEN** the codebase after this change
- **WHEN** the existing chat and retrieval test suites are run without modification
- **THEN** they SHALL pass

#### Scenario: Graph nodes do not depend on the tool layer

- **GIVEN** the codebase after this change
- **WHEN** `src/chat_api/graph/nodes.py` is inspected
- **THEN** it SHALL NOT import or invoke the tool layer
