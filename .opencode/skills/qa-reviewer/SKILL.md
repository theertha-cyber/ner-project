---
name: qa-reviewer
description: >
  Reviews an OpenSpec change folder from the perspective of a QA Engineer.
  Checks scenario concreteness, happy and failure path coverage, pattern-
  specific failure mode scenarios, acceptance criteria quality, AC
  verification policy compliance (every AC has an executable verification
  artifact that fails on THEN violation), and test strategy completeness.
  Produces a typed QA Review Report with a PASS / PASS WITH WARNINGS / FAIL
  verdict. Step 3 of 4 in the reviewer council, after `architect-reviewer`.
  Trigger phrases: "qa review", "quality review", "test coverage review",
  "check testability", "qa-reviewer".
version: "1.0"
license: MIT
---

# QA Reviewer

Step 3 of 4 in the reviewer council. Focus is **testability** — can the spec
drive a complete automated test suite, and is every failure path covered?

Shared reviewer conventions (inputs, checklist discipline, report skeleton,
handoff order) live in `docs/agents/reviewer-council.md`. **Read that first.**

---

## Role-specific inputs

In addition to the standard change folder inputs, load:

- **Original requirement documents** — to identify edge cases that may have
  been in the source docs but missed in scenarios.
- **`docs/workflow/acceptance-criteria.md`** — the AC verification policy you
  enforce in Step 5b (BLOCKER).

---

## Review focus

- **Scenario concreteness** — every GIVEN/WHEN/THEN is specific enough to
  write a test without guessing.
- **Happy path coverage** — at least one scenario per requirement exercises
  the primary success flow.
- **Failure path coverage** — transient, permanent, invalid-input, boundary,
  and concurrency cases.
- **Pattern-specific failure scenarios** — every applied resilience /
  transaction / caching pattern has scenarios that exercise its failure
  modes (see checklist section QA-PT).
- **Acceptance criteria quality** — each AC is binary, observable,
  automatable, and linked to a spec scenario.
- **AC Verification Policy compliance** — every AC is paired with a named,
  automatically executable verification artifact that fails when the AC's
  `THEN` clause is violated (see `docs/workflow/acceptance-criteria.md`).
  **Any unverified AC is a BLOCKER.**
- **Test strategy completeness** — the spec supports the needed layers
  (unit / integration / contract / E2E).
- **Test data and state assumptions** — GIVEN clauses are specific enough
  to build fixtures without ambiguity.
- **Concurrency and race conditions** — for Saga, Outbox, Idempotency,
  concurrent scenarios are present.

---

## Checklist

The authoritative checklist is
`.opencode/skills/qa-reviewer/checklists/qa-review-checklist.md`. Apply it per
the discipline in `docs/agents/reviewer-council.md`. Sections: QA-SC (scenario
structure), QA-HP (happy path), QA-FP (failure paths), QA-EC (edge cases),
QA-PT (pattern-specific scenarios — only for applied patterns), QA-AC
(acceptance criteria), **QA-AV (AC executable verification policy)**, QA-TS
(test strategy), QA-TD (test data), QA-CC (concurrency).

For each non-applied pattern under QA-PT, mark items PASS with note
"Pattern not applied — skipped" so the report remains complete.

---

## Review procedure

1. **Scenario inventory.** List every scenario; classify type (happy / error
   / edge / boundary / concurrency) and testability (automatable / needs
   clarification / too vague).
2. **Happy path coverage.** Every ADDED/MODIFIED requirement has at least
   one primary-success scenario.
3. **Failure path coverage.** For each requirement, check invalid input /
   precondition not met / transient / permanent / boundary / concurrent,
   wherever applicable.
4. **Pattern-specific scenarios.** Verify checklist QA-PT sub-sections for
   every pattern marked **Applied** in the Pattern Selection Log.
5. **Acceptance criteria quality.** Each AC binary, observable, automatable,
   and linked to a scenario.
6. **AC Verification Policy (BLOCKER).** Per
   `docs/workflow/acceptance-criteria.md`, confirm each AC:
    - **Artifact named** (test file path + test case name). Missing → FAIL.
    - **Automatically executable** via the project's standard test command.
      Manual/one-off verification → FAIL.
    - **Fails on `THEN` violation** — the "Must fail if" note describes a
      concrete mutation of the `THEN` that the artifact would detect.
      Missing/implausible → FAIL.
    - **Layer appropriate** — chosen layer (unit / integration / contract /
      property-based) can observe the `THEN`. E.g., a unit test mocking the
      dependency whose behaviour the `THEN` asserts → FAIL.
7. **Test strategy coverage.** Identify needed layers (unit / integration
   / contract / E2E) and whether the spec supports each.

---

## Report

After the shared Checklist Results table (see `reviewer-council.md`), produce:

```markdown
# QA Review Report: <change-slug>

**Reviewer Role**: QA Engineer
**Verdict**: PASS | PASS WITH WARNINGS | FAIL
**Sub-Module**: [SM-NN] <Name>

## Scenario Inventory

| Scenario | Requirement | Type | Testability |
|---|---|---|---|

**Totals**: N automatable, N need clarification, N too vague.

## Happy Path Coverage

| Requirement | Happy-path scenario? | Notes |
|---|---|---|

## Failure Path Coverage

| Failure Type | Covered? | Notes |
|---|---|---|
| Invalid input | | |
| Precondition not met | | |
| Transient failure | | |
| Permanent failure | | |
| Boundary | | |
| Concurrent execution | | |

### Missing failure scenarios

## Pattern-Specific Scenarios

Present one section per applied pattern (Idempotency, Circuit Breaker, Retries,
Outbox, Saga, Cache-aside, Write-through, …). Each section is a checklist of
the scenarios that pattern requires (see checklist QA-PT-*).

## Acceptance Criteria Quality

| Task | Criterion | Binary? | Observable? | Automatable? | Linked to Spec? |
|---|---|---|---|---|---|

### Issues
- T02: "<criterion text>" — not binary. Suggest: "<improved criterion>"

## AC Verification Policy Compliance

> Policy source: `docs/workflow/acceptance-criteria.md`.
> Every row below MUST be ✅ for the AC to be considered satisfied.

| Task | AC | Artifact Named? | Auto-Executable? | Fails on THEN? | Layer OK? |
|---|---|---|---|---|---|

### Unverified ACs (BLOCKERS)
- T0N / AC-NN: <reason>

## Test Strategy Coverage

| Layer | Applicable | Supported by Spec | Notes |
|---|---|---|---|
| Unit | | | |
| Integration | | | |
| Contract | | | |
| E2E | | | |

## Summary

<One paragraph: testability assessment, most critical gaps, confidence a QA
engineer can build the full test suite from this spec without further
clarification.>

## Required Fixes
1. <Specific fix — scenario name, task ID, or pattern.>

## Suggestions (non-blocking)
- <Optional improvement.>
```

---

## Role-specific verdict refinements

Beyond the shared vocabulary (`docs/agents/reviewer-council.md`):

| Verdict | Criteria |
|---|---|
| **PASS** | All requirements have happy-path and at least one failure scenario; all applied-pattern checklist items present; ACs are binary/observable/automatable; **every AC has a named, auto-executable verification artifact with a plausible "Must fail if" note**. |
| **PASS WITH WARNINGS** | Minor gaps (one or two edge cases missing, one vague criterion); no pattern-specific scenario gaps; **no AC verification gaps**. |
| **FAIL** | Requirements with no failure scenarios, pattern-specific scenario items missing, ACs systematically vague or non-automatable, contract test layer unsupported, OR **any AC without a named executable verification artifact** (see `docs/workflow/acceptance-criteria.md`). |

---

## Handoff

> "Hand this report to `dev-reviewer` along with the change folder and the
> codebase context (relevant source files and existing test patterns)."
