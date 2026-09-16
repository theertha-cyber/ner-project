# Tenant Admin Navigation Restructure — Implementation Map (Phase 1)

Status: **analysis only, no code changed**. Awaiting approval before Phase 2.

Sources reconciled: this repo (source of truth for implementation) + `Tenant-admin navigation
restructure.zip` (UI/IA reference) + the task brief (source of truth for **workflow semantics**,
esp. who reviews what).

---

## 1. What already exists (current implementation)

### 1.1 Architecture
- Python **microservices** under `src/`: `gateway`, `document_service`, `annotation_service`,
  `training_service`, `model_serving`, `extraction_service`, `analytics_service`, `chat_api`.
- **Portal**: Next.js App Router at `src/portal` (`src/portal/src/app/(auth)/…`). Talks to each
  service **directly** via `NEXT_PUBLIC_*_URL` (`src/portal/src/lib/api.ts`); the gateway is *not*
  a proxy for annotation/training.
- **Tenant isolation**: Postgres schema-per-tenant (`tenant_<uuid>`), cloned from
  `tenant_template`. Canonical shared tables live in `public` (`tenants`, `tenant_users`,
  `entity_definitions`, `audit_events`). Migrations in `alembic/versions`; per-tenant DDL fan-out
  via `tenant_schema_ddl.apply_to_all_tenant_schemas`.

### 1.2 RBAC
- Roles enum (`src/gateway/models/__init__.py::UserRole`): `system_admin`, `tenant_admin`,
  `business_user`, `annotator`. **Matches the brief's four roles.**
- **Backend**:
  - Gateway: `require_system_admin` / `require_tenant_admin` / `require_tenant_role` in
    `src/gateway/dependencies.py`, applied per-route via `Depends`.
  - `annotation_service`: `TenantContextMiddleware` validates JWT + tenant only — **no role
    check**. Role enforcement is per-route and **inconsistent**:
    - `review.py` — enforces `{annotator, tenant_admin}` (`require_annotator_or_admin`).
    - `tasks.py`, `spans.py`, `import_.py`, `export.py`, `llm_prelabel.py`, `seed_bootstrap.py`,
      `review_queue.py`, `retraining_decision.py` — **no role gate**. Any authenticated tenant
      user (incl. `business_user`) can assign tasks, edit spans, import annotations, launch
      pre-label batches, approve schema candidates.
  - `training_service`: `training_jobs.create_training_job` enforces `tenant_admin`;
    `approve`/`reject` enforce `system_admin`; `models.py` promote/demote/warmup enforce
    `tenant_admin`.
- **Frontend**: `src/portal/src/components/require-auth.tsx` supports a `roles` prop, but the
  `(auth)/layout.tsx` wraps everything in a bare `<RequireAuth>` with **no per-route roles**.
  Route protection today is effectively "logged in" + nav omission. `nav-config.ts::navFor`
  is the only thing that varies UI by role.

### 1.3 Current Tenant Admin navigation (`src/portal/src/lib/nav-config.ts`)
Flat, 13 items: Dashboard, Uploaded Documents, Entity Types, Suggest Entity Types, Batch
Pre-labeling, Annotation, Review Queue, Import Annotations, Retraining, Models & Training, Create
User, Chat, Widget Keys.
- **Annotator** (6): Dashboard, Annotation (badge 4), Review Queue, Import Annotations.
- **Business user** (4): Dashboard, Documents, Extractions, Chat.
- **System admin** (4): Dashboard, Tenants, Models & Training, Audit Log. (Brief says leave
  untouched; spec agrees.)
- `SCREEN_TITLES`: flat `route → [title, path]` map. `Topbar.tsx` derives the title by
  longest-prefix match. **No breadcrumb/section concept yet.**
- `NavItem` type is flat (`{id, icon, label, href, roles, badge?}`). No `section` / `children`.

### 1.4 The three annotation methods — current state

**Manual**
- Routes: `/annotation` (`AnnotationPage`, 3-pane workspace w/ annotator mode already),
  `/review-queue` (`ReviewQueuePage`).
- API (`annotation_service`): `POST/GET/PATCH /api/v1/annotation-tasks` (`tasks.py`),
  `spans.py` (span CRUD), `review_queue.py` (low-confidence disposition loop),
  `review.py` (annotator review actions).
- Task states (`tasks.py::valid_transitions`): `unannotated → in-progress → completed`
  (+ legacy `pending`). `completed` is terminal and requires ≥1 span. **There is no
  separate "reviewed/approved" state — the annotator marking the task `completed` IS final
  approval.** This already matches the brief (no second Tenant Admin review).
- Table `tenant_*.annotation_tasks` (cols incl. `document_id`, `annotator_user_id`, `status`,
  timestamps; unique partial index on active task per doc). Migrations `003`/`004`.
- `AssignTaskForm.tsx` + `TaskQueue.tsx` already exist. `create_task` requires the document's
  `purpose = 'training'`.
- Assignment currently has **no notification** to anyone on completion.

**Automated** (the "six annotation-automation changes" from commit `0762cc3`)
- Routes: `/schema-proposals` (`SchemaProposalPage`), `/prelabel-batches`
  (`BatchAcceptancePage`), `/retraining` (`RetrainingDecisionPage`).
- API (`annotation_service/seed_bootstrap.py`):
  `POST /api/v1/schema-proposals` (async, seed docs → LLM candidates),
  `GET /api/v1/schema-proposals/{id}`,
  `PATCH/POST …/candidates/{id}` (edit / **approve** / **reject**),
  `POST /api/v1/prelabel-batches` (async batch), `GET …/{id}` (status),
  `POST …/{id}/acceptance`, `…/acceptance/review`, `…/acceptance/accept`.
- `llm_prelabel.py`: `POST /api/v1/documents/{doc_id}/prelabel/llm` (single doc, 202),
  status endpoint. Job states: `queued`, `completed` (also `failed`; content-hash cache).
- `schema_proposal.py` service: LLM proposes entity types **from seed document text** and
  grounds each with quoted evidence. Approve → calls the existing entity-config API to create a
  **canonical** `public.entity_definitions` row.
- `retraining_decision.py`: `GET /api/v1/retraining-decision` — accumulation report only, no
  verdict/threshold/job.
- Tables (migrations `038`, `039`, `040`): `llm_prelabel_jobs`, schema-proposal +
  candidate tables, prelabel-batch + acceptance tables, `span_review_provenance`,
  `span_training_consumption`, `tenants.review_policy`.

**Import**
- Route: `/imported-documents` (623-line page component; reuses annotation Token/reducer
  components + `AnnotationImportPreview`/`Result`, `use-annotation-import` hook).
- API (`annotation_service/import_.py` + `export.py`): `POST /api/v1/annotation-import`
  (parses JSON/JSONL/CoNLL-ish token+tag rows → `tenant_*.imported_annotations`),
  plus export. Parser: `src/portal/src/lib/annotation-import-parser.ts`.
- Table `tenant_*.imported_annotations` (`tokens[]`, `tags[]`, `source_file`, `row_index`,
  `reviewed`/`reviewed_at`/`reviewed_by` — migrations `014`, `017`). **No document upload.**
- **Not currently wired into training export / accumulation.** (Brief wants imported data to be
  training-eligible.)

### 1.5 Entity Types — single source of truth
- Canonical model: `public.entity_definitions` (`src/gateway/models/__init__.py`), served by
  **gateway** `/api/v1/entity-types` (`src/gateway/api/v1/entity_types.py`, `require_tenant_role`).
  Has `qa_examples`, `value_kind`, `cardinality`, `version`, `is_active`, provenance-relevant
  fields.
- Portal: `/entity-types` (`EntityTypesPage`), `useEntityTypes` hook, `DefineEntityTypeSlideOver`
  (already supports QA pairs + cardinality).
- Schema proposals already write into this same table on approve. **So a single source of truth
  already exists** — there is no second entity-type table. The problem is purely **navigation
  duplication** ("Entity Types" vs "Suggest Entity Types" as sibling flat items) + no provenance
  chip.

### 1.6 Training lifecycle
- `training_service`: `POST /api/v1/training-jobs` (tenant_admin, lands `pending_approval`) →
  `POST /{id}/approve` (system_admin, enqueues Celery) / `reject` / `cancel`.
- `POST /api/v1/training-retrain-requests` (`retrain_request.py`) — thin wrapper over
  `create_training_job`; sets `X-Retrain-Warning` header when zero accumulation. Tenant-admin
  only.
- Job states: `pending_approval → queued → running → completed | failed` (+ `cancelled`).
- Model registry: `model_versions` table, MLflow (`infra/mlflow_registry.py`).
  `POST /api/v1/model-versions/{id}/promote|demote|warmup` — **tenant_admin** (keep as-is per
  brief). `promotion_evidence.py` compares run vs serving model.
- Portal: `/training-jobs` (`Models & Training`, shared with system_admin), `/models`.
- Training dataset export = `annotation_service/export.py` (spans). **Imported annotations and
  LLM-accepted batches' path into the training set needs verification in Phase 7.**

### 1.7 Notifications / task-state events
- **No notification system exists** (no table, API, WebSocket/SSE, activity feed). Grep for
  `notification` in `src/**/*.py` → nothing.
- Closest primitives: `public.audit_events` (append-only, `AuditEventKind`) and the dashboard
  `ActivityPanel`. Retrain decision surface is *pull* ("what accumulated"), not *push*.
- ⇒ The brief's "persistent notification to Tenant Admin on Annotator completion" requires
  **new infrastructure** (smallest viable: a `notifications` table + `annotation_service`
  write on task/batch completion + gateway read API + portal bell/feed). This is the single
  biggest genuinely-new piece.

---

## 2. Target implementation (from the ZIP + brief)

### 2.1 Navigation (grouped tree)
`NavItem` becomes a union: `NavLeaf { kind:"link", href, label, icon, badge?, children? }` |
`NavSection { kind:"section", label, items }`. Sections render as **non-navigable headers**;
sections with zero permitted children are dropped. `navFor("system_admin")` stays a flat array
(union still allows it).

**tenant_admin tree**
```
Dashboard                       /dashboard
Annotate  (section)
  Manual                        /annotate/manual   ⟶ tabs: Workspace /annotation · Review Queue /review-queue
  Automated                     /annotate/automated ⟶ stepper: schema · prelabel · review-sample · retrain
  Import                        /annotate/import    ⟶ Imported Files /imported-documents
Setup  (section)
  Uploaded Documents            /documents
  Entity Types                  /entity-types
Models & Training               /training-jobs   (badge)
Admin  (section)
  Create User                   /users
  Widget Keys                   /widget-keys
  Chat                          /chat
```
(Note: ZIP's two specs disagree on whether "Models & Training" sits under Setup or top-level, and
on `/annotate/*` vs `/annotation/*`. **Decision needed — see §6.** Recommendation: top-level
`Models & Training`, route prefix `/annotate/*` per the more detailed *Page Content Spec*.)

**annotator tree**: Dashboard + `Annotate → Manual` (+ `Import` if we confirm annotator import).
Setup/Admin sections drop entirely. Manual landing hides "Assign Task"; primary CTA becomes
"Open my queue".

**business_user / system_admin**: unchanged.

### 2.2 New routes (landing pages only — legacy routes stay canonical)
- `/annotate/manual` — `01 Manual Landing` / `12 Annotator Manual Landing`
- `/annotate/automated` — `04 Automated Landing` + nested `…/schema`, `…/prelabel`
  (Phase A/B/C incl. acceptance review), `…/retrain`, under a persistent **stepper header**.
  Legacy `/schema-proposals`, `/prelabel-batches`, `/retraining` **redirect** to the step routes.
- `/annotate/import` — `08 Import Landing` / `13 Annotator Import`
- `/imported-documents/[id]` — single-row review (`09 Import Review`) — **new sub-route**.

`SCREEN_TITLES` gains keys for the new routes; `Topbar` gains breadcrumb derivation by walking
the nav tree (section → landing → screen).

### 2.3 Workflow semantics the brief pins (override the ZIP where they conflict)
- **Manual**: Annotator `completed` = final approval → data training-eligible → **notify Tenant
  Admin** → Tenant Admin requests training. **No Tenant Admin annotation review.** (ZIP screen 01
  copy says "every submission lands in the review queue for approval" — that's the
  low-confidence disposition queue, *not* a Tenant Admin gate. Keep Review Queue as the
  model-confidence loop per *Page Content Spec*; do not add an approval gate.)
- **Automated**: Tenant Admin reviews **entity schema** (step 1) and the **initial 1–5**
  pre-labels (validation) — but **Annotator Admin** is the final reviewer of the 50+ batch. After
  Annotator approval → training-eligible → notify Tenant Admin. No second Tenant Admin review of
  the 50+.
- **Import**: imported labeled data → validation/parse (existing) → training-eligible → Tenant
  Admin requests training. No document-upload stage. Per-row `reviewed` flag already exists;
  keep it as *import validation*, not a mandated annotation-review gate.
- **Training**: Tenant Admin *requests*, System Admin *approves/executes*, Tenant Admin
  *promotes* (existing split — keep).

---

## 3. File-by-file plan

### 3.1 Navigation (Phase 2)
| File | Action |
|---|---|
| `src/portal/src/lib/nav-config.ts` | **Modify** — new `NavItem` union, grouped `navFor("tenant_admin")` + `navFor("annotator")`, add `SCREEN_TITLES` keys. Keep `system_admin`/`business_user` flat. |
| `src/portal/src/lib/nav-config.test.ts` | **Modify** — update expectations. |
| `src/portal/src/components/app-shell/Sidebar.tsx` | **Modify** — render `section` headers (non-clickable) + nested leaves; keep collapse behaviour. |
| `src/portal/src/components/app-shell/Topbar.tsx` | **Modify** — breadcrumb from nav-tree walk. |
| `src/portal/src/components/app-shell/sidebar.test.tsx` | **Modify**. |
| `src/portal/src/app/(auth)/annotate/manual/page.tsx` | **New** — landing (reuses `TaskQueue`, `AssignTaskForm`, metrics). |
| `src/portal/src/app/(auth)/annotate/automated/layout.tsx` + `/page.tsx` | **New** — stepper shell + landing. |
| `src/portal/src/app/(auth)/annotate/automated/{schema,prelabel,retrain}/page.tsx` | **New** — thin wrappers around existing `SchemaProposalPage` / `BatchAcceptancePage` / `RetrainingDecisionPage`. |
| `src/portal/src/app/(auth)/annotate/import/page.tsx` | **New** — landing (reuses import hook/preview). |
| `src/portal/src/app/(auth)/imported-documents/[id]/page.tsx` | **New** — single-row review; reuse workspace palette/Token/reducer. |
| `src/portal/src/app/(auth)/{schema-proposals,prelabel-batches,retraining}/page.tsx` | **Modify** → `redirect()` to `/annotate/automated/*` (keep files as 301 shims). |
| `src/portal/next.config.*` | **Optionally** add `redirects()` for the legacy paths. |
| `src/portal/src/components/require-auth.tsx` usage | **Modify** — add `roles=` to new route layouts (tenant_admin-only for `/annotate/automated`, etc.). |

### 3.2 Manual (Phase 3)
| File | Action |
|---|---|
| `src/annotation_service/api/v1/tasks.py` | **Modify** — add role gate (`tenant_admin` to create/assign; annotator to `PATCH` own task); on `→ completed`, emit notification + mark training-eligible. Keep state machine. |
| `src/portal/src/components/annotation/AssignTaskForm.tsx`, `TaskQueue.tsx` | **Reuse**, minor wiring into landing. |
| `src/portal/src/components/annotation/AnnotationPage.tsx` | **Reuse** — add breadcrumb + Workspace/Review tab pair in wrapper. |
| notification write | **New** — see §3.7. |

### 3.3 Automated (Phase 4)
| File | Action |
|---|---|
| `src/annotation_service/api/v1/seed_bootstrap.py` | **Modify** — role gates; add explicit stage/state field on batches (`QUEUED/PROCESSING/COMPLETED/PARTIALLY_COMPLETED/FAILED`); route the 50+ batch to an **Annotator** review queue after Tenant-Admin sample sign-off; on Annotator approval → training-eligible + notify. |
| `src/annotation_service/services/schema_proposal.py` | **Modify/extend** — accept a **Q&A pair** (PDF/DOCX/TXT) as an additional/primary proposal input (today it's seed-doc text only). Reuse `document_service` parsing. |
| `src/annotation_service/api/v1/llm_prelabel.py` | **Reuse** — batch driver; confirm 1–5 "initial" vs 50+ "large" batch distinction (may need a `batch_kind` column). |
| `src/annotation_service/services/batch_acceptance.py` | **Reuse/modify** — Tenant-Admin sample review feeds guidance into the large batch. |
| portal `seed-bootstrap/*` components | **Reuse** inside the new stepper routes. |
| new migration | batch stage/kind columns; annotator-review linkage. |

### 3.4 Import (Phase 5)
| File | Action |
|---|---|
| `src/annotation_service/api/v1/import_.py` | **Modify** — role gate; **explicit entity-type mapping** step (unknown types flagged, never auto-created — brief + ZIP screen 09/`10`); mark imported rows training-eligible. |
| `src/annotation_service/api/v1/export.py` | **Modify** — include `imported_annotations` in the training dataset export (Phase 7 dependency). |
| `src/portal/.../imported-documents/page.tsx` | **Modify** — add "Map types" bar/dialog + tabs (Imported Files / Unmapped Types); split list vs `[id]` review. |
| `src/portal/src/lib/annotation-import-parser.ts` | **Reuse**. |

### 3.5 Entity Types (Phase 6)
| File | Action |
|---|---|
| `nav-config.ts` | Remove standalone "Suggest Entity Types" flat item; it becomes `/annotate/automated/schema` (step 1). |
| `src/portal/src/components/entity-types/EntityTypeCard.tsx` | **Modify** — provenance chip (`manual` / `suggested vN` / `imported`). |
| `src/gateway/api/v1/entity_types.py` + `public.entity_definitions` | **Modify** — add `provenance` / `source` column (migration) if not derivable. Confirm schema-proposal approve + import-mapping both stamp it. |
| No new entity-type table. **Single source of truth already holds.** |

### 3.6 Training (Phase 7)
| File | Action |
|---|---|
| `src/training_service/api/v1/retrain_request.py` / `training_jobs.py` | **Reuse** — already the request/approve split the brief wants. |
| `src/training_service/services/consumed_spans.py`, `annotation_service/services/accumulation.py` | **Modify** — count manual-approved + annotator-approved-automated + imported spans as eligible/accumulated. |
| "training-eligible" surfacing | **New** small state per source (manual task, automated batch, import file) — a computed flag or a lightweight column. |

### 3.7 Notifications (cross-cutting, new)
| File | Action |
|---|---|
| `alembic/versions/041_notifications.py` | **New** — `public.notifications` (or `tenant_*`) : `id, tenant_id, recipient_user_id/role, kind, title, body, resource_ref, read_at, created_at`. |
| `src/gateway/api/v1/notifications.py` + router reg in `gateway/main.py` | **New** — `GET /api/v1/notifications`, `POST /{id}/read`. |
| `src/annotation_service/services/notify.py` | **New** — helper; called from `tasks.py` (manual complete), `seed_bootstrap.py` (annotator approves 50+ batch). |
| `src/portal/src/components/app-shell/Topbar.tsx` + new `NotificationBell` | **New** — persistent list, not a toast. |
| Dashboard `ActivityPanel` | **Optionally** surface the same feed. |

---

## 4. APIs

**Reuse as-is**: gateway `/api/v1/entity-types`; `annotation-tasks` (state machine);
`annotation-import` / `annotation-export`; `schema-proposals*`; `prelabel-batches*`;
`documents/{id}/prelabel/llm`; `retraining-decision`; `training-jobs*`;
`training-retrain-requests`; `model-versions/*` (promote/demote).

**Modify**: `annotation-tasks` (role gate + completion hook), `seed_bootstrap` batch endpoints
(explicit stage enum + annotator-review routing), `annotation-import` (type-mapping step +
training-eligible), `annotation-export` (include imports), `entity-types` (provenance).

**Genuinely new**: `GET/POST /api/v1/notifications` (gateway); optionally
`GET /api/v1/annotate/overview` per-method status aggregation for the three landing pages
(could also be assembled client-side from existing endpoints — prefer client-side first).

---

## 5. Database changes
1. `public.notifications` table (new migration).
2. `entity_definitions.provenance` (varchar) — or derive from existing schema-proposal linkage;
   decide in Phase 6.
3. `tenant_*.prelabel_batches`: `stage`/`state` enum column
   (`QUEUED|PROCESSING|COMPLETED|PARTIALLY_COMPLETED|FAILED`) + `batch_kind`
   (`initial` vs `large`) + annotator-review linkage columns.
4. Possibly `tenant_*.annotation_tasks.training_eligible_at` and an equivalent marker on
   `imported_annotations` / batches (or compute).
5. `imported_annotations` type-map storage (a `type_map` JSON on an import-file record, or a new
   `annotation_imports` header table — currently there is only the row table).

All per-tenant DDL via `apply_to_all_tenant_schemas`.

---

## 6. Conflicts & decisions needed before Phase 2

1. **Route prefix**: `/annotate/*` (Page Content Spec, detailed) vs `/annotation/*` (brief's
   suggested IA). Recommendation: **`/annotate/*`** (keeps existing `/annotation` workspace route
   untouched as the canonical child — no collision).
2. **"Models & Training" placement**: top-level (Page Content Spec) vs under "Setup" (Nav
   Restructure Spec). Recommendation: **top-level**.
3. **Annotator Import access**: ZIP open question. Brief lists no import rights for annotator but
   screen `13 Annotator Import` exists (read + per-row review, no upload). Recommendation:
   **annotator gets Import (review-only)**.
4. **Review Queue "accumulation card"**: Page Content Spec moves it off Review Queue onto
   `/annotate/automated/retrain`. Confirm that removal is acceptable.
5. **Agreement-rate threshold**: is it tenant-configurable (override a failing batch)? Affects
   pre-label step blocking copy. (`tenants` has `review_policy` already; no threshold column.)
6. **Notification model scope**: `public` (cross-tenant infra, simpler reads) vs `tenant_*`
   (isolation-pure). Recommendation: **`public.notifications` with `tenant_id` + RLS-style
   filtering in the query**, matching `audit_events`.
7. **Manual "initial 1–5" vs "50+" in Automated** — need a `batch_kind`; confirm the 1–5
   validation batch is a first-class object or just "the first prelabel batch".
8. **Q&A pair ingestion for schema proposal** — today proposals read seed *documents*. Adding a
   Q&A-pair input is a real change to `schema_proposal.py` + a new upload affordance. Confirm
   scope (Q&A pair *instead of* or *in addition to* seed docs).

---

## 7. Risks & assumptions

- **RBAC is the biggest risk.** Multiple `annotation_service` routers have **no role
  enforcement**; the brief demands backend RBAC parity. Phase 2/3 must add gates to
  `tasks.py`, `spans.py`, `import_.py`, `export.py`, `seed_bootstrap.py`, `llm_prelabel.py`,
  `review_queue.py` — this touches behaviour and existing tests. Assumption: JWT `role` claim is
  trustworthy (it's set from `decode_token`).
- **No notification infra** — new table + API + UI. Assumption: a simple polled feed (no
  WebSocket) is acceptable.
- **Imported annotations not in training path today** — wiring them in (Phase 5/7) may surface
  format/label-scheme mismatches (BIO tags vs span offsets; `export.py` comments already note
  offset-vs-token drift).
- **Legacy route redirects**: `/schema-proposals` etc. are referenced in `nav-config.ts`,
  tests, and possibly deep links / docs (`openspec/`). Must grep-and-fix all references, add
  redirects, not delete.
- **`(auth)/layout.tsx` has no per-route role guard** — adding `roles=` per route is new
  surface; must not lock out `system_admin` from shared screens (`/training-jobs`).
- **ZIP vs brief workflow conflict** (manual "review queue for approval" wording) resolved in
  favour of the brief: Review Queue stays the model-confidence disposition loop, no Tenant Admin
  annotation gate.
- **`create_task` requires `document.purpose == 'training'`** — the Manual landing "Upload
  Document → becomes a task" flow must set purpose correctly (reuse `DocumentUpload`
  annotationMode, which already exists).
- Automated is `tenant_admin`-only (annotators have no automated access) — confirmed by spec;
  section header must drop for annotators.
- System Admin nav + flows explicitly out of scope / untouched.

---

## 8. Phase sequence (unchanged from brief)
2 Navigation → 3 Manual → 4 Automated → 5 Import → 6 Entity Types → 7 Training → 8 Testing
(unit + integration + portal vitest + API + typecheck + lint, all four roles, RBAC bypass tests).
