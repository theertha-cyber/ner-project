## Why

`automated-batch-stage-visibility` made the large-batch section always visible, but its
upload picker still disappeared forever once a large batch existed — replaced permanently by
that batch's status card. For a tenant whose large batch had already run once (from earlier
testing, in this case), the screen showed only a "completed, 6/6 documents" status with no way
to upload anything new, which read as broken: "there should be an option to upload documents"
and "why is it shown 6 documents — I haven't done anything." The large batch is not a one-time
setup step like the initial validation batch; new documents arrive over time and the tenant
admin needs to be able to pre-label another batch of them whenever they want, not just once.

## What Changes

- The large-batch document picker is now always shown once the stage is unlocked, regardless
  of whether a previous large batch exists or what state it's in — starting another large
  batch is a repeatable action, not a one-time gate.
- The most recently created large batch's status is shown as its own labeled section ("Most
  recent large batch") below the picker, so it reads as history/status rather than as
  something blocking a new upload.
- Starting a new large batch is disabled (with an explanatory message) only while the most
  recent one is still queued or processing, to avoid a confusing double-submission; it is not
  disabled once that batch is completed.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `seed-bootstrap`: the requirement added by `automated-batch-stage-visibility`
  ("Batch Pre-labeling Screen Shows Both Stages Persistently") is modified — the large-batch
  section's picker is no longer described as appearing only "once" per tenant; it is
  repeatable.

## Impact

- **Frontend only**: `src/portal/src/components/seed-bootstrap/BatchAcceptancePage.tsx`.
- **Backend: none.** `create_prelabel_batch` already allowed multiple `large` batches per
  tenant (nothing in `annotation-workflow-review-simplification` limited it to one) — this was
  purely a frontend display gap hiding an already-supported backend capability.
- **No impact**: the sequencing gate (an approved `initial` batch required first) and
  automatic promotion are unchanged; they apply identically to every large batch a tenant
  creates, not just the first.

## Open Questions

None.
