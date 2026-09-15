# ADR-014. Chat Export: Persisted Row Snapshot, Rendered On-Demand

- **Status:** proposed
- **Date:** 2026-09-14

## Context

ADR-007 committed the chatbot to a full RAG pipeline where structured (SQL) results are validated, executed read-only, and then folded into an LLM prompt under a token budget — after which the raw result set is discarded. The `export-chat-results` change needs to make that raw result set (up to the SQL generation layer's existing 1000-row cap) downloadable as CSV/XLSX after the turn completes, which requires two decisions with consequences beyond this one feature: where the row data lives once the request that produced it has ended, and when the actual downloadable file gets built. Neither is addressed by ADR-007 or any other in-force ADR — this is the first feature in the platform that persists a per-message structured artifact for later retrieval, and the first that generates spreadsheet files at all (the existing `analytics-export` capability produces CSV/JSON, not XLSX).

## Decision

For chat-export, and as the default pattern for any future feature that needs to make a chat turn's structured result available after the request completes:

1. **Persist the validated result as JSONB on the owning row**, not in a separate table or object storage. The snapshot (`chat_messages.export_rows`) is written once, in the same transaction as the message insert, capped at whatever limit the upstream retrieval layer already enforces (here, SQL generation's 1000-row cap) — no independent size policy is introduced by the export mechanism itself.
2. **Render downloadable files on-demand from the snapshot at request time**, never pre-generated and stored as file blobs. CSV and XLSX are both produced by reading the JSONB snapshot when `GET .../export` is called.
3. **Escalate storage only when justified**: if table bloat or read-latency on the owning table becomes measurable, split the snapshot into a dedicated table (or object storage, per ADR-001's tenant-prefixed convention) in a later change — this ADR does not forbid that, it just says don't start there.

This does not change any ADR-007 compliance clause (citations, disclaimer, tenant scoping, SQL validation, complexity limits, P95 budget) — the snapshot is read from data ADR-007's pipeline already validated and executed; no new SQL execution path is introduced.

## Consequences

### Positive
- A future feature needing "make this turn's structured result downloadable later" has a settled default (snapshot-on-the-row, render-on-demand) instead of re-litigating storage architecture and pre-vs-on-demand rendering each time.
- On-demand rendering keeps the write path (message persistence) cheap and format-agnostic — adding a third export format later (e.g. Parquet) needs no schema change, only a new renderer reading the same snapshot.
- Avoids doubling storage (raw data + pre-rendered files) for a feature whose actual download rate is unknown pre-launch.

### Negative
- A future contributor who wants to pre-render and cache export files (e.g. because on-demand XLSX generation becomes a measured latency problem at larger row counts) must get a new ADR superseding this one, rather than quietly adding a file-cache layer.
- Ties snapshot size to whatever cap the upstream retrieval layer happens to enforce today; if a future change raises or removes that cap without revisiting this ADR, `chat_messages` row size grows unchecked. Verification for any such future change should explicitly re-check this ADR's assumption.

## Related

- Requirement(s): `chat-export` capability (new); `chat-api` capability, **RAG chat endpoint** requirement.
- Supersedes / Superseded by: None — additive; does not override ADR-001 or ADR-007.
- Depends on: ADR-001-tenant-data-isolation (snapshot lives inside the tenant schema, same as `chat_messages`); ADR-007-chatbot-architecture (snapshot source is data ADR-007's pipeline already validated).
