## MODIFIED Requirements

### Requirement: Fixed topology with no agentic behaviour

The graph SHALL contain at most one bounded agentic retrieval node, admitted only behind the `chat_agentic_retrieval` feature flag. The compiled graph SHALL remain acyclic: the agentic node's plan/observe cycle SHALL be internal to that node and SHALL NOT be expressed as graph edges. Conditional edges SHALL exist only for (a) the two early-exit paths that already exist — blocked question type and complexity above threshold — and (b) the selection after the guardrail node between the agentic retrieval node and the fixed parallel retrieval fan-out. The graph SHALL NOT contain planner nodes, reflection nodes, or LLM-decided routing between nodes. When `chat_agentic_retrieval` is disabled, the topology SHALL be exactly `guardrail -> (END | [sql_retrieval, retrieval]) -> ner_enrichment -> source_assembly -> prompt_assembly -> generation -> END`.

#### Scenario: Blocked question short-circuits to END

- **GIVEN** a message matching the `content_generation` blocked pattern
- **WHEN** the graph runs
- **THEN** the guardrail node routes directly to END
- **AND** the reply equals the existing `content_generation` decline string
- **AND** no retrieval, SQL, NER, agentic, or LLM call is made

#### Scenario: Excess complexity short-circuits to END when the loop is disabled

- **GIVEN** `chat_agentic_retrieval` is disabled and a message whose `GuardrailService.assess_complexity` score exceeds 3
- **WHEN** the graph runs
- **THEN** the graph routes directly to END with the existing "requires multiple lookups" reply
- **AND** no retrieval, SQL, NER, or LLM call is made

#### Scenario: Flag-off topology is unchanged

- **GIVEN** `chat_agentic_retrieval` is disabled
- **WHEN** the graph is compiled
- **THEN** its nodes and edges SHALL be identical to the pre-change topology
- **AND** the agentic node SHALL NOT be reachable

#### Scenario: Graph remains acyclic with the loop enabled

- **GIVEN** `chat_agentic_retrieval` is enabled
- **WHEN** the graph is compiled and inspected
- **THEN** the graph SHALL contain no cycle
- **AND** the only node capable of repeated tool invocation SHALL be the agentic retrieval node

### Requirement: Retrieval and model components are orchestrated, not replaced

The graph SHALL invoke the existing `HybridRetriever`, `RerankingRetriever`, `CrossEncoderReranker`, `SQLGenerator`, `EmbeddingService`, `NERClient`, and `GuardrailService` instances. Retrieval reached from the agentic node SHALL go through the shared retrieval tool layer (`ToolRegistry`, `ToolContext`), which itself delegates to those same instances and adds no retrieval, ranking, or fusion logic. No LangChain `Runnable`, `LLM`, `ChatModel`, `Embeddings`, `Retriever`, `VectorStore`, or prebuilt agent wrapper SHALL be introduced. Azure OpenAI SHALL continue to be called through `AsyncAzureOpenAI` directly, including for planner calls.

#### Scenario: No LangChain model, retriever, or agent wrappers are imported

- **GIVEN** the `src/chat_api/` tree
- **WHEN** its imports are inspected
- **THEN** no module imports `langchain_openai`, `langchain_community`, `langchain.chains`, `langchain.agents`, `langgraph.prebuilt`, or any LangChain vector-store or retriever class
- **AND** `langgraph` and `langchain_core` type imports are the only additions

#### Scenario: Retrieval stack is untouched

- **GIVEN** the implemented codebase
- **WHEN** `src/shared/retrieval/chunking.py`, `retriever.py` (`DenseRetriever`, `SparseRetriever`, `HybridRetriever`), and `models.py` are diffed against the pre-change revision
- **THEN** no retrieval, ranking, or fusion behaviour has changed

#### Scenario: Planner uses the existing client

- **GIVEN** an Azure-configured deployment
- **WHEN** the agentic node makes a planner call
- **THEN** the call SHALL be issued through the orchestrator's existing `AsyncAzureOpenAI` client
