# Verification Plan

**Change:** import-workspace-bulk-accept-and-train-handoff
**Generated:** 2026-09-15
**Status:** 🟡 Automated evidence collected this session; Audit Record sign-off still needs a
human reviewer.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Verification Artifact | Status |
|---|-----------|-------------|----------|------------------------|--------|
| 1 | annotation-import-ui | Bulk-Accept Unmapped Types | Accept all as new types creates every unmapped type in one call | src/portal/.../imported-documents/ImportedDocuments.test.tsx::"submits every unmapped type as a create-new mapping in one call" | [x] |
| 2 | annotation-import-ui | Bulk-Accept Unmapped Types | The file list reports current unmapped types | tests/test_annotation_import.py::test_list_import_files | [x] |
| 3 | annotation-import-ui | Bulk-Accept Unmapped Types | A file with nothing pending reports no unmapped types | tests/test_annotation_import.py::test_list_import_files | [x] |
| 4 | annotation-import-ui | Request Training From an Import (modified) | Request training from an eligible import | src/portal/.../imported-documents/ImportedDocuments.test.tsx::"routes straight to Models & Training scoped to the import source — no approval request" | [x] |
| 5 | annotation-import-ui | Import Deep Link (removed) | mechanic removed — picker never auto-opens | src/portal/.../imported-documents/ImportedDocuments.test.tsx::"never auto-opens the file picker on mount, regardless of how the page was reached" | [x] |
| 6 | import-annotation-landing | Workflow Steps (modified) | tenant_admin sees the two-step workflow in order | src/portal/.../annotate/import/page.test.tsx::"step 1 routes to the imported files workspace — the picker opens only on an explicit click there" | [x] |

Two supporting tests not tied to a named scenario, kept for a clearer failure signal:
`ImportedDocuments.test.tsx::"opens the file picker when the tenant admin clicks Import file"`
(the explicit-click path Import Deep Link's removal still needs to keep working) and
`AnnotationImportFlow.test.tsx`'s existing role-visibility tests, re-run unchanged to confirm the
`next/navigation` mock addition (`useRouter`) didn't regress them.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|--------------------|-----------------------|
| 1 | Silently keeping the retrain-request side effect | "Train model" could have been implemented as navigate-**and**-still-call `POST /training-retrain-requests`, quietly leaving the approval-gated job creation in place under a renamed button | Confirmed the button's `onClick` is only `router.push("/training-jobs?source=import")`; `useRequestRetrain` is no longer imported by `ImportedDocuments.tsx` at all — removing the import, not just the call site, rules out an accidental leftover call elsewhere in the file |
| 2 | Reintroducing the auto-open bug via a different trigger | Deleting only the `useEffect` but leaving `?import=1` in the landing page's hrefs would leave a dead, confusing query param and risk a future re-implementation re-wiring it | Both hrefs on the landing page (`annotate/import/page.tsx`) were updated to plain `/imported-documents` in the same change, and a dedicated test asserts the picker never auto-opens "regardless of how the page was reached" |
| 3 | Bulk-accept silently dropping rows instead of mapping them | "Accept all as new types" could have been implemented as marking rows reviewed/skipped rather than actually creating the entity types and remapping tags | The bulk action reuses the exact same `POST .../type-map` endpoint and `{"create": true}` mapping shape the existing, already-shipped per-type dropdown uses — no new backend path, so the same tested create-and-rewrite behavior applies |
| 4 | `unmapped_types` computed against the wrong tenant's entity types | A per-tenant computation touching every pending row could leak another tenant's canonical types into the "unknown" check if the schema/tenant_id were mixed up | `_unmapped_types_for_file` takes the already-tenant-scoped `schema` and a `known_lower` set fetched via the same `get_known_entity_types_lower(session, tenant_id)` helper every other endpoint in this file uses — no new tenant-resolution path introduced |

---

## 3. Pattern & ADR Compliance

- No new backend endpoint: the bulk-accept action reuses the existing
  `POST /api/v1/annotation-imports/{source_file}/type-map` endpoint, unchanged in behavior —
  only `GET /api/v1/annotation-imports`'s response grew a field.
- `require_tenant_admin` RBAC gates on both endpoints touched here are unchanged.
- No database migration: `unmapped_types` is derived from existing columns
  (`imported_annotations.pending_mapping`, `imported_annotations.tags`) at request time, not
  stored.

---

## 4. Evidence Log

- **Backend:** `pytest tests/test_annotation_import.py` — 36/36 passed, run in
  `ner-project-annotation_service-1` against `postgres-test`/`ner_dev`.
- **Frontend:** `vitest run` on the three touched test files
  (`ImportedDocuments.test.tsx`, `AnnotationImportFlow.test.tsx`, `annotate/import/page.test.tsx`)
  — 13/13 passed, run in `ner-portal-test`.
- **Docker:** rebuilt and restarted both `annotation_service` and `portal` (both are
  Docker-`build:`-based images, not live-mounted dev servers — confirmed this was the actual
  cause of an initial in-session false negative, where the bulk-accept button threw
  `unmapped_types is not iterable` because the *running* `annotation_service` process predated
  the backend change despite the source file on disk being current).
- **Live browser verification (demo-corp tenant):** reproduced the pre-fix bugs first (picker
  reopened after Review → Back; bulk-accept crashed against the stale container), then
  re-verified post-rebuild: bulk-accept's `POST .../type-map` returned 201 and the file flipped
  to "Training: Eligible"; Review → Back left the picker closed (instrumented
  `HTMLInputElement.prototype.click` call count stayed at 0 across the round-trip); "Train
  model" landed on `/training-jobs?source=import` with the Submit Training Job panel auto-open
  and "Training source: Imported annotations" shown.

---

## 5. Audit Record

- [ ] Human reviewer has re-run the test suites above independently.
- [ ] Human reviewer sign-off: ______________________ Date: ______________
