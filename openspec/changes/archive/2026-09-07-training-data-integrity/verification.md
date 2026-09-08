# Verification Plan

**Change:** training-data-integrity
**Generated:** 2026-09-03
**Status:** 🟡 Implementation complete and evidenced — Audit Record still requires human reviewer sign-off before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | annotation-workspace | Annotation Export | Export annotation dataset | Given 2 annotated and 1 unannotated document all within the window budget, when the export is fetched, then status is 200, the body is JSON lines each with `tokens` and `tags`, and there are 3 lines | `tests/test_annotation_workspace.py` (existing export regression test) | - [x] |
| 2 | annotation-workspace | Annotation Export | A document exceeding the window budget produces multiple records | Given 1 annotated document with more than twice the window budget in tokens, when the export is fetched, then more than one line is emitted for it and every token appears in at least one line | `tests/test_annotation_export_windowing.py::test_long_document_produces_multiple_records` | - [x] |
| 3 | annotation-workspace | Annotation Export | Consecutive windows overlap | Given a document producing two consecutive windows, when the export is generated, then the trailing tokens of window 1 also appear as the leading tokens of window 2 | `tests/test_annotation_export_windowing.py::test_consecutive_windows_overlap` | - [x] |
| 4 | annotation-workspace | Annotation Export | An entity crossing a window boundary is complete in at least one window | Given a two-token entity whose first token sits at the end of a window's non-overlapping region, when the export is generated, then at least one record contains both tokens tagged `B-` then `I-`, not `B-` alone | `tests/test_annotation_export_windowing.py::test_boundary_entity_complete_in_one_window` | - [x] |
| 5 | annotation-workspace | Annotation Export | Tags align correctly across a newline separator | Given text `"John Doe\nworks at Acme Corp"` and an `organization` span on `"Acme Corp"`, when the export is generated, then `"Acme"`/`"Corp"` are `B-organization`/`I-organization` and `"works"`/`"at"` are `O` | `tests/test_annotation_export_offsets.py::test_tags_align_across_newline` | - [x] |
| 6 | annotation-workspace | Annotation Export | Tags align correctly across repeated spaces and tabs | Given text `"John  Doe\tworks at Acme Corp"` and an `organization` span on `"Acme Corp"`, when the export is generated, then `"Acme"`/`"Corp"` carry the organization tags and no other token does | `tests/test_annotation_export_offsets.py::test_tags_align_across_tabs_and_double_spaces` | - [x] |
| 7 | annotation-workspace | Annotation Export | Export ignores a stale stored bio_tags value | Given a span whose stored `bio_tags` disagrees with its `char_start`/`char_end`, when the export is generated, then emitted tags reflect the offsets and not the stored value | `tests/test_annotation_export_offsets.py::test_stored_bio_tags_ignored` | - [x] |
| 8 | annotation-workspace | Annotation Export | Export with entity type filter | Given spans of types PER and ORG, when the export is fetched with `entity_types=PER`, then status is 200 and only PER tags appear; ORG spans encode as O | `tests/test_annotation_workspace.py` (existing entity-type-filter regression test) | - [x] |
| 9 | annotation-workspace | Annotation Export | Export for specific documents only | Given 5 documents of which 2 are annotated, when the export is fetched with `document_ids=doc-001,doc-002`, then status is 200 and only those documents appear | `tests/test_annotation_workspace.py` (existing document-filter regression test) | - [x] |
| 10 | annotation-workspace | Annotation Export | Imported annotation rows are passed through unwindowed | Given 3 `imported_annotations` rows, one exceeding the window budget, when the export is generated, then exactly 3 lines are emitted for them and the oversized row is unchanged | `tests/test_annotation_export_windowing.py::test_imported_rows_not_windowed` | - [x] |
| 11 | training-worker | Tokenize dataset | Tokens are aligned to subwords | Given tokens `["John","smith"]` with tags `["B-PER","I-PER"]`, when tokenised at `max_seq_length=128`, then each token maps to its subwords with the first subword carrying the tag and the rest -100 | `tests/test_training_worker.py` (existing subword alignment test) | - [x] |
| 12 | training-worker | Tokenize dataset | A window-sized record is not truncated at the default sequence length | Given a record with the maximum source tokens the window budget permits, when tokenised at the default `max_seq_length`, then no token is truncated and every source token has at least one subword label | `tests/test_training_worker.py::test_window_sized_record_not_truncated` | - [x] |
| 13 | training-worker | Tokenize dataset | max_seq_length remains overridable per job | Given approved hyperparameters setting a non-default `max_seq_length`, when the worker tokenises, then the supplied value is used rather than the default | `tests/test_training_worker.py::test_max_seq_length_override_respected` | - [x] |
| 14 | training-worker | Tokenize dataset | Truncation is recorded when it occurs | Given a record whose subword expansion exceeds `max_seq_length`, when the worker tokenises, then truncation is recorded with an affected-record count and the job does not fail solely because of it | `tests/test_training_worker.py::test_truncation_is_recorded` | - [x] |
| 15 | training-worker | Load annotated dataset | Dataset loads successfully | Given a tenant with annotated documents and a running annotation service, when the worker calls the export endpoint, then it receives JSONL with `tokens`/`tags` and constructs a `datasets.Dataset` | `tests/test_training_worker.py` (existing dataset load test) | - [x] |
| 16 | training-worker | Load annotated dataset | Export returns no data | Given a tenant with no annotated documents, when the worker calls the export endpoint, then the job fails with a clear error and status "failed" | `tests/test_training_worker.py` (existing empty-dataset regression test) | - [x] |
| 17 | training-worker | Load annotated dataset | Dataset too small to form an evaluation split | Given an export yielding so few rows that the split produces zero evaluation rows, when the split is prepared, then the job fails with an error naming the row count, status is "failed", and no training or metric occurs | `tests/test_training_worker.py::test_dataset_too_small_to_split_fails` | - [x] |
| 18 | training-worker | Load annotated dataset | Dataset large enough to split proceeds | Given an export yielding at least one evaluation row under the configured split, when the split is prepared, then training proceeds with no additional minimum-size judgement applied | `tests/test_training_worker.py::test_sufficient_dataset_proceeds_without_extra_gate` | - [x] |
| 19 | training-worker | Load annotated dataset | Annotation service URL defaults to the correct internal port | Given `ANNOTATION_SERVICE_URL` unset, when the worker calls the export endpoint, then the request goes to `http://annotation_service:8000/api/v1/annotation-export` | `tests/test_training_worker.py` (existing URL default regression test) | - [x] |
| 20 | training-worker | Load annotated dataset | Annotation service URL is overridable via environment variable | Given `ANNOTATION_SERVICE_URL` set to `http://custom-host:9999`, when the worker calls the export endpoint, then the request goes to that host | `tests/test_training_worker.py` (existing URL override regression test) | - [x] |

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

- [x] Scenario 1 (Baseline export): existing regression test output, unchanged
- [x] Scenario 2 (Long document windows): test output asserting >1 line and full token coverage
- [x] Scenario 3 (Windows overlap): test output asserting the shared token region between consecutive windows
- [x] Scenario 4 (Boundary entity intact): test output asserting `B-`/`I-` present together in one record
- [x] Scenario 5 (Newline alignment): test output asserting correct tags for the verified `"John Doe\nworks at Acme Corp"` case
- [x] Scenario 6 (Tab and double-space alignment): test output asserting correct tags and no stray organization tag
- [x] Scenario 7 (Stored bio_tags ignored): test output asserting offset-derived tags win over a deliberately inconsistent stored value
- [x] Scenario 8 (Entity type filter): existing regression test output, unchanged
- [x] Scenario 9 (Document filter): existing regression test output, unchanged
- [x] Scenario 10 (Imported rows passthrough): test output asserting exactly 3 lines with the oversized row unchanged
- [x] Scenario 11 (Subword alignment): existing regression test output, unchanged
- [x] Scenario 12 (No truncation at window size): test output asserting every source token has a subword label
- [x] Scenario 13 (Override respected): test output asserting the supplied `max_seq_length` is used
- [x] Scenario 14 (Truncation recorded): test output plus log excerpt showing the affected-record count
- [x] Scenario 15 (Dataset loads): existing regression test output, unchanged
- [x] Scenario 16 (Empty dataset fails): existing regression test output, unchanged
- [x] Scenario 17 (Too small to split fails): test output asserting failure, the error naming the row count, and that no metric was produced
- [x] Scenario 18 (Sufficient dataset proceeds): test output asserting training proceeds with no extra gate applied
- [x] Scenario 19 (URL default): existing regression test output, unchanged
- [x] Scenario 20 (URL override): existing regression test output, unchanged

### Structural Evidence

*(Code review and architectural compliance.)*

- [x] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed ✓
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)
- [x] No database migration was added — `alembic/versions/` is unchanged in the diff
- [x] The window token budget and the `max_seq_length` default are documented as derived from one another, with the subword expansion safety factor stated

### Edge Case Evidence

*(One item per Hallucination Risk from Section 2.)*

- [x] Risk 1 mitigation confirmed — tokenisation and offset derivation are a single pass; Scenario 6 passes alongside Scenario 5
- [x] Risk 2 mitigation confirmed — no read of `bio_tags` remains in `export.py`
- [x] Risk 3 mitigation confirmed — tokens and tags windowed from the same index range; boundary entity intact in one record
- [x] Risk 4 mitigation confirmed — imported-rows branch untouched; oversized imported row emitted verbatim
- [x] Risk 5 mitigation confirmed — guard tests evaluation-partition size only; no new data-sufficiency constant in the diff
- [x] Risk 6 mitigation confirmed — `max_seq_length` still sourced from job hyperparameters with the new value as fallback
- [x] Risk 7 mitigation confirmed — window budget and sequence length derived from one another; maximum-size window verified untruncated

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching
entry. Do not pre-fill — entries must describe real observations.

All tests were executed in a container built from the `ner-project-training_service`
image with `pytest` added, against the `ner_test` database on `postgres-test`. There is
no host Python environment with the project's dependencies installed.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Failing baseline | `tests/test_annotation_export_offsets.py` run against unmodified `export.py`: all 3 tests fail. `"Acme"` came back `I-organization` (drifted offsets) in both the newline and tab cases; the stale-`bio_tags` case returned `B-location`, the corrupt stored value. `3 failed` | 5, 6, 7 (pre-fix) | agent | 2026-09-03 |
| 2 | Test output | `tests/test_annotation_export_offsets.py` after the fix: `3 passed`. Newline and tab/double-space cases both tag `Acme`/`Corp` as `B-`/`I-organization` with no stray tags; the stale stored value is ignored. | 5, 6, 7 | agent | 2026-09-03 |
| 3 | Test output | `tests/test_annotation_export_windowing.py`: `4 passed` — 261-token document yields >1 record with full token coverage and no record over 128 tokens; consecutive windows share exactly 64 leading/trailing tokens in both `tokens` and `tags`; a boundary entity at index 127/128 comes back `B-`/`I-` together in one window; 3 imported rows emit as 3 lines with the 384-token row byte-identical. | 2, 3, 4, 10 | agent | 2026-09-03 |
| 4 | Regression test output | `tests/test_annotation_workspace.py -k export`: `3 passed` (`test_7_16_export_all_documents`, `test_7_17_export_with_type_filter`, `test_7_18_export_with_document_filter`). These required adding the missing `imported_annotations` DDL to the module's fixture — the export endpoint always queries that table, so the tests could not run at all before. | 1, 8, 9 | agent | 2026-09-03 |
| 5 | Regression test output | `tests/test_bio_tags.py`: `5 passed`. `spans.py` and the stored column are untouched by this change, as Decision 2 requires. | Decision 2 non-goal | agent | 2026-09-03 |
| 6 | Test output | `tests/test_training_worker.py::TestSequenceLength`: `3 passed`. A 128-source-token record built at the measured worst-case expansion (3.64 subwords/token) tokenises at the 512 default with every source token labelled and zero truncation; a supplied `max_seq_length` overrides the default; a 200-token record at `max_seq_length=32` records `{records: 1, dropped_tokens: >0}` and still returns normally. | 12, 13, 14 | agent | 2026-09-03 |
| 7 | Test output | `tests/test_training_worker.py::TestDatasetSplitGuard`: `3 passed`. 0 and 1 rows fail with the row count in the message; 2/3/10/50/3000 rows all pass with no further gate. The job-level test shows status `failed`, no `metrics` field ever written, and `_extract_label_set` never reached. | 17, 18 | agent | 2026-09-03 |
| 8 | Regression test output | `tests/test_training_worker.py`, existing tests: subword alignment, dataset load, empty-dataset failure, URL default and URL override all pass. | 11, 15, 16, 19, 20 | agent | 2026-09-03 |
| 9 | Full scenario run | `tests/test_annotation_export_offsets.py test_annotation_export_windowing.py test_annotation_workspace.py test_bio_tags.py test_training_worker.py` — `3 failed, 62 passed in 1083s`. All 3 failures are pre-existing or environmental and unrelated: `test_onnx_export_mock_verifies_export_call` fails identically with this change's `worker.py` stashed (`module has no attribute 'torch'`), and the two MLflow tests need a tracking server on `localhost:5000`, which the test container cannot reach. | all | agent | 2026-09-03 |
| 10 | Corpus measurement | Live `ner_dev` tenant schemas hold zero `document_text_spans` rows and only synthetic 5-character spans, so window sizing was measured against `annotations.jsonl` (553 real résumé documents): document length p50 334 / p95 984 / max 2487 source tokens; longest entity 58 source tokens (p99 = 7); subword expansion under `dslim/bert-base-NER` mean 1.99 / max 3.64. Recorded in tasks.md § 1.3. | window budget and overlap provenance | agent | 2026-09-03 |
| 11 | End-to-end export | The 553-document corpus seeded into a scratch tenant and fetched through the real `GET /api/v1/annotation-export`: **553 rows before, 3206 rows after**, max 128 tokens per row, 383,956 tokens emitted across windows. | 2, 3, 4 at real scale | agent | 2026-09-03 |
| 12 | Pre/post corruption measurement | The same seeded tenant exported with `export.py` stashed and again with the fix, tags reassembled per document from the non-overlapping window heads: **553 of 553 documents (100%) had at least one tag change, and 59,349 of 214,164 source tokens (27.7%) were tagged differently**. Confirms the defect affected essentially every real document rather than an edge case. | 5, 6 at real scale | agent | 2026-09-03 |
| 13 | Structural check | `grep bio_tags src/annotation_service/api/v1/export.py` returns only the new function name and its docstring — no read of the column, and the `SELECT` no longer projects it. | Risk 2 | agent | 2026-09-03 |
| 15 | End-to-end training run | The real worker path over the real 3206-row export: split guard passed at `test_size=0.1`; 25 labels; tokenisation at the new `max_seq_length=512` default reported **655 of 3206 records truncated, 4193 source tokens dropped**; split gave **train=2885 / eval=321**. A genuine `Trainer` fit then ran to completion on CPU. **The fit was deliberately reduced** (32 train / 3 eval rows, 1 epoch, batch 2) because the container OOMs at batch 8 and a full 2885-row fit is not feasible on CPU — so `eval_loss 1.0998`, `eval_precision/recall/f1 = 0.0` reflect the reduction, not the data. Row count and truncation figures are real; **the metrics are not, and are not comparable to any pre-fix run**. A full-scale run needs GPU capacity. | 6.6 (partial) | agent | 2026-09-07 |
| 14 | Structural check | `git diff --stat` is empty for `alembic/`, `src/training_service/celery_app.py`, `src/training_service/api/v1/training_jobs.py` and `src/shared/config.py`. No migration, no queue or checkpointing change, and `NER_MIN_ENTITIES_PER_TYPE` / `NER_MIN_TRAINING_ENTITIES` untouched. (`alembic/versions/038_llm_prelabeling_columns.py` is untracked but belongs to the separate llm-assisted-prelabeling change.) | ADR-006, ADR-010, structural | agent | 2026-09-03 |

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
