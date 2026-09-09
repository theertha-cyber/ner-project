# Verification Plan

**Change:** automated-annotation-guided-workflow
**Generated:** 2026-09-09
**Status:** 🔴 NOT VERIFIED — implementation not started.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | seed-bootstrap | Q&A-Pair Proposal Input | Schema proposal accepts a Q&A-pair document | Given 3 processed seed docs, when a proposal is requested with a TXT Q&A pair, then 202 + `proposal_id` and the Q&A doc is retrievable as a proposal input | `tests/test_seed_bootstrap_proposal.py::test_proposal_accepts_qa_pair_document` | - [ ] |
| 2 | seed-bootstrap | Q&A-Pair Proposal Input | Q&A-pair text reaches the proposal prompt | Given a Q&A doc containing a known question string, when the proposal is generated, then the LLM prompt contains that text | `tests/test_seed_bootstrap_proposal.py::test_qa_pair_text_in_prompt` | - [ ] |
| 3 | seed-bootstrap | Q&A-Pair Proposal Input | An unsupported Q&A-pair file type is rejected | Given a proposal request, when a `.csv` is uploaded as the Q&A pair, then 422 naming the supported types | `tests/test_seed_bootstrap_proposal.py::test_qa_pair_unsupported_type_422` | - [ ] |
| 4 | seed-bootstrap | Q&A-Pair Proposal Input | Uploading a Q&A pair creates no entity types | Given a tenant with exactly 2 active types, when a proposal is requested with a Q&A doc, then still exactly 2 | `tests/test_seed_bootstrap_proposal.py::test_qa_pair_creates_no_entity_types` | - [ ] |
| 5 | seed-bootstrap | Batch Kind | Initial batch is capped at five documents | Given 8 docs submitted as `initial`, when the trigger is called, then 422 stating the 5-doc cap | `tests/test_seed_bootstrap_batch.py::test_initial_batch_capped_at_five` | - [ ] |
| 6 | seed-bootstrap | Batch Kind | Large batch has no document cap | Given 120 docs submitted as `large`, when triggered, then 202 and `batch_kind = large` recorded | `tests/test_seed_bootstrap_batch.py::test_large_batch_no_cap` | - [ ] |
| 7 | seed-bootstrap | Batch Kind | Batch kind is reported on batch status | Given an `initial` and a `large` batch, when each status is read, then each reports its `batch_kind` | `tests/test_seed_bootstrap_batch.py::test_batch_status_reports_kind` | - [ ] |
| 8 | seed-bootstrap | Named Batch State | A fully successful batch reports completed | Given a 10-doc batch where all succeed, when finished, then `state = completed` | `tests/test_seed_bootstrap_batch.py::test_state_completed` | - [ ] |
| 9 | seed-bootstrap | Named Batch State | A batch with mixed outcomes reports partially_completed | Given 9 succeed / 1 fails, when finished, then `state = partially_completed` | `tests/test_seed_bootstrap_batch.py::test_state_partially_completed` | - [ ] |
| 10 | seed-bootstrap | Named Batch State | A batch where every document fails reports failed | Given all 5 docs fail, when finished, then `state = failed` and no spans exist | `tests/test_seed_bootstrap_batch.py::test_state_failed_no_spans` | - [ ] |
| 11 | seed-bootstrap | Named Batch State | Batch status is available while processing | Given a started-but-unfinished `large` batch, when status is read, then it returns promptly with `state = processing` + a progress count | `tests/test_seed_bootstrap_batch.py::test_state_processing_nonblocking` | - [ ] |
| 12 | seed-bootstrap | Initial-Batch Review Guidance | Initial-batch corrections are persisted | Given a completed `initial` batch, when a Tenant Admin corrects a span type and adds a note, then both are stored against the batch | `tests/test_seed_bootstrap_acceptance.py::test_initial_guidance_persisted` | - [ ] |
| 13 | seed-bootstrap | Initial-Batch Review Guidance | Guidance from the initial batch reaches the large-batch prompt | Given a reviewed `initial` batch with a guidance note, when a `large` batch is triggered, then the prompt contains that note | `tests/test_seed_bootstrap_batch.py::test_large_batch_prompt_includes_guidance` | - [ ] |
| 14 | seed-bootstrap | Initial-Batch Review Guidance | No guidance without a reviewed initial batch | Given a tenant with no `initial` batch, when a `large` batch is triggered, then it runs with the QA-pairs-only prompt | `tests/test_seed_bootstrap_batch.py::test_large_batch_without_guidance` | - [ ] |
| 15 | seed-bootstrap | Sampled Acceptance Gate | Sample is drawn randomly and recorded | (unchanged) drawn sample is not the first N and drawn ids are persisted | `tests/test_seed_bootstrap_acceptance.py::test_sample_is_random_and_recorded` | - [ ] |
| 16 | seed-bootstrap | Sampled Acceptance Gate | Batch meeting the threshold can be bulk-accepted | (unchanged) all spans promoted + record stores size/rate/reviewer/timestamp | `tests/test_seed_bootstrap_acceptance.py::test_batch_above_threshold_bulk_accepts` | - [ ] |
| 17 | seed-bootstrap | Sampled Acceptance Gate | Batch below the threshold cannot be bulk-accepted | (unchanged) rejected, zero spans promoted, rate recorded | `tests/test_seed_bootstrap_acceptance.py::test_batch_below_threshold_rejected` | - [ ] |
| 18 | seed-bootstrap | Sampled Acceptance Gate | Bulk acceptance is not permitted without a completed sample review | (unchanged) rejected with incomplete-review error | `tests/test_seed_bootstrap_acceptance.py::test_acceptance_requires_completed_sample_review` | - [ ] |
| 19 | seed-bootstrap | Sampled Acceptance Gate | Bulk-promoted spans record their acceptance route | (unchanged) distinguishable from individually promoted spans | `tests/test_seed_bootstrap_acceptance.py::test_bulk_promoted_spans_record_route` | - [ ] |
| 20 | seed-bootstrap | Sampled Acceptance Gate | A tenant admin cannot accept a large batch | Given a completed `large` batch with a passing review, when a `tenant_admin` accepts, then 403 | `tests/test_seed_bootstrap_acceptance.py::test_tenant_admin_cannot_accept_large_batch` | - [ ] |
| 21 | seed-bootstrap | Sampled Acceptance Gate | Annotator acceptance of a large batch makes it training-eligible and notifies the tenant admin | Given a passing `large` batch, when an `annotator` accepts, then spans promoted + `training_eligible_at` set + `annotator_review_status='approved'` + an `automated_batch_approved` notification for `recipient_role=tenant_admin` | `tests/test_seed_bootstrap_acceptance.py::test_annotator_accept_large_batch_eligible_and_notifies` | - [ ] |
| 22 | seed-bootstrap | Sampled Acceptance Gate | Accepting an initial batch neither notifies nor marks training-eligible | Given a passing `initial` batch reviewed by a `tenant_admin`, when accepted, then spans promoted, `training_eligible_at` null, no notification | `tests/test_seed_bootstrap_acceptance.py::test_initial_batch_accept_no_side_effects` | - [ ] |
| 23 | seed-bootstrap | Sampled Acceptance Gate (idempotency) | Re-accepting an approved large batch is a no-op | Given an already-approved `large` batch, when `accept` is called again, then no second span promotion and no second notification | `tests/test_seed_bootstrap_acceptance.py::test_large_batch_accept_is_idempotent` | - [ ] |
| 24 | seed-bootstrap | Batch Pre-labeling | Enqueue a batch pre-labeling job | (unchanged) 202 + single `batch_id` for 120 docs | `tests/test_seed_bootstrap_batch.py::test_enqueue_batch_returns_batch_id` | - [ ] |
| 25 | seed-bootstrap | Batch Pre-labeling | One document failing does not abort the batch | (unchanged) 9 succeeded / 1 failed, spans for the 9 | `tests/test_seed_bootstrap_batch.py::test_single_document_failure_does_not_abort_batch` | - [ ] |
| 26 | seed-bootstrap | Batch Pre-labeling | Batch pre-labeling honours the entity type constraint | (unchanged) every span's type configured, no type created | `tests/test_seed_bootstrap_batch.py::test_batch_honours_entity_type_constraint` | - [ ] |
| 27 | seed-bootstrap | Batch Pre-labeling | Batch pre-labeling grounds quotes the same way as single-document | (unchanged) ungrounded quote dropped and counted | `tests/test_seed_bootstrap_batch.py::test_batch_grounding_matches_single_document` | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change MUST
> appear as a row. Rows 15–19 and 24–27 restate scenarios carried unchanged from the base
> `seed-bootstrap` spec because the MODIFIED requirement text re-includes them.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Q&A-pair input (Decision 1) | Implementer adds a bespoke `qa_pair_documents` table or an in-memory upload that bypasses the documents pipeline's size/type/extraction handling | Confirm the Q&A pair is a `documents` row with `purpose = 'qa_pair'` and is parsed by the existing extraction path. Grep for any new table holding uploaded Q&A files. |
| 2 | `batch_kind` reviewer gate (Decision 2) | Implementer gates the acceptance endpoint on document count instead of `batch_kind`, or lets a `tenant_admin` accept a `large` batch | Read the acceptance endpoint: the role check must branch on `batch_kind`. Execute Scenarios 20, 21, 22. |
| 3 | `state` derivation (Decision 3) | Implementer introduces a hand-maintained state machine updated at each step, drifting from the per-document outcomes | Confirm `state` is computed from outcome rows, with only the terminal value cached. Execute Scenarios 8–11. |
| 4 | acceptance side effects (Decision 6, ADR-011) | Implementer writes the notification unconditionally, or in a separate transaction, so a retried accept double-notifies or double-promotes | Confirm span promotion + eligibility UPDATE + notification are one transaction and the notification is guarded on the conditional UPDATE's row count. Execute Scenario 23. |
| 5 | guidance prompt injection (Decision 5) | Implementer feeds initial-batch corrections into the *training set* directly, or writes synthetic QA pairs onto canonical entity types | Confirm guidance lands only in the `large`-batch prompt text via `prelabel_batch_guidance`; no write to `entity_definitions` or the confirmed-span set. Execute Scenarios 12–14. |
| 6 | `purpose = 'qa_pair'` filter leakage | Implementer adds the enum value but misses a `WHERE purpose = 'training'` filter, letting Q&A docs enter the seed picker or training export | Grep every `purpose` filter in `annotation_service` and `training_service`; a Q&A doc must appear in none of them. |

---

## 3. Pattern & ADR Compliance

| ADR | Constraint on This Change | Verification Step |
|-----|--------------------------|-------------------|
| ADR-001 tenant-data-isolation | New tables/columns in the tenant schema, resolved via the existing `_schema(tenant_id)` pattern; a batch task never iterates tenants | Trace schema resolution in the new endpoints and migration `042`. |
| ADR-006 training-infrastructure | Batch pre-labeling stays on the non-GPU LLM queue | Confirm the batch task registration is unchanged from `seed-bootstrap`; no GPU selector. |
| ADR-009 system-admin-sets-hyperparameters | `training_eligible_at` is a data flag, not a training trigger; System Admin approval untouched | Confirm nothing in the accept path enqueues or approves a training job. |
| ADR-011 annotation-idempotency-enforcement | accept→eligible→notify fires exactly once | Execute Scenario 23; read the transaction boundary. |
| ADR-012 annotation-fix-deployment-topology | New endpoints in `annotation_service`; notification reads stay in `gateway` | Confirm no new gateway route and no new annotation-service→gateway call. |

---

## 4. Evidence Requirements

Do not archive while any item below remains unchecked.

### Functional Evidence
- [ ] One test-output item per row 1–27 in Section 1, showing the THEN observed in a real run (PostgreSQL, LLM provider stubbed).

### Structural Evidence
- [ ] Code review — implementation matches design.md decisions with no undocumented deviation
- [ ] `git diff` shows only additive schema changes (migration `042`), no destructive ALTER
- [ ] The batch task and grounding path are the `seed-bootstrap` implementations, not reimplemented
- [ ] `notify.py` is reused for the `automated_batch_approved` notification — no second notification writer
- [ ] No AI-invented endpoints, fields, or behaviours vs the spec files

### Edge Case Evidence
- [ ] Risk 1 — Q&A pair is a `documents` row, extraction reused (no bespoke store)
- [ ] Risk 2 — acceptance role gate branches on `batch_kind`
- [ ] Risk 3 — `state` computed from outcomes, only terminal value cached
- [ ] Risk 4 — accept side effects are one idempotent transaction
- [ ] Risk 5 — guidance reaches only the prompt, not the training set or entity config
- [ ] Risk 6 — every `purpose = 'training'` filter audited; Q&A docs excluded everywhere

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: signed by a human reviewer before archive.**

**Change slug:** automated-annotation-guided-workflow
**Spec files reviewed:** specs/seed-bootstrap/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [ ] |
| All ADRs in Section 3 verified compliant | - [ ] |
| Spec Alignment table complete (no missing scenarios) | - [ ] |
| Evidence Log populated with real evidence | - [ ] |
| All functional evidence items in Section 4 checked | - [ ] |
| All structural evidence items in Section 4 checked | - [ ] |
| All edge case evidence items in Section 4 checked | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause in specs has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and all mitigations confirmed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**

- Depends on `seed-bootstrap` (landed) and the Tenant Admin nav restructure Phases 2–3
  (landed as commits `3747e25`, `f5febdf`) — specifically `public.notifications`,
  `services/notify.py`, and migration `041`'s `prelabel_batches` columns.
- The agreement threshold remains an unresolved measurement question inherited from
  `seed-bootstrap`. This change does not add an override; a reviewer must confirm the
  threshold in force was not lowered to make a batch pass.
- The PII / data-residency question inherited from `llm-assisted-prelabeling` applies — a
  `large` batch sends 50+ documents to an external LLM.

---

## 7. Agent Verification Record

### Slice 1 — batch_kind, named state, reviewer role gates, acceptance side effects (executed)

Implemented: migration `042`; `batch_kind` + `state` on `prelabel_batches` and the
`prelabel_batch_guidance` table; `_derive_batch_state`; worker writes the terminal `state`;
`get_prelabel_batch` reconciles on read; `_gate_acceptance_reviewer` (initial → tenant_admin,
large → annotator) on start/get/submit/accept plus gates on `GET /prelabel-batches/{id}` and
`GET /schema-proposals/{id}` and `require_tenant_admin` on the proposal request + candidate
mutations + batch trigger; `accept_batch` for a `large` batch does the one-transaction
promote → conditional eligibility UPDATE → guarded `automated_batch_approved` notification.

Run in the `ner-project-annotation_service-1` container (pytest installed ad hoc; repo
`docker cp`-ed in) against `postgres-test` / `ner_test`:

```
tests/test_automated_workflow_guided.py    11 passed   (spec rows 5-11, 20-23)
tests/test_seed_bootstrap_acceptance.py    22 passed   (carried-over rows 15-19 + others)
tests/test_seed_bootstrap_batch.py         }
tests/test_seed_bootstrap_proposal.py      }  all green — no regression from the RBAC gates
tests/test_seed_bootstrap_readiness.py     }
tests/test_annotation_workspace.py + test_llm_prelabel_api.py   47 passed (worker.py change)
```

`python -m py_compile` clean on every changed file. Migration `042` not yet applied to a
long-lived DB — the test DB builds its schema from `tests/seed_bootstrap_support.py`, which
was updated to match.

### Not yet implemented

- Q&A-pair proposal input (tasks 3.x, spec rows 1-4).
- Initial-batch review guidance persistence + prompt injection (tasks 5.x, spec rows 12-14).
- `purpose = 'qa_pair'` filter audit (task 7).
- Portal (tasks 8.x).
- Migration `042` guard test (task 2.3); explicit `partially_completed` status test (task 9.1).

---

## 8. Outstanding Items

- Tasks 3.x, 5.x, 7, 8.x, 2.3 (see §7).
- Apply migration `042` in the deployment DB.
- Fill §1 status column, §4/§5 evidence, get §6 sign-off.
