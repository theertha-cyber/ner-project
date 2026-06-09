---
name: review-synthesizer
description: >
  Aggregates the four reviewer council reports (ba-reviewer,
  architect-reviewer, qa-reviewer, dev-reviewer) into a Council Review
  Report with a final PASS / PASS WITH WARNINGS / FAIL verdict, a
  priority-ordered action list, and a clear recommendation on whether to
  proceed to `/opsx:apply`, revise first, or escalate. Resolves
  cross-reviewer conflicts. Final step in the reviewer council. Trigger
  phrases: "synthesize reviews", "final verdict", "council verdict",
  "review-synthesizer".
version: "1.0"
license: MIT
---

# Review Synthesizer

Final quality gate before `/opsx:apply` or `/opsx:archive`. Aggregates all
four council reports and produces a single Council Review Report.

Shared council conventions live in `docs/agents/reviewer-council.md`.

---

## Inputs

All four reports in full — BA, Architect, QA, Developer — plus the change
slug. If any report is missing, ask the user to run the missing reviewer
before synthesizing.

---

## Synthesis procedure

1. **Collect individual verdicts.**
2. **Derive the council verdict** (first matching rule wins):

    | Condition | Council Verdict |
    |---|---|
    | Any reviewer = FAIL | FAIL |
    | 3 or more reviewers = PASS WITH WARNINGS | PASS WITH WARNINGS |
    | Any reviewer = PASS WITH WARNINGS | PASS WITH WARNINGS |
    | All reviewers = PASS | PASS |

3. **Resolve cross-reviewer conflicts.** Common patterns:
    - **BA wants a requirement that Architect says violates an ADR** — the
      ADR wins unless overridden by a new ADR. Flag for user decision.
    - **QA wants a scenario that Dev says is infeasible** — keep the
      scenario; the task notes the constraint and proposes an alternative.
      Flag for user decision.
    - **Architect flags a missing pattern that Dev calls
      over-engineering** — present both views + omission risk; default to
      Architect if an applicable ADR exists.
    - **Dev flags a missing task that QA has an AC for** — not a conflict;
      this is a Dev FAIL finding.

    Each conflict gets a **Conflict Resolution** entry with competing
    positions and a recommendation.

4. **Deduplicate required fixes** — when multiple reviewers flag the same
   underlying issue from different angles, merge into one fix with all
   reviewer references.

5. **Prioritise fixes**:
    - **P1 — Blocker** — must resolve before `/opsx:apply`. Incorrect
      behaviour, data loss, security exposure, ADR violation, **or any AC
      Verification Policy violation** (any AC without a named,
      auto-executable verification artifact with a plausible "Must fail
      if" note — see `docs/workflow/acceptance-criteria.md`). Unverified
      ACs are P1 by definition.
    - **P2 — Should fix** — resolve before archiving; can apply with
      caution. Quality issues that don't cause bugs.
    - **P3 — Nice to have** — can defer to a follow-up change.

6. **Determine the recommendation**:

    | Council Verdict | P1 Fixes | Recommendation |
    |---|---|---|
    | PASS | 0 | ✅ Proceed to `/opsx:apply` |
    | PASS WITH WARNINGS | 0 | ✅ Proceed with documented caveats |
    | PASS WITH WARNINGS | ≥1 | 🔧 Resolve P1 then proceed |
    | FAIL | Any | ❌ Revise, re-run affected reviewers, re-synthesize |

---

## Report

```markdown
# Council Review Report: <change-slug>

**Sub-Module**: [SM-NN] <Name>
**Review Date**: <date>

## Individual Verdicts

| Reviewer | Verdict | Critical Issues |
|---|---|---|

## Council Verdict: PASS | PASS WITH WARNINGS | FAIL

**Rationale**: <one sentence on how the verdict was derived>.

## Conflict Resolutions

<Omit if none. Otherwise one entry per conflict with competing positions and
a recommendation. Mark "Decision required from user: Yes/No".>

## Consolidated Action List

### P1 — Blockers (must fix before /opsx:apply)

| # | Fix | Raised By | Artifact | Source Reference |
|---|---|---|---|---|

### P2 — Should Fix (before /opsx:archive)

| # | Fix | Raised By | Artifact | Notes |
|---|---|---|---|---|

### P3 — Nice to Have (can defer)

| # | Suggestion | Raised By | Notes |
|---|---|---|---|

## Recommendation

<One of the three outcomes below, with a paragraph of context.>

- ✅ **Proceed to `/opsx:apply`** — all blockers resolved; ready for
  implementation.
- 🔧 **Resolve P1 blockers, then proceed** — list which reviewers to re-run.
- ❌ **Revise and re-review** — list P1 fixes and the reviewers to re-run.

## Re-Review Scope

<Only for 🔧 or ❌ recommendations. Re-run only reviewers whose domain was
affected by the fixes, using this map:>

| Fix Area | Re-run Reviewer |
|---|---|
| Requirements / scenarios | `ba-reviewer`, `qa-reviewer` |
| Design (patterns, data model, contracts) | `architect-reviewer`, `dev-reviewer` |
| Tasks / acceptance criteria | `dev-reviewer`, `qa-reviewer` |
| ADR violation fixed | `architect-reviewer` |

## Archive Readiness Checklist

<For PASS verdicts only.>

- [ ] All P1 fixes applied
- [ ] `openspec validate <change-slug>` passes
- [ ] Implementation complete and tests green
- [ ] **Every AC has a named verification artifact that runs green in the
      project's standard test command** — AC Verification Policy
      (`docs/workflow/acceptance-criteria.md`) satisfied
- [ ] P2 items documented as open questions in `proposal.md` or deferred
      to a follow-up change
- [ ] Ready to run `/opsx:archive`
```

---

## Handoff

- **PASS / PASS WITH WARNINGS (no P1)** — tell the user to commit artifacts,
  run `openspec validate <change-slug>`, then `/opsx:apply`.
- **PASS WITH WARNINGS (with P1)** — fix P1 items, re-run only the listed
  reviewers, then re-run `review-synthesizer`.
- **FAIL** — address all P1 fixes (use `spec-generator` for targeted
  corrections), re-run the listed reviewers, then re-run
  `review-synthesizer`.
