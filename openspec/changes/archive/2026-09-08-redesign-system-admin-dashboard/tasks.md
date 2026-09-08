## 1. Backend: generic audit-event activity feed helper

- [x] 1.1 In `src/gateway/api/v1/dashboard.py`, add `_system_activity_feed(db, limit)` that queries the most recent `public.audit_events` rows (`ORDER BY created_at DESC LIMIT :limit`) across all tenants with **no `action`/`kind` filter** — every action type is eligible to appear
- [x] 1.2 Add `_SYSTEM_ACTIVITY_TITLES` (a cosmetic `action` → friendly title dict, e.g. `tenant.create` → "Tenant created", `user.create` → "User onboarded", `model_version.promote` → "Model promoted" — illustrative, not exhaustive) used only to prettify known actions; any `action` not in the dict SHALL still produce a row, titled via a humanized fallback (`action.replace('_', ' ').replace('.', ': ')`), not be dropped
- [x] 1.3 Map each row to an `ActivityRow` with `tk`/`icon` derived from `kind` (reusing the existing `_activity_tag_colour`-style mapping) and `go` set per action prefix (`tenant.*` → `"tenants"`, `user.create` → `"users"`, `training_job.*` → `"training"`, `model_version.promote` → `"models"`; unmapped actions fall back to `"dashboard"`)
- [x] 1.4 Verification: `tests/test_dashboard_summary.py` — new test asserting `pRows` for `system_admin` reflects multi-tenant `audit_events` rows ordered by `created_at DESC` with human-readable titles for known actions (covers verification.md row 11)
- [x] 1.5 Verification: `tests/test_dashboard_summary.py` — new test seeding an `audit_events` row with an `action` not present in `_SYSTEM_ACTIVITY_TITLES`, asserting it still appears in `pRows` with a humanized fallback title rather than being dropped or filtered (covers verification.md row 11 and Hallucination Risk #1)

## 2. Backend: Active Users, Training Jobs Running, deterministic Platform Health

- [x] 2.1 In `_system_admin_data`, add an `active_user_count` query against `public.tenant_users WHERE status = 'active'`
- [x] 2.2 Replace the `doc_count_all` (Documents (all)) computation with a `training_jobs_running_count` computation: reuse `_all_tenant_schemas` and, in the same per-schema loop pass already used for Pending Approvals, add `COUNT(*) FROM {schema}.training_jobs WHERE status = 'running'`, summing across schemas — delete the now-unused `doc_count_all`/documents-sum code path entirely (no dead code left behind)
- [x] 2.3 Delete the `avg_f1` computation and its per-schema F1/`model_versions` query entirely (replaced by 2.2's Training Jobs Running stat — no `model_versions` query remains in the system_admin branch)
- [x] 2.4 Set the `sources["training"]` flag from the same per-schema try/except used for Pending Approvals and Training Jobs Running (both stats share one schema-iteration pass and one source flag, matching the existing `docs_complete`-style partial-tracking pattern)
- [x] 2.5 Add `_platform_service_health()` — fires concurrent `httpx` GETs (3s timeout each) via `asyncio.gather` against `settings.chat_api_url`, `settings.extraction_service_url`, `settings.training_service_url`, `settings.model_serving_url` `/health` endpoints, returning `"Online"`/`"Offline"` per service; the gateway's own status is hard-coded `"Online"` (no self HTTP call); a timeout/exception on any one call SHALL be caught locally so it marks only that service `"Offline"` and never propagates
- [x] 2.6 Add `_platform_health_status(gateway, chat_api, extraction, training, model_serving)` implementing the deterministic rule from design.md Decision 4: `"Healthy"` if all five are `"Online"`; `"Critical"` if Gateway or Model Serving is `"Offline"` (checked first, regardless of the other three); else `"Degraded"` (at least one of Chat API/Extraction Service/Training Service is `"Offline"` while Gateway and Model Serving are both `"Online"`)
- [x] 2.7 Verification: `tests/test_dashboard_summary.py` — new test asserting `stats` for `system_admin` is `[Active Tenants, Active Users, Pending Approvals, Training Jobs Running]` with correct values from seeded `tenant_users`/`training_jobs` fixtures (covers verification.md rows 1, 13)
- [x] 2.8 Verification: `tests/test_dashboard_summary.py` — new test asserting `_platform_health_status` returns `"Healthy"` when all 5 inputs are `"Online"`, `"Degraded"` when exactly one non-critical service is `"Offline"`, and `"Critical"` when Gateway or Model Serving is `"Offline"` even if all others are `"Online"` (covers verification.md rows 12, and the two new Critical/Degraded scenarios)
- [x] 2.9 Verification: `tests/test_dashboard_summary.py` — new test mocking one service's `/health` as unreachable, asserting per-service Online/Offline reporting, the correct derived `big` status, and response completing within a bounded time (covers verification.md row 12)
- [x] 2.10 Verification: `tests/test_dashboard_summary.py` — new test asserting the health-check calls are issued concurrently (e.g. via a mock that records call timing/order), that a single service's exception/timeout does not raise out of `_platform_service_health()` or fail the endpoint, and that the gateway status is reported without an outbound HTTP call (covers verification.md Hallucination Risk #3)

## 3. Backend: assemble system_admin response and hero copy

- [x] 3.1 Rewrite `_system_admin_data`'s `DashboardData` construction: new `kicker`/`title`/`line` framed around platform operations, tenant management, and approvals; `stats` from tasks 2.1–2.2; `pTitle="Platform Activity"`, `pRows` from task 1.1; `sideTop="Platform Health"`, `sideMeta`, `big`/`bigUnit` = the status from task 2.6, `sideMetrics` = Gateway/Chat API/Extraction Service Online/Offline, `sideRows` = Training Service/Model Serving Online/Offline (via `pct`/`c` per design.md Decision 5)
- [x] 3.2 Confirm `_null_sources()` / the `sources` dict is populated using only the existing keys (`tenants`, `training`) for the new reads — no new key introduced, and no `sources.models` reference remains in the system_admin branch (covers verification.md Hallucination Risk #7)
- [x] 3.3 Verification: `tests/test_dashboard_summary.py` — new/updated test asserting the full system_admin response shape (kicker/title/line wording, 4 stats, pTitle, sideTop) matches the spec, with no F1/precision/recall/loss field present anywhere in the payload (covers verification.md rows 1, 14, 19, 23)
- [x] 3.4 Verification: `tests/test_dashboard_summary_roles.py` — confirm `tenant_admin`, `annotator`, `business_user` branches are byte-for-byte unchanged (covers verification.md rows 2–4, 15–17, 20–22)

## 4. Backend: preserve existing failure-isolation and schema-exclusion behavior

- [x] 4.1 Confirm (no code change expected) that the rewritten Training Jobs Running/pending-approvals loop still uses `_all_tenant_schemas` and the same try/except-with-rollback pattern per schema, so one tenant's failure doesn't abort others (covers verification.md Hallucination Risk #5, ADR-001)
- [x] 4.2 Verification: `tests/test_dashboard_summary.py` — existing "one tenant schema failure" test updated to assert against Pending Approvals/Training Jobs Running instead of documents/F1 (covers verification.md row 7)
- [x] 4.3 Verification: `tests/test_dashboard_summary.py` — existing virtual-system-tenant-exclusion test still passes unmodified against the new code path (covers verification.md row 8)
- [x] 4.4 Verification: `tests/test_dashboard_summary.py` — existing schema-less-tenant-exclusion test updated to assert against Pending Approvals/Training Jobs Running (covers verification.md row 9)
- [x] 4.5 Verification: `tests/test_dashboard_summary.py` — existing partial-aggregate test updated to fail the `training_jobs` query for one schema and assert `sources.training: false` / Training Jobs Running not reported complete (covers verification.md row 10)
- [x] 4.6 Verification: `tests/test_dashboard_summary.py` — existing unavailable-training-service and unauthenticated-request tests confirmed to still pass unmodified (covers verification.md rows 5–6, 24)

## 5. Frontend: activity navigation and Platform Health colour

- [x] 5.1 Add `tenants: "/admin/tenants"` to `GO_HREF` in `src/portal/src/hooks/use-dashboard-data.ts`
- [x] 5.2 Extend `statusColor()` in `src/portal/src/components/dashboard/MetricsPanel.tsx` with three additional literal-string cases: `"Healthy"` → green, `"Degraded"` → amber/warn, `"Critical"` → red/bad (alongside its existing `"Online"`/`"Offline"` cases) — a few-line addition to an existing function; no new component, prop, or layout (design.md Decision 5)
- [x] 5.3 Verification: `src/portal/src/hooks/use-dashboard-data.test.ts` (or equivalent) — new test asserting `goToHref("tenants")` returns `/admin/tenants` (covers verification.md row 26)
- [x] 5.4 Verification: `src/portal/src/components/dashboard/ActivityPanel.test.tsx` — confirm existing navigation and status-dot/tag-colour tests still pass unmodified (covers verification.md rows 25, 27)
- [x] 5.5 Verification: `src/portal/src/components/dashboard/MetricsPanel.test.tsx` — new test asserting a `sideMetrics`/`sideRows` value of `"Offline"` renders with the red/bad status colour (covers verification.md row 31)
- [x] 5.6 Verification: `src/portal/src/components/dashboard/MetricsPanel.test.tsx` — new test asserting `big: "Critical"` renders red/bad, `big: "Degraded"` renders amber/warn, and `big: "Healthy"` renders green/good (covers verification.md row 32)
- [x] 5.7 Verification: `src/portal/src/components/dashboard/MetricsPanel.test.tsx` — confirm existing progress-bar, sideMetrics-inline-row, and sideRows-colour tests still pass unmodified (covers verification.md rows 28–30)
- [x] 5.8 Verification: manual check via dev server that the `src/portal/src/app/(auth)/dashboard/page.tsx` hero renders the new `kicker`/`title`/`line` from the API response with no hard-coded system_admin copy left in the component (confirms design.md Migration Plan step 5)

## 6. Structural and dead-code review

- [x] 6.1 Diff `src/portal/src/types/dashboard.ts` — confirm it is untouched (`sideMetrics` remains the 3-tuple type) (covers verification.md Hallucination Risk #4)
- [x] 6.2 Grep the final diff of `dashboard.py` for any leftover reference to `doc_count_all`, `avg_f1`, `model_versions`, or the SLA/p95/GPU placeholder strings in the system_admin branch — confirm none remain (covers verification.md Hallucination Risk #6)
- [x] 6.3 Confirm the Model Serving health check in task 2.5 is a single call against `settings.model_serving_url`, not iterated per tenant schema (covers verification.md ADR-003 compliance step)
- [x] 6.4 Confirm no `#### Scenario:` in either delta spec enumerates a fixed, closed list of `audit_events.action` values as a normative (SHALL) requirement — only illustrative examples are permitted in Platform Activity wording (covers stakeholder-review Decision 2 / Non-Goal on avoiding an action allowlist)

## 7. Verification & Evidence

- [x] 7.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 7.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 7.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 7.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 7.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required).
- [x] 7.6 Run `openspec validate redesign-system-admin-dashboard --type change --strict` and confirm it exits clean before archive.
