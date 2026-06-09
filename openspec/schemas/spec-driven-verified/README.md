# spec-driven-verified OpenSpec Schema

`spec-driven-verified` is a spec-driven workflow for changes that need
the full proposal-to-tasks pipeline **plus** a durable, auditable verification
plan that proves the implementation matches its specifications before the
change is archived.

It extends `spec-driven-with-adr` with a `verification.md` gate artifact that
must be completed by a human reviewer — not an AI agent — before archive is
permitted.

---

## When to use this schema

- **Good fit:** Any change where you need evidence that AI-generated output
  matches the specification — feature additions, behaviour changes, API
  contracts, cross-module work, or any change flagged for security/compliance
  review.
- **Not a good fit:** Docs-only edits, dependency bumps, or simple refactors
  where specs and behaviour are not changing.

---

## Stage Gates

Artifact pipeline:

```text
proposal → specs → design → adr → verification → tasks
```

| Artifact | Gate Expectation |
|----------|-----------------|
| `proposal` | States WHY, lists capabilities, identifies open questions |
| `specs` | One delta spec per capability; every scenario uses GIVEN/WHEN/THEN |
| `design` | Accounts for in-force ADRs; explains decisions and trade-offs |
| `adr` | Durable decisions recorded in `docs/adr/ADR-NNN-<title>.md`; immutable once accepted |
| `verification` | Every spec scenario mapped; hallucination risks identified; evidence requirements defined |
| `tasks` | Planned only after all upstream artifacts complete; includes a required Verification & Evidence group |

`verification.md` is a **hard gate** — the change cannot be archived until:
1. The Evidence Log (§5) is populated with real evidence.
2. The Audit Record (§6) is signed off by a human reviewer.

---

## Activate

Set this in `openspec/config.yaml`:

```yaml
schema: spec-driven-verified
```

Validate:

```bash
openspec schema validate spec-driven-verified
```

---

## Change folder structure

```
openspec/changes/<change-slug>/
├── proposal.md       — why, what, capabilities, open questions
├── specs/
│   └── <capability>/
│       └── spec.md   — delta spec (ADDED / MODIFIED / REMOVED only)
├── design.md         — how to implement; decisions and trade-offs
├── verification.md   — spec alignment, hallucination risks, evidence gate ← NEW
└── tasks.md          — implementation checklist + required Verification & Evidence group
```

ADRs are written to `docs/adr/ADR-NNN-<title>.md` (outside the change folder),
not inside `openspec/changes/<change-slug>/`.

---

## verification.md sections

| Section | Purpose | Filled by |
|---------|---------|-----------|
| §1 Spec Alignment | Every requirement + scenario mapped to an acceptance criterion | Agent |
| §2 Hallucination Risk Register | Areas where AI might deviate from spec | Agent |
| §3 Pattern & ADR Compliance | In-force ADRs and verification steps | Agent |
| §4 Evidence Requirements | Checkboxes — what must be collected | Agent (defines items) |
| §5 Evidence Log | Actual evidence collected | Human reviewer |
| §6 Audit Record | Sign-off before archive | Human reviewer (mandatory) |

---

## ADR conventions

- Filename: `ADR-NNN-<kebab-title>.md` (e.g., `ADR-042-use-postgres-for-catalog.md`)
- Location: `docs/adr/` (project root-relative)
- Immutable once accepted — supersede with a new ADR, never edit the prior file
- Governance rules: `docs/architecture/adr-discipline.md`

---

## Spec format

Delta specs use OpenSpec merge headers so the archive merger can apply them:

```md
## ADDED Requirements

### Requirement: User can export data

The system SHALL allow users to export their data in CSV format.

#### Scenario: Successful CSV export

- **GIVEN** a logged-in user with saved records
- **WHEN** the user requests CSV export
- **THEN** the system returns a CSV file containing all the user's records
```

Use `SHALL` (mandatory), `SHOULD` (recommended), or `MAY` (optional).
Every `#### Scenario:` block must be traceable to a row in `verification.md §1`.

---

## Related documentation

- `docs/workflow/openspec-artifacts.md` — OpenSpec artifact locations and delta spec rules
- `docs/workflow/acceptance-criteria.md` — AC verification policy and enforcement
- `docs/architecture/adr-discipline.md` — ADR immutability and enforcement rules
- `docs/agents/reviewer-council.md` — Reviewer council gates before archive
