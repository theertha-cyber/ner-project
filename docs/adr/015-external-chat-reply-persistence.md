# ADR-015. External Chat Replies Persist; External Rows Do Not

- **Status:** accepted, supersedes ADR-013 (partially — clarifies the "result rows are not persisted" clause only)
- **Date:** 2026-09-13
- **Supersedes:** 013-contract-governed-external-postgresql-chat

## Context

ADR-013 says external PostgreSQL "result rows are not persisted." Connecting external chat to the conversation flow (change `external-postgresql-chat-sql-generation`) exposes two readings of that clause.

1. **The platform citation model.** For SQL answers, the model serializes admitted rows into `Source(source_type="sql", value=json.dumps(rows))`, and that source is persisted with the chat message. Reusing it for external answers would store tenant database rows verbatim.
2. **The natural-language reply.** The reply ("There are 42 unclaimed users", "Arjun is in Sales") is persisted as the assistant message, like every chat turn. It necessarily contains values derived from the rows. Refusing to persist it would break conversation history and follow-up questions for every external answer.

The product owner decided on 2026-09-13 that the reply persists. This ADR records that decision and narrows the ADR-013 clause without editing ADR-013. Every other ADR-013 clause stays in force.

## Decision

- Result rows from a tenant's external database SHALL NOT be written to any platform table in structured or serialized form. That includes chat message sources/citations, caches, audit rows, and telemetry.
- The generated natural-language reply for an external answer SHALL be persisted as the assistant message, the same as any other chat turn.
- A citation for an external answer SHALL carry only the source type `external_postgresql` and the names of the contract relations used.
- External rows MAY appear in the current turn's generation prompt. They SHALL NOT appear in logs or metrics.

## Consequences

- Conversation history and follow-ups work for external answers.
- Values that the LLM restates in the reply are retained on the platform with the chat history, under the existing chat retention and deletion rules. Tenants that need zero retention of external-derived values need a future per-connection "do not persist replies" option, which is not in scope.
- External evidence needs its own channel through retrieval, prompt assembly, and citation assembly. It cannot reuse the platform `sql_results` path, which serializes rows.
- An LLM tracing tool that captures generation prompts (LangSmith, when enabled) would capture external rows. Keeping tracing disabled, or redacting external evidence, is an operational requirement for tenants with external connections.
