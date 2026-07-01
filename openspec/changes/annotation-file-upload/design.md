## Context

The annotation service currently stores span-level annotations in the `spans` table (tenant schema), with char-level offsets into document text. The export endpoint (`GET /api/v1/annotation-export`) reads these spans, converts them to token-level BIO tags, and returns JSONL. The training worker consumes this JSONL to build HuggingFace Datasets for fine-tuning.

Users need to inject externally-sourced annotation data (from other tools, prior annotation rounds, or scripts) into this training pipeline. The annotations are already in token-level format (`{"tokens": [...], "tags": [...]}`) and have no document binding — they're standalone labeled sentences.

Key constraints:
- Training worker must not change — it calls the export endpoint and expects JSONL
- Data must be tenant-isolated (per ADR-001, separate schemas)
- Imported annotations have no document binding, so they cannot be merged into the `spans` table
- Entity type validation against tenant configuration must happen at import time

## Goals / Non-Goals

**Goals:**
- Accept uploads of annotation files (JSONL or CoNLL TXT) and persist them as token+BIO tag rows
- Expose imported annotations through the existing export endpoint alongside workspace spans
- Validate entity types against the tenant's configured entity definitions
- Keep the training worker completely unchanged
- Track provenance (source filename, row index) for each imported row

**Non-Goals:**
- No UI/portal changes in this scope (API-only)
- No modification to the `spans` table or annotation workspace
- No document binding for imported annotations (they exist independently)
- No real-time span creation or annotation workspace integration
- No raw file storage in MinIO (parse-and-discard after import)
- No deduplication logic for repeated imports of the same data

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 | Separate PostgreSQL schemas per tenant | `imported_annotations` table MUST be created in tenant schema |
| ADR-004 | OpenSpec spec-driven governance | This change follows the SDD pipeline via this change folder |
| ADR-005 | OpenCode agent boundaries | Implementation is gated behind human approval |

## Decisions

### Decision 1: Store imported annotations in a new tenant-scoped table, not the `spans` table

**Choice:** Create a new `imported_annotations` table in each tenant schema.

**Rationale:** Imported annotations are token-level (not char-level) and have no document foreign key. The `spans` table requires a `document_id` FK and uses char offsets. Forcing a fit would require either creating synthetic document rows or reconstructing text from tokens — both add complexity without benefit. A new table keeps the data model honest and clean.

**Alternatives considered:**
- **Store in `spans` with synthetic documents** — ruled out because every imported JSONL line would create a fake document row, polluting the documents table and confusing the portal UI.
- **Store as raw JSONB blob in a single record** — ruled out because it prevents querying individual rows, filtering by entity type, or deleting specific imported annotations later.
- **Store in MinIO and parse at export time** — ruled out because each export call would need to fetch and parse files, adding latency and complexity to the hot path.

### Decision 2: Merge imported annotations into the export endpoint

**Choice:** The export endpoint queries both `spans` and `imported_annotations` and unions their JSONL output.

**Rationale:** The training worker already calls the export endpoint and expects the JSONL format. Adding a second source at the export layer keeps the training pipeline ignorant of the import feature — no configuration, no new HTTP calls, no merge logic. The export endpoint's responsibility is already "gather all annotations and serialize as JSONL."

**Alternatives considered:**
- **Separate export endpoint for imported data** — ruled out because the training worker (or any consumer) would need to call two endpoints and merge, propagating the two-source problem to every consumer.
- **Modify training worker to merge** — ruled out because the worker is the most complex piece in the system; modifying it for this feature increases risk.

### Decision 3: Token-based storage over char-based storage

**Choice:** The `imported_annotations` table stores `tokens TEXT[]` and `tags TEXT[]` directly, matching the JSONL format.

**Rationale:** The input format is already token-level BIO. Converting to char-level would require reconstructing text from tokens, which is lossy (tokenization may differ between exporters). Storing the data in its natural format avoids unnecessary transformation and potential errors.

**Alternatives considered:**
- **Convert to char-level spans** — ruled out as lossy and unnecessary since no downstream consumer needs char offsets for imported data.
- **Store raw file text** — ruled out per user preference (Option A, parse-and-discard).

### Decision 4: Accept both JSONL and CoNLL TXT formats

**Choice:** Support JSONL (`{"tokens": [...], "tags": [...]}`) and CoNLL (token\tBIO per line, blank line separator) as input formats.

**Rationale:** JSONL matches the export format, enabling round-trip workflows (export → edit → re-import). CoNLL is a widely-used interchange format supported by most annotation tools (LabelStudio, Prodigy, brat). Both are text-based and trivially parseable.

**Alternatives considered:**
- **JSONL only** — ruled out because many external tools export CoNLL natively, adding friction for users migrating data.

### Decision 5: Validate entity types at import time

**Choice:** Reject rows with entity tags not matching the tenant's configured entity types.

**Rationale:** Importing annotations with unknown entity types would produce training data with labels the model doesn't know about, causing training failures or silent mislabeling. Early validation at import time provides clear feedback.

**Alternatives considered:**
- **Skip unknown types with a warning** — ruled out because it produces an incomplete training dataset without clear user visibility.
- **Auto-create missing entity types** — ruled out because it bypasses the tenant's intentional entity configuration.

## Risks / Trade-offs

- [**Orphaned imports after entity type deletion**] → If a tenant deletes an entity type after importing annotations that use it, the export will produce JSONL with tags for that type, but the training worker will still handle it (it extracts labels from the data). The deleted type will simply be excluded from displayed entity lists. Acceptable for MVP.
- [**No deduplication on re-import**] → Uploading the same file twice inserts duplicate rows. Users can truncate and re-import if needed. A future enhancement could add content-hash dedup.
- [**Large files causing request timeouts**] → The import endpoint parses synchronously. For files >100K lines, users may hit FastAPI timeout. Mitigation: documented file size recommendation; future batch import with background processing.

## Migration Plan

1. Create Alembic migration to add `imported_annotations` table to the tenant template schema
2. Deploy annotation service with new import endpoint and modified export endpoint
3. No data migration needed (new table, no existing data)
4. Rollback: revert the migration and deploy previous annotation service version

## Open Questions

- Should the import endpoint accept multiple file uploads in a single request, or one file per request? (One file per request keeps it simple — users can script batch uploads.)
- Should there be a bulk-delete endpoint for imported annotations (e.g., `DELETE /api/v1/annotation-imported` to clear all imported rows for a tenant)?
