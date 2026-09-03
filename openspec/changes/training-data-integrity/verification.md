# Verification Plan

**Change:** training-data-integrity
**Generated:** 2026-09-03
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | annotation-workspace | Annotation Export | Export annotation dataset | Given 2 annotated and 1 unannotated document all within the window budget, when the export is fetched, then status is 200, the body is JSON lines each with `tokens` and `tags`, and there are 3 lines | `tests/test_annotation_workspace.py` (existing export regression test) | - [ ] |
| 2 | annotation-workspace | Annotation Export | A document exceeding the window budget produces multiple records | Given 1 annotated document with more than twice the window budget in tokens, when the export is fetched, then more than one line is emitted for it and every token appears in at least one line | `tests/test_annotation_export_windowing.py::test_long_document_produces_multiple_records` | - [ ] |
| 3 | annotation-workspace | Annotation Export | Consecutive windows overlap | Given a document producing two consecutive windows, when the export is generated, then the trailing tokens of window 1 also appear as the leading tokens of window 2 | `tests/test_annotation_export_windowing.py::test_consecutive_windows_overlap` | - [ ] |
| 4 | annotation-workspace | Annotation Export | An entity crossing a window boundary is complete in at least one window | Given a two-token entity whose first token sits at the end of a window's non-overlapping region, when the export is generated, then at least one record contains both tokens tagged `B-` then `I-`, not `B-` alone | `tests/test_annotation_export_windowing.py::test_boundary_entity_complete_in_one_window` | - [ ] |
| 5 | annotation-workspace | Annotation Export | Tags align correctly across a newline separator | Given text `"John Doe\nworks at Acme Corp"` and an `organization` span on `"Acme Corp"`, when the export is generated, then `"Acme"`/`"Corp"` are `B-organization`/`I-organization` and `"works"`/`"at"` are `O` | `tests/test_annotation_export_offsets.py::test_tags_align_across_newline` | - [ ] |
| 6 | annotation-workspace | Annotation Export | Tags align correctly across repeated spaces and tabs | Given text `"John  Doe\tworks at Acme Corp"` and an `organization` span on `"Acme Corp"`, when the export is generated, then `"Acme"`/`"Corp"` carry the organization tags and no other token does | `tests/test_annotation_export_offsets.py::test_tags_align_across_tabs_and_double_spaces` | - [ ] |
| 7 | annotation-workspace | Annotation Export | Export ignores a stale stored bio_tags value | Given a span whose stored `bio_tags` disagrees with its `char_start`/`char_end`, when the export is generated, then emitted tags reflect the offsets and not the stored value | `tests/test_annotation_export_offsets.py::test_stored_bio_tags_ignored` | - [ ] |
| 8 | annotation-workspace | Annotation Export | Export with entity type filter | Given spans of types PER and ORG, when the export is fetched with `entity_types=PER`, then status is 200 and only PER tags appear; ORG spans encode as O | `tests/test_annotation_workspace.py` (existing entity-type-filter regression test) | - [ ] |
| 9 | annotation-workspace | Annotation Export | Export for specific documents only | Given 5 documents of which 2 are annotated, when the export is fetched with `document_ids=doc-001,doc-002`, then status is 200 and only those documents appear | `tests/test_annotation_workspace.py` (existing document-filter regression test) | - [ ] |
| 10 | annotation-workspace | Annotation Export | Imported annotation rows are passed through unwindowed | Given 3 `imported_annotations` rows, one exceeding the window budget, when the export is generated, then exactly 3 lines are emitted for them and the oversized row is unchanged | `tests/test_annotation_export_windowing.py::test_imported_rows_not_windowed` | - [ ] |
| 11 | training-worker | Tokenize dataset | Tokens are aligned to subwords | Given tokens `["John","smith"]` with tags `["B-PER","I-PER"]`, when tokenised at `max_seq_length=128`, then each token maps to its subwords with the first subword carrying the tag and the rest -100 | `tests/test_training_worker.py` (existing subword alignment test) | - [ ] |
| 12 | training-worker | Tokenize dataset | A window-sized record is not truncated at the default sequence length | Given a record with the maximum source tokens the window budget permits, when tokenised at the default `max_seq_length`, then no token is truncated and every source token has at least one subword label | `tests/test_training_worker.py::test_window_sized_record_not_truncated` | - [ ] |
| 13 | training-worker | Tokenize dataset | max_seq_length remains overridable per job | Given approved hyperparameters setting a non-default `max_seq_length`, when the worker tokenises, then the supplied value is used rather than the default | `tests/test_training_worker.py::test_max_seq_length_override_respected` | - [ ] |
| 14 | training-worker | Tokenize dataset | Truncation is recorded when it occurs | Given a record whose subword expansion exceeds `max_seq_length`, when the worker tokenises, then truncation is recorded with an affected-record count and the job does not fail solely because of it | `tests/test_training_worker.py::test_truncation_is_recorded` | - [ ] |
| 15 | training-worker | Load annotated dataset | Dataset loads successfully | Given a tenant with annotated documents and a running annotation service, when the worker calls the export endpoint, then it receives JSONL with `tokens`/`tags` and constructs a `datasets.Dataset` | `tests/test_training_worker.py` (existing dataset load test) | - [ ] |
| 16 | training-worker | Load annotated dataset | Export returns no data | Given a tenant with no annotated documents, when the worker calls the export endpoint, then the job fails with a clear error and status "failed" | `tests/test_training_worker.py` (existing empty-dataset regression test) | - [ ] |
| 17 | training-worker | Load annotated dataset | Dataset too small to form an evaluation split | Given an export yielding so few rows that the split produces zero evaluation rows, when the split is prepared, then the job fails with an error naming the row count, status is "failed", and no training or metric occurs | `tests/test_training_worker.py::test_dataset_too_small_to_split_fails` | - [ ] |
| 18 | training-worker | Load annotated dataset | Dataset large enough to split proceeds | Given an export yielding at least one evaluation row under the configured split, when the split is prepared, then training proceeds with no additional minimum-size judgement applied | `tests/test_training_worker.py::test_sufficient_dataset_proceeds_without_extra_gate` | - [ ] |
| 19 | training-worker | Load annotated dataset | Annotation service URL defaults to the correct internal port | Given `ANNOTATION_SERVICE_URL` unset, when the worker calls the export endpoint, then the request goes to `http://annotation_service:8000/api/v1/annotation-export` | `tests/test_training_worker.py` (existing URL default regression test) | - [ ] |
| 20 | training-worker | Load annotated dataset | Annotation service URL is overridable via environment variable | Given `ANNOTATION_SERVICE_URL` set to `http://custom-host:9999`, when the worker calls the export endpoint, then the request goes to that host | `tests/test_training_worker.py` (existing URL override regression test) | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

For each area of complexity in this change, identify what an AI agent might get wrong
and how a human reviewer can detect and correct it.

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Offset derivation (design.md Decision 1) | Implementer patches the existing advance to skip whitespace (`while text[i].isspace()`) while leaving tokenisation and offset derivation as two separate operations — fixing the observed newline case but preserving the structural disagreement that caused it | Confirm tokenisation and offset derivation are one pass producing `(token, start, end)` together. Two functions that each independently decide what a separator is means the defect can recur. Scenario 6 (tabs and double spaces) must pass, not just Scenario 5. |
| 2 | Stored `bio_tags` consumption (design.md Decision 2) | Implementer keeps the `stored = span["bio_tags"]` branch as a fallback "when present", so most real spans still take the corrupt path and the fix appears to work only in tests using spans with no stored tags | Grep `export.py` for any read of `bio_tags`. There must be none. Scenario 7 deliberately supplies a stored value that disagrees with the offsets and must show the offsets winning. |
| 3 | Window overlap correctness (design.md Decision 3) | Implementer windows without overlap, or applies overlap only to tokens and not to the tag array, so boundary entities are shredded into partial spans — manufacturing exactly the partial-label problem this change exists to remove | Verify tokens and tags are windowed together from the same index range. Scenario 4 must show a boundary entity tagged `B-` then `I-` in one record, not `B-` alone in two. |
| 4 | Imported annotations regression (design.md Non-Goals) | Implementer routes `imported_annotations` rows through the new windowing path, re-tokenising or splitting rows that are already correctly shaped and pre-tagged | Confirm the imported-rows branch is untouched and emits rows verbatim. Scenario 10 includes an oversized imported row specifically to catch this. |
| 5 | Competing dataset threshold (design.md Decision 4, ADR-010) | Implementer adds a minimum row count (e.g. "at least 50 rows") as a sufficiency check, creating a second definition of "enough data" that conflicts with ADR-010's per-entity-type readiness mechanism | Read the guard: it must test only whether the split yields ≥1 evaluation row. Any constant expressing a data-quality opinion is a violation. Scenario 18 asserts no extra gate is applied. |
| 6 | Hardcoded sequence length (ADR-006 / ADR-009) | Implementer raises `max_seq_length` by hardcoding it in the worker rather than changing the default, removing the ability for a System Admin to set it at approval time | Confirm the value still reads from the job's hyperparameters with the new value as a fallback default. Scenario 13 must pass with a non-default override. |
| 7 | Window budget and sequence length sized independently | Implementer picks a window token budget and a `max_seq_length` that are not consistent — a full window's subword expansion still overflows, so truncation continues silently despite the change | Confirm the two values are derived from one another (with a documented safety factor for subword expansion), not chosen separately. Scenario 12 exercises a maximum-size window against the default sequence length. |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

List every currently-in-force ADR that constrains this change (as identified in design.md).

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-010-per-entity-type-dataset-threshold | Dataset readiness measured per entity type at 200 per type, enforced via `NER_MIN_ENTITIES_PER_TYPE` (default 0, inert) | This change must not introduce a competing notion of "enough data"; its guard must be mechanically limited to whether a train/evaluation split can be formed | Read the guard implementation and confirm it tests only evaluation-partition size. Grep the diff for any new numeric data-sufficiency constant. Confirm `NER_MIN_ENTITIES_PER_TYPE` and `NER_MIN_TRAINING_ENTITIES` semantics and defaults are unchanged. |
| ADR-009-system-admin-sets-training-hyperparameters | A System Admin sets training hyperparameters at approval time, not at submission | The `max_seq_length` default may change, but the approval-time override path must remain intact | Confirm the worker still reads `max_seq_length` from the job's hyperparameters, using the new value only as a fallback. Execute Scenario 13 with an explicit override. |
| ADR-006-training-infrastructure | Async Celery GPU workers consuming from a queue; hyperparameters accompany the job (hyperparameter clause superseded by ADR-009) | Queue topology, worker lifecycle, and checkpointing behaviour must be unaffected — this change touches dataset preparation only | Confirm `git diff` shows no changes to Celery queue configuration, task registration, or checkpointing logic in `training_service`. |
| ADR-001-tenant-data-isolation | Tenant isolation via separate PostgreSQL schemas | Export must continue resolving the tenant schema per request exactly as before | Confirm the tenant schema resolution in `export_annotations` is unchanged in the diff; windowing must operate on already-scoped query results. |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

*(Minimum one item per row in Section 1 — test output, screenshot, log excerpt, or API
trace proving the THEN was observed in a real execution.)*

- [ ] Scenario 1 (Baseline export): existing regression test output, unchanged
- [ ] Scenario 2 (Long document windows): test output asserting >1 line and full token coverage
- [ ] Scenario 3 (Windows overlap): test output asserting the shared token region between consecutive windows
- [ ] Scenario 4 (Boundary entity intact): test output asserting `B-`/`I-` present together in one record
- [ ] Scenario 5 (Newline alignment): test output asserting correct tags for the verified `"John Doe\nworks at Acme Corp"` case
- [ ] Scenario 6 (Tab and double-space alignment): test output asserting correct tags and no stray organization tag
- [ ] Scenario 7 (Stored bio_tags ignored): test output asserting offset-derived tags win over a deliberately inconsistent stored value
- [ ] Scenario 8 (Entity type filter): existing regression test output, unchanged
- [ ] Scenario 9 (Document filter): existing regression test output, unchanged
- [ ] Scenario 10 (Imported rows passthrough): test output asserting exactly 3 lines with the oversized row unchanged
- [ ] Scenario 11 (Subword alignment): existing regression test output, unchanged
- [ ] Scenario 12 (No truncation at window size): test output asserting every source token has a subword label
- [ ] Scenario 13 (Override respected): test output asserting the supplied `max_seq_length` is used
- [ ] Scenario 14 (Truncation recorded): test output plus log excerpt showing the affected-record count
- [ ] Scenario 15 (Dataset loads): existing regression test output, unchanged
- [ ] Scenario 16 (Empty dataset fails): existing regression test output, unchanged
- [ ] Scenario 17 (Too small to split fails): test output asserting failure, the error naming the row count, and that no metric was produced
- [ ] Scenario 18 (Sufficient dataset proceeds): test output asserting training proceeds with no extra gate applied
- [ ] Scenario 19 (URL default): existing regression test output, unchanged
- [ ] Scenario 20 (URL override): existing regression test output, unchanged

### Structural Evidence

*(Code review and architectural compliance.)*

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)
- [ ] No database migration was added — `alembic/versions/` is unchanged in the diff
- [ ] The window token budget and the `max_seq_length` default are documented as derived from one another, with the subword expansion safety factor stated

### Edge Case Evidence

*(One item per Hallucination Risk from Section 2.)*

- [ ] Risk 1 mitigation confirmed — tokenisation and offset derivation are a single pass; Scenario 6 passes alongside Scenario 5
- [ ] Risk 2 mitigation confirmed — no read of `bio_tags` remains in `export.py`
- [ ] Risk 3 mitigation confirmed — tokens and tags windowed from the same index range; boundary entity intact in one record
- [ ] Risk 4 mitigation confirmed — imported-rows branch untouched; oversized imported row emitted verbatim
- [ ] Risk 5 mitigation confirmed — guard tests evaluation-partition size only; no new data-sufficiency constant in the diff
- [ ] Risk 6 mitigation confirmed — `max_seq_length` still sourced from job hyperparameters with the new value as fallback
- [ ] Risk 7 mitigation confirmed — window budget and sequence length derived from one another; maximum-size window verified untruncated

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching
entry. Do not pre-fill — entries must describe real observations.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** training-data-integrity
**Proposal:** `openspec/changes/training-data-integrity/proposal.md`
**Spec files reviewed:**

- specs/annotation-workspace/spec.md
- specs/training-worker/spec.md

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
| No undocumented patterns used | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause in specs has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and all mitigations confirmed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**

- Post-fix training metrics are NOT comparable to pre-fix metrics. Every model trained before this change saw truncated and misaligned data. A metric shift after this lands is expected and is a correction, not a regression — reviewer should confirm this is communicated at rollout rather than discovered later.
- Per design.md Decision 5, existing model versions are deliberately NOT auto-invalidated or auto-retrained. Whether to surface them in the model registry as trained on corrupt data is an open product question deferred to change 6's human-gated retraining surface.
- `_compute_bio_tags` in `src/annotation_service/api/v1/spans.py` retains the same single-space defect. Decision 2 makes it harmless for training by having export ignore the stored column, but the column keeps accumulating incorrect values. Whether `spans.py` should stop writing it requires confirming no other consumer depends on it — a follow-up change, not this one.
- The concrete window size and overlap values are deliberately left to implementation and must be measured against real tenant documents. Reviewer should confirm the chosen values were measured rather than guessed, and that overlap exceeds the longest entity observed in the tenant corpus.
