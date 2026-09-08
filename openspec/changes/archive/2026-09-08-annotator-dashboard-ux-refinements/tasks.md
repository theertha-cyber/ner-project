## 1. Backend: stat label rename

- [x] 1.1 In [src/gateway/api/v1/dashboard.py](src/gateway/api/v1/dashboard.py), change `_stat("Spans confirmed", ...)` to `_stat("Entities Annotated", ...)` in `_annotator_data`. No other args change.

## 2. Backend: dataset readiness progress and copy

- [x] 2.1 In `_annotator_side_panel` ([src/gateway/api/v1/dashboard.py](src/gateway/api/v1/dashboard.py)), add `bar_pct` (and `total_spans`) to the function's return tuple.
- [x] 2.2 In `_annotator_data`, capture the new `bar_pct` return value and pass it as `bar=bar_pct` in the `DashboardData(...)` construction (replacing the hardcoded `bar=0`).
- [x] 2.3 In `_annotator_data`, compute `remaining = max(DATASET_READINESS_ENTITY_THRESHOLD - total_spans, 0)` and set `sideMeta` to a string conveying entities still needed when `remaining > 0`, or threshold-met copy when `remaining == 0`.
- [x] 2.4 In `_annotator_data`, set `big`/`bigUnit` to convey percent-complete (`big=f"{round(bar_pct)}"`, `bigUnit="% to training-ready"`) instead of the raw count/`"/ 500 spans"`.
- [x] 2.5 In `_annotator_data`, update `sideBot` to convey that reaching the threshold unlocks training, replacing `"Spans by entity type"`.
- [x] 2.6 Threaded `total_spans` out of `_annotator_side_panel` into `_annotator_data` alongside `bar_pct`/`side_metrics_list`/`side_rows`.

Note: reused the existing `DATASET_READINESS_ENTITY_THRESHOLD` module constant (already present in dashboard.py, shared with the tenant_admin "Dataset reached training readiness" activity event) instead of a literal `500`, for single-source-of-truth consistency.

## 3. Frontend sanity check (no code change expected)

- [x] 3.1 Confirmed `StatCard.tsx` and `MetricsPanel.tsx` render `label`/`sideMeta`/`big`/`bigUnit`/`sideBot` as opaque strings with no annotator-specific branching — no edits made to these files, per design.md Decision 1.

## 4. Verification: dashboard-summary-endpoint scenarios

- [ ] 4.1 Verify scenario "system_admin summary returns role-specific data" — `tests/test_dashboard_summary_roles.py::test_system_admin_summary_returns_role_specific_data`. BLOCKED: fails/errors in the current working tree from unrelated, pre-existing test-fixture drift (see note below), not from this change.
- [ ] 4.2 Verify scenario "tenant_admin summary returns pipeline data" — `tests/test_dashboard_summary_roles.py::test_tenant_admin_summary_returns_pipeline_data`. BLOCKED: same unrelated fixture drift.
- [x] 4.3 Verify scenario "annotator summary returns task data with entity terminology" — updated `tests/test_dashboard_summary_roles.py::test_annotator_summary_returns_task_data` to assert `stats[1]["label"] == "Entities Annotated"` and 3 stats total. **PASSES.**
- [x] 4.4 Verify scenario "annotator dataset readiness reflects real progress and threshold purpose" — added `tests/test_dashboard_summary_roles.py::test_annotator_dataset_readiness_shows_progress` seeding 113 `spans` rows, asserting `bar == 22.6`, `sideMeta` mentions "387"/needed wording, `sideBot` mentions the threshold. **PASSES.**
- [x] 4.5 Verify scenario "annotator dataset readiness at or above threshold" — added `tests/test_dashboard_summary_roles.py::test_annotator_dataset_readiness_at_threshold` seeding 500 `spans` rows, asserting `bar == 100` and threshold-met copy. **PASSES.**
- [ ] 4.6 Verify scenario "business_user summary returns extraction data" — BLOCKED: the `business_user` role handler has been independently rewritten (conversations/chat-based, not extraction-based) by unrelated concurrent changes to `dashboard.py`/`conftest.py` during this session, outside this change's scope. Existing `test_business_user_summary_returns_extraction_data` no longer exists in the test file as of the current tree.
- [ ] 4.7 Verify scenario "unavailable training service returns null values" — BLOCKED: same unrelated fixture drift (see note below).
- [ ] 4.8 Verify scenario "unauthenticated request rejected" — BLOCKED: same unrelated fixture drift; not expected to be affected by this change but could not get a clean run to confirm.

## 5. Verification: portal-dashboard scenarios

- [ ] 5.1 Verify scenario "system_admin data shape" — same blocker as 4.1.
- [ ] 5.2 Verify scenario "tenant_admin data shape" — same blocker as 4.2.
- [x] 5.3 Verify scenario "annotator data shape" — covered by 4.3/4.4/4.5 test artifacts. Manual browser screenshot of the rendered card NOT captured (no running portal dev server in this environment) — outstanding for human reviewer.
- [ ] 5.4 Verify scenario "business_user data shape" — same blocker as 4.6.
- [ ] 5.5 Verify scenario "partial service failure degrades gracefully" — NOT run (`MetricsPanel.test.tsx`/`StatCard.test.tsx` not executed this session); no code changes made to these files so regression risk is low, but not confirmed.
- [ ] 5.6 Verify scenario "system_admin summary returns real data from wired sources" — same blocker as 4.1.
- [ ] 5.7 Verify scenario "tenant_admin summary returns real data from wired sources" — same blocker as 4.2.
- [x] 5.8 Verify scenario "annotator summary returns real task data and a live progress bar" — same artifact as 4.4/4.5. **PASSES.**
- [ ] 5.9 Verify scenario "business_user summary returns real extraction data" — same blocker as 4.6.
- [ ] 5.10 Verify scenario "sources map includes all data domains" — same blocker as 4.1/4.2 (not run cleanly this session).
- [ ] 5.11 Verify scenario "unauthenticated request rejected" — same blocker as 4.8.

**Unrelated fixture-drift note (ongoing):** `tests/conftest.py` and `src/gateway/api/v1/dashboard.py` are being actively edited by other in-flight OpenSpec changes in this same repo (`redesign-business-user-dashboard`, `tenant-dashboard-workspace-refresh`) — the business_user role was rewritten to a conversations/chat model, `_null_sources`/`_ROLE_SERVICES` keys changed, and new test classes were added, all outside this change's scope. As a result full-suite runs are not reproducible session-to-session: one run surfaced `relation "tenant_test_tenant.model_versions" does not exist`, a later run surfaced the same kind of transaction-abort cascade on `spans` — both from a table-creation ordering issue in `conftest.py`'s growing, concurrently-edited `_TENANT_TABLES_SQL`. This change's own code (`_annotator_data`/`_annotator_side_panel`) has not changed since it was last confirmed passing.

One pre-existing, in-scope-adjacent gap was fixed as a minimal unblock: `tests/conftest.py`'s `annotation_tasks` table was missing the `annotator_user_id` column that `dashboard.py` and multiple existing tests already depend on (added in [alembic/versions/004_annotation_service_tables.py](alembic/versions/004_annotation_service_tables.py) but never added to the test fixture) — without it, every annotator-role dashboard query silently zeroed out because the missing column aborted the whole DB transaction. Added the column to `tests/conftest.py` to match production schema; this also fixes several previously-broken, unrelated `test_dashboard_summary.py` annotator tests.

Recommend the human reviewer re-run tests 4.3-4.5/5.3/5.8 once the concurrent changes settle, before signing off; the business_user/model_versions-ordering failures are unrelated to this change and were not fixed here.

## 6. Verification & Evidence

- [ ] 6.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 6.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 6.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 6.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 6.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required).
- [ ] 6.6 Run `openspec validate annotator-dashboard-ux-refinements --strict` before archive.
