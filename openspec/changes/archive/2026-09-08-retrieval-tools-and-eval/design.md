## Context

Retrieval today is a fixed pipeline: `retrieval_node` (`src/chat_api/graph/nodes.py:87`) calls `orchestrator.retriever.retrieve(message, session, schema, top_k=settings.retrieval_top_k, ...)` once per chat turn. The retriever itself is a composition — `RerankingRetriever(HybridRetriever(DenseRetriever, SparseRetriever), CrossEncoderReranker)` — assembled at construction time and parameterized entirely from the process-global `settings` object (`retrieval_top_k`, `reranker_enabled`, `rerank_candidate_count`). SQL entity retrieval lives on a separate path, `RAGOrchestrator._sql_source`, reachable only through the orchestrator instance.

Two gaps block the roadmap. First, the agentic loop needs retrieval as *selectable, argument-validated, self-describing tools*, not one hard-wired call. Second, nothing in the repo measures retrieval quality: existing tests assert RRF fuses and that reranker failure falls back, but no test says the right chunk comes back for a real question. Every retrieval tuning decision so far — `RRF_K = 60`, `CANDIDATE_MULTIPLIER = 3`, `rerank_candidate_count = 20`, the `ms-marco-MiniLM-L-6-v2` reranker choice — was argued, not measured.

Constraints shaping this design: tenant isolation is schema-based and must not be reachable from LLM-supplied arguments (ADR-001); the chat pipeline's three-source structure and guardrails are fixed (ADR-007); the local and CI environment is CPU-only, so reranking is slow and a full eval matrix is minutes, not seconds; embeddings cost money and drift, so a default eval run must not call the provider.

## Goals / Non-Goals

**Goals:**

- A tool contract over existing retrieval that the agentic loop can bind directly, with tenant scope structurally unreachable from tool arguments.
- A reproducible, offline, deterministic retrieval evaluation over a committed golden set, producing standard IR metrics.
- Side-by-side comparison of named retrieval configurations in one run, so tuning is measured.
- A committed baseline plus a regression gate that a retrieval-touching change can be run against.
- Zero behaviour change to the live chat pipeline.

**Non-Goals:**

- Wiring tools into the LangGraph flow or any agentic control flow — that is `agentic-retrieval-loop`.
- Answer-quality evaluation (faithfulness, groundedness, LLM-as-judge). This change measures *retrieval*, not generation.
- Adopting an external eval framework (`ragas`, `trulens`, `promptfoo`).
- Query rewriting, HyDE, multi-query expansion, or any new retrieval strategy.
- Changes to ingestion, chunking, embeddings, or the vector index.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 Tenant Data Isolation via Separate Database Schemas | Per-tenant PostgreSQL schemas, `search_path` enforcement, prefix-isolated object storage | Tool execution must derive `schema` from authenticated request context only; `schema`/`tenant_id` must not appear in any tool argument schema. Eval fixtures must be seeded into a disposable test schema, never a real tenant's. |
| ADR-003 Per-Tenant Model Serving Topology | Shared serving pool, tenant-aware routing, on-demand model loading | The reranker is reached over HTTP through `model_serving`; eval configurations that enable reranking depend on that service being up, so eval must degrade explicitly (record `degraded`) rather than silently score a non-reranked run as reranked. |
| ADR-004 OpenSpec SDD Governance | Proposal → design → spec → tasks → evidence gates | Metrics and the golden set are themselves the evidence artifact for future retrieval changes; the report format must be durable and diffable. |
| ADR-007 Chatbot Architecture with Full RAG and Guardrails | Three-source RAG (SQL + pgvector + NER); SQL validation layer; citation enforcement; P95 < 10s | `search_entities` must route through the existing SQL validation layer, not a parallel SQL path. The tool layer must not become a fourth retrieval source or bypass guardrails. |

ADR-002 is partially superseded by ADR-008; neither constrains this design (both concern base-model selection and default-model behaviour).

## Decisions

### Decision 1: Tools wrap existing retrievers; they contain no retrieval logic

**Choice:** `RetrievalTool` is a thin adapter — argument validation, `ToolContext` scope injection, invocation of the already-composed `Retriever` / SQL path, and result envelope construction. `search_documents` calls whatever `Retriever` the `ToolContext` carries; it does not know whether that is dense, hybrid, or reranking.

**Rationale:** Retrieval logic has just been stabilized across two changes. Duplicating any of it into a tool creates a second path that will drift from the chat path, which defeats the purpose of measuring the tool path. Keeping tools ignorant of composition also means the eval matrix varies configuration by handing the tool a differently-composed retriever, with no tool-side branching.

**Alternatives considered:**
- Tools own retrieval and the graph calls tools — a bigger, riskier change that alters live chat behaviour, which this proposal explicitly excludes.
- One `retrieve` tool with a `strategy` argument — puts strategy selection in LLM-controlled arguments, expanding the attack and error surface for no gain; strategy is an operator decision, not a per-query one.

### Decision 2: Tenant scope travels in `ToolContext`, never in `args`

**Choice:** `ToolContext` is a frozen dataclass holding `tenant_id`, `schema`, `session`, `retriever`, `jwt_token`, and configuration limits. It is constructed by the calling application from authenticated request state. Tool `args_schema` is restricted to query-shaped parameters (`query`, `top_k`, `document_id`), and validation rejects unknown keys.

**Rationale:** ADR-001 makes schema selection a security boundary. Once an LLM chooses tool arguments, anything in `args_schema` is attacker-influenceable through prompt content in retrieved documents. Structural exclusion beats validation: a parameter that does not exist cannot be injected. The existing hard-coded `purpose = 'query'` restriction in the retriever SQL stays where it is and is inherited for free.

**Alternatives considered:**
- Accept `schema` in args and validate it against the JWT — one missed validation is a cross-tenant leak; there is no upside.
- Bind schema by constructing a fresh tool object per request — allocates a registry per request and makes schema export request-dependent; context injection gives the same isolation with a static registry.

### Decision 3: Retrieval configuration becomes an explicit override object resolved ahead of `settings`

**Choice:** Introduce a small `RetrievalConfig` (`top_k`, `reranker_enabled`, `rerank_candidate_count`) that retrievers accept optionally at construction. Resolution order is: explicit call argument → instance config → global `settings`. Defaults are byte-identical to today when no override is passed.

**Rationale:** `RerankingRetriever.retrieve` reads `settings.reranker_enabled` mid-call (`src/shared/retrieval/retriever.py:178`). The eval matrix must run reranking-off and reranking-on configurations in the same process; the only way to do that today is to monkeypatch a global, which is order-dependent, leaks between runs, and is unusable under any future concurrency. Making config an object also gives the agentic loop a way to run a cheap first pass and an expensive second pass in one turn.

**Alternatives considered:**
- Monkeypatch `settings` per configuration in the runner — leaks state, cannot run configurations concurrently, and enshrines a global as the tuning interface.
- Separate processes per configuration — sidesteps the leak but multiplies startup and model-load cost per configuration on CPU, and still leaves the underlying global-coupling defect in place.

### Decision 4: Extract the SQL entity path out of `RAGOrchestrator` into a shared service

**Choice:** Move the query-generation-plus-execution body of `RAGOrchestrator._sql_source` into a service under `src/shared/retrieval/` (or a shared services module) that both the orchestrator and `search_entities` call. `_sql_source` becomes a delegating wrapper so the graph is untouched.

**Implementation note (resolved during apply):** A pure move was not taken. `tests/test_chat_api_sql.py::TestSQLPrompt::test_prompt_includes_document_join_instruction` asserts on `inspect.getsource` of `src.chat_api.services.sql_generator` itself, so relocating `SQLGenerator`'s body would have broken that unmodified test. The alternative below was used instead: `ToolContext` carries an injected `sql_search` callable; `entity_tools.py` never imports `SQLGenerator` or `src.chat_api`, and `RAGOrchestrator._sql_source` is unchanged. Whoever constructs a `ToolContext` for entity search (the eval harness, and later `agentic-retrieval-loop`) supplies `SQLGenerator().generate_and_execute` as that callable.

**Rationale:** `src/shared` must not import `src/chat_api` — that inverts the dependency direction and would make every service that touches shared retrieval pull in the chat API. The alternative (duplicating SQL generation) violates ADR-007's single validated SQL path.

**Alternatives considered:**
- Put the tool layer in `chat_api` instead of `shared` — the eval harness and future services would then depend on `chat_api`; wrong direction for the same reason.
- Inject a callable into `ToolContext` so the tool never imports the SQL path — workable and cheap, but leaves the entity path unreachable to non-chat callers and makes the tool's guardrail behaviour depend on whoever supplies the callable. Kept as fallback if extraction proves larger than expected.

### Decision 5: Golden set is a synthetic, committed corpus with precomputed embeddings

**Choice:** `tests/fixtures/retrieval_eval/` holds `corpus.jsonl` (synthetic documents authored for eval), `golden_set.jsonl` (queries with graded judgments), `embeddings.json` (precomputed query and chunk vectors, tagged with the embedding model name), and `baseline.json`. The runner seeds the corpus into a disposable test schema, uses a fixture embedding service reading `embeddings.json`, and refuses to run when the recorded model name does not match the configured one.

**Rationale:** Determinism is the whole point — a metric that moves because the embedding API drifted or because a different tenant's data was sampled cannot gate anything. Synthetic content also keeps tenant data out of the repository, which ADR-001's isolation posture demands. Committing vectors costs repository size but buys free, offline, reproducible runs.

**Alternatives considered:**
- Live embedding calls every run — per-run cost, network dependency in CI, and silent metric drift when the model version changes. Retained as an opt-in flag for validating against a new embedding model.
- Label against a real tenant's documents — better external validity, but the corpus cannot be committed, so nobody else can reproduce a run.

### Decision 6: Metrics implemented in-repo, no eval framework dependency

**Choice:** Implement `recall@k`, `precision@k`, `MRR@k`, `nDCG@k` in `eval/metrics.py` as pure functions over `(ranked_results, judgments)`.

**Rationale:** These are a few dozen lines of well-specified arithmetic with no ambiguity, and pure functions are unit-testable without a database. `ragas` and similar frameworks target generation quality, pull in LLM calls and a large dependency tree, and would make the deterministic-offline goal harder, not easier.

**Alternatives considered:**
- `ragas` — LLM-judged, non-deterministic, heavy; also out of scope since this change does not evaluate answers.
- `pytrec_eval` — correct and standard, but a C extension dependency for four formulas.

### Decision 7: Eval executes through the tool layer, not directly against retrievers

**Choice:** The runner invokes `search_documents` from the registry.

**Rationale:** It makes the harness the tool layer's first real consumer, so the contract is exercised before the agentic loop depends on it, and it guarantees the measured path is the path the agent will take. Measuring `HybridRetriever` directly while the agent calls a tool wrapper would leave the wrapper unmeasured.

**Alternatives considered:**
- Call retrievers directly — simpler, but measures a path nothing in production uses once the agentic loop lands.

### Decision 8: Regression gate is marker-gated and advisory-by-default

**Choice:** A pytest marker (alongside the existing `verification` marker convention) plus `scripts/run_retrieval_eval.py`. Not part of default `pytest`. Failure compares aggregate `recall@5` and `nDCG@5` against `baseline.json` with an explicit tolerance.

**Rationale:** The gate needs Postgres + pgvector and, for reranking configurations, `model_serving`. Wiring that into every PR run would make the whole suite fragile and slow on CPU. Gating on demand keeps the signal trustworthy; making it blocking on retrieval-touching PRs is a later, cheap follow-up once the baseline has proven stable.

**Alternatives considered:**
- Blocking on every PR — flaky infrastructure dependency turns a quality gate into an ignored red build.
- Report-only, never failing — nobody reads reports; a threshold that can fail is what makes a baseline meaningful.

## Risks / Trade-offs

- [Golden set is synthetic, so metrics may not transfer to real tenant documents] → Treat metrics as *relative* signal for comparing configurations, not as an absolute quality claim; document this in the report header. Revisit with a held-out real-document set once one tenant consents.
- [Small golden set (~30–50 queries) makes aggregate metrics noisy; a 0.02 tolerance may be within noise] → Report per-query deltas alongside aggregates so a regression can be traced to specific queries; set the initial tolerance after observing run-to-run variance on the committed fixtures, not before.
- [Committed embeddings go stale when the embedding model changes] → The model-name mismatch check fails the run loudly rather than scoring against wrong vectors; regenerating is a scripted, reviewable commit.
- [Extracting the SQL path out of `RAGOrchestrator` could change chat behaviour] → Extraction is pure code movement with `_sql_source` delegating; existing chat tests (`test_chat_api_rag.py`, `test_chat_api_sql.py`, `test_langgraph_parity.py`) must pass unmodified as the gate. If extraction turns out to be non-mechanical, fall back to Decision 4's injected-callable alternative.
- [`RetrievalConfig` threading touches every retriever signature and could regress live retrieval] → Resolution falls back to `settings` when no override is given, so the no-override path is unchanged; covered by a spec scenario asserting existing suites pass unmodified.
- [Tool layer ships with no production consumer and could rot before the agentic loop lands] → The eval harness is a real consumer exercised by the gate, so the contract stays honest.
- [Reranking configurations depend on `model_serving` being up; a silent fallback would score a non-reranked run as reranked] → `ToolResult.degraded` propagates into the report; a configuration whose runs were degraded is labelled as such and excluded from baseline comparison.

## Migration Plan

1. Land `RetrievalConfig` resolution with `settings` fallback; existing suites are the parity gate. Independently revertable.
2. Land the tool layer (`base`, `document_tools`, `registry`, schema export) with unit tests using fakes — no database required.
3. Extract the SQL entity path; add `search_entities`. Chat suites are the parity gate.
4. Author the corpus and golden set; generate `embeddings.json` once via the opt-in live path and commit it.
5. Land metrics as pure functions with unit tests (no infrastructure).
6. Land the runner, report, and CLI; execute the matrix; commit `baseline.json` from the chosen default configuration's run.
7. Enable the marker-gated regression test.

**Rollback:** Every step is additive except step 1 (signature-compatible) and step 3 (pure extraction). Reverting the change removes fixtures and new modules; live chat is unaffected at every step because nothing in `src/chat_api/graph/` is modified.

## Open Questions

1. Whether step 3's extraction is mechanical enough to keep in this change, or whether the injected-callable fallback (Decision 4 alternative) is the shipping shape. Resolve while reading `RAGOrchestrator._sql_source`.
2. Repository-size tolerance for `embeddings.json` — 1536-dim float vectors for a corpus of a few hundred chunks plus ~50 queries is on the order of a few MB as JSON. Consider a compressed binary format if that is unacceptable.
3. Tolerance value for the regression gate — must be derived from observed run-to-run variance, which cannot be known until the first runs exist.
4. Whether the golden set should include known-negative queries (questions with no relevant chunk) to measure over-retrieval, given the current metrics all assume at least one relevant chunk.
5. No in-force ADR needs revisiting for this change. If measurement later shows the three-source fan-out in ADR-007 is the wrong default under an agentic loop, that supersession belongs to `agentic-retrieval-loop`, not here.
