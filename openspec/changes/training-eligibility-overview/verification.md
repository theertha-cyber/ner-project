# Verification Plan

**Change:** training-eligibility-overview
**Generated:** 2026-09-09
**Status:** 🔴 NOT VERIFIED — implementation not started.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | human-gated-retraining | Retraining Decision Surface | Decision surface shows accumulation against the serving version | (unchanged) 134 reported, version 3 identified | `tests/test_retraining_decision.py::test_accumulation_against_serving_version` | - [ ] |
| 2 | human-gated-retraining | Retraining Decision Surface | Accumulation is broken down per entity type | (unchanged) 120 `organization`, 14 `person_name` | `tests/test_retraining_decision.py::test_accumulation_per_entity_type` | - [ ] |
| 3 | human-gated-retraining | Retraining Decision Surface | Accumulation is broken down per source | Given 90 manual / 30 automated / 14 import accumulated spans, when requested, then `by_source` reports `manual:90, automated:30, import:14` | `tests/test_retraining_decision.py::test_accumulation_per_source` | - [ ] |
| 4 | human-gated-retraining | Retraining Decision Surface | A tenant with no trained model is shown distinctly | (unchanged) no-model state, not a zero figure | `tests/test_retraining_decision.py::test_no_trained_model_distinct` | - [ ] |
| 5 | human-gated-retraining | Retraining Decision Surface | Accumulation is not presented as readiness | (unchanged) labelled distinctly, not compared to the threshold | `tests/test_retraining_decision.py::test_accumulation_not_readiness` | - [ ] |
| 6 | human-gated-retraining | Retraining Decision Surface | Overview counts training-eligible units per source | Given 2 completed tasks, 1 approved large batch, 3 mapped import files (none consumed), when requested, then `eligible_overview` = `manual:2, automated:1, import:3` each with a latest timestamp | `tests/test_retraining_decision.py::test_eligible_overview_counts` | - [ ] |
| 7 | human-gated-retraining | Retraining Decision Surface | Consumed units drop off the overview | Given 2 completed tasks consumed by a since-completed run, when requested, then `eligible_overview.manual = 0` | `tests/test_retraining_decision.py::test_consumed_units_drop_off` | - [ ] |
| 8 | human-gated-retraining | Retraining Decision Surface | The overview is a report only | Given eligible units in every source, when the surface is requested repeatedly, then no job created, no Celery task enqueued, serving version unchanged | `tests/test_retraining_decision.py::test_overview_is_report_only` | - [ ] |
| 9 | human-gated-retraining | Retraining Decision Surface | Import "unconsumed" respects the run completion time | Given a mapped import file whose `training_eligible_at` precedes a completed run's `completed_at`, when requested, then it is NOT counted in `eligible_overview.import` | `tests/test_retraining_decision.py::test_import_unconsumed_by_run_time` | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Per-source split (Decision 1) | Implementer adds a new `source` column to spans instead of reading existing provenance markers | Confirm no schema change; the split reads `span_batch_provenance` / the manual/import markers already present. |
| 2 | Overview becoming a gate (ADR-009/010) | Implementer compares `eligible_overview` counts to a threshold and hides "Request training" below it, or auto-submits | Confirm the endpoint returns counts only; the portal's "Request training" is always available for an eligible unit. Execute Scenario 8. |
| 3 | Double counting | A document both manually annotated and imported inflates `by_source` totals beyond `spans_accumulated` | Assert `sum(by_source.values()) == spans_accumulated`. Execute Scenario 3. |
| 4 | Consumed filtering (Decision 2) | Import files are always shown as waiting (no consumed check) or never (over-eager check) | Execute Scenarios 7, 9 — one consumed, one boundary case. |
| 5 | Old-field regression | The additive fields change the type or value of `spans_accumulated` / `by_entity_type` | Execute Scenarios 1, 2 unchanged against the new response. |

---

## 3. Pattern & ADR Compliance

| ADR | Constraint | Verification Step |
|-----|-----------|-------------------|
| ADR-001 tenant-data-isolation | One tenant schema per request, resolved as today | Read schema resolution in the modified endpoint. |
| ADR-009 system-admin-sets-hyperparameters | Report only — no enqueue/approve | Execute Scenario 8. |
| ADR-010 per-entity-type-dataset-threshold | Overview counts are not compared to the readiness threshold | Grep the endpoint/service for the readiness constant — must not appear. Execute Scenario 5. |

---

## 4. Evidence Requirements

### Functional Evidence
- [ ] One test-output item per row 1–9.

### Structural Evidence
- [ ] Code review — matches design.md; no schema change
- [ ] `sum(by_source.values()) == spans_accumulated` holds in the per-source test
- [ ] The endpoint imports no readiness threshold constant
- [ ] Existing response fields unchanged in name, type, and value

### Edge Case Evidence
- [ ] Risk 1 — split reads existing provenance, no new column
- [ ] Risk 2 — no gate, no auto-submit
- [ ] Risk 3 — headline figure not double-counted
- [ ] Risk 4 — consumed/boundary import cases correct
- [ ] Risk 5 — old fields unregressed

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: signed by a human reviewer before archive.**

**Change slug:** training-eligibility-overview
**Spec files reviewed:** specs/human-gated-retraining/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [ ] |
| All ADRs in Section 3 verified compliant | - [ ] |
| Spec Alignment table complete | - [ ] |
| Evidence Log populated with real evidence | - [ ] |
| All functional evidence items checked | - [ ] |
| All structural evidence items checked | - [ ] |
| All edge case evidence items checked | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and mitigations confirmed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**

- Depends on the manual (Phase 3, landed), `automated-annotation-guided-workflow`, and
  `import-annotation-training-eligibility` changes for the three `training_eligible_at`
  sources.

---

## 7. Agent Verification Record

Implemented: `accumulation.py` — `by_source` (`manual`/`automated`) via `LEFT JOIN
span_batch_provenance`, summing to `spans_accumulated`; new `eligible_overview` counting
training-eligible-and-unconsumed units per source (task / approved large batch / mapped
import file) against the last completed run's `completed_at`. `retraining_decision.py`
adds `by_source` + `eligible_overview` additively. Portal: types + a "By source" line and
a "Training-eligible and waiting" panel on `RetrainingDecisionPage`.

```
tests/test_training_eligibility_overview.py    4 passed  (by_source sum, overview counts,
                                                          consumed drop-off, report-only)
tests/test_retraining_decision.py + accumulation + no_auto_retraining   27 passed (no regression)
src/portal RetrainingDecisionPage.test.tsx    12 passed  (+1 overview test)
```

`py_compile` clean; `tsc --noEmit` no new errors. No migration — all source fields exist
after the prior changes.

**Spec revision during apply:** scenario 3 originally claimed imports contribute to
`spans_accumulated`. Imported annotations are not confirmed spans, so the accumulation
figure and its `by_source` split cover `manual` + `automated` only (summing to the figure);
imports appear solely in `eligible_overview`. The spec's "Retraining Decision Surface"
requirement and scenario 3 were updated to reflect this.

### Not done
- Stepper step-4 state from `eligible_overview` (task 5.3) — the layout does not fetch the
  decision surface.
- §4/§5 evidence tables; §6 sign-off.

---

## 8. Outstanding Items

- Task 5.3; §4/§5 evidence; §6 sign-off.
