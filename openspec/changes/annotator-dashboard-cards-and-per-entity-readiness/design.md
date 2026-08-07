## Context

`GET /api/v1/dashboard/summary` serves every role from one payload shape (`DashboardData`), with a per-role builder function selecting what fills it. The annotator builder (`_annotator_data`, `dashboard.py:834`) produces three `StatItem`s and a side panel driven by `_annotator_side_panel` (`dashboard.py:943`).

Today the side panel computes a single tenant-wide span count, divides it by `DATASET_READINESS_ENTITY_THRESHOLD = 500`, and renders the top five entity types as share-of-total bars with a hardcoded `c="blue"` (`dashboard.py:998`). Three problems follow from that shape:

1. The denominator is a tenant-wide total, so a corpus dominated by one label reads as "ready" while most labels have almost no examples.
2. The breakdown only enumerates entity types that already appear in `spans`. A configured type with zero annotations — precisely the one an annotator needs to go find — is invisible.
3. The same tenant-wide span count also fills the "Entities Annotated" stat card, so one number appears twice on a personal dashboard under two different names.

Constraints shaping this design:

- **`spans` has no annotator attribution.** Migrations 002, 004, and 009 define no `annotator_user_id` or equivalent. Nothing per-annotator can be computed from spans without a schema change, which is out of scope here.
- **Entity definitions live in `public`, spans live in the tenant schema.** `public.entity_definitions` is keyed by `tenant_id` with an `is_active` flag; `{schema}.spans` carries a free-text `entity_type`. Per-type readiness requires joining across that boundary.
- **The dashboard handler swallows failures per-block.** Each metric sits in its own `try/except` that leaves the field `None` and marks a `sources` flag false. New queries must preserve that "degrade one card, not the page" behaviour, including the `await db.rollback()` discipline that `_tenant_response_quality_card` documents at `dashboard.py:792-798`.
- **`/annotation` cannot be linked to.** `AnnotationPage` holds `selectedTask` in `useState` (`AnnotationPage.tsx:46`) with no URL binding.

## Goals / Non-Goals

**Goals:**

- Express dataset readiness in units that predict model quality: labeled examples per entity type.
- Surface every configured entity type in the readiness breakdown, including those at zero.
- Give annotators a one-click route back into the document they were last working on.
- Make `Assigned tasks` an honest progress fraction, and stop shipping decorative sub-labels.
- Keep one definition of "training-ready" shared between what the dashboard displays and what the training gate can enforce.
- Ensure every action the new card offers actually succeeds — including starting a task whose status the API currently refuses to transition (Decision 6).

**Non-Goals:**

- Per-annotator span attribution, leaderboards, or "your contribution" metrics — these need a `spans` schema change and are deliberately deferred.
- Turning the per-type gate on in deployment. This change introduces the knob; setting it is an operational decision.
- Reworking the tenant_admin, system_admin, or business_user dashboards beyond removing the `"active"` placeholder sub-labels.
- Any change to how spans are created, validated, or exported.
- Broader repair of the task status vocabulary. Decision 6 adds the single transition the new card depends on; reconciling `seed.py`, the migrations, and `annotation_service` on one vocabulary — and backfilling existing rows — is left to its own change.
- Writing `annotation_tasks.updated_at`. Task 1.2 confirmed nothing maintains it; Decision 4 works around that rather than fixing it.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 Tenant Data Isolation via Separate Database Schemas | Tenant data lives in per-tenant Postgres schemas | Per-type readiness queries must stay inside `{schema}` for spans; the `public.entity_definitions` read must be filtered by `tenant_id` and must not leak across tenants |
| ADR-004 OpenSpec Spec-Driven Development Governance | Behaviour changes land through spec deltas before code | Threshold semantics must be recorded as a spec delta, not only as a constant edit |
| ADR-006 Training Infrastructure (in force except the hyperparameter clause superseded by ADR-009) | Compliance section states both "500-entity minimum dataset threshold" and "500 labeled entities per entity type" | The contradiction is the direct subject of this change; ADR-006 is not edited — a new superseding ADR is required (see Open Questions) |
| ADR-009 System Admin Sets Training Hyperparameters at Approval | Partially supersedes ADR-006 on hyperparameters only | Confirms the partial-supersession convention this change follows for the threshold clause |

ADR-002 is partially superseded by ADR-008; neither constrains this design. ADR-003, ADR-005, ADR-007 are unrelated.

## Decisions

### Decision 1: Readiness is measured per active entity type, at 200 each

**Choice:** Replace `DATASET_READINESS_ENTITY_THRESHOLD = 500` with `DATASET_READINESS_ENTITIES_PER_TYPE = 200`. Evaluate each entity type against 200 independently. The set of types evaluated SHALL be the **union** of the tenant's active entity definitions (`public.entity_definitions WHERE tenant_id = :tid AND is_active = true`) and the distinct `entity_type` values already present in `{schema}.spans`.

**Rationale:** NER model quality is bounded by the weakest label, not the aggregate corpus size. A per-type target is the smallest change that makes the displayed number predictive of the thing it claims to predict, and it converts the panel from a passive counter into a directive one — the annotator can see which label to go find.

The union is what makes both halves work. Enumerating `entity_definitions` is what makes zero-count types visible — grouping `spans` alone structurally cannot show a label nobody has tagged yet, which is the whole defect being fixed. But a definitions-only enumeration loses data in the opposite direction: task 1.3 found `demo-tenant` has **525 spans across 5 types and zero entity definitions**, so a definitions-only query would report readiness as unavailable for a tenant with real annotation data currently rendering a full bar. Taking the union costs one `UNION` and cannot regress any tenant.

**Alternatives considered:**
- *Enumerate `entity_definitions` only* — the original choice; ruled out by the task 1.3 finding above. A tenant that never configured its label list silently loses its readiness panel.
- *Enumerate `spans` only (status quo)* — cannot surface a configured-but-untagged type, which is the defect this change exists to fix.
- *Fall back to `spans` only when a tenant has no definitions* — a conditional that produces two different panel semantics depending on invisible configuration state; the union gives one rule.
- *Keep a tenant-wide total, raise or lower it* — preserves the exact defect: aggregate size stays a poor proxy for per-label sufficiency.
- *Weight the target by type (e.g. more for rare entities)* — more accurate in principle, but requires per-type configuration that does not exist on `entity_definitions` and would need its own change.

### Decision 2: Overall readiness is the mean of per-type progress, each capped at 100%

**Choice:** `bar = mean(min(count_t / 200, 1) for t in active_types) * 100`, with a sub-label stating "N of M types ready". When a tenant has zero active entity types, readiness is reported as unavailable rather than as `0%` or `100%`.

**Rationale:** The bar's job on this dashboard is feedback — it must move when work happens, or annotators stop reading it. `min()` across types is the honest gate but stays pinned at 0% until the single weakest label moves, which is demotivating and uninformative for most of the run. The mean moves continuously; pairing it with the "N of M types ready" count restores the gate reading, so the card carries both without either being hidden. Capping each type at 100% stops an over-annotated label from masking a starved one — the defect this whole change exists to fix.

**Alternatives considered:**
- *`min()` across types* — ruled out as the headline for the reason above; it remains available implicitly through the per-type rows, which show the weakest type directly.
- *Uncapped mean* — reintroduces the original bug in a new coordinate system: 900 of one label and 0 of another would read as ready.
- *Percentage of types at 100%* — identical information to the "N of M" sub-label but discards all partial progress, so the bar would sit at 0% for most of the effort.

### Decision 3: `continueWork` is a new optional top-level payload field, not a `StatItem`

**Choice:** Add `ContinueWork | None` to `DashboardData` alongside the existing `responseQuality` and `activeModel` optionals, and render it with a dedicated `ContinueWorkCard` component placed as the first cell of the annotator stat row.

**Rationale:** `StatItem` is a label/value/unit/sub/delta tuple built for a single scalar. The continue card needs a document title, a task id, a status, and a navigable target — forcing that through `StatItem` would mean encoding structure into the `sub` string and special-casing it in `StatCard`. `DashboardData` already carries two role-specific optional card payloads with dedicated components, so this follows an established pattern rather than inventing one. The dashboard page already renders the stat row as `repeat(${data.stats.length}, 1fr)`, so the annotator branch renders one `ContinueWorkCard` plus `data.stats.map(StatCard)` in the same grid.

**Alternatives considered:**
- *Encode it as a `StatItem` with the filename in `sub`* — no room for a link target, and `StatCard` would need a branch on label text.
- *Render it full-width above the stat row* — arguably better for long filenames, but the requested card set is three-across; the truncation strategy in Decision 5 addresses the width concern instead.

### Decision 4: Task selection precedence, with an ordering fallback

**Choice:** Select the annotator's continue-work task in this order:

1. Most recently worked task with status `in-progress` → `mode: "resume"`
2. Else oldest not-started task → `mode: "start"`
3. Else most recently worked task with status `completed` → `mode: "review"`
4. Else `null` → caught-up state

"Most recently worked" is ordered by `COALESCE(annotation_tasks.updated_at, (SELECT MAX(updated_at) FROM spans WHERE document_id = at.document_id), annotation_tasks.created_at)`.

**Rationale:** The card's purpose is to return the annotator to the task they were last working on, so an in-progress task always wins. When nothing is in progress, unstarted work outranks finished work — pointing someone at a document they already submitted while their queue still has untouched tasks is unhelpful. The completed case is the last resort before blank: an annotator whose only recent activity was finishing something still sees what that was, under a `review` label rather than `resume`, so the card never invites an accidental edit to submitted work while still honouring "the latest task worked on".

The `COALESCE` exists because task 1.2 confirmed nothing writes `annotation_tasks.updated_at` — the only UPDATE against the table is `SET status = :status` (`tasks.py:202`), so the column is always NULL in practice. Ordering solely by it would be arbitrary. The document's latest span timestamp reconstructs "last worked on" from data that is definitely maintained, and `created_at` is a guaranteed non-null floor.

**Alternatives considered:**
- *In-progress only, caught-up otherwise* — cleanest against the stuck-`pending` problem in Decision 5, but leaves the card blank for an annotator holding a full queue of untouched tasks.
- *Completed ahead of unstarted* — a literal reading of "latest task worked on", but sends someone back into finished work while real work waits.
- *Single `resume` mode covering completed tasks too* — the card would read "Resume" on a submitted document, which misdescribes what clicking it does.
- *Order by `updated_at` alone* — correct only if a writer exists; task 1.2 confirmed none does.
- *Fix `updated_at` maintenance as part of this change* — touches the span write path in `annotation_service`, widening scope well past a dashboard change.

### Decision 5: Three status vocabularies are normalised at the query boundary

**Choice:** Treat `status = 'completed'` as the completed numerator and all non-completed rows as the remainder; treat `'unannotated'`, `'open'`, **and `'pending'`** as "not started" wherever the distinction matters. Do not migrate the data.

**Rationale:** Three vocabularies are in play and none of the three sources agree. Migration 002 defaults `status` to `'open'`; migration 004 changes the default to `'unannotated'`; `annotation_service` writes `'unannotated'` on create (`tasks.py:82`). But task 1.1 found the live database contains **none of those** — the only not-started value present is `'pending'`, 14 rows in `demo-tenant`, written by `seed.py:248`. A spec covering only `open`/`unannotated` would match nothing real, and the card would report "caught up" to an annotator holding 14 untouched tasks. Accepting all three is the only version that works against both the documented schema and the actual data.

Defining the fraction as completed-over-total keeps the denominator correct regardless of vocabulary, so only the "not started" classification needs the alias.

**Alternatives considered:**
- *Alias `'pending'` only, drop `'open'`/`'unannotated'` as fictional* — they are what the migrations and the create path actually specify; a tenant provisioned from `tenant_template` will produce them.
- *Backfill all variants to `'unannotated'`* — correct long-term, but a data migration inside a dashboard change; better proposed on its own.
- *Ignore `'pending'`* — the defect described above; the card would be silently wrong for the only tenant that has unstarted tasks.

### Decision 6: `pending` is added to the task state machine

**Choice:** Add `"pending": ["in-progress"]` to `valid_transitions` in `src/annotation_service/api/v1/tasks.py`. No other transition is altered.

**Rationale:** Decision 4's fallback offers the annotator an unstarted task with a **Start** action. Task 1.1 found that every unstarted task in the live database has status `'pending'`, and that `'pending'` is absent from `valid_transitions` (`tasks.py:175-177`) — so `allowed` resolves to `[]` and every transition out of it returns `422 INVALID_TRANSITION`. Those 14 tasks cannot be started through the API today, by any route.

This is a pre-existing bug, not one this change introduces. It becomes load-bearing here because the chosen card behaviour puts a Start button in front of exactly those tasks: without this one-line addition, the feature ships a button that always fails. Fixing the reachable transition is strictly smaller than the alternative of building a card that knowingly offers dead actions.

**Alternatives considered:**
- *Leave the state machine alone and ship the fallback anyway* — delivers a visibly broken button; rejected.
- *Drop the unstarted-task fallback instead* — sidesteps the bug but was explicitly ruled out when the card's empty-case behaviour was chosen.
- *Backfill `'pending'` → `'unannotated'` in the data* — fixes the 14 rows but leaves the state machine unable to handle the value if anything writes it again, `seed.py` included.

### Decision 7: The training gate gains a separate, default-off per-type variable

**Choice:** Add `NER_MIN_ENTITIES_PER_TYPE` (default `0`) to `create_training_job` alongside the existing `NER_MIN_TRAINING_ENTITIES`. When non-zero, reject submission with 422 naming the specific types that fall short. Leave `NER_MIN_TRAINING_ENTITIES` and its default untouched.

**Rationale:** The dashboard and the gate must be able to share one definition of readiness, or the dashboard is asserting a rule nothing enforces — the exact situation flagged in the archived `2026-07-08-remove-training-span-gate` change. A separate variable defaulting to `0` means no deployment behaviour changes on merge, and the 15 existing `NER_MIN_TRAINING_ENTITIES` call sites in `tests/test_training_jobs_api.py` stay valid. Naming the failing types in the 422 makes the error actionable rather than just prohibitive.

**Alternatives considered:**
- *Redefine `NER_MIN_TRAINING_ENTITIES` to mean per-type* — silently changes the meaning of a configured production value; a deployment setting it to 500 for a total would suddenly demand 500 per type.
- *Leave the gate alone entirely* — keeps the dashboard's claim unenforceable, which is half the original problem.

## Risks / Trade-offs

- [Readiness can never reach 100% if a tenant configures entity types its documents never contain] → Readiness enumerates `is_active = true` only, so deactivating an unused type is the supported escape hatch; surfaced explicitly in Open Questions and in the proposal.
- [Three-across layout leaves ~220px per card at `maxWidth: 1240`, and document filenames like `AbdullahSuhailA[7_0].pdf` will not fit] → `ContinueWorkCard` truncates the filename with `text-overflow: ellipsis` on a single line and exposes the full name via `title`; the call-to-action is an icon-plus-short-label, not a full sentence.
- [Entity-type breakdown grows unbounded — a tenant with 20 active types produces 20 rows in a side panel currently capped at 5] → Sort types with the least progress first and cap the rendered rows, with a "+N more" affordance; the panel's job is to point at the next label to work on, which the worst-first ordering serves directly.
- [Existing dashboard tests assert the 500-total behaviour and the removed annotator stats, so they will fail] → Expected and intentional; rewriting them is an explicit task, and the spec scenarios map one-to-one onto the replacements.
- [Joining `public.entity_definitions` into a previously tenant-schema-only path risks cross-tenant leakage if the `tenant_id` filter is omitted] → The filter is a spec-level requirement with its own scenario, not just an implementation detail, and ADR-001 makes it a compliance concern.
- [The continue-work card's deep link can point at a task that was completed or reassigned between page load and click] → The annotation workspace resolves `?task=` against the annotator's current queue and falls back to its default selection when the id is absent or no longer theirs, rather than erroring.
- [Two card-count changes land together (stat set replaced, readiness redefined), making a partial rollback awkward] → Both are display-layer changes behind one endpoint version; rollback is a single revert, and no data is written or migrated.
- [Adding `pending → in-progress` widens an API state machine from inside a dashboard change, and a careless edit could loosen other transitions] → The addition is one dict entry; the spec pins every other transition explicitly, including that `completed` remains terminal and that no transition into `pending` is created.
- [Readiness numbers will visibly drop for tenants whose configured label list exceeds what they have tagged — Inapp HR falls from ~5% to ~1.5% because it is now measured against 8 types rather than the 3 that happen to have spans] → Intended and correct: the earlier figure only looked healthy because untouched labels were invisible. Flagged here so the drop is not mistaken for a regression at review time.
- [The union in Decision 1 can surface `spans.entity_type` values that no longer correspond to a configured label — e.g. a type renamed or deactivated after annotation] → Such a type has real spans behind it and is legitimately part of the dataset; showing it is more honest than hiding it, and `is_active = false` only removes a type from the definitions half of the union, not from spans that already exist.

## Migration Plan

No data migration is required — this change reads existing tables and writes nothing.

1. Land the `pending → in-progress` transition (Decision 6) **first**. It is independently safe — it only widens what the API accepts — and landing it ahead of the card guarantees the Start action never ships broken.
2. Land the backend payload changes (`continueWork` field, per-type readiness, stat-set replacement, `"active"` sub removal) together, since the portal reads all four from one response.
3. Land the portal changes in the same deploy. The payload is not versioned, so a portal build older than the gateway would render an empty stat row for annotators.
4. Land `?task=` support in the annotation workspace **before or with** the dashboard card, so the deep link is never dead.
5. Add `NER_MIN_ENTITIES_PER_TYPE` to the training service with default `0`. No `docker-compose.yml` or `.env` change — the gate stays inert until a separate operational decision turns it on.
6. Record the superseding ADR (see Open Questions) in the same change so the threshold has a single documented source.

**Rollback:** revert the gateway and portal commits together. `NER_MIN_ENTITIES_PER_TYPE` is inert at its default, so it can be left in place or reverted independently without behavioural effect. The Decision 6 transition can be left in place on rollback — it fixes a pre-existing defect and nothing depends on its absence.

## Open Questions

- **ADR-006 needs revisiting and this design cannot do it.** Its Compliance section carries two mutually inconsistent thresholds ("500-entity minimum dataset threshold" and "500 labeled entities per entity type"), and this change moves the real figure to 200 per type. Per the supersession convention set by ADR-008 and ADR-009, the adr step should record a new ADR partially superseding ADR-006's dataset-threshold clauses. ADR-006 must not be edited in place.
- **Is 200 the right figure?** It was chosen as the requested target, not derived from measured F1-versus-example-count on this corpus. Worth revisiting once a model has trained against a per-type-balanced dataset.
- **Should the "N of M types ready" count use `is_active` or a narrower "expected in corpus" flag?** No such flag exists today; adding one is a separate change to `entity_definitions`.
- **Should `?task=` be a query parameter or a path segment (`/annotation/<task-id>`)?** Query parameter chosen for a non-breaking addition to an existing route; a path segment would be more idiomatic if the workspace later needs per-task routing state.
- **Which task status vocabulary wins long-term?** `seed.py` writes `pending`, `annotation_service` writes `unannotated`, migration 002 defaults to `open`. Decision 5 accepts all three and Decision 6 makes `pending` workable, but the underlying disagreement is unresolved and should get its own change.

**Resolved during pre-flight (see tasks.md Group 1):**
- *Does anything maintain `annotation_tasks.updated_at`?* No — task 1.2. The Decision 4 `COALESCE` is required, not defensive.
- *Do any live rows carry `status = 'open'`?* No — task 1.1 found `pending` instead, which drove Decisions 5 and 6.
- *Does every tenant have entity definitions to render against?* No — task 1.3 found `demo-tenant` has 525 spans and zero definitions, which drove the union in Decision 1.
