## Why

Import Annotation is meant to be the third way training data reaches the platform:
already-labelled data goes straight in. Two things stop it being that today:

1. **Unknown entity types are silently dropped.** `POST /api/v1/annotation-import` skips
   any row whose tags reference a type not in `entity_definitions` and reports a count.
   The Page Content Spec is explicit: unknown types must be *flagged for mapping, never
   created silently* — and never lost. A vendor export that uses `JOB_TITLE` where the
   tenant calls it `job_title` currently loses every one of those rows.
2. **Imported annotations are not training data.** `imported_annotations` has a `reviewed`
   flag but nothing consumes it. `annotation-export` (the training dataset builder) reads
   spans only. There is no per-file "training eligible" state and no way for the Tenant
   Admin to request training from an import.

## What Changes

- **Type mapping instead of silent skip.** On import, rows with unknown entity types are
  held, not discarded. The response returns an `unmapped_types` list. A new
  `POST /api/v1/annotation-imports/{source_file}/type-map` maps each unknown type either to
  an existing canonical entity type (rewriting the stored tags on those rows) or to a new
  entity type created through the existing `entity-config` API. No type is ever created
  implicitly.
- **`annotation_imports` header row per file** (table added in migration 041): holds
  `row_count`, the `type_map`, and `training_eligible_at`. A file becomes training-eligible
  when every row is imported and no unmapped type remains.
- **Imported rows join the training dataset.** `annotation-export` includes
  `imported_annotations` rows from training-eligible files, in the same token/tag shape it
  already emits, deduplicated against span-derived rows by source.
- **Tenant Admin can request training from an import.** The `/imported-documents` surface
  shows per-file training-eligibility and a "Request training" action wired to the existing
  `POST /api/v1/training-retrain-requests`.
- **RBAC.** `annotation-import` and the new type-map endpoint require `tenant_admin`;
  per-row review (`imported-annotations` PATCH / mark-reviewed) stays `annotator` or
  `tenant_admin` as today.
- **Portal.** `/imported-documents` gains an "Unmapped Types" tab and a "Map types" dialog
  (per the Page Content Spec wireframe), a per-file training-eligibility indicator, and the
  "Request training" action. The single-row review route `/imported-documents/[id]` is
  added, reusing the annotation workspace's palette and span components.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `annotation-import-ui`: unknown entity types are held and surfaced as `unmapped_types`
  rather than skipped; a type-mapping step maps them to existing or newly-created canonical
  entity types; an `annotation_imports` header row tracks per-file training-eligibility;
  the training dataset export includes imported rows from eligible files; the portal gains
  the mapping dialog, the eligibility indicator, the "Request training" action, and the
  single-row review route.

## Impact

- **Backend**: `src/annotation_service/api/v1/import_.py` (hold unmapped rows, return
  `unmapped_types`, write the `annotation_imports` header), a new type-map endpoint,
  `src/annotation_service/api/v1/export.py` (include eligible imported rows),
  `src/annotation_service/api/v1/_rbac.py` (apply `tenant_admin` gate). Reuses the
  `entity-config` create API and `services/notify.py`.
- **Database**: `annotation_imports` table exists (migration 041). This change adds
  `imported_annotations.mapped` (bool) or an equivalent "held pending mapping" marker, and
  a nullable `imported_annotations.source_file` FK-style link to `annotation_imports`.
  Additive.
- **Frontend**: `src/portal/src/app/(auth)/imported-documents/page.tsx` +
  `/[id]/page.tsx`, components under `src/portal/src/components/annotation/`.
- **No impact**: manual/automated annotation flows, model serving, extraction; System
  Admin training approval and model promotion.

## Open Questions

- **Tag rewrite vs mapping table.** When `JOB_TITLE → job_title`, do we rewrite the stored
  `tags` arrays on the affected rows, or keep an original-tag column plus a mapping applied
  at export time? Assume rewrite-in-place with the pre-map value retained on the
  `annotation_imports.type_map` for audit.
- **Eligibility and review.** Does a file need every row `reviewed = true` to be
  training-eligible, or only "imported with all types mapped"? The brief says imported
  labelled data is usable as training data without a mandated re-review. Assume
  types-mapped is sufficient for eligibility; `reviewed` stays an optional quality pass.
- **Dedup against spans.** If the same document was both manually annotated and imported,
  which wins in the export? Assume imported rows are tagged with a distinct source and both
  are emitted unless a later change adds reconciliation.
