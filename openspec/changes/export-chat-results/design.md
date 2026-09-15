## Context

Chat answers backed by structured retrieval (SQL over the tenant's entity tables) are already capped upstream: `SQLGenerator` limits execution to at most 1000 rows (`sql_generator.py` `DEFAULT_LIMIT=100`, hard cap 1000), and `ContextAssembler._fit_rows` further truncates whatever `ChatState.sql_results` holds to fit `settings.context_token_budget` before it ever reaches the LLM prompt (`AdmittedEvidence.rows`/`rows_truncated`/`matched_rows`). Today, once a turn is persisted (`_persist_turn_and_respond` in `chat.py`), only the LLM's prose `reply` and the `sources` citations survive — `sql_results` is discarded when the request completes. There is no way to recover the full structured result for a turn after the fact, and no way for the portal to know a result was too large to show completely.

This change adds a persisted snapshot of the full SQL result per turn, a download endpoint, and a portal file-card affordance gated on a size/truncation threshold — without touching SQL generation, guardrails, or the RAG pipeline itself.

Relevant in-force ADRs (all others in `docs/adr/` are either unrelated — training/model-serving/annotation — or don't constrain this area):
- **ADR-001** (tenant data isolation via per-tenant schema): the snapshot table/column MUST live in the tenant schema and be reachable only through the existing `search_path`-scoped connection, exactly like `chat_messages`.
- **ADR-007** (chatbot architecture): SQL execution stays inside the existing validated, read-only, timeout-bound path. This change reads `ChatState.sql_results` — the already-validated result of a query that already ran — and does not introduce a second SQL execution or a new query surface.
- **ADR-013** (confidence hedging is advisory-only, additive to ADR-007): unrelated to this change's data path; noted only because it modified `chat-api` most recently and confirms the additive-delta pattern this change also uses (new `export` field, no change to existing response fields).

## Goals / Non-Goals

**Goals**
- Preserve the full SQL result set for a turn (up to the existing 1000-row cap) so it can be downloaded after the fact, independent of what the LLM's prompt budget admitted.
- Let the portal decide, per turn, whether to show a file card instead of/alongside inline text, using a signal already computed by the pipeline (truncation) plus a simple row-count threshold.
- Support both CSV (no new dependency) and XLSX (one new dependency, `openpyxl`) from the same stored snapshot.

**Non-Goals**
- Exporting document/semantic-search results (chunks) or NER inference results — only structured SQL rows are in scope.
- Editing, filtering, or re-running the export after the fact — the snapshot is exactly the rows returned at turn time, immutable.
- Export from the widget/embeddable chat surface — this change is portal-only (see Open Questions).
- Long-term archival/analytics use of exported data — this reuses the `chat-export` capability name distinctly from the existing `analytics-export` capability (which exports over the full entity corpus via a filter body, not per-message).

## Decisions

### Decision 1: Snapshot storage — new column on `chat_messages`, not a new table

Store the snapshot as `chat_messages.export_rows JSONB NULL`, written once in the same transaction as the assistant row insert in `_persist_turn_and_respond`.

Alternatives considered:
- **New `chat_message_exports` table** (id, message_id FK, rows JSONB, row_count, created_at): cleaner separation, easier independent retention/TTL policy, avoids bloating the hot `chat_messages` table read path (conversation history fetch doesn't need to touch large blobs). Rejected for v1 because it adds a join and a second insert to a code path (`_persist_turn_and_respond`) that's shared by streaming and non-streaming routes and already does two inserts in one transaction; the extra complexity isn't justified until snapshot volume is measured.
- **Object storage** (reuse the existing tenant-prefixed S3 convention from ADR-001): right long-term answer if snapshots turn out to be large/frequent, but adds a new I/O dependency to the request-persist path for a feature whose actual row-size distribution is unknown pre-launch.

Follow-up: if `chat_messages` read latency or table bloat becomes a problem, split `export_rows` into its own table in a later change — this is flagged in Risks/Trade-offs, not deferred silently.

### Decision 2: Snapshot source — `ChatState.sql_results`, not `AdmittedEvidence.rows`

Confirmed by the proposal already: the export must reflect what the SQL query actually returned, not what fit in the LLM's context window. `retrieval_execution_node` writes `sql_results` before any budget-fitting happens; `prompt_assembly_node` calls `ContextAssembler().assemble()` which produces `AdmittedEvidence` for the prompt only. The persistence step reads `state["sql_results"]` directly, independent of `admitted_evidence`.

**Refined during live testing**: the persistence check is `if sql_results:` (truthy — a non-empty list), not `if sql_results is not None:`. The original `is not None` check treats a validated query that matched zero rows the same as one that matched hundreds — both persist a snapshot. In practice, the SQL generator's LLM occasionally targets an empty or wrongly-named entity relation (observed live: a tenant with both a `NAME` entity type holding real data and an unrelated, empty `full_name` entity type — the LLM picked the empty one) and still produces a query that validates and executes cleanly, just against nothing. That surfaced as a "0 results / Download the full result" export card with nothing useful behind it. Since there's nothing worth exporting from an empty result, it's now treated identically to structured retrieval not having been used at all (see the `chat-export` capability's revised requirement and its new scenario for this).

### Decision 3: Threshold signal — `export.row_count`, gating an inline preview truncation, not just a file-card show/hide

**Revised three times during implementation** — the full arc is worth keeping, because each revision was caught a different way (a spec-reading gap, then direct product feedback, then a live bug report), and the final shape only makes sense in light of what each one ruled out.

1. **Original plan**: trigger on `export.row_count > 20` **or** the turn's retrieval status reporting truncation, on the assumption that `sql_completeness`/`AdmittedEvidence.rows_truncated` were already computed and available to key off of. They are computed — but only inside `ChatState`, server-side; neither is ever serialized onto `ChatResponse` (`schemas.py`'s `RetrievalStatusOut`/`RetrievalStatusEntry` carry `outcome`/`result_count`/confidence-hedge fields, not a truncation boolean), so the portal has no wire-level signal to read a "truncated" condition from. **Revision 1**: dropped the truncation clause, kept `export.row_count > threshold` (then 20) as the sole trigger, gating only whether the file card showed — the reply text itself always rendered in full regardless.
2. **Product feedback during live testing**: a full-length reply with a large row count (e.g. "list every candidate," 28 rows) is unwieldy inline — the request was for the reply itself to preview only the first 5 results, with the file card and a "See more" toggle appearing right at the truncation point, not just a card bolted below an already-full reply. **Revision 2**: reworked the trigger into `export.row_count > PREVIEW_LINE_LIMIT` (renamed and lowered to 5) driving both an inline text truncation (first `PREVIEW_LINE_LIMIT` non-empty lines of the reply, `MessageThread.tsx`'s `contentLines`/`isTruncatable`) and the file card together, plus a "See more"/"See less" toggle to reveal/re-collapse the full reply in place.
3. **Live bug found via a real query** ("give me one single candidate"): the revision-2 implementation gated truncation on the reply's *line count* alone (`lines.length > PREVIEW_LINE_LIMIT`), not on `export.row_count`. A detailed single-candidate answer (job title, experience, education, each on its own line) has plenty of lines despite being exactly one result, so it was wrongly truncated with an absurd "See more (12 more)" under a one-result answer. **Revision 3 (final)**: truncation now requires **both** `export.row_count > PREVIEW_LINE_LIMIT` **and** `lines.length > PREVIEW_LINE_LIMIT` — a high result count with a short reply doesn't truncate (nothing to hide), and a long reply about few results doesn't truncate either (nothing to page through). This is the behavior specified in the `chat-ui` capability's "Inline preview truncation and file card, driven by result count" requirement.

The threshold's exact value (5) is still an unconfirmed placeholder pending real UX/product input, same caveat as when it was 20 — only the number and what it gates have changed. The `LIMIT`-truncation edge case from revision 1 (a query whose `LIMIT` was small on purpose but still matched more rows than it returned) is unaffected by revisions 2/3 and remains an accepted v1 gap — see Risks.

### Decision 4: XLSX generation — server-side via `openpyxl`, generated on request (not pre-generated)

Both CSV and XLSX are generated at export-request time from the stored JSONB snapshot, not pre-built and stored. Alternatives considered:
- **Pre-generate both files at persist time and store as blobs**: avoids repeat generation cost on every download, but doubles storage (JSONB + two file blobs) for a feature that may be downloaded zero or one times per turn. Rejected — generation from up to 1000 rows is cheap (`openpyxl` write of ~1000 rows is sub-second), so there's no latency case for pre-generation.
- **Client-side XLSX generation from a CSV/JSON payload** (e.g. a JS `xlsx` library in the portal): removes the new Python dependency, but requires shipping the full row data to the browser first (defeats the "don't inline rows into `ChatResponse`" goal) and duplicates formatting logic across client/server. Rejected.

Row values in the snapshot originate from extracted document/entity data (e.g. a name, organization, or skill string pulled from an uploaded resume) — content the platform does not author or control. Both renderers MUST treat every cell value as untrusted text and neutralize CSV/Excel formula injection (a value beginning with `=`, `+`, `-`, or `@` is interpreted as a formula by Excel/Sheets/LibreOffice on open — a well-known CSV-injection class, OWASP-documented): prefix any such value with a leading `'` (or otherwise force text interpretation) before writing, for both the CSV writer and the `openpyxl` writer. This applies regardless of format, so it belongs in the shared row-serialization step rather than being duplicated per-format.

### Decision 5: Access control — reuse conversation ownership check, no new authorization concept

The export endpoint resolves `message_id` → `conversation_id` → verify `conversation.user_id == current_user.id AND conversation.tenant_id == current_tenant` (mirrors the existing `DELETE /conversations/{conv_id}` 404-on-mismatch pattern in `chat-api`'s Conversation CRUD requirement, and the `chat_message_feedback` ownership check at `chat.py:412-416`). No new role or permission model needed.

## Risks / Trade-offs

- **[Risk] CSV/Excel formula injection via exported cell values** (row data is document-derived, untrusted text — see Decision 4) → **Mitigation**: shared row-serialization step neutralizes any cell value beginning with `=`, `+`, `-`, or `@` before it reaches either the CSV or `openpyxl` writer; covered by an explicit verification scenario using a constructed formula-injection payload, not left implicit.
- **[Risk] `chat_messages` row bloat from `export_rows` JSONB** (up to 1000 rows × N columns per structured turn) → **Mitigation**: cap enforced upstream by `sql_generator.py`'s existing 1000-row `LIMIT` clamp; monitor `chat_messages` table size post-launch; Decision 1's table-split fallback is the escape hatch if this becomes a real cost.
- **[Risk] Conversation history fetch (`GET /conversations/{conv_id}`) becomes slower** if it ever starts selecting `export_rows` incidentally → **Mitigation**: only the small `export_row_count` integer is selected there (needed so a message's file card survives a reload — see Decision 3's sibling finding below); the bulky `export_rows` JSONB column MUST stay excluded from that query's column list, and only the export endpoint selects it. This is a code-review-enforceable constraint, not a schema one — flag explicitly in `verification.md`.
- **[Risk] Snapshot and displayed reply can drift** if a future change re-generates a reply from a message without re-snapshotting rows → **Mitigation**: snapshot write happens in the same transaction as the assistant message insert; there is no code path today that mutates `chat_messages.content` after insert, so this is currently a non-issue, but worth a regression scenario if message-editing is ever added.
- **[Trade-off] Truncation/file-card threshold ignores intentional-`LIMIT` truncation** (Decision 3) — a "top 5" style query that matched more rows than it returned stays fully inline, untruncated, even though its result is technically incomplete, because no truncation signal reaches `ChatResponse` today. Accepted for v1; the fix (expose `sql_completeness`/a `truncated` boolean on `ChatResponse`) is a small, separately-scoped follow-up, not bundled into this change.
- **[Risk] Truncation gated on line count alone would misfire on verbose single-result answers** (Decision 3, revision 3) → **Mitigation**: truncation requires `export.row_count > PREVIEW_LINE_LIMIT` in addition to the reply's line count exceeding it — confirmed by a regression test (`MessageThread.test.tsx`, "does not truncate a detailed single-result answer, even with many lines") using a realistic multi-field single-candidate reply.
- **[Trade-off] No independent retention policy for `export_rows` in v1** — it lives and dies with the message row (cascades via existing `conversations` → `chat_messages` FK `ON DELETE CASCADE`). Accepted for v1; revisit if storage growth or compliance requirements demand a shorter TTL than message retention itself.

## Migration Plan

New Alembic migration (next revision after `037_entity_definitions_view_metadata.py`, i.e. `047_chat_messages_export_rows.py`), following the exact pattern established in `010_chatbot_infrastructure.py`:
- `ALTER TABLE tenant_template.chat_messages ADD COLUMN export_rows JSONB, ADD COLUMN export_row_count INTEGER;`
- The same `DO $$ ... FOR schema_name IN SELECT nspname FROM pg_namespace WHERE nspname LIKE 'tenant\_%' ...` loop applying the same `ALTER TABLE` to every existing tenant schema.
- `downgrade()` drops both columns, same loop pattern.

No backfill needed — existing messages simply have `export_rows = NULL`, which the `chat-api`/`chat-export` specs already treat as "no export available" (404 / `export: null`).

Deployment is a standard additive migration (nullable columns, no default computation, no table lock beyond the `ALTER TABLE`) — no special rollout sequencing required beyond the project's normal migration-then-deploy order.

## Open Questions

- Carried over from the proposal, now narrowed by Decision 1: is a JSONB column on `chat_messages` acceptable long-term, or should this change ship the `chat_message_exports` table from day one instead of treating it as a fallback? (Leaning: ship the column; split later if metrics justify it — see Risks.)
- Should `export_row_count` be a stored column (Decision 1's migration includes it) or derived by reading `jsonb_array_length(export_rows)` on demand? Migration above stores it denormalized for cheap inclusion in `ChatResponse.export` without deserializing the full snapshot on every chat turn's response — flagging in case that's considered premature.
- Confirm the `PREVIEW_LINE_LIMIT` default (5 results; originally 20, revised down during live product feedback — Decision 3) with actual product/UX input before treating it as the final shipped default.
- Widget/embeddable export (out of scope per Non-Goals) — confirm this is acceptable to defer, since the widget has its own stricter rate limit tier and a different trust boundary (API-key rather than user JWT).
