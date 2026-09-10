## Why

The `seed-bootstrap` capability already does most of what the Tenant Admin's Automated
annotation workflow needs — LLM schema proposal, batch pre-labeling, a sampled acceptance
gate — but it was built as an engineer's pipeline, not the guided four-stage workflow the
product model calls for. Three gaps block it from being that workflow:

1. There is no **Q&A-pair document** as a proposal input. The proposal job reads seed
   document text plus whatever `qa_examples` already sit on entity types; a Tenant Admin
   cannot upload the question/answer pair that defines what they want extracted.
2. A batch has per-document outcomes but **no named lifecycle**. The UI cannot show
   `QUEUED / PROCESSING / COMPLETED / PARTIALLY_COMPLETED / FAILED`, and there is no
   distinction between the **initial 1–5 validation batch** (which the Tenant Admin
   reviews to refine the model) and the **large 50+ batch** (which an Annotator Admin
   reviews as the final annotation gate).
3. Acceptance review has no role. The large batch must go to an **Annotator Admin** as the
   final reviewer; on their approval the batch becomes training-eligible and the Tenant
   Admin is *notified* — there is no second Tenant Admin review of the 50+ documents.

## What Changes

- Add a **Q&A-pair upload** to the schema proposal step. A Tenant Admin uploads one PDF /
  DOC / DOCX / TXT question–answer document; it is parsed via the existing document text
  extraction path and passed to the proposal prompt alongside the seed documents. Approved
  candidates are still created through the existing entity-config API into the canonical
  `entity_definitions` — no automated-only entity table.
- Add a **`batch_kind`** to pre-label batches: `initial` (1–5 documents, reviewed by the
  Tenant Admin) or `large` (the main batch, reviewed by an Annotator Admin). The trigger
  endpoint takes the kind; `initial` is capped at 5 documents.
- Add an explicit **batch state** field —
  `QUEUED → PROCESSING → COMPLETED | PARTIALLY_COMPLETED | FAILED` — derived from
  per-document outcomes, exposed on the batch status response, and never blocking the
  browser.
- **Initial-batch review feedback becomes guidance.** A Tenant Admin's corrections on the
  1–5 initial batch are persisted and injected into the prompt for the subsequent `large`
  batch, the same way `qa_examples` are.
- **Route the `large` batch to Annotator Admin review.** The sampled acceptance gate for a
  `large` batch requires the `annotator` role. When an Annotator Admin accepts a `large`
  batch: bulk-promote its spans (unchanged), stamp `prelabel_batches.training_eligible_at`,
  set `annotator_review_status = 'approved'`, and write a `public.notifications` row for
  `recipient_role = 'tenant_admin'` (kind `automated_batch_approved`). The Tenant Admin
  does **not** review the batch again.
- The Tenant Admin proceeds to training via the existing
  `POST /api/v1/training-retrain-requests` — no change to that path.
- **Portal**: fill in the Phase-2 stepper step pages
  (`/annotate/automated/schema | prelabel | retrain`) with the Q&A upload, the
  initial-vs-large batch distinction, the named batch states, and the "training eligible —
  request training" hand-off. The Annotator Admin's large-batch review reuses the existing
  acceptance-review UI, surfaced from their own navigation.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `seed-bootstrap`: schema proposal gains a Q&A-pair document input; batches gain a
  `batch_kind` and a named state lifecycle; initial-batch corrections are persisted as
  prompt guidance for the large batch; the acceptance gate for a `large` batch is
  restricted to the Annotator Admin and, on acceptance, marks the batch training-eligible
  and notifies the Tenant Admin.

## Impact

- **Backend**: `src/annotation_service/api/v1/seed_bootstrap.py` (batch trigger + status +
  acceptance endpoints), `src/annotation_service/services/schema_proposal.py` (Q&A-pair
  input, initial-batch guidance in the prompt), `src/annotation_service/services/batch_acceptance.py`
  (role gate + training-eligibility + notification), `src/annotation_service/api/v1/_rbac.py`
  (reuse). Reuses `src/annotation_service/services/notify.py` and the document text
  extraction path from `document_service`.
- **Database**: migration 041 already added `prelabel_batches.annotator_review_status` and
  `prelabel_batches.training_eligible_at`. This change adds `prelabel_batches.batch_kind`
  (`initial` | `large`), `prelabel_batches.state`
  (`queued|processing|completed|partially_completed|failed`), and a table to hold initial-batch
  review corrections used as guidance. Additive only.
- **Frontend**: `src/portal/src/app/(auth)/annotate/automated/{schema,prelabel,retrain}/` step
  pages and their components under `src/portal/src/components/seed-bootstrap/`; a Q&A upload
  control; the Annotator Admin's view of the large-batch acceptance queue.
- **No impact**: the per-document Suggest flow, model serving, extraction, chat/analytics;
  System Admin training approval and Tenant Admin model promotion are unchanged.

## Open Questions

- **Initial-batch size floor.** Spec says 1–5. Is 1 enough to be useful as validation, or
  should the floor be 3 (matching the schema proposal seed-set floor)? Assume 1–5,
  Tenant-Admin's choice.
- **Guidance format.** Are initial-batch corrections fed to the large-batch prompt as raw
  corrected spans, as synthesised QA pairs, or as free-text notes? Assume corrected spans
  plus an optional free-text note per document; design.md decides the prompt encoding.
- **Agreement threshold override for `large` batches.** `tenants.review_policy` exists but
  no agreement-rate threshold column does. Is the threshold tenant-configurable (letting an
  Annotator Admin accept a sub-threshold batch with a reason), or fixed? Assume fixed and
  conservative until real batch data exists, matching the original `seed-bootstrap`
  decision.
- **Q&A-pair storage.** Is the uploaded Q&A document retained (as a `documents` row with a
  new `purpose`, or its own table) or consumed and discarded after the proposal? Assume
  retained as a `documents` row with `purpose = 'qa_pair'` so a proposal is reproducible.
