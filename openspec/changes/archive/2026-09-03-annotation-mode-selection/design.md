## Context

`DocumentUpload` (`src/portal/src/components/documents/DocumentUpload.tsx`) renders the `/documents` upload zone. It takes a `purpose` prop (`"query" | "training"`) that is fixed by the caller from the signed-in role and is deliberately not user-selectable; line 173 already branches its explanatory copy on that value. Following the `multi-document-upload` change (38/44 tasks complete), it accepts multiple files and uploads them sequentially in a loop (`await upload(files[i], purpose)`), tracking per-file status in a `batch` array and reporting a succeeded/failed summary when the batch finishes.

Change 1 added `POST /api/v1/documents/{doc_id}/prelabel/llm`, which returns 202 with a `job_id`, rejects documents with no extracted text (422), and rejects tenants with no active entity types (422). It also added an optional `qa_examples` field to entity type definitions, which the portal currently has no way to populate — `DefineEntityTypeSlideOver` exposes `description`, `examples`, and base label mapping only.

This change wires both into the portal. It writes no backend code.

## Goals / Non-Goals

**Goals:**
- Let a tenant choose, per training-document batch, whether to hand-annotate or have the LLM pre-label.
- Let a tenant enter QA pairs on an entity type so change 1's prompt has few-shot context.
- Keep Manual mode indistinguishable from today's behaviour.
- Never let a pre-labeling failure damage or reverse a successful upload.

**Non-Goals:**
- No new backend endpoints, including a batch pre-label trigger (see Decision 3).
- No changes to file validation, upload progress, the document table, or polling.
- No changes to the annotation workspace or the suggested-span review/promote UI — LLM suggestions appear there through the existing `?type=suggested` listing with no frontend change required.
- No pre-label status column on the document table (proposal Open Questions).
- No bulk import of QA pairs (proposal Open Questions).
- Nothing from changes 3–6: no training fixes, no seed bootstrap, no confidence routing, no retraining trigger.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001-tenant-data-isolation | Tenant isolation via separate PostgreSQL schemas, enforced at the API gateway via JWT `tenant_id` and an injected `X-Tenant-ID` header | This change makes no direct database access; it must issue every call through the existing authenticated fetch layer (`src/portal/src/lib/auth-fetch.ts`) so tenant context is attached the same way as every other portal request. It must never accept a tenant identifier as UI state. |

> ADR-002, ADR-003 and ADR-008 govern the tenant's own trained/served model; ADR-006, ADR-009 and ADR-010 govern training infrastructure, hyperparameters and dataset thresholds. None constrain a frontend-only change that neither trains nor serves a model. ADR-004 (OpenSpec governance) and ADR-005 (agent boundaries) are process ADRs and are honoured by producing this artifact set before any code.

## Decisions

### Decision 1: Gate the selector on `purpose === "training"`

**Choice:** Render the Manual/Automated selector only when `purpose === "training"`. Never render it for `purpose === "query"`.

**Rationale:** Query documents are ingested for chat retrieval and are never annotated, so a pre-labeling choice is meaningless there and would be a confusing dead control. `DocumentUpload` already branches its copy on this exact condition, so the gate reuses an established distinction rather than inventing one.

**Alternatives considered:**
- Always show the selector, disabled for query uploads — rejected: a permanently-disabled control on the most common upload path is noise, not information.
- Make `purpose` user-selectable and derive the annotation mode from it — rejected: `purpose` is deliberately role-derived per the existing component contract; changing that is out of scope and would alter behaviour for query uploads.

### Decision 2: Manual is the default, and is a strict no-op

**Choice:** The selector defaults to Manual on every batch. Manual performs zero additional API calls — the code path is identical to today's.

**Rationale:** Automated spends money (LLM calls) and sends tenant documents to an external provider. Defaulting to the cheaper, more conservative option means a tenant must actively opt in per batch, and it guarantees this change cannot alter existing behaviour for anyone who ignores the new control. It also means the unresolved PII question from change 1 is never triggered by accident.

**Alternatives considered:**
- Remember the last-used mode per tenant — rejected for v1: a sticky setting that silently sends future batches to an external LLM is exactly the surprise the default is meant to prevent. Can be revisited once the data-residency policy is settled.
- Default to Automated when QA pairs exist — rejected for the same reason; configuring QA pairs is not consent to send every future batch off-platform.

### Decision 3: Frontend loops change 1's per-document endpoint; no batch endpoint

**Choice:** For an N-document batch in Automated mode, issue N sequential `POST /api/v1/documents/{doc_id}/prelabel/llm` calls after uploads complete, reusing the sequential pattern `DocumentUpload` already uses for uploads.

**Rationale:** Keeps this change frontend-only as scoped in the 6-change plan, and mirrors an in-file pattern rather than introducing a second concurrency model. Change 1 deliberately specified a per-document endpoint; consuming it as-specified avoids re-opening a committed spec.

**Alternatives considered:**
- Add a batch-trigger endpoint — rejected *for this change* (it is backend work in a frontend-only change), but explicitly flagged in proposal.md Open Questions as the better shape for change 4's 100–200 document batches. This is a known, deliberate deferral, not an oversight.
- Fire the N requests in parallel — rejected: no backpressure, and a browser firing 200 concurrent POSTs is a good way to hit rate limits and produce partial, hard-to-report failure.

### Decision 4: Pre-label triggers run after uploads and cannot fail an upload

**Choice:** Trigger pre-labeling only for documents whose upload succeeded, only after the upload batch finishes. A failed trigger is recorded and reported but never marks the upload as failed, never retries automatically, and never blocks the remaining triggers.

**Rationale:** Upload and pre-labeling are independent concerns with different failure modes and different costs to redo. A document that uploaded fine but failed to queue is fully recoverable — the annotator can still open it and use the workspace's existing Suggest action. Coupling them would mean an LLM outage makes document ingestion look broken.

**Alternatives considered:**
- Trigger pre-labeling per file as each upload completes — rejected: interleaves two progress streams into one confusing indicator, and makes "which phase failed" harder to report.
- Roll back or flag uploads whose trigger failed — rejected: destroys good work over a recoverable, unrelated failure.

### Decision 5: Disable Automated when the tenant has no active entity types

**Choice:** When the tenant has zero active entity types, render the Automated option disabled with a short hint pointing at entity-type configuration. Automated remains available when entity types exist but have no QA pairs.

**Rationale:** Change 1's endpoint returns 422 for a tenant with no active entity types, so offering Automated there guarantees N failures. But change 1 also explicitly specifies that entity types *without* QA pairs are still extracted (using `description` and `examples` as context) — so QA pairs must not be treated as a precondition, only as an enhancement. Gating on QA pairs would contradict a committed spec.

**Alternatives considered:**
- Require at least one QA pair before enabling Automated — rejected: directly contradicts change 1's Extraction Scope requirement and would deny tenants a working feature.
- Let the user pick Automated and surface the 422s afterwards — rejected: a preventable, guaranteed failure should be prevented at the control, not reported after the fact.

## Risks / Trade-offs

- [A large Automated batch issues many sequential requests, making the post-upload phase visibly slow] → Report progress for the trigger phase separately from upload progress ("queueing N of M"), so the user sees deliberate work rather than a hang. The underlying fix is the batch endpoint deferred to change 4.
- [Tenant selects Automated without understanding documents leave the platform for an external LLM] → Out of scope to solve in UI copy alone; depends on the unresolved data-residency policy from change 1 task 1.1. Recorded here so that whatever consent surface that decision produces is attached to this control rather than bolted on later.
- [QA-pairs row editor may be the wrong input shape if tenants think in bulk imports] → Flagged in proposal Open Questions; the underlying field is a JSON array, so a bulk-import affordance can be added later without a data model change or a migration.
- [This change depends on `multi-document-upload` (38/44) landing for its batch semantics] → The selector and trigger logic degrade correctly to a single-document batch, so this change is not hard-blocked; only the batch outcome summary assumes multi-file batches.

## Migration Plan

1. Land the QA-pairs editor in the entity-type slide-over first — it is independent of the upload flow and lets tenants populate `qa_examples` before any pre-labeling is triggered.
2. Land the mode selector defaulting to Manual. At this point Automated is selectable but the tenant is opting in explicitly per batch, and Manual is unchanged for everyone else.
3. No data migration, no feature flag required: the change is inert for any tenant that never selects Automated, and inert for all query-purpose uploads by construction.
4. Rollback: revert the frontend change. No backend state is created by this change beyond the pre-label jobs change 1 already owns, and `qa_examples` values already written remain valid and harmless.

## Open Questions

- What consent or warning copy, if any, must accompany the Automated option? Depends entirely on the data-residency decision gated in change 1 task 1.1 — this design leaves a deliberate slot for it rather than inventing wording.
- Should the trigger phase be resumable if the user navigates away mid-batch? Currently it is not; the remaining documents simply go un-pre-labeled and can be handled per-document from the workspace. Acceptable for v1, worth revisiting alongside the batch endpoint in change 4.
- No in-force ADR covers "sending tenant data to an external processor" as a category. If the data-residency decision produces a durable rule, it likely warrants its own ADR — noted here; ADR authorship is a separate step.
