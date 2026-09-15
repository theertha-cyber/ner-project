## Context

CAP-4 (ADR-013) delivered the guards for external PostgreSQL chat:

- **Contract lifecycle** — `src/shared/external_postgres/contract.py` validates, versions, fingerprints, and publishes contracts. Gateway routes live in `src/gateway/api/v1/external_pg_contracts.py`; the portal upload is in `components/data-sources/contracts.tsx`.
- **Schema index** — `index.py` writes one `entry_text` row per relation into `tenant_<id>.external_pg_schema_index` at publish. Nothing reads it (`fetch_entries` has no caller).
- **Execution** — `connector.execute_external_query` runs drift gate → AST validation (`validator.py`) → `clamp_limit` → `ExternalDatabase.execute`. `AzureExternalDatabase` is asyncpg in a read-only transaction with `SET LOCAL statement_timeout`.
- **Capability** — `capability.resolve_external_capability(session, tenant_id)` returns the published contract when the tenant has an active `azure_postgresql` connection.
- **Unwired** — `src/chat_api/services/external_postgres_chat.external_chat_answer(session, tenant_id, statement, params, database)` expects a finished statement. It has no production caller.

Platform chat is a LangGraph flow (`src/chat_api/graph/nodes.py`):

- `orchestrator_node` makes one planner call over `orchestrator.tool_registry.export_schemas()`.
- `retrieval_execution_node` runs the plan through `execute_plan` with a per-call `ToolContext`.
- `_accumulate` in `src/shared/retrieval/orchestrator.py` splits evidence into `chunks` and `sql_results` by capability name.
- `prompt_assembly_node` → `ContextAssembler.assemble`.
- `source_assembly_node` serializes admitted SQL rows into `Source(source_type="sql", value=json.dumps(rows))`. That source is persisted with the chat message.

Constraints:

- The validator rejects every inline literal, including `LIMIT n`, plus subqueries, CTEs, set operations, and window functions.
- The drift gate compares **all** live columns the role can see for each contract relation.
- The demo target is a real Azure Database for PostgreSQL. The connection goes through the existing TLS-handshake connection test to reach `active`. The password is an `env://` secret reference that chat-api resolves.
- The demo is tomorrow, so the design reuses existing seams over new abstractions.

## Goals / Non-Goals

**Goals:**

- A tenant admin uploads a contract with descriptions, publishes it, and a chat user gets correct answers from the tenant's Azure Postgres.
- Every generated statement passes the existing validator and drift gate. No new execution path.
- External row values never reach platform storage, logs, or metrics.
- Tenants without an executable external capability see no behavior change.

**Non-Goals:**

- Embedding/vector retrieval over the schema index (deferred; whole-contract context instead).
- Platform-storage schema externalization (the `global_postgres` JSON idea).
- Loosening the validator (subqueries, `NOT EXISTS`, window functions).
- Portal UI for editing descriptions in place (JSON file upload only).
- Multi-connection tenants (the resolver already picks the one active `azure_postgresql` connection).
- Streaming-specific changes. The SSE path shares the graph and gets the behavior for free.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001-tenant-data-isolation | Per-tenant schemas; tenant context from authenticated state only | Contract, index, and capability lookups keyed by the JWT-resolved tenant; tool args carry no tenant/connection id |
| ADR-007-chatbot-architecture (Proposed, referenced by ADR-013) | Platform RAG + SQL chat path | The external tool is additive; platform capabilities and their prompts stay unchanged for tenants without a connection |
| ADR-011-tenant-scoped-azure-connection-control-plane | CAP-2 connection rows, secret references, activation evidence | Live database built only from the active row's own configuration and resolved secret (`resolve_live_database`) |
| ADR-013-contract-governed-external-postgresql-chat | Contract authorizes; index is context only; drift gate before every query; LLM never touches the DB; rows not persisted | Generator reads index for context only and executes solely via `execute_external_query`; no row values in persisted citations |
| ADR-015-external-chat-reply-persistence (new, this change; partially supersedes ADR-013) | Reply text persists; row values do not | Citation for external answers carries relation names only |
| ADR-016-contract-grounded-external-sql-generation (new, this change) | Schema context from contract; local validation before DB; per-turn tool offering; whole-contract context until retrieval | Decisions 1–7 below |

## Decisions

### Decision 1: Descriptions live beside columns, not inside them

**Choice:** Each relation object gains two optional fields. `description` is a string. `column_descriptions` is an object mapping each declared column to a description string. `columns` stays a list of names.

```json
{"version": 1,
 "relations": {"fisc_user_profile": {
    "columns": ["record_id", "pbwuserid", "claim_ind"],
    "primary_key": "record_id",
    "description": "User profiles: names, job, student data, claim/approver flags.",
    "column_descriptions": {"claim_ind": "'0'=Unclaimed, '1'=Claimed"}}},
 "joins": []}
```

`validate_contract_document` enforces the following. Each check adds a field-path error and the reason `invalid_shape`:

- `description` is a string of at most 2,000 characters.
- `column_descriptions` is an object.
- Every key in `column_descriptions` is a declared column.
- Every value is a string of at most 2,000 characters.

`store_draft` keeps both fields in the canonical relations. It must also stop relying on the accidental pass-through of unknown relation keys: it persists a normalized relation dict containing only `columns`, `primary_key`, `description`, and `column_descriptions`. `canonical_fingerprint` is unchanged, because it already reads only `columns` and joins.

**Rationale:** Existing contracts, the fingerprint, drift comparison, and the validator's column checks all treat `columns` as `list[str]`. Keeping that shape makes the change additive and leaves drift behavior untouched.

**Alternatives considered:**
- Columns as objects (`[{"name": ..., "description": ...}]`) — ruled out because it breaks every consumer of `columns`, and existing published contracts would need a migration.
- Accepting the proposed `allowed_tables` / `key_columns` format and converting it — ruled out because it creates two formats. `key_columns` also implies a column subset, which the drift gate rejects.

### Decision 2: Index entry text carries descriptions; no schema change

**Choice:** `entry_text_for_relation` takes the relation definition and renders:

```
table fisc_user_profile — User profiles: names, job, ...
columns:
  claim_ind — '0'=Unclaimed, '1'=Claimed
  pbwuserid
  ...
join fisc_user_profile.pbwuserid = other.pbwuserid
```

Columns are sorted. Undescribed columns render as a bare name.

**Rationale:** `entry_text` is `TEXT`, so no migration is needed. Publish already rewrites a version's entries. The same text later becomes the embedding input once vector retrieval lands, so this also prepares that work.

**Alternatives considered:**
- Building the prompt straight from the canonical JSONB and skipping the index — ruled out because the requirement names the index as the context source, and later retrieval needs one rendering, not two.

### Decision 3: Generator in chat-api, injected into the shared tool through `ToolContext`

**Choice:** Add `src/chat_api/services/external_sql_generator.py` with `ExternalSQLGenerator.answer(question, session, tenant_id, conversation_context, deadline) -> ExternalAnswer`. The steps:

1. Call `resolve_external_capability`. If the tenant is not executable, return that finite reason.
2. Call `fetch_entries(session, tenant_schema, connection_id, version)` and render the schema context. If it is over `settings.external_pg_schema_context_max_chars` (default 60,000), return `schema_context_too_large`.
3. Loop for up to `settings.external_pg_sql_max_attempts` attempts (default 3):
   - Call the LLM with `response_format={"type": "json_object"}` and `temperature=0`.
   - Parse `{sql, params}`. A bad shape fails with `malformed_output`.
   - Check every `%(name)s` has a key in `params`. Otherwise fail with `missing_param`.
   - Run `validate_statement(sql, contract["canonical"])`. On `ValidationRejected`, record the reason and loop, with feedback `"previous attempt rejected: <reason> (<reference>)"`.
4. Call `resolve_live_database(session, tenant_id)`. `ExternalDatabaseUnavailable` maps to `not_active_connection`.
5. Call `execute_external_query(database, contract, sql, params)` once. Map its errors: `DriftBlocked.outcome`, `ValidationRejected` becomes `validation_rejected`, and `ExternalExecutionFailed` becomes `execution_failed`.
6. Return rows, `truncated`, the relation names used, and the connection id.

`ToolContext` gains an optional `external_search` callable, mirroring `sql_search`. `src/shared/retrieval/tools/external_tools.py` defines `ExternalDatabaseTool`, which calls `context.external_search` and turns the result into a `ToolResult`. `RAGOrchestrator` builds the generator and passes `external_search=orchestrator._external_source` into the `ToolContext` in `retrieval_execution_node`.

`external_postgres_chat.external_chat_answer` stays as the lower-level executor-only entry point, so its existing tests keep passing. The generator calls the connector functions directly, so it can validate locally before any database call.

**Rationale:** This keeps `src/shared` free of `src.chat_api` imports, as the existing `sql_search` design does. Local validation means rejected attempts cost only LLM calls, never a drift introspection or a database round-trip. It also lets retries use the rejection reason, which is already non-sensitive (a finite class plus a contract identifier).

**Alternatives considered:**
- Retrying through `execute_external_query` each time — ruled out because every retry would introspect the tenant database. The first attempt would also touch the DB for statements the validator rejects anyway.
- Extending `SQLGenerator` — ruled out because its prompt, grounding, recovery loop, and whitelist are specific to platform entity views. Mixing the two paths risks platform regressions right before a demo.

### Decision 4: Hardcoded prompt rules match the validator's grammar exactly

**Choice:** The external system prompt is a module constant. It states:

- One `SELECT` only.
- Bare relation names only; no schema qualification.
- Only listed relations, columns, and joins.
- Every value (strings, numbers, dates, `DATE_TRUNC` units, `IN` lists as separate placeholders) is a `%(pN)s` placeholder with its value in `params`.
- Never write `LIMIT` or `OFFSET`; the server applies a row cap.
- No subqueries, `WITH`, `UNION`/`INTERSECT`/`EXCEPT`, window functions, or `OVER`.
- Only these functions: COUNT, SUM, AVG, MIN, MAX, COALESCE, NULLIF, CAST, EXTRACT, DATE_TRUNC, NOW, CURRENT_DATE, CURRENT_TIMESTAMP, LOWER, UPPER.
- Use `ILIKE %(pN)s` with `%` wildcards in the parameter value for name matching.
- Output JSON `{"sql": ..., "params": {...}}` only.
- If the question can't be answered within these rules, return `{"sql": "", "params": {}}`, which maps to `unanswerable`.

A unit test asserts the function list in the prompt equals `validator._ALLOWED_FUNCTIONS`.

**Rationale:** Every rule the model breaks costs a retry. Mirroring the grammar is the cheapest way to raise first-attempt acceptance. The equality test stops the prompt and the validator drifting apart.

**Alternatives considered:**
- Letting the model write literals and parameterizing them afterwards — ruled out because rewriting SQL means a second parser with its own injection surface, and the spec already allows "bound or rejected".

### Decision 5: Tool set composed per turn

**Choice:** `orchestrator_node` calls `resolve_external_capability(state["session"], tenant_id)`.

- **If executable:** it builds a turn registry with the platform tools plus a new `ExternalDatabaseTool` instance. That instance's description is rendered from the contract: fixed purpose text plus `relation — description`, each truncated to 200 characters, the whole block capped at 2,000 characters.
- **Otherwise:** it uses `orchestrator.tool_registry` unchanged.

The chosen registry goes into state (`tool_registry`), and `retrieval_execution_node` reads it from state. `_build_messages` gets an optional addendum paragraph, used only when the tool is offered, explaining when to prefer `external_database`: questions about the connected database's records, not uploaded documents. `plan_retrieval._resolve_entry` already rejects names that aren't in the given registry, which covers the "unoffered call is rejected" requirement. `build_fallback_plan` already names only the platform capabilities.

Capability resolution failure (an exception) is logged with its error class and treated as not executable, so platform chat never breaks because of it.

**Rationale:** Tenants without a connection get byte-identical planner input, so there is no regression surface. Relation names in the description are the planner's only signal for routing.

**Alternatives considered:**
- Always registering the tool and failing at call time — ruled out because it changes planner input for every tenant and wastes planner choices.
- A keyword or classifier router before the planner — ruled out because the planner already routes, and a second router is more work than one day allows.

### Decision 6: Separate evidence channel for external rows

**Choice:**

- `_accumulate` routes `external_database` results into a new `external_results` list, with the relation names used and a completeness flag. Failures go into `external_failure_reason`.
- `RetrievalExecution` and graph state carry these fields.
- `ContextAssembler.assemble` takes `external_results` and `external_failure_reason`:
  - Rows render as a block headed "Results from the tenant's connected database (<relations>)", with the same truncation note used for SQL completeness.
  - A failure reason renders the fixed message from `EXTERNAL_OUTCOME_MESSAGES[reason]` and instructs the model to relay it.
- `AdmittedEvidence` records `external_relations`.
- `source_assembly_node` emits `Source(source_type="external_postgresql", value=json.dumps({"relations": [...]}), relevance_score=1.0)` and nothing else for external evidence.
- The hit-rate recorder counts `external_database` separately.

**Rationale:** The platform `sql_results` channel serializes rows into persisted citations. It also runs `document_id` filtering and entity-citation enrichment that don't apply to external rows. A separate channel makes "no rows in citations" true by construction.

**Alternatives considered:**
- Reusing `sql_results` with a tag — ruled out because every consumer of `sql_results` (document-id filter, source assembly, enrichment) would need an "is external" branch. Missing one leaks rows into storage.

### Decision 7: The external generator's LLM client is not LangSmith-wrapped

**Choice:** `ExternalSQLGenerator` builds `AsyncAzureOpenAI`/`AsyncOpenAI` from the same settings as `SQLGenerator`, without `wrap_openai`. Metrics use `_metrics().measure_llm_call("external_sql_generation")`, which records only token usage and latency.

**Rationale:** LangSmith traces capture the prompt and output, meaning schema text and SQL. ADR-013 forbids SQL text in telemetry.

**Alternatives considered:**
- Wrapping with input/output redaction — deferred, because the redaction hooks aren't used elsewhere and that isn't demo-critical.

### Decision 8: Contract skeleton script for exact-match contracts

**Choice:** Add `scripts/external_pg_contract_skeleton.py`. It:

- reads a DSN from the `EXTERNAL_PG_DSN` environment variable (never a CLI argument, so the password doesn't land in shell history);
- takes `--tables a,b,c` and `--version N`;
- queries `information_schema.columns` for `public` and `information_schema.table_constraints` / `key_column_usage` for primary and foreign keys;
- writes the contract JSON to stdout, with every visible column, the primary key, foreign keys as joins, and an empty `description` plus a `column_descriptions` entry per column for the admin to fill in. Empty strings are allowed.

It uses asyncpg (already a dependency), and the same `information_schema.columns` query the drift gate uses, so the generated columns match the drift fingerprint.

**Rationale:** A contract missing even one live column blocks every query with `drift_mismatch`. Generating the column list removes the most likely demo failure.

**Alternatives considered:**
- An LLM-drafted contract via a portal button — deferred. That's product work and it needs a portal flow.

## Risks / Trade-offs

- [The generator writes invalid SQL for complex questions within three attempts] → Keep demo questions to single-table filters, counts, group-bys, and one approved join. Rehearse against the live database. `generation_exhausted` shows a fixed message instead of an error.
- [sqlparse tokenizes `%(p1)s` in a way the validator misreads as a literal or name] → An early task runs the existing validator on representative placeholder statements. Existing CAP-4 tests already cover parameterized statements.
- [The planner doesn't pick `external_database` for questions about the connected data] → The description lists relation names and descriptions, and the addendum paragraph gives routing guidance. A test pins that the tool is offered, and the demo rehearsal checks routing.
- [Whole-contract context gets too large] → A character budget fails closed with `schema_context_too_large`. The demo contract is small. Vector retrieval is the follow-up.
- [The reply text persists tenant data values] → An accepted product decision recorded in ADR-015. Citations carry no rows.
- [LangSmith tracing of the *answer-generation* call captures the external rows in its prompt when `LANGSMITH_TRACING=true`] → Tracing is off by default (`.env.example`). Keep it off for the demo. A follow-up is recorded to redact external evidence from traced prompts.
- [Azure network: the chat-api container can't reach the Azure server (firewall/IP allowlist)] → Verify reachability with the connection test and the skeleton script from the same host before the demo. `metadata_unavailable` surfaces distinctly.
- [Drift gate and execution each open a new asyncpg connection (two TLS connects per question)] → Acceptable latency for the demo. Connection reuse per turn is a follow-up.
- [Sensitive columns visible to the role must be listed in the contract] → Onboarding note: restrict the role with column-level `GRANT`s.

## Migration Plan

1. No database migration. Contract fields are additive inside existing JSONB. Previously published contracts render index entries without descriptions until republished.
2. Deploy chat-api and gateway together. The gateway accepts the new fields, and chat-api uses them.
3. Demo setup:
   - Create the `azure_postgresql` connection with `password_ref=env://...`, the variable set in both the gateway and chat-api environments.
   - Run the test and activate it.
   - Run the skeleton script, add descriptions, upload, and publish.
4. Rollback: revert chat-api. Without the per-turn registry, no tenant is offered `external_database`, and platform chat is unchanged. Contracts with descriptions stay valid under the old validator, which ignores the unknown relation keys (it doesn't reject them).

## Open Questions

- Whether persisting reply text derived from external rows needs a tenant-facing notice in the portal. It's recorded in ADR-015 as a product decision. The notice is not part of this change.
- Redacting external evidence from LangSmith-traced generation prompts (follow-up).
- Vector retrieval over `external_pg_schema_index` once contracts exceed the context budget (follow-up change; the embedding input is the Decision 2 entry text).
