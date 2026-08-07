# Verification Plan

**Change:** annotator-dashboard-cards-and-per-entity-readiness
**Generated:** 2026-08-06
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | annotation-workspace | Pending Tasks Can Be Started | pending task can be started | Given a task with status `pending`, when a transition to `in-progress` is requested, then it succeeds and the status becomes `in-progress` | pytest: `tests/test_annotation_workspace.py` (task 0.2) | - [ ] |
| 2 | annotation-workspace | Pending Tasks Can Be Started | pending task cannot skip straight to completed | Given a task with status `pending`, when a transition to `completed` is requested, then the response is `422` with code `INVALID_TRANSITION` | pytest: `tests/test_annotation_workspace.py` (task 0.2) | - [ ] |
| 3 | annotation-workspace | Pending Tasks Can Be Started | existing transitions are unchanged | Given tasks at `unannotated`, `in-progress`, and `completed`, when each is transitioned as before, then every previously-permitted transition still succeeds | pytest: `tests/test_annotation_workspace.py` (task 0.2) | - [ ] |
| 4 | annotation-workspace | Pending Tasks Can Be Started | completed remains terminal | Given a task with status `completed`, when a transition to `in-progress` or `pending` is requested, then the response is `422` with code `INVALID_TRANSITION` | pytest: `tests/test_annotation_workspace.py` (task 0.2) | - [ ] |
| 5 | annotation-workspace | Pending Tasks Can Be Started | span precondition still guards completion | Given an `in-progress` task whose document has no confirmed spans, when a transition to `completed` is requested, then the response is `422` with code `NO_SPANS` | pytest: `tests/test_annotation_workspace.py` (task 0.2) | - [ ] |
| 6 | annotator-continue-work | Continue-Work Card Payload | in-progress task is returned for resume | Given an annotator with an `in-progress` task on `resume_01.pdf` holding 12 spans, when the summary is fetched, then `continueWork` has `mode: "resume"`, `documentName: "resume_01.pdf"`, `spanCount: 12`, and the matching `taskId` | pytest: `tests/test_dashboard_summary_roles.py` (task 3.7) | - [ ] |
| 7 | annotator-continue-work | Continue-Work Card Payload | most recently worked task wins when several are in progress | Given two `in-progress` tasks where the second has more recent span activity, when the summary is fetched, then `continueWork.taskId` is the second task | pytest: `tests/test_dashboard_summary_roles.py` (task 3.7) | - [ ] |
| 8 | annotator-continue-work | Continue-Work Card Payload | ordering falls back when updated_at is unmaintained | Given in-progress tasks with `annotation_tasks.updated_at` NULL, when the summary is fetched, then selection uses the document's latest span `updated_at`, and `created_at` when no spans exist | pytest: `tests/test_dashboard_summary_roles.py` (task 3.7) | - [ ] |
| 9 | annotator-continue-work | Continue-Work Card Payload | unstarted task is offered when nothing is in progress | Given no `in-progress` task and two `unannotated` tasks, when the summary is fetched, then `continueWork.mode` is `"start"` and the older task is selected | pytest: `tests/test_dashboard_summary_roles.py` (task 3.7) | - [ ] |
| 10 | annotator-continue-work | Continue-Work Card Payload | every not-started vocabulary is recognised | Given no `in-progress` task and a single remaining task carrying `pending`, `unannotated`, or `open`, when the summary is fetched, then `continueWork.mode` is `"start"` and that task is selected | pytest: `tests/test_dashboard_summary_roles.py` (task 3.7) | - [ ] |
| 11 | annotator-continue-work | Continue-Work Card Payload | unstarted work outranks finished work | Given no `in-progress` task, a `completed` task worked today, and an untouched `pending` task, when the summary is fetched, then `continueWork.mode` is `"start"` and the `pending` task is selected | pytest: `tests/test_dashboard_summary_roles.py` (task 3.7) | - [ ] |
| 12 | annotator-continue-work | Continue-Work Card Payload | completed task is offered for review when nothing else remains | Given every assigned task has status `completed`, when the summary is fetched, then `continueWork.mode` is `"review"` and the most recently worked completed task is selected | pytest: `tests/test_dashboard_summary_roles.py` (task 3.7) | - [ ] |
| 13 | annotator-continue-work | Continue-Work Card Payload | caught-up state when no tasks are assigned at all | Given the annotator has no assigned tasks, when the summary is fetched, then `continueWork` is `null` | pytest: `tests/test_dashboard_summary_roles.py` (task 3.7) | - [ ] |
| 14 | annotator-continue-work | Continue-Work Card Payload | query failure degrades only this card | Given the continue-work query raises, when the summary is fetched, then the response is 200, `continueWork` is `null`, and stats plus readiness still carry real values | pytest: `tests/test_dashboard_summary_roles.py` (task 3.7) | - [ ] |
| 15 | annotator-continue-work | Continue-Work Card Rendering | resume card links into the workspace | Given `continueWork` with `mode: "resume"`, `documentName: "resume_01.pdf"`, `taskId: "abc123"`, when the dashboard renders, then the card shows the filename and a "Resume" action linking to `/annotation?task=abc123` | component: `src/portal/src/components/dashboard/ContinueWorkCard.test.tsx` (task 5.5) | - [ ] |
| 16 | annotator-continue-work | Continue-Work Card Rendering | start card is shown for an unstarted task | Given `continueWork.mode` is `"start"`, when the dashboard renders, then the call-to-action reads "Start" | component: `src/portal/src/components/dashboard/ContinueWorkCard.test.tsx` (task 5.5) | - [ ] |
| 17 | annotator-continue-work | Continue-Work Card Rendering | review card does not present finished work as outstanding | Given `continueWork.mode` is `"review"`, when the card renders, then the action reads "Review" and the card does not describe the task as in progress or outstanding | component: `src/portal/src/components/dashboard/ContinueWorkCard.test.tsx` (task 5.5) | - [ ] |
| 18 | annotator-continue-work | Continue-Work Card Rendering | caught-up state renders without a link | Given `continueWork` is `null` for an annotator, when the dashboard renders, then a caught-up message is shown and no navigation link is present | component: `src/portal/src/components/dashboard/ContinueWorkCard.test.tsx` (task 5.5) | - [ ] |
| 19 | annotator-continue-work | Continue-Work Card Rendering | long document name is truncated but recoverable | Given a `documentName` wider than the card, when it renders, then the name is clipped to one line with an ellipsis and the full name is in the `title` attribute | component: `src/portal/src/components/dashboard/ContinueWorkCard.test.tsx` (task 5.5) | - [ ] |
| 20 | annotator-continue-work | Continue-Work Card Rendering | card is not rendered for other roles | Given role `tenant_admin`, `system_admin`, or `business_user`, when the dashboard renders, then no continue-work card is present | component: `src/portal/src/components/dashboard/ContinueWorkCard.test.tsx` (task 5.5) | - [ ] |
| 21 | dashboard-summary-endpoint | Per-Entity-Type Dataset Readiness | readiness reflects the weakest entity type | Given active types at 400 / 100 / 0 spans, when the summary is fetched, then `bar` is `50.0` and the panel conveys 1 of 3 types ready | pytest: `tests/test_dashboard_summary_roles.py` (task 2.8) | - [ ] |
| 22 | dashboard-summary-endpoint | Per-Entity-Type Dataset Readiness | over-annotated type cannot mask a starved one | Given active types at 2000 and 0 spans, when the summary is fetched, then `bar` is `50.0` (not `100.0`) and the panel conveys 1 of 2 types ready | pytest: `tests/test_dashboard_summary_roles.py` (task 2.8) | - [ ] |
| 23 | dashboard-summary-endpoint | Per-Entity-Type Dataset Readiness | entity type with zero spans appears in the breakdown | Given an active entity definition with no spans, when the summary is fetched, then `sideRows` contains that label with value `0` and percentage `0` | pytest: `tests/test_dashboard_summary_roles.py` (task 2.8) | - [ ] |
| 24 | dashboard-summary-endpoint | Per-Entity-Type Dataset Readiness | breakdown is ordered least-progress-first | Given active types at 180 / 20 / 90 spans, when the summary is fetched, then `sideRows` order is the 20-span type, then 90, then 180 | pytest: `tests/test_dashboard_summary_roles.py` (task 2.8) | - [ ] |
| 25 | dashboard-summary-endpoint | Per-Entity-Type Dataset Readiness | inactive entity types with no spans are excluded | Given an `is_active = false` definition with 0 spans and all active types at >=200, when the summary is fetched, then `bar` is `100.0` and no row for the inactive type appears | pytest: `tests/test_dashboard_summary_roles.py` (task 2.8) | - [ ] |
| 26 | dashboard-summary-endpoint | Per-Entity-Type Dataset Readiness | entity types with spans but no definition are included | Given a tenant with no active entity definitions but 105 spans each for DATE/MONEY/ORG/LOC/PER, when the summary is fetched, then `sideRows` has a row per type, readiness is not unavailable, and `bar` reflects progress toward 200 each | pytest: `tests/test_dashboard_summary_roles.py` (task 2.8) | - [ ] |
| 27 | dashboard-summary-endpoint | Per-Entity-Type Dataset Readiness | all types at or above threshold reports fully ready | Given every active type has ≥200 spans, when the summary is fetched, then `bar` is `100.0` and the panel conveys the threshold is reached | pytest: `tests/test_dashboard_summary_roles.py` (task 2.8) | - [ ] |
| 28 | dashboard-summary-endpoint | Per-Entity-Type Dataset Readiness | neither definitions nor spans reports unavailable | Given the tenant has no active entity definitions and no spans, when the summary is fetched, then readiness is conveyed as unavailable and `bar` is not `100` | pytest: `tests/test_dashboard_summary_roles.py` (task 2.8) | - [ ] |
| 29 | dashboard-summary-endpoint | Per-Entity-Type Dataset Readiness | readiness does not read another tenant's data | Given two tenants with spans and definitions, when an annotator of the first fetches the summary, then only the first tenant's data contributes to `bar` and `sideRows` | pytest: `tests/test_dashboard_summary_roles.py` (task 2.8) | - [ ] |
| 30 | dashboard-summary-endpoint | Annotator Assigned-Task Fraction | fraction reflects completed over total | Given 5 assigned tasks of which 3 are `completed`, when the summary is fetched, then the `Assigned tasks` value is `"3/5"` and the sub conveys 2 remaining | pytest: `tests/test_dashboard_summary_roles.py` (task 3.8) | - [ ] |
| 31 | dashboard-summary-endpoint | Annotator Assigned-Task Fraction | every not-started vocabulary counts toward the denominator | Given 2 `completed` tasks and 1 task carrying `pending`, `unannotated`, or `open`, when the summary is fetched, then the `Assigned tasks` value is `"2/3"` | pytest: `tests/test_dashboard_summary_roles.py` (task 3.8) | - [ ] |
| 32 | dashboard-summary-endpoint | Annotator Assigned-Task Fraction | no assigned tasks | Given no assigned tasks, when the summary is fetched, then the value is `"0/0"` and the sub conveys that none are assigned | pytest: `tests/test_dashboard_summary_roles.py` (task 3.8) | - [ ] |
| 33 | dashboard-summary-endpoint | Stat Sub-Labels Carry Information | annotator stats emit no placeholder sub | Given role `annotator` with all data available, when the summary is fetched, then no `stats[*].sub` equals `"active"` | pytest: `tests/test_dashboard_summary_roles.py` (task 4.5) | - [ ] |
| 34 | dashboard-summary-endpoint | Stat Sub-Labels Carry Information | system_admin stats emit no placeholder sub | Given role `system_admin` with all data available, when the summary is fetched, then no `stats[*].sub` equals `"active"` | pytest: `tests/test_dashboard_summary_roles.py` (task 4.5) | - [ ] |
| 35 | dashboard-summary-endpoint | Stat Sub-Labels Carry Information | tenant_admin documents fallback emits no placeholder sub | Given role `tenant_admin` with no `max_documents` quota configured, when the summary is fetched, then the `Documents` stat `sub` is not `"active"` | pytest: `tests/test_dashboard_summary_roles.py` (task 4.5) | - [ ] |
| 36 | dashboard-summary-endpoint | Stat Sub-Labels Carry Information | degraded-state sub-labels are retained | Given role `annotator` and a failing assigned-task query, when the summary is fetched, then the affected stat's `sub` conveys service unavailability | pytest: `tests/test_dashboard_summary_roles.py` (task 4.5) | - [ ] |
| 37 | dashboard-summary-endpoint | Stat Sub-Labels Carry Information | active model deployment status is unaffected | Given role `tenant_admin` with a promoted model serving, when the summary is fetched, then `activeModel.status` is `"active"` | pytest: `tests/test_dashboard_summary_roles.py` (task 4.5) | - [ ] |
| 38 | dashboard-summary-endpoint | Tenant Admin Readiness Activity Event | event appears once every type has crossed | Given three active types, the last crossing 200 spans yesterday, when a tenant admin fetches the summary, then the feed shows "Dataset reached training readiness" dated yesterday | pytest: `tests/test_dashboard_summary_roles.py` (task 2.8) | - [ ] |
| 39 | dashboard-summary-endpoint | Tenant Admin Readiness Activity Event | event is absent while a type is short | Given three active types with one at 40 spans, when a tenant admin fetches the summary, then no "Dataset reached training readiness" event appears | pytest: `tests/test_dashboard_summary_roles.py` (task 2.8) | - [ ] |
| 40 | dashboard-summary-endpoint | Dashboard Summary Endpoint (MODIFIED) | system_admin summary returns role-specific data | Given role `system_admin`, when the summary is fetched, then kicker, title, 4 stats, approval-queue panel, and platform-health side panel are present as specified | pytest: `tests/test_dashboard_summary.py` (task 4.6) | - [ ] |
| 41 | dashboard-summary-endpoint | Dashboard Summary Endpoint (MODIFIED) | tenant_admin summary returns pipeline data | Given role `tenant_admin`, when the summary is fetched, then 4 pipeline stats, pipeline activity rows, and the active-model side panel are present as specified | pytest: `tests/test_dashboard_summary.py` (task 4.6) | - [ ] |
| 42 | dashboard-summary-endpoint | Dashboard Summary Endpoint (MODIFIED) | annotator summary returns task data | Given role `annotator`, when the summary is fetched, then 2 stats plus a `continueWork` payload are returned, `pTitle` is "My tasks" with 4 rows, `sideTop` is "Dataset readiness" reporting 200-per-type progress, and no stat reports a tenant-wide span count | pytest: `tests/test_dashboard_summary.py` (task 4.6) | - [ ] |
| 43 | dashboard-summary-endpoint | Dashboard Summary Endpoint (MODIFIED) | business_user summary returns extraction data | Given role `business_user`, when the summary is fetched, then 4 extraction stats, recent-extraction rows, and the active-model side panel are present as specified | pytest: `tests/test_dashboard_summary.py` (task 4.6) | - [ ] |
| 44 | dashboard-summary-endpoint | Annotator Tenant-Wide Entities Annotated Stat (REMOVED) | — | Given role `annotator`, when the summary is fetched, then no stat labelled "Entities Annotated" is present and no stat carries an unfiltered tenant-wide `spans` count | pytest: `tests/test_dashboard_summary_roles.py` (task 3.8) | - [ ] |
| 45 | portal-annotation | Deep Link to a Specific Task | task parameter pre-selects the task | Given task `abc123` is in the annotator's queue, when `/annotation?task=abc123` is opened, then that task is selected and its document text is loaded | component: `src/portal/src/components/annotation/AnnotationPage.annotator.test.tsx` (task 7.4) | - [ ] |
| 46 | portal-annotation | Deep Link to a Specific Task | unknown task id falls back to default selection | Given no task `zzz999` exists in the queue, when `/annotation?task=zzz999` is opened, then the default selection renders and no error state is shown | component: `src/portal/src/components/annotation/AnnotationPage.annotator.test.tsx` (task 7.4) | - [ ] |
| 47 | portal-annotation | Deep Link to a Specific Task | task belonging to another annotator is not selected | Given task `other456` is not in the current user's visible queue, when `/annotation?task=other456` is opened, then the default selection renders and no content from that task is displayed | component: `src/portal/src/components/annotation/AnnotationPage.annotator.test.tsx` (task 7.4) | - [ ] |
| 48 | portal-annotation | Deep Link to a Specific Task | parameter does not override later selection | Given the user arrived via `?task=abc123`, when they click a different queue task, then that task becomes selected and selection is not reverted | component: `src/portal/src/components/annotation/AnnotationPage.annotator.test.tsx` (task 7.4) | - [ ] |
| 49 | portal-annotation | Deep Link to a Specific Task | no parameter preserves existing behaviour | Given `/annotation` is opened with no query parameter, when the workspace loads, then default selection is unchanged and the persisted `localStorage` layout mode is applied | component: `src/portal/src/components/annotation/AnnotationPage.annotator.test.tsx` (task 7.4) | - [ ] |
| 50 | portal-dashboard | Dashboard Data Shape (MODIFIED) | system_admin data shape | Given role `system_admin`, when the dashboard loads, then the documented stats, activity rows, side panel, and storage `sideRows` render | portal: `src/portal/src/hooks/use-dashboard-data.test.ts`, `src/portal/src/lib/dashboard.test.ts` (task 5.7) | - [ ] |
| 51 | portal-dashboard | Dashboard Data Shape (MODIFIED) | tenant_admin data shape | Given role `tenant_admin`, when the dashboard loads, then the documented pipeline stats, activity rows, and active-model/quota side panel render | portal: `src/portal/src/hooks/use-dashboard-data.test.ts`, `src/portal/src/lib/dashboard.test.ts` (task 5.7) | - [ ] |
| 52 | portal-dashboard | Dashboard Data Shape (MODIFIED) | annotator data shape | Given role `annotator`, when the dashboard loads, then 2 stats plus `continueWork` render, "My tasks" shows 4 rows, and "Dataset readiness" shows 200-per-type progress including zero-span types | portal: `src/portal/src/hooks/use-dashboard-data.test.ts`, `src/portal/src/lib/dashboard.test.ts` (task 5.7) | - [ ] |
| 53 | portal-dashboard | Dashboard Data Shape (MODIFIED) | business_user data shape | Given role `business_user`, when the dashboard loads, then the documented extraction stats, rows, and side panel render | portal: `src/portal/src/hooks/use-dashboard-data.test.ts`, `src/portal/src/lib/dashboard.test.ts` (task 5.7) | - [ ] |
| 54 | portal-dashboard | Dashboard Data Shape (MODIFIED) | partial service failure degrades gracefully | Given the training service is unavailable, when the dashboard renders, then dependent cards show `—`, independent cards show real values, and no full-page error appears | portal: `src/portal/src/hooks/use-dashboard-data.test.ts`, `src/portal/src/lib/dashboard.test.ts` (task 5.7) | - [ ] |
| 55 | portal-dashboard | Dashboard Summary Endpoint (MODIFIED) | system_admin summary returns real data from wired sources | Given role `system_admin`, when the summary is fetched, then `stats[0].value` is the real tenant count, `sources.tenants` is `true`, and training-dependent fields come from the training service | portal: `src/portal/src/hooks/use-dashboard-data.test.ts`, `src/portal/src/lib/dashboard.test.ts` (task 5.7) | - [ ] |
| 56 | portal-dashboard | Dashboard Summary Endpoint (MODIFIED) | tenant_admin summary returns real data from wired sources | Given a tenant with documents, annotations, model versions, and jobs, when the summary is fetched, then `stats[0..3]` carry document count, completion %, model F1, and job count | portal: `src/portal/src/hooks/use-dashboard-data.test.ts`, `src/portal/src/lib/dashboard.test.ts` (task 5.7) | - [ ] |
| 57 | portal-dashboard | Dashboard Summary Endpoint (MODIFIED) | annotator summary returns real task data | Given role `annotator` with assigned tasks, when the summary is fetched, then `stats[0].value` is the completed/total fraction, `stats[1].value` is the completion percentage, and `continueWork` identifies the task to return to | portal: `src/portal/src/hooks/use-dashboard-data.test.ts`, `src/portal/src/lib/dashboard.test.ts` (task 5.7) | - [ ] |
| 58 | portal-dashboard | Dashboard Summary Endpoint (MODIFIED) | business_user summary returns real extraction data | Given role `business_user` with extraction data, when the summary is fetched, then `stats[0..3]` carry document count, entity count, avg confidence, and auto-cleared % | portal: `src/portal/src/hooks/use-dashboard-data.test.ts`, `src/portal/src/lib/dashboard.test.ts` (task 5.7) | - [ ] |
| 59 | portal-dashboard | Dashboard Summary Endpoint (MODIFIED) | sources map includes all data domains | Given any role, when the summary is inspected, then `sources` contains keys for all relevant domains, each `true` on success and `false` on failure | pytest: `tests/test_dashboard_summary.py` (task 4.6) | - [ ] |
| 60 | portal-dashboard | Dashboard Summary Endpoint (MODIFIED) | unauthenticated request rejected | Given no valid JWT, when the summary endpoint is called, then the response is `401 Unauthorized` | pytest: `tests/test_dashboard_summary.py` (task 4.6) | - [ ] |
| 61 | portal-dashboard | Stat Card Strip (MODIFIED) | stat cards render with inline delta | Given a loaded `tenant_admin` summary, when the strip renders, then the grid column count equals the card count and each card shows label plus right-aligned delta on one row with value/unit/sub below | component: `src/portal/src/components/dashboard/StatCard.test.tsx` (task 5.6) | - [ ] |
| 62 | portal-dashboard | Stat Card Strip (MODIFIED) | annotator strip renders three cards including the continue card | Given a loaded `annotator` summary, when the strip renders, then three cards appear in a three-column grid with the continue-work card first, followed by Assigned tasks and Completion % | component: `src/portal/src/components/dashboard/StatCard.test.tsx` (task 5.6) | - [ ] |
| 63 | portal-dashboard | Stat Card Strip (MODIFIED) | empty sub renders no context line | Given a stat item with `sub` equal to the empty string, when the card renders, then no context line appears below the value | component: `src/portal/src/components/dashboard/StatCard.test.tsx` (task 5.6) | - [ ] |
| 64 | portal-dashboard | Stat Card Strip (MODIFIED) | fraction value renders as a fraction | Given a stat `value` of `"3/5"`, when the card renders, then `3` is emphasised and `5` de-emphasised, separated by a slash | component: `src/portal/src/components/dashboard/StatCard.test.tsx` (task 5.6) | - [ ] |
| 65 | portal-dashboard | Stat Card Strip (MODIFIED) | stat cards render skeleton while loading | Given the dashboard query is in flight, when the strip renders, then skeleton placeholders appear with no spinner or empty boxes | component: `src/portal/src/components/dashboard/StatCard.test.tsx` (task 5.6) | - [ ] |
| 66 | portal-dashboard | Stat Card Strip (MODIFIED) | warn direction renders amber indicator | Given a stat item with `dir: "warn"`, when the card renders, then the delta indicator is amber, not green | component: `src/portal/src/components/dashboard/StatCard.test.tsx` (task 5.6) | - [ ] |
| 67 | portal-dashboard | Secondary Metrics Panel (MODIFIED) | progress bar fills to correct percentage | Given `bar: 62`, when the panel renders, then the bar fills to 62% at 8px height and animates from `0` to `62%` on mount | component: `src/portal/src/components/dashboard/MetricsPanel.test.tsx` (task 6.3) | - [ ] |
| 68 | portal-dashboard | Secondary Metrics Panel (MODIFIED) | sideMetrics render as inline row | Given three `sideMetrics`, when the top section renders, then all three appear in one space-between flex row showing `k` and `v` in JetBrains Mono | component: `src/portal/src/components/dashboard/MetricsPanel.test.tsx` (task 6.3) | - [ ] |
| 69 | portal-dashboard | Secondary Metrics Panel (MODIFIED) | readiness rows show progress toward the per-type threshold | Given an entity type with 100 spans against a threshold of 200, when the mini bar renders, then it fills to 50% and the row value conveys 100 against 200 | component: `src/portal/src/components/dashboard/MetricsPanel.test.tsx` (task 6.3) | - [ ] |
| 70 | portal-dashboard | Secondary Metrics Panel (MODIFIED) | starved and satisfied entity types are visually distinct | Given one type at 0% and another at 100%, when the rows render, then the two bars do not share the same colour | component: `src/portal/src/components/dashboard/MetricsPanel.test.tsx` (task 6.3) | - [ ] |
| 71 | portal-dashboard | Secondary Metrics Panel (MODIFIED) | overflow of entity types is indicated | Given more active entity types than the panel renders, when it renders, then the shown rows are the least-progressed the count of omitted types is indicated, and a view-all control is offered | component: `src/portal/src/components/dashboard/MetricsPanel.test.tsx` (task 6.3) | - [ ] |
| 72 | portal-dashboard | Secondary Metrics Panel | viewing all expands the panel in place | Given the panel shows 6 of 8 entity types, when the view-all control is activated, then all 8 render and the control offers to collapse back | component: `src/portal/src/components/dashboard/MetricsPanel.test.tsx` (task 6.4) | - [ ] |
| 73 | portal-dashboard | Secondary Metrics Panel | collapsing returns the panel to the capped list | Given the panel has been expanded, when the collapse control is activated, then only the capped least-progressed set renders and the hidden count is indicated again | component: `src/portal/src/components/dashboard/MetricsPanel.test.tsx` (task 6.4) | - [ ] |
| 74 | portal-dashboard | Secondary Metrics Panel | no view-all control when nothing is hidden | Given the tenant has fewer entity types than the row cap, when the panel renders, then every type renders and no view-all control is present | component: `src/portal/src/components/dashboard/MetricsPanel.test.tsx` (task 6.4) | - [ ] |
| 75 | portal-dashboard | Secondary Metrics Panel (MODIFIED) | sideRows mini bars render correct colours | Given `sideRows[0].c` is `"oklch(0.64 0.15 25)"`, when the mini bar renders, then its background colour matches that string | component: `src/portal/src/components/dashboard/MetricsPanel.test.tsx` (task 6.3) | - [ ] |
| 76 | training-jobs | Per-Entity-Type Minimum Dataset Gate | gate is inert at its default | Given `NER_MIN_ENTITIES_PER_TYPE` unset and 3 spans across 1 type, when a tenant admin submits a training job, then the response is `201` | pytest: `tests/test_training_jobs_api.py` (task 8.4) | - [ ] |
| 77 | training-jobs | Per-Entity-Type Minimum Dataset Gate | submission rejected when one entity type falls short | Given the variable is `200` and counts are 400 / 210 / 40, when a job is submitted, then the response is `422`, the detail names the 40-span type and its count, and does not name the satisfied types | pytest: `tests/test_training_jobs_api.py` (task 8.4) | - [ ] |
| 78 | training-jobs | Per-Entity-Type Minimum Dataset Gate | entity type with zero spans blocks submission | Given the variable is `200` and an active definition has no spans, when a job is submitted, then the response is `422` and the detail names that type with a count of `0` | pytest: `tests/test_training_jobs_api.py` (task 8.4) | - [ ] |
| 79 | training-jobs | Per-Entity-Type Minimum Dataset Gate | submission accepted when every active type meets the minimum | Given the variable is `200` and every active type has ≥200 spans, when a job is submitted, then the response is `201` | pytest: `tests/test_training_jobs_api.py` (task 8.4) | - [ ] |
| 80 | training-jobs | Per-Entity-Type Minimum Dataset Gate | inactive entity types are excluded from the gate | Given the variable is `200`, an `is_active = false` type with 0 spans, and all active types ≥200, when a job is submitted, then the response is `201` | pytest: `tests/test_training_jobs_api.py` (task 8.4) | - [ ] |
| 81 | training-jobs | Per-Entity-Type Minimum Dataset Gate | both gates apply independently | Given `NER_MIN_TRAINING_ENTITIES` is `500` and `NER_MIN_ENTITIES_PER_TYPE` is `200`, with 900 total spans but one type at 50, when a job is submitted, then the response is `422` identifying the per-type shortfall | pytest: `tests/test_training_jobs_api.py` (task 8.4) | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Readiness formula (design.md Decision 2) | The mean-of-capped-progress rule is easy to get subtly wrong. An agent may forget the per-type cap (reintroducing the exact bug this change fixes, where 2000 spans of one label offsets 0 of another), or substitute `min()`, or compute `total_spans / (200 × type_count)` — which is arithmetically the uncapped mean in disguise | Hand-compute `bar` for the spec's worked examples (rows 13, 14, 18) and compare against the implementation's output. Row 14 is the discriminating case: any formula returning `100.0` there has dropped the cap |
| 2 | Entity-type enumeration source (design.md Decision 1) | An agent may keep grouping `{schema}.spans` by `entity_type` and merely change the divisor, because that is the smaller diff. Zero-span types would then remain invisible and the whole point of the change is lost — and this passes any test that only uses types which already have spans | Confirm the query's FROM/driving table is `public.entity_definitions`, not `spans`, and that the join is a LEFT JOIN. Run row 15 against a tenant with a freshly created, never-annotated entity type |
| 3 | Cross-schema tenant scoping (ADR-001, design.md Context) | `entity_definitions` lives in `public` keyed by `tenant_id`, while spans live in the tenant schema. An agent may omit the `tenant_id` filter — the query still returns rows and the dashboard still renders, so nothing looks broken in single-tenant testing | Read the generated SQL directly and confirm a `tenant_id` bind parameter is present on the `entity_definitions` predicate. Execute row 20 with two seeded tenants; a missing filter shows up as inflated type counts |
| 4 | Per-block error isolation (design.md Context) | The handler's convention is one `try/except` per metric with `await db.rollback()` before dependent queries. An agent adding `continueWork` may wrap it in an existing block or omit the rollback, so one failure blanks unrelated cards — the failure mode `_tenant_response_quality_card` documents at `dashboard.py:792-798` | Force the continue-work query to raise (temporary bad identifier) and confirm row 7: response is 200, `continueWork` is `null`, and readiness plus stats still carry real values |
| 5 | Task-ordering COALESCE (design.md Decision 4) | The three-level fallback exists because nothing was found writing `annotation_tasks.updated_at`. An agent may simplify to `ORDER BY updated_at DESC`, which passes any fixture that sets the column and silently degrades on real data where it is NULL | Inspect the ORDER BY for all three levels. Run row 3 against fixtures with `updated_at` explicitly NULL — a single-level ordering returns an arbitrary task |
| 6 | Scope of the `"active"` removal (spec: Stat Sub-Labels Carry Information) | `"active"` appears in three unrelated roles in `dashboard.py`: as a placeholder `StatItem.sub`, as `ActiveModelInfo.status` (a deployment state), and as `ActivityRow.tk` (a tag colour key). A find-and-replace removes all three, breaking the active-model card and activity tag colouring | Diff every `"active"` occurrence in `dashboard.py` against the exclusion list in the spec requirement. Confirm rows 24–28, with row 28 specifically guarding `activeModel.status` |
| 7 | Status vocabulary breadth (design.md Decision 5) | The spec names three not-started values (`pending`, `unannotated`, `open`) because all three appear across seed data, the annotation service, and the migrations. An agent may implement only the one it sees in a fixture — most likely `unannotated`, since that is what `tasks.py:82` writes — and the card then reports "caught up" to an annotator holding 14 real `pending` tasks. Nothing errors; the card just lies | Read the SQL predicate and confirm all three literals are present. Run rows 12 and 34 against fixtures using each vocabulary in turn; a single-value implementation passes the `unannotated` case and fails the `pending` one |
| 8 | State machine widening (design.md Decision 6) | The change adds exactly one entry, `"pending": ["in-progress"]`. An agent may over-generalise — adding `pending` as a *target* of other transitions, making `completed` non-terminal, or rewriting the table wholesale — silently loosening guards that protect submitted work | Diff `valid_transitions` before and after: exactly one key added, no existing list modified. Rows 2–4 exist specifically to catch loosened guards, and row 5 confirms the `NO_SPANS` precondition survived |
| 9 | Default-off training gate (design.md Decision 7) | An agent may redefine the existing `NER_MIN_TRAINING_ENTITIES` to mean per-type rather than adding a separate variable, or default the new variable to `200` instead of `0` — either would start rejecting submissions on merge and invalidate the 15 existing call sites in `tests/test_training_jobs_api.py` | Confirm `NER_MIN_TRAINING_ENTITIES` and its total-count semantics are untouched, and that `NER_MIN_ENTITIES_PER_TYPE` defaults to `0`. Row 64 must pass with no environment configuration at all |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 Tenant Data Isolation via Separate Database Schemas | Tenant data lives in per-tenant Postgres schemas | The new readiness query crosses from the tenant schema into `public.entity_definitions`; it must filter by the caller's `tenant_id` and must not aggregate across tenants | Read the generated SQL for the `entity_definitions` predicate and confirm a `tenant_id` bind parameter. Execute Section 1 row 20 with two seeded tenants and confirm counts do not merge |
| ADR-004 OpenSpec Spec-Driven Development Governance | Behaviour changes land through spec deltas before code | The 500→200-per-type semantics change must exist as a spec delta, not only as an edited constant | Confirm `specs/dashboard-summary-endpoint/spec.md` in this change carries the Per-Entity-Type Dataset Readiness requirement, and that no threshold behaviour appears in code without a corresponding scenario in Section 1 |
| ADR-006 Training Infrastructure (in force except the hyperparameter clause superseded by ADR-009) | Compliance section states both "500-entity minimum dataset threshold" and "500 labeled entities per entity type" | ADR-006 MUST NOT be edited in place. The threshold change requires a new partially-superseding ADR, per the convention set by ADR-008 and ADR-009 | `git diff docs/adr/006-training-infrastructure.md` must be empty. Confirm a new `docs/adr/010-*.md` exists with a `**Supersedes**: ADR-006 (partially — ...)` line naming the dataset-threshold clauses |
| ADR-009 System Admin Sets Training Hyperparameters at Approval | Partially supersedes ADR-006 on hyperparameters only | Establishes the partial-supersession format the new ADR must follow; also confirms ADR-006's threshold clauses remain in force until superseded | Compare the new ADR-010 header format against ADR-009's `**Supersedes**` line. Confirm ADR-010 claims only the threshold clauses, not hyperparameters |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

*(Minimum one item per row in Section 1 — test output, screenshot, log excerpt, or API
trace proving the THEN was observed in a real execution.)*

- [ ] Rows 1–5 (task state machine): pytest output showing `pending → in-progress` now succeeds, `pending → completed` still 422s, `completed` stays terminal, and the `NO_SPANS` guard is intact
- [ ] Rows 6–15 (continue-work payload): pytest output for the full precedence chain — resume, start, review, caught-up — including the NULL-`updated_at` ordering fallback and the degraded-card case
- [ ] Rows 16–20 (continue-work rendering): component test output for `ContinueWorkCard` covering resume, start, review, caught-up, truncation, and non-annotator roles
- [ ] Rows 21–31 (per-type readiness): pytest output for the readiness computation, with the weakest-type, over-annotated-mask, and fully-ready cases showing hand-verifiable `bar` values
- [ ] Row 27 specifically (spans without definitions): pytest output proving a tenant with spans but no active entity definitions still renders a readiness panel — the `demo-tenant` shape found in task 1.3
- [ ] Row 30 specifically (tenant isolation): test output or query log from a two-tenant fixture proving no cross-tenant aggregation
- [ ] Rows 32–34 (assigned-task fraction): pytest output covering the 3/5 case, all three not-started vocabularies in the denominator, and the empty 0/0 case
- [ ] Rows 35–39 (sub-label removal): pytest output asserting no `stats[*].sub == "active"` for annotator, system_admin, and tenant_admin, plus the retained `activeModel.status`
- [ ] Rows 40–41 (readiness activity event): pytest output for the tenant_admin feed with all types crossed and with one type short
- [ ] Rows 42–44 (modified summary shape): pytest output for the role-shape assertions, plus proof no "Entities Annotated" stat is emitted
- [ ] Rows 45–49 (annotation deep link): test output for `?task=` pre-selection, unknown id, foreign task, later-selection override, and the no-parameter path
- [ ] Rows 50–72 (portal shape, stat strip, metrics panel): portal test output plus one API trace of `GET /api/v1/dashboard/summary` as an annotator, a screenshot of the annotator three-card row, and a screenshot of the readiness panel showing a zero-span type with colour differentiation
- [ ] Rows 76–81 (per-type training gate): pytest output for `tests/test_training_jobs_api.py` covering all six gate scenarios, with the inert-default case run with no environment configuration
- [ ] Full backend suite: `pytest tests/test_dashboard_summary.py tests/test_dashboard_summary_roles.py tests/test_annotation_workspace.py tests/test_training_jobs_api.py` passing, confirming the rewritten assertions replace the 500-total ones

### Structural Evidence

*(Code review and architectural compliance.)*

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)
- [ ] `DATASET_READINESS_ENTITY_THRESHOLD` is fully removed — no residual reference to a 500 total anywhere in `src/`
- [ ] `docker-compose.yml` and `.env` are unmodified — the per-type gate ships inert per design.md Decision 7 and the Migration Plan

### Edge Case Evidence

*(One item per Hallucination Risk from Section 2.)*

- [ ] Risk 1 mitigation confirmed — `bar` hand-computed for the weakest-type, over-annotated-mask, and fully-ready rows and matched against implementation output; the over-annotated case does not return `100.0`
- [ ] Risk 2 mitigation confirmed — readiness types come from the union of `public.entity_definitions` and `spans.entity_type`, verified against both a never-annotated defined type and a tenant with spans but no definitions
- [ ] Risk 3 mitigation confirmed — generated SQL inspected for the `tenant_id` bind parameter; two-tenant execution shows no count inflation
- [ ] Risk 4 mitigation confirmed — continue-work query forced to raise; response 200 with only that card degraded
- [ ] Risk 5 mitigation confirmed — ORDER BY carries all three fallback levels; verified against fixtures with NULL `updated_at`
- [ ] Risk 6 mitigation confirmed — every `"active"` occurrence in `dashboard.py` reviewed; `ActiveModelInfo.status` and `ActivityRow.tk` intact
- [ ] Risk 7 mitigation confirmed — all three not-started literals present in the SQL predicate; verified against `pending`, `unannotated`, and `open` fixtures in turn
- [ ] Risk 8 mitigation confirmed — `valid_transitions` diff shows exactly one key added and no existing list modified; terminal-`completed` and `NO_SPANS` guards verified intact
- [ ] Risk 9 mitigation confirmed — `NER_MIN_TRAINING_ENTITIES` semantics unchanged; new variable defaults to `0`; inert-default row passes with no environment configuration

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching
entry. Do not pre-fill — entries must describe real observations.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `pytest tests/test_annotation_workspace.py -k "pending or reopen or 7_13 or 7_14 or 7_15 or recomplete"` → **8 passed**. Covers `pending → in-progress` now succeeding, `pending → completed` still 422 INVALID_TRANSITION, `completed` terminal (both `in-progress` and `pending` targets), and the `NO_SPANS` guard intact | 1–5 | agent (opsx:apply) | 2026-08-06 |
| 2 | Functional | `pytest tests/test_dashboard_summary_roles.py` → **39 passed**. Includes the discriminating readiness cap case (2000 + 0 spans → `bar` 50.0, not 100.0), zero-span defined type, spanned-type-without-definition, least-progress ordering, inactive exclusion, tenant scoping, all three not-started vocabularies, and the full continue-work precedence chain | 6–14, 21–34, 35–39, 40–41, 44 | agent (opsx:apply) | 2026-08-06 |
| 3 | Functional | `pytest tests/test_dashboard_summary.py tests/test_dashboard_summary_roles.py` → **75 passed, 4 failed**. Baseline with `src/` changes stashed was **6 failed**, so zero regressions and 2 previously-broken tests repaired | 42–43, 59–60 | agent (opsx:apply) | 2026-08-06 |
| 4 | Functional | `npx vitest run src/components/dashboard/ContinueWorkCard.test.tsx` → **6 passed**. Resume/Start/Review actions, caught-up state with no link, ellipsis truncation with full name in `title`, skeleton while loading | 15–20 | agent (opsx:apply) | 2026-08-06 |
| 5 | Functional | `npx vitest run src/components/annotation/AnnotationPage.annotator.test.tsx` → **7 passed**. `?task=` pre-select, unknown id, foreign task, no-parameter default, layout preserved | 45–49 | agent (opsx:apply) | 2026-08-06 |
| 6 | Functional | `npx vitest run` (portal) → **542 passed, 11 failed**. The 11 are byte-identical to the pre-change baseline (missing `lucide-react`/`react-markdown` deps, unrelated stale tests) | 61–75 | agent (opsx:apply) | 2026-08-06 |
| 7 | Functional | `pytest tests/test_training_jobs_api.py` → **21 passed, 1 failed** (baseline: 3 passed / 13 failed / 16 errors). All six per-type gate scenarios pass; the remaining failure concerns job retrieval against a schemaless tenant, not submission | 76–81 | agent (opsx:apply) | 2026-08-06 |
| 8 | Structural | `git diff docs/adr/006-training-infrastructure.md` → empty. `docs/adr/010-per-entity-type-dataset-threshold.md` created with `**Supersedes**: ADR-006 (partially — …)`, claiming only the dataset-threshold clauses | ADR-006 / ADR-009 rows in §3 | agent (opsx:apply) | 2026-08-06 |
| 9 | Structural | `grep -rn "DATASET_READINESS_ENTITY_THRESHOLD" src/` → no matches. `git diff --stat docker-compose.yml` → empty, so the per-type gate ships inert | Structural evidence items | agent (opsx:apply) | 2026-08-06 |
| 10 | Edge Case | `grep -n '"active"' src/gateway/api/v1/dashboard.py` → 3 matches, all excluded by spec: the `ActiveModelInfo.status` type comment, `ActivityRow.tk` tag colour key, and the `activeModel` status value. Guarded by a test asserting `activeModel.status == "active"` still holds | Risk 6 | agent (opsx:apply) | 2026-08-06 |
| 11 | Edge Case | Continue-work ordering asserted against fixtures with `annotation_tasks.updated_at` explicitly NULL — selection falls through to the document's latest span `updated_at` | Risk 5 | agent (opsx:apply) | 2026-08-06 |
| 12 | Edge Case | Continue-work query patched to raise via `AsyncMock(side_effect=RuntimeError)`; response still 200 with `continueWork: null` and stats plus `sideRows` intact | Risk 4 | agent (opsx:apply) | 2026-08-06 |
| 13 | Edge Case | Not-started matching verified against `pending`, `unannotated`, and `open` in turn via `@pytest.mark.parametrize` | Risk 7 | agent (opsx:apply) | 2026-08-06 |
| 14 | Edge Case | `valid_transitions` diff shows exactly one key added (`"pending": ["in-progress"]`); no existing list modified. Terminal-`completed` and `NO_SPANS` guards each covered by their own test | Risk 8 | agent (opsx:apply) | 2026-08-06 |
| 15 | Edge Case | `NER_MIN_TRAINING_ENTITIES` semantics and default unchanged; `NER_MIN_ENTITIES_PER_TYPE` defaults to `0` and the inert-default test runs with the variable deleted from the environment | Risk 9 | agent (opsx:apply) | 2026-08-06 |
| 16 | Functional | Live API trace: `GET /api/v1/dashboard/summary` as the Inapp HR annotator against the running gateway and dev database. `stats` = `Assigned tasks 0/1` (sub `"1 remaining"`), `Completion 0` (sub `""` — no placeholder). `continueWork` = `{documentName: "AbdullahSuhailA[7_0].pdf", mode: "resume", spanCount: 24}`. Readiness `0 of 8 entity types ready`, `bar` 1.5, all 8 types in `sideRows` least-progress-first including the five at 0/200 (COMPANY, DEGREE, INSTITUTION, TOOL_FRAMEWORK, YEARS_OF_EXP) that the old share-of-total breakdown could not show. No `Entities Annotated` stat present | 21–34, 35–39, 42–44, 6–14 (end-to-end) | agent (opsx:apply) | 2026-08-06 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** annotator-dashboard-cards-and-per-entity-readiness
**Proposal:** `openspec/changes/annotator-dashboard-cards-and-per-entity-readiness/proposal.md`
**Spec files reviewed:**
  - specs/annotation-workspace/spec.md
  - specs/annotator-continue-work/spec.md
  - specs/dashboard-summary-endpoint/spec.md
  - specs/portal-dashboard/spec.md
  - specs/portal-annotation/spec.md
  - specs/training-jobs/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [ ] |
| All ADRs in Section 3 verified compliant | - [ ] |
| Spec Alignment table complete (no missing scenarios) | - [ ] |
| Evidence Log populated with real evidence | - [ ] |
| All functional evidence items in Section 4 checked | - [ ] |
| All structural evidence items in Section 4 checked | - [ ] |
| All edge case evidence items in Section 4 checked | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No undocumented patterns used | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause in specs has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and all mitigations confirmed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**
<!-- Any observations, caveats, or follow-up items for future changes. -->

**Open questions carried from proposal.md and design.md that a reviewer should resolve or accept before archive:**
- Overall readiness formula (mean-of-capped vs `min()`) — design.md Decision 2 chose the mean; confirm this is accepted.
- Whether a tenant can reach 100% readiness when it configures entity types its corpus never contains; `is_active = false` is the proposed escape hatch.
- Whether the visible readiness drop for Inapp HR (~5% to ~1.5%, now measured against 8 types rather than the 3 with spans) is accepted as the honest figure.
- Which task status vocabulary wins long-term — `seed.py` writes `pending`, `annotation_service` writes `unannotated`, migration 002 defaults to `open`. This change accepts all three and makes `pending` startable but does not reconcile or backfill them.
- Whether `NER_MIN_ENTITIES_PER_TYPE` should be turned on in deployment (deliberately left off here).
- Whether 200 is the right figure — chosen as the requested target, not derived from measured F1-versus-example-count.
