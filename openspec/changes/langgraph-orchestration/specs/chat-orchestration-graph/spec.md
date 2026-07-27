## ADDED Requirements

### Requirement: Graph-based chat execution flow

The chat RAG flow SHALL be executed by a LangGraph `StateGraph` compiled once at module import. `RAGOrchestrator.execute` SHALL delegate to that compiled graph and SHALL retain its existing signature `(message, session, schema, tenant_id, jwt_token=None, conversation_context=None) -> tuple[str, list[Source | Citation]]` so that `src/chat_api/api/v1/chat.py` and `src/chat_api/api/v1/public.py` require no call-site change.

#### Scenario: Chat request produces the same response through the graph

- **GIVEN** a tenant with indexed document chunks and a stubbed Azure OpenAI chat client
- **WHEN** a `POST /api/v1/chat` request is handled
- **THEN** the response body matches the pre-migration `ChatResponse` field-for-field — `reply`, `sources`, `conversation_id`, `disclaimer`
- **AND** the LLM receives a prompt string byte-identical to the pre-migration prompt for the same inputs

#### Scenario: Widget endpoint uses the same graph

- **GIVEN** a valid widget API key
- **WHEN** a `POST` to the public widget chat endpoint is handled
- **THEN** the same compiled graph executes with `jwt_token` absent from state
- **AND** the `WidgetChatResponse` payload is unchanged from pre-migration

#### Scenario: Existing test suite passes unmodified

- **GIVEN** the test files `tests/test_chat_api_rag.py`, `tests/test_chat_api_guardrails.py`, `tests/test_hybrid_retrieval.py`, `tests/test_reranking_retriever.py`, `tests/test_reranker_client.py`, `tests/test_chat_api_conversations.py`, `tests/test_chat_api_widget.py`
- **WHEN** the suite runs against the migrated code with no edits to those files
- **THEN** every test passes

### Requirement: Per-request state isolation

Per-request values — user message, tenant id, schema name, JWT token, conversation context, database session — SHALL be carried in graph state, and SHALL NOT be stored as mutable attributes on any module-level singleton. `RerankingRetriever` SHALL NOT hold a `jwt_token` attribute; the token SHALL be supplied as a call argument.

#### Scenario: Concurrent requests from different tenants do not share authorization context

- **GIVEN** two concurrent chat requests, one from tenant A with token A and one from tenant B with token B
- **WHEN** both flows reach the reranking stage
- **THEN** the rerank call made on behalf of tenant A carries token A and the call for tenant B carries token B
- **AND** no interleaving of the two requests can cause one tenant's token to be used for the other's rerank call

#### Scenario: Reranker Protocol matches its implementation

- **GIVEN** the `Reranker` Protocol in `src/shared/retrieval/reranker.py`
- **WHEN** `CrossEncoderReranker` is checked against it
- **THEN** the Protocol declares `jwt_token: str | None = None` as a parameter of `rerank`
- **AND** the existing `SpyReranker` test double in `tests/test_reranking_retriever.py` satisfies the Protocol without modification

### Requirement: Explicit stage outcomes in state

Each retrieval-producing node SHALL record its outcome in graph state rather than collapsing failures into an empty list. State SHALL distinguish "stage produced zero results" from "stage raised an error", and the error SHALL be retained for logging.

#### Scenario: Vector retrieval failure is distinguishable from an empty corpus

- **GIVEN** a tenant schema where `document_chunks` does not exist
- **WHEN** the retrieval node runs
- **THEN** graph state carries an error value for the retrieval stage
- **AND** the flow continues to LLM generation exactly as it does today, producing the same reply the pre-migration code produced for that failure

#### Scenario: Empty retrieval is not reported as an error

- **GIVEN** a tenant schema with a valid but empty `document_chunks` table
- **WHEN** the retrieval node runs
- **THEN** graph state carries an empty result list and no error value

### Requirement: Node-level observability

Every graph node SHALL emit one structured log record on completion containing the node name, the tenant id, elapsed milliseconds, and a count of the primary artifact it produced (candidates retrieved, chunks after rerank, SQL rows, sources emitted). Reranking SHALL log whether the reranker returned a reordering or fell back to the unranked candidates.

#### Scenario: Retrieval trace is emitted for a successful chat turn

- **GIVEN** a chat request that reaches LLM generation
- **WHEN** the graph completes
- **THEN** log records exist for each executed node with node name, tenant id, duration, and output count

#### Scenario: Reranker fallback is visible

- **GIVEN** a model_serving instance that returns a non-200 status for `/internal/v1/rerank`
- **WHEN** the reranking node runs
- **THEN** a log record states that reranking fell back to unranked candidates
- **AND** the node returns the candidate list truncated to `top_k`, matching pre-migration behaviour

### Requirement: Fixed topology with no agentic behaviour

The graph in this change SHALL be a fixed DAG. Conditional edges SHALL exist only for the two early-exit paths that already exist in `RAGOrchestrator.execute` — blocked question type and complexity above threshold. The graph SHALL NOT contain loops, tool-calling nodes, planner nodes, reflection nodes, or LLM-decided routing.

#### Scenario: Blocked question short-circuits to END

- **GIVEN** a message matching the `content_generation` blocked pattern
- **WHEN** the graph runs
- **THEN** the guardrail node routes directly to END
- **AND** the reply equals the existing `content_generation` decline string
- **AND** no retrieval, SQL, NER, or LLM call is made

#### Scenario: Excess complexity short-circuits to END

- **GIVEN** a message whose `GuardrailService.assess_complexity` score exceeds 3
- **WHEN** the graph runs
- **THEN** the graph routes directly to END with the existing "requires multiple lookups" reply
- **AND** no retrieval, SQL, NER, or LLM call is made

### Requirement: Retrieval and model components are orchestrated, not replaced

The graph SHALL invoke the existing `HybridRetriever`, `RerankingRetriever`, `CrossEncoderReranker`, `SQLGenerator`, `EmbeddingService`, `NERClient`, and `GuardrailService` instances. No LangChain `Runnable`, `LLM`, `ChatModel`, `Embeddings`, `Retriever`, or `VectorStore` wrapper SHALL be introduced. Azure OpenAI SHALL continue to be called through `AsyncAzureOpenAI` directly.

#### Scenario: No LangChain model or retriever wrappers are imported

- **GIVEN** the migrated `src/chat_api/` tree
- **WHEN** its imports are inspected
- **THEN** no module imports `langchain_openai`, `langchain_community`, `langchain.chains`, or any LangChain vector-store or retriever class
- **AND** `langgraph` and `langchain_core` type imports are the only additions

#### Scenario: Retrieval stack is untouched

- **GIVEN** the migrated codebase
- **WHEN** `src/shared/retrieval/chunking.py`, `retriever.py` (`DenseRetriever`, `SparseRetriever`, `HybridRetriever`), and `models.py` are diffed against pre-migration
- **THEN** the only change is the removal of `RerankingRetriever`'s `jwt_token` attribute and the corresponding parameter threading
