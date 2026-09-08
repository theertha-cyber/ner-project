## Why

The annotator dashboard's readiness panel tells annotators that training unlocks at "500 entities", but that number is a tenant-wide count of every span across every entity type (`src/gateway/api/v1/dashboard.py:951`). Five hundred spans made almost entirely of one label trains one usable recogniser and leaves the rest unusable, so the number does not measure what it claims to measure. ADR-006 already contradicts itself on this point — its Compliance section states both "500-entity minimum dataset threshold" and "500 labeled entities per entity type". This change settles the semantics on **200 labeled entities per entity type** and makes the dashboard report against it.

At the same time the annotator's three stat cards carry little information: "Assigned tasks" counts every task ever assigned including completed ones while labelling itself "active" (`dashboard.py:844`), "Entities Annotated" is the tenant-wide span count re-rendered under a personal-sounding label, and every card carries a hardcoded `"active"` sub-label that conveys nothing. Annotators have no on-dashboard route back into the document they were working on.

## What Changes

- **BREAKING**: Dataset readiness is redefined from *500 spans tenant-wide* to *200 spans per active entity type*. The `DATASET_READINESS_ENTITY_THRESHOLD = 500` constant is replaced by `DATASET_READINESS_ENTITIES_PER_TYPE = 200`. Readiness percentage, remaining-count copy, and the entity-type breakdown rows are all recomputed against the new definition.
- The readiness breakdown enumerates the **union** of the tenant's active entity definitions and the entity types that already have spans, so a configured type with zero annotations appears at 0/200 instead of being silently absent, and a tenant that never configured its label list does not lose its panel.
- **BREAKING**: The annotator stat row changes from `Assigned tasks` / `Entities Annotated` / `Completion` to `Continue where you left off` / `Assigned tasks` / `Completion %`.
  - `Continue where you left off` is a new card type carrying the annotator's most recently worked task, with a deep link into the annotation workspace. Precedence: most recent `in-progress` task (`resume`) → oldest unstarted task (`start`) → most recently completed task (`review`) → caught-up.
  - `Assigned tasks` becomes a completed/total fraction (`COUNT(*) FILTER (WHERE status = 'completed')` over total assigned).
  - `Entities Annotated` is removed — it duplicated the readiness panel's number under a misleading label.
- The `/annotation` route gains a `?task=<id>` query parameter so the new card can open a specific task. The workspace currently holds `selectedTask` in local state only (`AnnotationPage.tsx:46`) and cannot be linked to.
- The placeholder `"active"` sub-label is removed from stat cards on **all** role dashboards: annotator (`dashboard.py:893-895`), system_admin (`dashboard.py:292,294,296`), and the tenant_admin Documents fallback (`dashboard.py:370,373`). Cards keep only subs that carry real information.
- **BREAKING**: The tenant_admin "Dataset reached training readiness" activity event changes meaning — it now fires when the *last* entity type crosses 200, not when the 500th span overall is written (`dashboard.py:621-634`).
- The training-service submission gate gains an optional per-entity-type minimum (`NER_MIN_ENTITIES_PER_TYPE`) alongside the existing total-count `NER_MIN_TRAINING_ENTITIES`, so the backend can enforce the same definition the dashboard displays. Defaults to `0` (disabled), preserving current behaviour until deliberately configured.
- A new ADR (ADR-010) partially supersedes ADR-006's dataset-threshold clauses, replacing the contradictory "500 total" / "500 per entity type" pair with a single unambiguous figure. ADR-006 itself is left intact per the supersession convention already used by ADR-008 and ADR-009.

## Capabilities

### New Capabilities

- `annotator-continue-work`: The "Continue where you left off" card — task selection precedence (in-progress → unstarted → caught up), payload shape, empty and unavailable states, and the deep link into the annotation workspace.

### Modified Capabilities

- `dashboard-summary-endpoint`: Annotator readiness computed per entity type at 200 rather than 500 tenant-wide; annotator stat set replaced; `"active"` placeholder subs removed across all roles; tenant_admin readiness activity event re-derived.
- `portal-dashboard`: Annotator stat row renders a mixed card set (one continue-work card plus two stat cards); readiness panel renders per-type progress with health colouring instead of a single hardcoded blue share-of-total bar.
- `portal-annotation`: `/annotation` accepts a `?task=<id>` parameter and pre-selects that task on load.
- `annotation-workspace`: The task transition table accepts `pending → in-progress`, so tasks written by the seed path can actually be started. Pre-existing defect; becomes blocking because the continue-work card offers a Start action on exactly those tasks.
- `training-jobs`: Submission gate optionally enforces a per-entity-type minimum in addition to the existing total-count minimum.

## Impact

**Backend**
- `src/gateway/api/v1/dashboard.py` — `_annotator_data`, `_annotator_side_panel`, `_annotator_task_activity`, `_tenant_curated_activity`, `_system_admin_data`, `_tenant_admin_data`, the threshold constant, and the `StatItem`/`DashboardData` models (new `continueWork` field, following the existing optional-field precedent set by `responseQuality` and `activeModel`).
- `src/training_service/api/v1/training_jobs.py:120-133` — submission gate.
- Readiness now reads `public.entity_definitions` (tenant-scoped, `is_active`) in addition to `{schema}.spans`; the annotator path previously touched only the tenant schema.

**Frontend**
- `src/portal/src/components/dashboard/` — new `ContinueWorkCard`, changes to `MetricsPanel` (per-type rows) and the annotator branch of `dashboard/page.tsx`.
- `src/portal/src/types/dashboard.ts` — new payload types.
- `src/portal/src/components/annotation/AnnotationPage.tsx` — query-param task pre-selection.

**Docs**
- `docs/adr/010-*.md` — new ADR partially superseding ADR-006's dataset-threshold clauses.

**Tests**
- `tests/test_dashboard_summary_roles.py`, `tests/test_dashboard_summary.py` — assertions pinned to 500-total readiness and to the removed annotator stats will fail and need rewriting.
- `tests/test_training_jobs_api.py` — 15 call sites set `NER_MIN_TRAINING_ENTITIES`; the new variable must default safely so these remain valid.
- Portal component tests for `StatCard`, `MetricsPanel`, and the dashboard page.

**Not affected**
- `ActiveModelInfo.status = "active"` (`dashboard.py:64,706`) and `ActivityRow.tk = "active"` (`dashboard.py:645`) are a deployment-state enum and a tag colour key respectively, not placeholder sub-labels. They stay.
- Business-user stat cards already pass empty subs.

## Open Questions

- **Overall readiness percentage formula.** With per-type targets there is no single obvious number. Candidates: mean of per-type progress (each capped at 100%) — moves smoothly as work happens; or `min()` across types — honest about the gate but sits at 0% until the weakest type moves. design.md proposes the mean plus an "N of M types ready" sub-label; needs confirmation.
- **Entity types with zero spans and no realistic source.** If a tenant defines nine entity types but its documents only ever contain three, readiness can never reach 100%. Should inactive/unused types be excludable, or is `is_active = false` the intended escape hatch?
- **Three-across layout for the continue-work card.** At `maxWidth: 1240` with the existing `1.5fr` column, three cards leave roughly 220px each — tight for a filename plus a call-to-action. Alternative is a full-width continue card above a two-up stat row. Proposal assumes three-across per the requested card set; design.md records the truncation strategy.
- **Whether to actually set `NER_MIN_ENTITIES_PER_TYPE` in deployment.** Introducing the variable is in scope; turning it on in `docker-compose.yml` is an operational decision that would start rejecting training submissions. Left off by default.
- **Long-term task status vocabulary.** Three values are in play — `seed.py` writes `pending`, `annotation_service` writes `unannotated`, migration 002 defaults to `open`. This change accepts all three and makes `pending` startable, but does not reconcile them or backfill. That belongs in its own change.

**Resolved during pre-flight (tasks.md Group 1):**
- *`annotation_tasks` status vocabulary in live data* — no `open` or `unannotated` rows exist; the only not-started value present is `pending` (14 rows, `demo-tenant`), and it is missing from the transition table, so those tasks cannot be started at all.
- *`annotation_tasks.updated_at` maintenance* — nothing writes it; the column is always NULL, so the `COALESCE` ordering fallback is required.
- *Entity definitions coverage* — only one tenant has any; `demo-tenant` has 525 spans and zero definitions, which is why the breakdown takes the union rather than definitions alone.
