# Verification Plan

**Change:** fix-prelabel-keyword-search
**Generated:** 2026-07-02
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | annotation-workspace | Pre-labeling | Pre-label a processed document | Given a document with text "Vellore Institute of Technology is a deemed university" and entity type `institute` with `examples: ["Vellore Institute of Technology"]`, when POST /prelabel, then response has status 200 and body contains a suggested span for "Vellore Institute of Technology" (char_start: 0, char_end: 31, confidence < 1.0) | | - [ ] |
| 2 | annotation-workspace | Pre-labeling | Pre-label matching is case-insensitive | Given a document with text "Vellore INSTITUTE of Technology" and entity type `institute` with `examples: ["Vellore Institute of Technology"]`, when POST /prelabel, then response includes a suggestion for "Vellore INSTITUTE of Technology" | | - [ ] |
| 3 | annotation-workspace | Pre-labeling | Pre-label longest match wins | Given a document with text "Apple Inc is based in Cupertino" and entity type `organization` with `examples: ["Apple Inc", "Apple"]`, when POST /prelabel, then exactly one suggestion for "Apple Inc" (0-9) is returned and no separate "Apple" suggestion | | - [ ] |
| 4 | annotation-workspace | Pre-labeling | Pre-label replaces existing suggestions | Given a document with two existing suggested spans from a previous call, when POST /prelabel again, then old suggestions are removed and new ones returned | | - [ ] |
| 5 | annotation-workspace | Pre-labeling | List suggested spans | Given a document with 3 suggested spans, when GET /spans?type=suggested, then response has status 200 and contains 3 suggestions | | - [ ] |
| 6 | annotation-workspace | Pre-labeling | Promote a suggested span | Given a suggested span "suggest-1" for entity type "institute" at offsets 10-31, when POST /spans/promote/suggest-1, then a confirmed span is created with same offsets and entity type, and the suggestion is removed | | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Example sort order | AI may not sort examples by descending length before overlap checking, causing the wrong (shorter) match to win | Verify the longest-match logic sorts examples by `len(example)` descending before iterating |
| 2 | NULL/empty examples | AI may crash or misbehave when `examples` column is `NULL`, `[]`, or contains empty strings | Verify the code skips entity types with no examples or empty example strings |
| 3 | Case insensitivity gaps | AI may apply `re.IGNORECASE` to the main search but miss secondary text operations (e.g., `match.group()` should preserve original casing) | Verify `match.group()` returns the original document text, not the lowercased example |
| 4 | SQL query doesn't select examples | AI may keep the old SQL query (`SELECT name, base_label_mapping ...`) and only change the Python logic, never reading the `examples` column | Verify the SQL query now includes `examples` in the SELECT clause |
| 5 | Overlap detection bug | AI may compare exact `(start, end)` pairs but miss partial overlaps (e.g., "Apple Inc" 0-9 and "Apple" 0-5 — these overlap but `(0,9) != (0,5)`) | Verify the overlap check uses range intersection (start < existing_end and end > existing_start), not exact equality |

---

## 3. Pattern & ADR Compliance

No ADRs are formally `ACCEPTED` as in force. All 8 ADRs are `Proposed` and do not constrain this change.

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| None | — | — | — |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1: Test output showing `test_prelabel_examples_keyword_source` passes — verifies the correct example is matched at correct offsets
- [ ] Scenario 2: Test output showing `test_prelabel_case_insensitive` passes — verifies case-insensitive matching with re.IGNORECASE
- [ ] Scenario 3: Test output showing `test_prelabel_longest_match_wins` passes — verifies only the longest overlapping example is suggested
- [ ] Scenario 4: Test output showing `test_prelabel_replaces_existing` passes — verifies old suggestions are deleted before new ones
- [ ] Scenario 5: Test output showing `test_prelabel_list_suggestions` passes — verifies GET with type=suggested returns only suggestions
- [ ] Scenario 6: Test output showing `test_prelabel_promote_suggestion` passes — verifies promote moves suggestion to confirmed span

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] SQL query in `prelabel_document()` includes `examples` column — confirmed
- [ ] Examples are sorted by descending length before loop — confirmed
- [ ] Overlap check uses range intersection, not exact match — confirmed
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 (example sort order): Code sorts examples by `len(example)` descending — confirmed by inspection
- [ ] Risk 2 (NULL/empty examples): Code skips entity types where `examples` is None or empty list — confirmed by test
- [ ] Risk 3 (case insensitivity): `re.IGNORECASE` flag is present and `match.group()` preserves original document casing — confirmed
- [ ] Risk 4 (SQL doesn't read examples): SELECT clause includes `examples` — confirmed by inspection
- [ ] Risk 5 (overlap detection): Overlap check uses proper range intersection logic — confirmed by test

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx-archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** fix-prelabel-keyword-search
**Proposal:** `openspec/changes/fix-prelabel-keyword-search/proposal.md`
**Spec files reviewed:**
- specs/annotation-workspace/spec.md

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
