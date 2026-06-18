---
name: feature-decomposer
description: >
  Analyzes requirements (from user input or a document) through collaborative
  brainstorming, fills gaps, explores the codebase, and decomposes the result
  into independently implementable specs. Each spec includes its name, NFRs,
  constraints, assumptions, the exact requirement slice it covers, and evidence
  for that slice. Trigger phrases: "decompose this feature", "break down
  requirements", "split into specs", "plan features from this doc".
version: "2.0"
license: MIT
---

# Feature Decomposer

Turns raw requirements into a set of well-scoped, evidence-backed specs through
a two-phase process: **brainstorm first, decompose second**. Do not produce any
decomposition output until the brainstorming phase is complete and the user has
confirmed the understanding is correct.

---

## Phase 1 — Brainstorm

The goal of this phase is to deeply understand the requirements before carving
them up. Think of yourself as a curious thinking partner, not a task executor.

### 1.1 Gather inputs

The user will either:
- Paste requirements directly into the conversation, or
- Point you to a file (e.g. `docs/requirements/feature-x.md`).

If a file path is given, read it before doing anything else. Also run:

```bash
openspec list --json
```

to check whether any active changes already exist that might overlap with these
requirements.

### 1.2 Explore the codebase (when relevant)

Before asking questions, get grounded in reality. Look for:

- Existing patterns that the feature must fit into (auth, error handling, data
  models, API conventions).
- Integration points — what will the new feature touch?
- Gaps between what the requirements assume and what already exists.

Use ASCII diagrams freely when they help clarify what you find:

```
EXISTING SYSTEM (example sketch)
══════════════════════════════════════════

  ┌──────────┐    REST     ┌──────────────┐
  │  Client  │ ──────────▶ │  API Server  │
  └──────────┘             └──────┬───────┘
                                  │ SQL
                           ┌──────▼───────┐
                           │     DB       │
                           └──────────────┘

  New feature likely touches: API Server + DB
  Auth layer: currently JWT middleware on all routes
```

### 1.3 Ask clarifying questions — one at a time

Surface gaps, ambiguities, and hidden assumptions. Ask **one question per
message**. Prefer multiple-choice questions when possible, but open-ended is
fine when the space is genuinely open.

Good questions to consider (pick what's relevant — don't recite the full list):

- What does success look like for this feature? (user-visible outcome)
- Who are the actors? (end user, admin, external system, background job?)
- What are the hard constraints? (deadline, tech stack, compliance, scale)
- What is explicitly out of scope?
- Are there edge cases the requirements don't mention?
- Does this feature replace existing behaviour, or extend it?
- What failure modes matter most?

**Do not move to Phase 2 until you have asked the questions that matter and the
user has confirmed the understanding is correct.** A short summary before
transitioning is recommended:

```
## What we understand so far

**Core goal**: <one sentence>
**Key constraints**: <bullet list>
**Confirmed out of scope**: <bullet list>
**Open questions resolved**: <list>
**Remaining uncertainty**: <if any>

Ready to decompose? (yes / no / let's keep exploring)
```

---

## Phase 2 — Decompose

Only begin this phase after the user confirms the understanding in Phase 1 is
correct.

### 2.1 Identify spec candidates

A good spec has:

- A **single domain boundary** — one logical area of the system.
- An **independently testable surface** — an endpoint, a UI component, a
  background worker, a data migration.
- **Explicit contracts** with other specs (types, API schemas, events, DB
  tables) rather than shared mutable state.
- A realistic scope: one OpenSpec change cycle.

Aim for **3–8 specs** per feature. If a scope description contains "and",
that's a signal to split further.

### 2.2 Map dependencies

List prerequisites and shared contracts for each spec. Dependencies must be
acyclic. Represent them as an ordered list or a text DAG:

```
DEPENDENCY MAP (example)
════════════════════════
  [SP-01] DB schema        ◀─── no deps
       │
       ▼
  [SP-02] API endpoints    ◀─── depends on SP-01
       │
       ▼
  [SP-03] UI components    ◀─── depends on SP-02
```

### 2.3 Produce the decomposition output

Use the exact structure below so downstream tools can consume it without
ambiguity.

---

## Output format

```markdown
# Feature Decomposition: <Feature Name>

## Summary
<One paragraph: what this feature does and what this decomposition covers.>

## Source Documents
<List of documents and/or inline requirement text analysed.>

## Brainstorm Notes
<Key decisions, resolved ambiguities, and confirmed scope from Phase 1.
Include any important codebase findings that shaped the decomposition.>

---

## Specs

### [SP-01] <Spec Name>

**Domain**: `<suggested-openspec-domain-slug>`

**Scope**
<1–3 sentences: exactly what this spec covers and where it stops.>

**Requirement Coverage**
<Quote or closely paraphrase the exact portion of the requirement this spec
addresses. If the requirement was given inline, reproduce the relevant
fragment. If it came from a file, cite the section/line.>

**Evidence**
<Why does this spec address that requirement? What behaviour, output, or
system state would demonstrate that the requirement is satisfied?>

**NFRs**
- <Non-functional requirements that apply to this spec specifically —
  performance targets, security constraints, accessibility, scalability, etc.
  If an NFR applies to all specs it should also appear in Cross-Cutting
  Concerns below.>

**Constraints**
- <Hard limits: tech stack, third-party APIs, regulatory rules, backward
  compatibility, time.>

**Assumptions**
- <What we are taking as true without explicit confirmation. Flag anything
  that could invalidate this spec if the assumption is wrong.>

**Contracts / Interfaces**
<Types, API endpoints, events, or DB tables this spec defines or consumes.>

**Prerequisites**: None | [SP-NN], [SP-NN]

**Implementation Notes**
<Caveats, risks, tech choices, or gotchas worth flagging before work starts.>

---

### [SP-02] ...

---

## Dependency Order (Suggested Implementation Sequence)

Wave 1 (no prerequisites): SP-01, SP-02
Wave 2 (depends on Wave 1): SP-03
Wave 3 (depends on Wave 2): SP-04

## Cross-Cutting Concerns
<NFRs, shared utilities, or patterns that span multiple specs — auth
middleware, error-handling conventions, logging standards, shared types.
Each relevant spec should reference these.>

## Recommended Next Step
Run the `spec-generator` skill, passing this decomposition and the original
requirement documents. Start with Wave 1 specs to unblock downstream work.
```

---

## Persist the output

- Derive a kebab-case filename from the feature name
  (e.g., `user-authentication.md`).
- Create `docs/decomposition/` if it does not already exist.
- Write the full output to `docs/decomposition/<feature-name>.md`.
- If a file with that name already exists, append a numeric suffix
  (`-2`, `-3`, …) rather than overwriting.
- Confirm the written path to the user.

---

## Quality checks before outputting

- Every requirement in the source maps to at least one spec.
- No spec duplicates another.
- Dependencies are acyclic.
- Each spec can be described in a single paragraph.
- Every spec has populated Requirement Coverage and Evidence sections — not
  left blank or filled with placeholders.
- `docs/decomposition/<feature-name>.md` exists and is complete.

---

## Key principles

- **Brainstorm before you decompose** — never skip Phase 1.
- **One question at a time** — don't overwhelm; let answers shape the next
  question.
- **Grounded in the codebase** — explore what exists before assuming anything.
- **Evidence-backed** — every spec must justify why it satisfies its
  requirement slice, not just assert it.
- **YAGNI ruthlessly** — if a requirement doesn't exist, don't invent a spec
  for it.
- **Visual when helpful** — ASCII diagrams clarify architecture and
  dependencies better than prose.
- **No implementation** — this skill produces specs, not code.