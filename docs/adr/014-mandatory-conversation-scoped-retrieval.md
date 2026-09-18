# 014. Conversation Scoping Is a Mandatory Retrieval Guardrail, Not a Model-Selected Scope

## Status
Proposed

## Context
ADR-011 made chat attachments conversation-owned `documents` rows and stated that "retrieval and deletion are conversation-scoped". Deletion was implemented; retrieval was not. Attachment content never reached `document_chunks` at all, so the retrieval half of ADR-011 was never exercised and its enforcement mechanism was never chosen.

Making attachment content retrievable forces that choice now, and the platform offers two places to put it. Retrieval already has a model-facing `scope` argument on `semantic_retrieval` that narrows a search to specific document ids, and it already has a caller-invisible restriction — `purpose = 'query'` — compiled into every retriever's SQL. Conversation scoping could plausibly be expressed as either.

They are not equivalent. A `scope` argument is chosen by an LLM per call: it can be omitted, forgotten, or argued out of the model by the user's own message text. If conversation confinement lived there, a session's private attachment would leak into every other session of that tenant whenever the model declined to pass the argument — a silent, non-deterministic isolation failure.

There is also more than one retrieval channel. ADR-007 defines the answer pipeline over both pgvector document search and generated SQL, and the SQL whitelist exposes `document_chunks.chunk_text` and `documents.filename`. A rule applied only to the vector retriever would leave the relational path as an open second channel for the same content.

## Decision
Conversation scoping is a **mandatory guardrail**, enforced from the authenticated request's conversation context, and applied to every retrieval channel.

Concretely:

- `document_chunks` carries a denormalized `conversation_id` from its parent document, in the same way it already carries `purpose`.
- Every `Retriever` implementation unconditionally admits a chunk only when its `conversation_id` is null, or equals the conversation the turn is being answered for. With no conversation in context, only null-owned chunks are admitted.
- The generated-SQL path applies the same rule by rewriting conversation-bearing table references into inline views, reusing the mechanism `apply_document_scope` already established.
- The conversation is never taken from `metadata_filter`, from a model-selected tool argument, or from the user's message text. The model-facing `scope` argument retains its existing meaning — narrowing within what is already visible — and can never widen it.

A document with no conversation owner is tenant-library content and remains visible in every conversation, unchanged.

## Alternatives Considered
| Option | Why not chosen |
| --- | --- |
| Express conversation scoping as a `scope` type on the retrieval tool | Puts an isolation guarantee in model-controlled data; an omitted argument becomes a silent cross-session leak. |
| Apply the rule to the vector path only | Leaves the relational path, which can select `chunk_text` and `filename`, as an unguarded second channel for the same content. |
| Join `document_chunks` to `documents` per query instead of denormalizing | Adds a join between the `hnsw` index scan and the vector ranking on the hot path, and cannot be expressed in the single-table inline-view rewrite the SQL path uses. |
| PostgreSQL Row-Level Security keyed on a per-transaction setting | The most complete option, and a plausible future supersession: it would cover every present and future query path with no per-call-site enforcement. Rejected for now because RLS governs every statement against `documents` and `document_chunks` — including ingestion writes, extraction, analytics and hard delete — making it a platform-wide security-posture change that warrants its own change and ADR. |

## Consequences
Conversation confinement becomes a property of the retrieval layer rather than of any caller's diligence, so new call sites and new tools inherit it without having to remember it, and it is testable the same way the `purpose` restriction already is: by asserting no caller-supplied parameter can defeat it.

The cost is that every retrieval channel must be enumerated and individually rewritten. This is the decision's main liability: a future channel that reaches `document_chunks` or `documents` without going through a `Retriever` or through the SQL scope rewrite would not inherit the rule. The SQL scope-column map is therefore defined next to the query whitelist and guarded by a test asserting every whitelisted conversation-bearing table appears in it, so an addition to the whitelist cannot quietly escape scoping.

Denormalizing `conversation_id` onto chunks makes ownership a fact the chunk row must keep correct; it is written once at processing time from the parent document and never updated, since an attachment cannot change conversations.

Should the channel enumeration become unmanageable, RLS is the intended successor, and superseding this ADR would change only the enforcement mechanism — ADR-011's ownership model would survive intact.

## Related
- Requirement(s): FR-001, FR-006
- ADR-011 (conversation ownership — this ADR supplies the retrieval enforcement it specified), ADR-007 (multi-channel answer pipeline), ADR-001 (tenant isolation, which conversation scoping composes with and never replaces)
- Supersedes / Superseded by: None
