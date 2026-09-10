## Context

`seed-bootstrap` shipped the mechanism: schema proposal, batch pre-labeling, sampled
acceptance, readiness check. The Tenant Admin Console restructure (this workstream's Phase
2, already landed) added the `/annotate/automated` stepper and the `schema | prelabel |
retrain` step routes; Phase 3 added `public.notifications` and
`src/annotation_service/services/notify.py`, plus the columns
`prelabel_batches.annotator_review_status` and `prelabel_batches.training_eligible_at`
(migration 041).

What is missing is the *shape* of the guided workflow: the Q&A-pair document that a Tenant
Admin actually starts from, the `initial` vs `large` batch distinction that decides **who
reviews** (Tenant Admin validates the small batch; Annotator Admin is the final reviewer of
the large one), the named batch lifecycle the UI needs, and the training-eligibility +
notification hand-off on annotator approval.

## Goals / Non-Goals

**Goals:**
- Let a Tenant Admin drive schema derivation from a question/answer document, not just seed
  text.
- Distinguish the 1–5 validation batch (Tenant-Admin-reviewed, feeds guidance) from the
  50+ batch (Annotator-Admin-reviewed, final).
- Give a batch a single named state the UI can render without polling logic in the client.
- On Annotator Admin approval of a `large` batch: training-eligible + Tenant Admin
  notification, with no second Tenant Admin review.

**Non-Goals:**
- No new entity-type table or create path — approved candidates still go through the
  `entity-config` API into `public.entity_definitions` (unchanged from `seed-bootstrap`).
- No new training submission mechanism — the Tenant Admin uses the existing
  `POST /api/v1/training-retrain-requests`.
- No agreement-threshold override UI — threshold stays fixed/conservative (see Decision 4).
- No change to the single-document Suggest flow, the `initial`-batch acceptance mechanics
  beyond the role gate, or System Admin training approval.

## Currently-In-Force ADRs

| ADR | Constraint on this design |
|-----|---------------------------|
| ADR-001 tenant-data-isolation | The Q&A document, `batch_kind`, `state`, and guidance rows all live in the tenant schema and resolve it the way existing `annotation_service` endpoints do. |
| ADR-006 training-infrastructure | Batch pre-labeling stays on the non-GPU LLM queue; nothing here touches `training.jobs`. |
| ADR-009 system-admin-sets-hyperparameters | Training-eligibility is a data-state flag, not a training trigger; the System Admin approval step is untouched. |
| ADR-011 annotation-idempotency-enforcement | The acceptance→eligible→notify transition MUST be idempotent: re-accepting an already-approved `large` batch MUST NOT write a second notification or a second set of confirmed spans. |
| ADR-012 annotation-fix-deployment-topology | New endpoints stay within `annotation_service`; the notification read API stays in `gateway` (added in Phase 3). |

## Decisions

### Decision 1: The Q&A pair is a `documents` row with `purpose = 'qa_pair'`

**Choice:** A Tenant Admin uploads the Q&A document through the existing document upload
path with a new `purpose` value `qa_pair`. It is parsed by the normal text-extraction
pipeline. The schema proposal records a reference to that document id among its inputs; the
proposal prompt reads the document's extracted text.

**Rationale:** Reuses upload, storage, virus/size limits, text extraction, and tenant
scoping. A proposal stays reproducible because its exact input document is retained and
addressable. `purpose = 'qa_pair'` keeps it out of the training-document set and out of the
seed-document picker.

**Alternatives:** a dedicated `qa_pair_documents` table (rejected — duplicates the
documents pipeline); consume-and-discard the upload (rejected — proposal not reproducible,
and a re-run silently uses different input).

### Decision 2: `batch_kind` is chosen at trigger time and drives the reviewer role

**Choice:** `prelabel_batches.batch_kind ∈ {initial, large}`, set by the trigger endpoint.
`initial` ⇒ ≤ 5 documents, acceptance review gated to `tenant_admin`, acceptance does not
mark eligible or notify. `large` ⇒ no cap, acceptance review gated to `annotator`,
acceptance marks `training_eligible_at` + `annotator_review_status='approved'` + notifies
`tenant_admin`.

**Rationale:** The product model is explicit that these are different review steps with
different owners. Encoding the kind on the batch keeps the acceptance endpoint's role check
and side effects data-driven rather than requiring two parallel endpoints.

**Alternatives:** infer kind from document count (rejected — a 5-document `large` batch is
legitimate and a Tenant Admin re-running validation with 5 docs is not a `large` batch);
separate `/initial-batches` and `/large-batches` routes (rejected — duplicates the batch
machinery).

### Decision 3: `state` is derived, not stored as a workflow field

**Choice:** `state` is computed from existing per-document outcome rows:
`queued` (no outcomes yet, job enqueued), `processing` (some outcomes, job not finished),
`completed` (finished, all succeeded), `partially_completed` (finished, mixed),
`failed` (finished, all failed). A nullable `prelabel_batches.state` column caches the
terminal value written once when the job finishes, so a status read after completion is a
single-row lookup.

**Rationale:** The per-document outcomes are already the source of truth; a separately
maintained state machine would be a second thing to keep consistent. Caching only the
terminal state avoids write contention during processing while keeping post-hoc reads
cheap.

### Decision 4: The agreement threshold stays fixed and conservative

**Choice:** No tenant-configurable threshold and no override path in this change. The
`large`-batch acceptance gate uses the same configured threshold `seed-bootstrap`
established.

**Rationale:** `seed-bootstrap`'s open question — "the threshold must be measured against
real reviewed batches rather than guessed" — is still open. Adding an override before that
evidence exists invites accepting bad batches. Revisit as a follow-up once real
`large`-batch agreement data exists.

### Decision 5: Initial-batch guidance is corrected spans + an optional per-document note, encoded into the prompt as text

**Choice:** Reviewing an `initial` batch writes rows to a new
`{schema}.prelabel_batch_guidance` table: `(batch_id, document_id, corrected_spans jsonb,
note text)`. When a `large` batch is triggered, `schema_proposal`/`llm_prelabel` prompt
construction appends a "Reviewer guidance from validation" section built from the most
recent reviewed `initial` batch's guidance rows — corrected spans rendered as
"`<quote>` → `<type>`" lines, notes rendered verbatim.

**Rationale:** Keeps the guidance human-readable and auditable, and reuses the existing
QA-pair prompt-append mechanism rather than inventing a fine-tuning/example-selection path.

**Alternatives:** synthesise QA pairs from corrections and write them onto entity types
(rejected — pollutes canonical entity config with batch-specific artifacts); silently add
corrected spans to the training set (rejected — they were never annotator-reviewed).

### Decision 6: The acceptance→eligible→notify transition is idempotent and single-transaction

**Choice:** `POST …/acceptance/accept` for a `large` batch, in one DB transaction:
promote spans (existing), then `UPDATE prelabel_batches SET training_eligible_at = NOW(),
annotator_review_status = 'approved' WHERE id = :id AND training_eligible_at IS NULL`, and
write the notification only when that UPDATE affected a row.

**Rationale:** ADR-011. A retried or double-clicked accept must not double-promote or
double-notify. Guarding the notification on the conditional UPDATE's row count makes the
whole side effect fire exactly once.

## Risks / Trade-offs

- **Guidance staleness:** guidance is taken from the *most recent* reviewed `initial`
  batch. A Tenant Admin who runs two `initial` batches gets only the later one's guidance.
  Acceptable — the workflow is "validate, then run large"; multiple validation rounds are
  rare and the latest is the most informed.
- **`state` cache vs live:** if the worker crashes after the last document outcome but
  before writing the terminal `state`, a status read computes `processing` forever. Mitigate
  with a reconcile on read: if all outcomes are present and `state` is null, compute and
  cache it then.
- **Q&A `purpose` proliferation:** adding `qa_pair` to the `purpose` enum touches every
  `WHERE purpose = 'training'` filter. Audited in tasks; the filters are few and already
  explicit.

## Migration Plan

1. Migration `042`: add `prelabel_batches.batch_kind` (default `large` for existing rows,
   which were all effectively large), `prelabel_batches.state` (nullable), and
   `{schema}.prelabel_batch_guidance`. Extend the `documents.purpose` check/enum to allow
   `qa_pair`. All additive; `apply_to_all_tenant_schemas`.
2. No backfill of `training_eligible_at` — existing batches predate the concept and a
   Tenant Admin can re-request training from accumulation regardless.
3. `scripts/setup_test_db.py` and the annotation test fixtures gain the new columns/table.

## Open Questions

- Should an `initial` batch be re-runnable in place (same `batch_id`) or always a new
  batch? Assume always new; guidance selection picks the latest reviewed one.
- Does the Annotator Admin need to see *which* Tenant Admin corrections informed the
  `large` batch during their review? Out of scope here; surface later if reviewers ask.
