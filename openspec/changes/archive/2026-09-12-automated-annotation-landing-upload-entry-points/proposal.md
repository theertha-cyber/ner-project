## Why

The Automated annotation landing page (`/annotate/automated`) shows a 4-step stepper and a
single "Start with step 1" button, but Step 1 ("Suggest Entity Types") reads from seed documents
that must already be sitting in the tenant's document library — the page itself gives a new
tenant admin no path to get those documents in, or to upload the optional Q&A-pair guidance
document that sharpens schema suggestion. A tenant admin arriving here for the first time has
nowhere to click before "Start with step 1" fails for lack of processed seed documents.

## What Changes

- Add a "Before you begin" section to the Automated landing page with two entry points:
  "Upload documents" (opens the uploader pre-set to Automated annotation mode) and "Upload Q&A
  pair" (opens the Q&A-pair uploader). Both link to the Documents page's existing upload dialog
  rather than duplicating upload UI.
- Extend the Documents page's `?upload=1` deep link to also accept `purpose` (`training` |
  `qa_pair`) and `mode` (`manual` | `automated`) query parameters, so a link can open the
  uploader already set to what the linking flow needs instead of always defaulting to Manual
  training uploads.
- Give `DocumentUpload` (and `UploadDialog`, which wraps it) an optional `defaultAnnotationMode`
  prop that seeds the annotation-mode radio's initial selection. The existing safety behavior —
  the selector always resets to Manual once a batch completes, regardless of how it started — is
  unchanged; only the very first render's selection can be seeded.

## Capabilities

### New Capabilities

- `automated-annotation-landing`: the `/annotate/automated` page's own pre-step-1 content — the
  "Before you begin" upload entry points and their navigation targets. Mirrors the existing
  `manual-annotation-landing` capability, which covers the equivalent page for the Manual flow.

### Modified Capabilities

- `portal-documents`: the "Upload deep link" requirement gains `purpose` and `mode` query
  parameters alongside the existing `upload=1`.
- `annotation-mode-selection`: the annotation-mode selector can now be seeded to a non-Manual
  initial selection by the caller; the per-batch reset-to-Manual invariant is unchanged.

## Impact

- Frontend: [app/(auth)/annotate/automated/page.tsx](src/portal/src/app/(auth)/annotate/automated/page.tsx),
  [app/(auth)/documents/page.tsx](src/portal/src/app/(auth)/documents/page.tsx),
  [components/documents/DocumentUpload.tsx](src/portal/src/components/documents/DocumentUpload.tsx),
  [components/documents/UploadDialog.tsx](src/portal/src/components/documents/UploadDialog.tsx).
- Tests: new [annotate/automated/page.test.tsx](src/portal/src/app/(auth)/annotate/automated/page.test.tsx);
  extended [documents/page.test.tsx](src/portal/src/app/(auth)/documents/page.test.tsx) and
  [DocumentUpload.annotationMode.test.tsx](src/portal/src/components/documents/DocumentUpload.annotationMode.test.tsx).
- No backend or database changes.
