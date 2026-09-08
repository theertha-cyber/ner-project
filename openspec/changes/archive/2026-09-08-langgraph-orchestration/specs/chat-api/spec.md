## ADDED Requirements

### Requirement: Per-request authorization context isolation

The chat API SHALL NOT carry per-request authorization context on shared service instances. The `RAGOrchestrator` and every collaborator it holds (`SQLGenerator`, `EmbeddingService`, `NERClient`, `RerankingRetriever`, `CrossEncoderReranker`, `GuardrailService`) SHALL be free of request-scoped mutable attributes. Request-scoped values SHALL be passed as call arguments or carried in execution state.

#### Scenario: Orchestrator singleton holds no request-scoped state

- **GIVEN** the module-level `orchestrator` instances in `src/chat_api/api/v1/chat.py` and `src/chat_api/api/v1/public.py`
- **WHEN** a chat request completes
- **THEN** no attribute of the orchestrator or of any object it holds has been assigned a value derived from that request
- **AND** the tenant id, JWT token, schema name, and database session are visible only in the per-request execution state

#### Scenario: Interleaved tenant requests do not leak tokens

- **GIVEN** requests for tenant A and tenant B executing concurrently in one process
- **WHEN** tenant B's flow reaches the reranking stage between tenant A's retrieval and tenant A's reranking
- **THEN** tenant A's rerank request carries tenant A's Authorization header
- **AND** tenant B's rerank request carries tenant B's Authorization header
