## 1. Frontend: upload plumbing

- [x] 1.1 Add an optional `defaultAnnotationMode` prop to `DocumentUpload`, seeding the
  `annotationMode` state's initial value; the existing post-batch reset to `"manual"` is
  unchanged.
- [x] 1.2 Thread `defaultAnnotationMode` through `UploadDialog` to `DocumentUpload`.
- [x] 1.3 Documents page: read `purpose` and `mode` query parameters alongside `upload=1` and
  apply them (`setUploadPurpose`, a new `uploadMode` state) before opening the dialog; reset
  `uploadMode` to `undefined` when either in-page upload button is clicked directly, so a prior
  deep-linked mode doesn't leak into an unrelated upload.

## 2. Frontend: Automated landing page

- [x] 2.1 Add a "Before you begin" work-card section to `/annotate/automated/page.tsx` with
  "Upload documents" (`/documents?upload=1&purpose=training&mode=automated`) and "Upload Q&A
  pair" (`/documents?upload=1&purpose=qa_pair`).

## 3. Tests

- [x] 3.1 New `annotate/automated/page.test.tsx`: both cards render, each routes to the correct
  URL, and the primary "Start with step 1" action is unaffected.
- [x] 3.2 Extend `documents/page.test.tsx`: `?upload=1&purpose=qa_pair` opens the dialog with
  `purpose="qa_pair"`; `?upload=1&purpose=training&mode=automated` opens it with
  `defaultAnnotationMode="automated"`.
- [x] 3.3 Extend `DocumentUpload.annotationMode.test.tsx`: the selector seeds from
  `defaultAnnotationMode`, and still resets to Manual after a batch even when seeded as
  Automated.

## 4. Verification & Evidence

- [x] 4.1 Run the new/updated test files against the portal test container; confirm all pass.
- [x] 4.2 Run the full `src/components/documents` suite as a regression check; confirm the only
  failures match the pre-existing `StatusFilterTabs.test.tsx` baseline.
- [x] 4.3 Rebuild and restart the `portal` container.
- [x] 4.4 Live-verify in the browser: both "Before you begin" cards render on
  `/annotate/automated`; "Upload documents" opens the dialog on `/documents` with "Automated"
  already selected; "Upload Q&A pair" opens the Q&A-pair uploader.
- [ ] 4.5 Run `openspec validate automated-annotation-landing-upload-entry-points --type change
  --strict` and `openspec archive automated-annotation-landing-upload-entry-points --yes`.
