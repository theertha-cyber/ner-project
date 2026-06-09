# AGENTS.md — Baseline Agent Instructions

> **Read this file first, every session.** It is intentionally short.
> Detailed policy lives in `docs/` and must be loaded on demand — do not
> preload it.

---

## 1. First steps every session

1. Read `PROJECT.md` in the project root. It holds the project-specific
   context (tech stack, service topology, ADRs, conventions) that
   overrides the defaults referenced below. **If `PROJECT.md` does not
   exist, stop and tell the user.**
2. For the task at hand, load only the `docs/` files relevant to it
   (see the router below).

---

## 2. The invariants

This project uses **Spec-Driven Development (SDD)** via OpenSpec. Two
invariants govern everything else:

1. **No code is written before a spec exists and has been reviewed.**
   See `docs/workflow/sdd-pipeline.md` for exceptions and the full
   pipeline. If in doubt, treat it as spec-required.
2. **Every Acceptance Criterion in any `spec.md` must have at least one
   executable verification artifact that fails when the AC's `THEN`
   clause is violated.** See `docs/workflow/acceptance-criteria.md` for
   the full policy (allowed artifact types, what counts as satisfied,
   enforcement points).

---

## 3. Router — where the rules live

Load each file only when the current task matches its "when to read"
column. Do not read them all upfront.

| Topic | File | When to read |
|---|---|---|
| SDD pipeline & exceptions | `docs/workflow/sdd-pipeline.md` | Starting any feature/fix/refactor; deciding if a spec is required. |
| Skills catalog | `docs/workflow/skills-catalog.md` | Choosing which skill to invoke. |
| OpenSpec artifacts & delta-spec rules | `docs/workflow/openspec-artifacts.md` | Creating, validating, or archiving a change. |
| AC verification policy | `docs/workflow/acceptance-criteria.md` | Writing or reviewing ACs; pairing tasks with tests; deciding if an AC is satisfied. |
| Microservice patterns & pattern defaults | `docs/architecture/microservice-patterns.md` | Writing or reviewing any spec that touches service boundaries, resilience, or data ownership. |
| ADR discipline | `docs/architecture/adr-discipline.md` | Proposing, superseding, or enforcing an ADR. |
| Coding standards & commits | `docs/standards/coding-standards.md` | Implementing tasks, writing tests, preparing commits. |
| Context hygiene | `docs/agents/context-hygiene.md` | Running the reviewer council or any multi-step skill chain. |
| Guardrails (NOT-to-do + escalation) | `docs/agents/guardrails.md` | Before any irreversible action, or when uncertain whether to proceed. |
| Project ADRs | `docs/adr/` | When a spec or design references a specific ADR. |
| Feature decompositions | `docs/decomposition/` | Reviewing an existing feature breakdown before spec-generation or implementation planning. |

`docs/README.md` has the same index in a browsable form.

---

## 4. Conflict resolution

When instructions disagree, apply this precedence (highest wins):

```
ADR  >  PROJECT.md  >  AGENTS.md (this file)  >  docs/
```

## 5. When in doubt

Ask the user. Do not assume. Escalation triggers are listed in
`docs/agents/guardrails.md`.

---

## 6. Feature decomposition documents

When the `feature-decomposer` skill is used, it writes a structured
Markdown document to `docs/decomposition/<feature-name>.md`. Each file
contains:

- A one-paragraph feature summary.
- A numbered list of sub-modules (`[SM-01]`, `[SM-02]`, …), each with
  its OpenSpec domain, scope, key requirements, contracts/interfaces,
  prerequisites, and implementation notes.
- A dependency wave table (Wave 1, Wave 2, …) showing the suggested
  implementation sequence.
- A cross-cutting concerns section covering NFRs and shared utilities.

Load the relevant file from `docs/decomposition/` whenever you are
planning spec-generation or implementation for an already-decomposed
feature.
