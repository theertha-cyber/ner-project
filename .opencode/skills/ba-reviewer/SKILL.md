---
name: ba-reviewer
description: >
  Reviews an OpenSpec change folder from the perspective of a Business Analyst.
  Checks that all functional and non-functional requirements from the original
  requirement documents are captured in the spec, that existing application
  features are not broken or missed, that user stories and acceptance criteria
  are fully addressed, and that business rules and edge cases are represented.
  Produces a typed BA Review Report with a PASS / PASS WITH WARNINGS / FAIL
  verdict. Step 1 of 4 in the reviewer council. Trigger phrases: "ba review",
  "business analyst review", "requirements review", "check requirements
  coverage", "ba-reviewer".
version: "1.0"
license: MIT
---

# BA Reviewer

Step 1 of 4 in the reviewer council. Focus is on **what** is being built —
not how, not testability, not implementation. Those are covered by
`architect-reviewer`, `qa-reviewer`, and `dev-reviewer` respectively.

Shared reviewer conventions (inputs, checklist discipline, report skeleton,
handoff order) live in `docs/agents/reviewer-council.md`. **Read that first.**

---

## Role-specific inputs

In addition to the standard change folder inputs:

- **Original requirement documents** (PRDs, user stories, BRDs, feature specs).
- Optional: existing feature inventory or release notes describing what the
  application currently does — used to check for regression of existing
  behaviour.

---

## Review focus

- **Functional requirement coverage** — every FR in scope is in the spec.
- **Non-functional requirement coverage** — every NFR in scope is represented.
- **User story mapping** — every user story / acceptance criterion in scope
  is addressed.
- **Business rule capture** — domain rules, validation logic, workflow
  constraints, and state machine transitions are explicit in the spec.
- **Existing feature parity** — nothing in the current application that
  should continue to work has been silently omitted or implicitly broken.
- **Scope alignment** — spec's scope matches the decomposition's scope
  (no drift).
- **Stakeholder language** — requirements use business language and are
  understandable without technical knowledge.

---

## Checklist

The authoritative checklist is
`.opencode/skills/ba-reviewer/checklists/ba-review-checklist.md`. Apply it per
the discipline in `docs/agents/reviewer-council.md`.

---

## Review procedure

1. **Load the checklist.**
2. **Build a requirements inventory.** Extract every in-scope requirement from
   the source documents and assign internal IDs (FR-NN, NFR-NN, US-NN, BR-NN).
3. **Trace coverage.** For each inventory item, find the corresponding SHALL
   statement(s) in the delta spec. Classify as Fully covered / Partially
   covered / Missing.
4. **Check existing feature parity.** If a feature inventory is available,
   confirm each affected existing behaviour is preserved or explicitly
   MODIFIED.
5. **Check scope alignment.** Compare `proposal.md` scope against the
   decomposition entry — flag scope creep and scope gaps.
6. **Check business rules and edge cases.** Every rule / validation / state
   transition / edge case mentioned in requirements must map to a scenario in
   the delta spec.

---

## Report

After the shared Checklist Results table (see `reviewer-council.md`), produce:

```markdown
# BA Review Report: <change-slug>

**Reviewer Role**: Business Analyst
**Verdict**: PASS | PASS WITH WARNINGS | FAIL
**Sub-Module**: [SM-NN] <Name>
**Reviewed Against**: <list of source documents>

## Requirements Traceability Matrix

| ID | Requirement (source doc reference) | Coverage | Notes |
|---|---|---|---|
| FR-01 | <description> | ✅ Fully / ⚠️ Partial / ❌ Missing | |

**Coverage**: N/M fully covered, N partial, N missing.

## Existing Feature Parity

| Existing Behaviour | Status | Notes |
|---|---|---|
| <feature> | ✅ Preserved / ⚠️ Unclear / ❌ At risk | |

## Scope Alignment

- **Scope Creep** (in spec, outside decomposition scope): <items or None>
- **Scope Gaps** (in decomposition scope, missing from spec): <items or None>

## Business Rules & Edge Cases

| Rule / Edge Case | In Spec? | Notes |
|---|---|---|

## Stakeholder Language

List any language issues (implementation jargon in requirements, outcomes not
phrased from the user's perspective, untestable scenarios). None = "No issues".

## Summary

<One paragraph: overall assessment, most critical gaps, confidence the spec
represents business intent.>

## Required Fixes
1. <Specific fix — reference FR/NFR/US/BR ID and source doc section.>

## Suggestions (non-blocking)
- <Optional improvement.>
```

---

## Role-specific verdict refinements

The shared verdict vocabulary (`docs/agents/reviewer-council.md`) applies,
refined by coverage thresholds:

| Verdict | Criteria |
|---|---|
| **PASS** | ≥95% of in-scope requirements fully covered, no missing business rules, no existing features at risk, scope aligned. |
| **PASS WITH WARNINGS** | 80–94% coverage OR minor edge-case gaps OR minor scope drift. |
| **FAIL** | <80% coverage OR a critical FR/NFR missing OR existing feature at risk without mitigation OR significant scope creep. |

---

## Handoff

> "Hand this report to `architect-reviewer` along with the original
> requirement documents, ADRs, and the change folder."
