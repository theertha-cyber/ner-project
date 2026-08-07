## 0. Task state machine (blocks the Start action)

- [x] 0.1 Add `"pending": ["in-progress"]` to `valid_transitions` in `src/annotation_service/api/v1/tasks.py:175-177`. Add exactly one key — do not modify any existing list, do not make `completed` non-terminal, and do not create a transition into `pending`.
- [x] 0.2 Verify scenarios 1–5 — `tests/test_annotation_workspace.py`.
  - Added `test_task_pending_can_be_started`, `test_task_pending_cannot_skip_to_completed`, `test_task_completed_cannot_move_to_pending`; strengthened `test_7_15` to assert the `NO_SPANS` code. Scenario 3 is covered by the existing `test_7_13` / `test_7_14` / `test_task_recomplete_*`. **8 passed.**
  - Environment: the suite needs a test Postgres on `localhost:54320` (a recurring pre-existing gap noted in several archived changes) — started container `ner-pytest-db`; the dev DB is untouched. Also installed the missing `tenacity` dep and added `bio_tags TEXT[]` to the `spans` fixture DDL in `tests/conftest.py` and `tests/test_annotation_workspace.py`, which migration 009 adds but the fixtures lacked.
  - Not fixed (pre-existing, unrelated): `test_7_16/17/18` fail because the export tests' fixture DDL omits `imported_annotations`.

## 1. Pre-flight data checks

- [x] 1.1 Query live tenant schemas for `annotation_tasks` rows with `status = 'open'` and record the result — determines whether the legacy-status accommodation in design.md Decision 5 is load-bearing or merely defensive (proposal.md Open Questions).
  - **Finding: `open` does not exist; `pending` does.** Live counts across all 10 tenant schemas: `tenant_demo_tenant` → `completed=21, pending=14`; `tenant_e57120b0…` (Inapp HR) → `in-progress=1`; all others empty. Zero `open` rows and zero `unannotated` rows anywhere. `pending` is written by `src/gateway/seed.py:248`. It is absent from the `annotation_service` state machine (`tasks.py:175-177`), so `allowed = []` and every transition out of `pending` returns 422 INVALID_TRANSITION — those 14 tasks cannot be started through the API. Decision 5's alias must target `pending`, not `open`.
- [x] 1.2 Search `src/annotation_service/` and `src/gateway/` for any writer of `annotation_tasks.updated_at`. Record the finding; if none exists, confirm the Decision 4 `COALESCE` fallback is required and note it for a follow-up change.
  - **Finding: no writer exists.** The only UPDATE against the table is `SET status = :status` (`src/annotation_service/api/v1/tasks.py:202`); `updated_at` appears only in a SELECT list (`tasks.py:112`). The column is always NULL in practice. Decision 4's `COALESCE` fallback is required, not merely defensive.
- [x] 1.3 Confirm `public.entity_definitions` carries active rows for the seeded dev tenant, so per-type readiness has data to render against.
  - **Finding: only one tenant has any.** `e57120b0…` (Inapp HR) has 8 definitions, all active: COMPANY, CONTACT_DETAILS, DEGREE, INSTITUTION, JOB_TITLE, PROGRAMMING_LANGUAGE, TOOL_FRAMEWORK, YEARS_OF_EXP. Its spans cover only 3 of those (PROGRAMMING_LANGUAGE 18, JOB_TITLE 4, CONTACT_DETAILS 2). `demo-tenant` has **zero** entity definitions but **525 spans** across 5 types (DATE/MONEY/ORG/LOC/PER, 105 each) — so a definitions-only enumeration reports readiness as unavailable for a tenant that has real annotation data.

## 2. Threshold semantics (backend)

- [x] 2.1 In `src/gateway/api/v1/dashboard.py`, replace `DATASET_READINESS_ENTITY_THRESHOLD = 500` with `DATASET_READINESS_ENTITIES_PER_TYPE = 200`, updating the module comment to state the per-type semantics.
- [x] 2.2 Rewrite `_annotator_side_panel` to evaluate the **union** of `public.entity_definitions` (filtered by `tenant_id`, `is_active = true`) and the distinct `entity_type` values in `{schema}.spans`, returning one row per type — including defined types with zero spans and spanned types with no definition.
- [x] 2.3 Compute `bar` as the mean of `min(count / 200, 1)` across all evaluated types, expressed as a percentage; return "N of M types ready" for the panel's supporting copy.
- [x] 2.4 Return the unavailable state (not `0%` or `100%`) only when the union is empty — no active entity definitions **and** no spans.
- [x] 2.5 Order `sideRows` least-progress-first and set each row's `pct` to progress-toward-threshold, replacing the share-of-total calculation and the hardcoded `c="blue"` with progress-based colouring.
- [x] 2.6 Update `sideMeta` / `sideBot` copy to state the per-type threshold instead of "500 entities unlocks training".
- [x] 2.7 Rewrite the `_tenant_curated_activity` "Dataset reached training readiness" event to fire at the timestamp the last active entity type crossed 200, replacing the `ROW_NUMBER() = 500` query.
- [x] 2.8 Verify scenarios 21–31 and 40–41 — `tests/test_dashboard_summary_roles.py`.
  - Added 9 readiness tests incl. the discriminating cap case (2000 + 0 spans → `bar` 50.0, not 100.0), zero-span defined type, spanned-type-without-definition (demo-tenant's shape), least-progress ordering, inactive exclusion, and tenant scoping.

## 3. Annotator stat set (backend)

- [x] 3.1 Add a `ContinueWork` Pydantic model (`taskId`, `documentId`, `documentName`, `status`, `spanCount`, `mode` — one of `resume`/`start`/`review`) and an optional `continueWork` field on `DashboardData`, following the `responseQuality` / `activeModel` precedent.
- [x] 3.2 Implement continue-work selection in `_annotator_data`: most recently worked `in-progress` task (`resume`) → oldest not-started task (`start`) → most recently worked `completed` task (`review`) → `None`. Order by `COALESCE(annotation_tasks.updated_at, MAX(spans.updated_at) for the document, annotation_tasks.created_at)`. Match not-started against all three of `pending`, `unannotated`, `open`.
- [x] 3.3 Wrap the continue-work query in its own `try/except` with `await db.rollback()` recovery so a failure sets `continueWork = None` without affecting other cards.
- [x] 3.4 Replace the `Assigned tasks` stat with a `COUNT(*) FILTER (WHERE status = 'completed')` over total fraction string, and set its `sub` to the remaining count (or the no-tasks message at `"0/0"`). The denominator counts every assigned task regardless of status vocabulary.
- [x] 3.5 Remove the `Entities Annotated` stat and its unfiltered `SELECT COUNT(*) FROM {schema}.spans` query.
- [x] 3.6 Keep the `Completion` stat, removing its `"active"` sub.
- [x] 3.7 Verify scenarios 6–14 — `tests/test_dashboard_summary_roles.py`.
  - Added 6 continue-work tests covering resume/start/review/null precedence, NULL-`updated_at` span-activity ordering, and the degrade-only-this-card path (patched to raise; response still 200 with stats and readiness intact).
- [x] 3.8 Verify scenarios 32–34 and 44 — `tests/test_dashboard_summary_roles.py`.

## 4. Placeholder sub-label removal (backend, all roles)

- [x] 4.1 Remove the `"active"` sub from the annotator stats (`dashboard.py:893-895`), passing `""` where no informative sub exists.
- [x] 4.2 Remove the `"active"` sub from the system_admin stats (`dashboard.py:292,294,296`), retaining `"service unavailable"` diagnostics and the `"needs review"` pending-approvals sub.
- [x] 4.3 Replace the tenant_admin Documents `doc_sub = "active"` fallbacks (`dashboard.py:370,373`) with `""`.
- [x] 4.4 Confirm `ActiveModelInfo.status = "active"` (`dashboard.py:64,706`) and `ActivityRow.tk = "active"` (`dashboard.py:645`) are untouched — these are a deployment state and a tag colour key, not sub-labels.
- [x] 4.5 Verify scenarios 35–39 — `tests/test_dashboard_summary_roles.py`.
- [x] 4.6 Verify scenarios 42–43 and 59–60 — `tests/test_dashboard_summary.py`.

## 5. Portal types and cards

- [x] 5.1 Add `ContinueWork` to `src/portal/src/types/dashboard.ts` and make `stats` a variable-length array on `DashboardData`.
- [x] 5.2 Create `src/portal/src/components/dashboard/ContinueWorkCard.tsx` with resume / start / review / caught-up states, single-line ellipsis truncation, and a `title` attribute carrying the full document name. A `review` card must not describe finished work as outstanding.
- [x] 5.3 Render `ContinueWorkCard` as the first cell of the annotator stat row in `src/portal/src/app/(auth)/dashboard/page.tsx`, keeping the grid column count equal to the total card count.
- [x] 5.4 Add a skeleton state for `ContinueWorkCard` consistent with `StatCardSkeleton`.
- [x] 5.5 Verify scenarios 15–20 — `src/portal/src/components/dashboard/ContinueWorkCard.test.tsx` (new).
- [x] 5.6 Verify scenarios 61–66 — `src/portal/src/components/dashboard/StatCard.test.tsx`.
- [x] 5.7 Verify scenarios 50–58 — `src/portal/src/hooks/use-dashboard-data.test.ts` and `src/portal/src/lib/dashboard.test.ts`.
  - Payload shape covered by the backend role tests (which assert the rendered contract end-to-end through the HTTP endpoint) plus `ContinueWorkCard.test.tsx`; no new hook-level test was needed since the hook is a pass-through.

## 6. Portal readiness panel

- [x] 6.1 Update `MetricsPanel` so `sideRows` render count-against-threshold values and progress-based bar colours, with starved and satisfied types visually distinct.
- [x] 6.2 Cap the rendered row count and show a "+N more" indicator when evaluated entity types are omitted.
- [x] 6.3 Verify scenarios 67–72 — `src/portal/src/components/dashboard/MetricsPanel.test.tsx`.
- [x] 6.4 Replace the static "+N more" overflow label with a view-all control that expands the panel in place to every entity type and collapses back. State is local to the panel and does not persist.
- [x] 6.5 Verify scenarios 73–75 — `src/portal/src/components/dashboard/MetricsPanel.test.tsx`. **15 passed.** Portal suite now **542 passed, 11 failed** (same pre-existing 11).
  - Portal suite: **538 passed, 11 failed** — the 11 are byte-identical to the pre-change baseline (missing `lucide-react`/`react-markdown` deps and unrelated stale tests), so zero regressions.

## 7. Annotation workspace deep link

- [x] 7.1 Read the `task` query parameter in `AnnotationPage` and pre-select the matching task on first load, resolving it against the user's visible queue.
- [x] 7.2 Fall back to default selection without an error state when the parameter is absent, unknown, or names a task outside the user's queue.
- [x] 7.3 Ensure the parameter affects initial selection only and does not override later user selection or the `localStorage` layout-mode behaviour.
- [x] 7.4 Verify scenarios 45–49 — `src/portal/src/components/annotation/AnnotationPage.annotator.test.tsx`.
  - 5 deep-link tests added (pre-select, unknown id, foreign task, no-parameter, layout preserved). **7 passed.**
  - Also widened `AnnotationTask["status"]` and the two status colour/label maps to carry `pending`/`open`, and made `handleSelectTask` auto-start `pending` tasks — without that the Start action would open a task but never transition it.

## 8. Training gate

- [x] 8.1 Add `NER_MIN_ENTITIES_PER_TYPE` (default `0`) to `create_training_job` in `src/training_service/api/v1/training_jobs.py`, leaving `NER_MIN_TRAINING_ENTITIES` and its semantics untouched.
- [x] 8.2 When the value is greater than zero, count spans per entity type across the tenant's active entity definitions and reject with `422` naming each short type and its count.
- [x] 8.3 Confirm no change to `docker-compose.yml` or `.env` — the gate ships inert per design.md Decision 7.
- [x] 8.4 Verify scenarios 73–78 — `tests/test_training_jobs_api.py`.
  - 6 gate tests added. **21 passed, 1 failed** (was 3 passed / 13 failed / 16 errors at baseline). Unblocked the file by adding the missing `public.audit_events` table to `scripts/setup_test_db.py`; the 1 remaining failure is pre-existing and concerns job *retrieval* against a tenant with no schema, not submission.

## 9. Documentation

- [x] 9.1 Created `docs/adr/010-per-entity-type-dataset-threshold.md` with `**Supersedes**: ADR-006 (partially — ...)` naming only the dataset-threshold clauses, following the ADR-009 format. Record the 200-per-active-type figure and the reasoning from design.md Decision 1.
- [x] 9.2 Confirm `docs/adr/006-training-infrastructure.md` is unmodified (`git diff` empty) — supersession, not in-place edit. **Verified: diff empty.**

## 10. Test migration

- [x] 10.1 Rewrite the assertions in `tests/test_dashboard_summary_roles.py` and `tests/test_dashboard_summary.py` that pin the 500-total readiness behaviour and the removed `Entities Annotated` stat.
  - **Result: 75 passed, 4 failed** across both files. All 4 remaining failures were confirmed pre-existing by running the suite with `src/` changes stashed (baseline was 6 failures) — so this change causes zero regressions and repairs 2 previously-broken tests.
  - Fixed two more stale test fixtures found en route: `annotation_tasks.updated_at` missing from `tests/conftest.py` (migration 004), and `_seed_annotator_tasks` using `"annotated"` as a task status — that is a *document* status in `seed.py`, never a task status, so it matched no production code path.
- [x] 10.2 Confirm the 15 existing `NER_MIN_TRAINING_ENTITIES` call sites in `tests/test_training_jobs_api.py` still pass unchanged.
- [x] 10.3 Grep `src/` for any residual reference to a 500-span total threshold and remove it.
  - `DATASET_READINESS_ENTITY_THRESHOLD` fully removed; only the new per-type constant remains.

## 11. Verification & Evidence

- [x] 11.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 11.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
  - All 16 evidence rows populated. Row 16 is a live API trace against the rebuilt gateway and the real dev database for the Inapp HR tenant, confirming the predicted readiness drop (5% → 1.5%) and the five previously-invisible zero-span entity types now appearing. Visual browser confirmation is left to the reviewer at sign-off — logging in requires credentials the agent must not enter.
- [x] 11.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 11.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 11.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 11.6 Run `openspec validate annotator-dashboard-cards-and-per-entity-readiness --type change --strict` and confirm it exits clean before archive.
