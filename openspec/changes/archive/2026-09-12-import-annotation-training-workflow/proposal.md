## Why

The Manual and Automated annotation flows both walk a tenant admin through a named workflow
ending in a "Train model" hand-off scoped to that workflow's own data
(`/training-jobs?source=manual`, `/training-jobs?source=automated`). The Import flow's landing
page (`/annotate/import`) had neither: it showed at-a-glance stats and a single "Imported files"
card, with no visible path from "I imported some files" to "now train on them," and no
source-scoped hand-off at all. Separately, its "＋ Import file" button linked to
`/imported-documents?import=1`, but nothing on that page read the `import` parameter — the link
opened the plain file list, not the file picker it implied.

## What Changes

- Add a "Your workflow" section to `/annotate/import` for `tenant_admin`: "1. Import file"
  (`/imported-documents?import=1`) and "2. Review imported files" (`/imported-documents`).
  `annotator` keeps the single existing "Imported files" review card, matching the Manual and
  Automated landing pages' pattern of giving annotators only the review-facing entry point.
- Fix `/imported-documents?import=1` to actually open the file picker on arrival, for
  `tenant_admin` — it previously did nothing.
- Add a "Train model" hand-off to `/annotate/import`, visible once at least one imported file is
  training-eligible, navigating to `/training-jobs?source=import` — the Import workflow's own
  entry point, so a run started from here trains only on imported data.
- Generalize `TrainModelBanner` (shared by Manual, and now Import) with optional `label`/
  `sublabel` overrides, since "N documents annotated" is Manual's fact, not Import's ("N
  imported files training-eligible").

## Capabilities

### New Capabilities

- `import-annotation-landing`: the `/annotate/import` page's workflow steps and Train Model
  hand-off. Mirrors `manual-annotation-landing` and `automated-annotation-landing`, the
  equivalent capabilities for the other two workflows.

### Modified Capabilities

- `annotation-import-ui`: `/imported-documents` gains an `import=1` deep link that opens the
  file picker on arrival, for `tenant_admin`.

## Impact

- Frontend: [app/(auth)/annotate/import/page.tsx](src/portal/src/app/(auth)/annotate/import/page.tsx),
  [components/imported-documents/ImportedDocuments.tsx](src/portal/src/components/imported-documents/ImportedDocuments.tsx)
  (new `useSearchParams` effect), [components/annotate/TrainModelBanner.tsx](src/portal/src/components/annotate/TrainModelBanner.tsx)
  (`label`/`sublabel` props, backward-compatible defaults).
- Tests: new [annotate/import/page.test.tsx](src/portal/src/app/(auth)/annotate/import/page.test.tsx),
  new [ImportedDocuments.test.tsx](src/portal/src/components/imported-documents/ImportedDocuments.test.tsx);
  extended [TrainModelBanner.test.tsx](src/portal/src/components/annotate/TrainModelBanner.test.tsx);
  fixed a regression this change caused in the pre-existing
  [AnnotationImportFlow.test.tsx](src/portal/src/app/(auth)/imported-documents/AnnotationImportFlow.test.tsx)
  (added the `next/navigation` mock the new `useSearchParams` call now requires).
- No backend changes — `source_scope=import` gating on `POST /api/v1/training-jobs` and
  `GET /api/v1/annotation-export?source=import` were both already implemented and tested in an
  earlier change this session; this change only wires the portal's Import landing page to the
  existing `?source=` entry point the Training Jobs screen already recognizes.

## Open Question — flagged, not resolved here

`/imported-documents` already has a per-file "Request training" button (pre-existing,
`annotation-import-ui`'s "Request Training From an Import" requirement) that calls
`POST /api/v1/training-retrain-requests` directly — a different endpoint that creates an
**unscoped** job (no `source_scope`), which can blend with other workflows' data. This change's
new "Train model" hand-off is properly scoped (`source_scope=import`). The two paths now
coexist with different scoping guarantees for what looks like the same action. This is called
out rather than silently fixed: removing or rescoping the older button is a separate decision,
not something this change makes unilaterally.
