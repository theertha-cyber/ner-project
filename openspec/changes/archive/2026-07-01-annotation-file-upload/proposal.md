## Why

Users need to train NER models on annotation data that exists outside the platform — from external annotation tools, previous annotation rounds, or programmatically generated datasets. Currently, the only way to get annotations into the training pipeline is through the annotation workspace UI, one span at a time. This makes it impossible to leverage existing labeled corpora or bulk-import annotations from other tools.

## What Changes

- New `POST /api/v1/annotation-import` endpoint on the annotation service that accepts JSONL and TXT (CoNLL) annotation files, parses them into token+BIO tag rows, and stores them in a new `imported_annotations` table (tenant-scoped).
- The existing `GET /api/v1/annotation-export` endpoint is modified to UNION rows from `imported_annotations` alongside computed rows from the `spans` table, so the training pipeline transparently receives all available annotations.
- The training worker is **not modified** — it continues to call the same export endpoint.
- New `imported_annotations` DB table in each tenant schema to store token-level annotations with their source file provenance.

## Capabilities

### New Capabilities

- `annotation-import`: Accept uploads of JSONL and CoNLL-format annotation files, validate against tenant entity type definitions, persist token+BIO tag rows in tenant-isolated storage, and expose them through the export endpoint for downstream training consumption.

### Modified Capabilities

- *(No existing spec requirements change — the export endpoint's output expands, but its contract format is unchanged.)*

## Impact

- **annotation-service/api/v1/**: New `import.py` module for the import endpoint; minor addition to `export.py` to include imported rows.
- **Database**: New `imported_annotations` table in each tenant schema (migration required).
- **training-service**: No changes needed — worker continues calling the same export endpoint.
- **Portal UI**: No changes in this scope (API-only for initial delivery).
- **Gateway**: No changes needed (portal calls annotation service directly).

## Open Questions

- Should the upload accept a single JSONL file, multiple files, or both?
- Should imported annotations be individually deletable (delete by ID) or only bulk-cleared?
- Should the import endpoint also store the raw uploaded file in MinIO for provenance, or parse-and-discard as scoped?
