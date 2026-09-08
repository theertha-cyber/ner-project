## Why

Change 1 (`llm-assisted-prelabeling`) added a backend capability to generate LLM-based span suggestions for a document, plus a `qa_examples` field on entity type definitions to supply few-shot context. Neither is reachable from the portal today: there is no UI to enter QA pairs, and no way for a tenant to ask for LLM pre-labeling instead of hand-annotating from scratch. This change makes both reachable. It is change 2 of a 6-change plan and is frontend-only — it introduces no new backend endpoints and no changes to training.

## What Changes

- Add an annotation-mode selector (Manual / Automated) to the document upload flow, shown only when `purpose === "training"` — documents uploaded for querying are never annotated, so the control is irrelevant there.
- **Manual** is the default and preserves today's behaviour exactly: documents upload, and annotators label them by hand. No LLM call is made.
- **Automated** additionally triggers LLM pre-labeling for each successfully uploaded document in the batch, by calling change 1's per-document endpoint `POST /api/v1/documents/{doc_id}/prelabel/llm` once per document, sequentially — mirroring the sequential-upload pattern already used by `DocumentUpload`.
- Report pre-label trigger outcomes per batch: how many documents were queued for pre-labeling, and which failed to queue, without blocking or reverting the uploads themselves. A failed pre-label trigger never fails the upload.
- Disable the Automated option, with an explanatory hint, when the tenant has no active entity types — change 1's endpoint rejects that case with 422, so offering the option would guarantee failure.
- Add a QA-pairs editor to the Define / Edit Entity Type slide-over, writing the `qa_examples` field added by change 1. Each row is a question and an answer; the field is optional and an entity type with no QA pairs remains valid.
- **BREAKING**: none. Manual mode is the default and is byte-for-byte today's flow. The upload endpoint, file validation, progress reporting, and document table are untouched.

## Capabilities

### New Capabilities

- `annotation-mode-selection`: the Manual/Automated selector in the training-document upload flow — its visibility rules, gating, default, per-document pre-label trigger orchestration, and batch outcome reporting.

### Modified Capabilities

- `entity-types-screen`: the Define / Edit Entity Type Slide-Over requirement gains an optional QA-pairs editor bound to the `qa_examples` field, alongside the existing Examples input.

## Impact

- **Frontend**: `src/portal/src/components/documents/DocumentUpload.tsx` (mode selector + post-upload trigger loop + outcome summary); `src/portal/src/components/entity-types/DefineEntityTypeSlideOver.tsx` (QA-pairs editor); a new hook for the pre-label trigger call alongside the existing `use-upload` hook.
- **Backend**: none. This change consumes change 1's endpoint and change 1's `qa_examples` field; it adds neither.
- **Dependency on in-flight work**: `DocumentUpload` batch behaviour comes from the `multi-document-upload` change, currently 38/44 tasks complete. This change assumes multi-file batch upload is landed; if it is not, the selector still functions for a one-file batch, but the batch outcome summary has nothing to attach to.
- **No impact**: document upload API contract, file validation, `DocumentTable`, `DocumentRow`, `StatusFilterTabs`, polling, the annotation workspace, or the suggested-span review/promote flow — LLM suggestions surface through the existing review UI unchanged.

## Open Questions

- **Per-document trigger vs. a batch endpoint**: this change fires N sequential requests for an N-document batch, keeping the change frontend-only as scoped. For the 100–200 document batches anticipated in change 4, a single batch-trigger endpoint would be sturdier (one job to track, one failure surface). Deferred deliberately — flagged here so change 4 can revisit rather than inherit this silently.
- **Does the tenant need to see which documents got LLM suggestions before opening them?** This change reports queue outcomes at upload time only; the document table is not extended with a pre-label status column. If reviewers need that visibility, it is a follow-up, not part of this change.
- **QA-pairs editor shape**: this change specifies a repeatable question/answer row editor. Whether tenants would rather paste/import many pairs at once (CSV/JSON) is unvalidated — worth confirming with a real tenant before building the row editor if bulk entry is the common case.
