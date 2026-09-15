## Why

CAP-4 (ADR-013) shipped every guard around external PostgreSQL chat: contract upload and publish, a tenant-isolated schema index, the drift gate, the AST validator, and a read-only Azure executor. What it did not ship is the step that turns a user's question into SQL, or any wiring into chat. `external_chat_answer` and `resolve_live_database` have no production callers, and `fetch_entries` (the index read) is never called. A tenant can publish a contract today, but nobody can ask a question against it. This change closes that gap so a tenant with an active Azure Database for PostgreSQL connection can chat with their own data, for a live demo against a real Azure Postgres instance.

The contract also has no place for meaning. It lists relation and column *names* only, so an LLM sees `claim_ind` with no way to learn that `'0'` means unclaimed. Descriptions are what make generated SQL correct.

## What Changes

- **Contract descriptions (additive, non-breaking):** a published contract MAY carry an optional `description` per relation and an optional `column_descriptions` map (`{column: text}`) per relation. Both are validated (known columns only, bounded length) and excluded from the fingerprint, so editing prose never trips the drift gate. Contracts without descriptions stay valid.
- **Schema index carries descriptions:** index entry text includes relation and column descriptions next to names and join keys.
- **External SQL generation:** a new generator builds a prompt from hardcoded rules (read-only, placeholders for every value, no LIMIT, no subqueries/CTEs/UNION/window functions) plus the tenant's published schema context. It asks the LLM for `{sql, params}` JSON and checks the result with the existing validator *locally* before touching the tenant database. On rejection it retries at most twice, feeding back only the finite reason class and the offending contract identifier. The accepted statement then runs through the existing drift-gated `execute_external_query`.
- **Whole-contract context (no vector retrieval yet):** every relation's index entry goes into the prompt. Embedding-based top-K retrieval is deferred to a later change.
- **Chat wiring:** a new `external_database` retrieval capability, offered to the planner **only** when `resolve_external_capability` says the authenticated tenant is executable. Its description names the contract's relations so the planner can route to it. External rows go into the generation prompt through their own channel.
- **Rows are never retained:** external rows SHALL NOT be serialized into persisted citations. The citation for an external answer carries only a source type and relation names. The natural-language reply is persisted like any other chat turn. This is an explicit product decision, recorded as an ADR-013 clarification.
- **Safe user-facing outcomes:** drift-blocked, metadata-unavailable, not-executable, generation-exhausted, and execution-failed outcomes each reach the answer as a fixed, non-sensitive message (for example, "The connected database's schema changed; an administrator must publish an updated contract").
- **Contract bootstrap tooling:** a developer script introspects a live Postgres database and emits a contract skeleton (every column of the chosen tables, foreign-key joins, empty descriptions), so a demo contract matches live metadata exactly.

## Capabilities

### New Capabilities

- `external-postgresql-sql-generation`: turning a natural-language question plus the tenant's published contract context into one validated, parameterized SELECT with bounded, reason-guided retries.

### Modified Capabilities

- `external-postgresql-chat`: contracts gain optional validated descriptions excluded from the fingerprint. The schema index includes them. External answers persist the reply but never row values in citations.
- `retrieval-tools`: adds the `external_database` tool, and tool availability becomes per-request (gated on server-side capability resolution) instead of one static registry for every tenant.

## Impact

- **Code:** `src/shared/external_postgres/contract.py`, `index.py`; new `src/shared/external_postgres/generation.py` (or `src/chat_api/services/external_sql_generator.py`); `src/chat_api/services/external_postgres_chat.py`; `src/shared/retrieval/tools/` (new tool, registry composition); `src/shared/retrieval/orchestrator.py` (`_accumulate`, planner prompt); `src/chat_api/graph/nodes.py` (per-turn registry, external evidence channel, citation assembly); `src/chat_api/services/context_assembler.py`.
- **Portal:** contract upload hint text only. The upload flow and its 256 KB cap are unchanged.
- **Data:** no migration. Descriptions live inside the existing `canonical` JSONB, and `entry_text` is already `TEXT`.
- **APIs:** no new endpoints. `POST /api/v1/data-sources/{id}/contracts` accepts the additive fields.
- **Dependencies:** none new. Reuses the OpenAI/Azure OpenAI client configuration already used by `SQLGenerator`, plus `asyncpg`.
- **Operations:** the demo needs an `active` `azure_postgresql` connection, a password `env://` secret reference resolvable by chat-api, and network reachability from chat-api to the Azure server.
- **Tests:** new unit tests on `FixtureExternalDatabase`. A live Azure check is manual, per the verification plan.

## Open Questions

- **Contract size ceiling without retrieval:** whole-contract context is bounded by the existing 100-relation / 200-column caps plus description caps. A contract near those caps would exceed a sensible prompt budget. For now the generator enforces a character budget and fails with a finite reason rather than truncating. Confirm that is acceptable until vector retrieval lands.
- **Hiding sensitive columns:** the drift gate compares *all* live columns the database role can see, so a contract cannot omit a column the role can read. Tenants hide columns with column-level `GRANT`s on the read-only role. This needs documenting for onboarding, not a code change.
- **Negative ("who does NOT…") questions:** unsupported, because the validator forbids subqueries per the existing spec. Accepted for this change.
- **Fallback plan:** when the planner fails, the degraded fallback plan runs the platform capabilities only. External queries are never run speculatively. Confirm.
