---
name: spec-generator
description: >
  Generates a complete, OpenSpec-compliant change folder for a given
  sub-module — `proposal.md`, `design.md`, delta `spec.md`, and `tasks.md` —
  from a `feature-decomposer` output plus the original requirement
  documents. Selects and applies the relevant microservice architecture
  patterns (Database-per-service, CQRS, Saga, Outbox, Idempotency, Retries,
  Circuit Breaker, Bulkheads, Cache-aside / Read-through / Write-through,
  Cache Invalidation) based on the sub-module's requirements and the
  existing architecture. Every Acceptance Criterion emitted has a paired
  executable verification artifact (AC Verification Policy). Trigger
  phrases: "generate spec", "create openspec change", "write spec for",
  "spec-generator".
version: "2.0"
license: MIT
---

# Spec Generator

Turns a single sub-module entry (from `feature-decomposer`) plus the source
requirement documents into a complete OpenSpec change folder, ready to
commit and apply with `/opsx:apply`.

---

## Inputs

1. **Sub-module entry** (SM-NN block) from `feature-decomposer` output.
2. **Original requirement documents**.
3. **OpenSpec domain** (from the sub-module's "OpenSpec Domain" field).
4. **Change slug** (kebab-case name for `openspec/changes/<slug>/`).
5. **Architecture context** (strongly recommended) —
   `project.md`, `openspec/specs/`, ADRs, architecture docs.

If items 1–4 are missing, ask before proceeding. If item 5 is missing,
state assumptions explicitly in `proposal.md` and flag them as open
questions.

---

## Invariant — AC Verification Policy

Every Acceptance Criterion in the delta spec and in `tasks.md` **MUST** be
paired with at least one executable verification artifact that fails when
the AC's `THEN` clause is violated. Allowed artifact types: unit,
integration, contract, property-based tests. Pick the narrowest layer
that can observe the `THEN` clause.

This is built into the tasks you generate — not something reviewers add
later. See `docs/workflow/acceptance-criteria.md` for the full policy
(allowed artifact types, what "satisfied" means, enforcement points).

For every functional task you emit:

- Name the verification artifact (test file path + test case name) for
  every listed acceptance criterion.
- Include a "Must fail if" note describing the mutation of the `THEN`
  clause that the artifact would detect.
- If the task cannot be verified by an automatable test, **stop** — either
  rewrite the AC so it can, or surface it as an open question in
  `proposal.md`. Do not emit an AC with no verification artifact.

---

## Step 0 — Pattern Selection

Before drafting any artifact, reason explicitly about which microservice
patterns apply. This drives `design.md` and the delta spec scenarios.

### 0.1 — Load the pattern reference

The canonical decision criteria for every pattern live in
**`docs/architecture/microservice-patterns.md`**. Load that file now.
It defines, per pattern, when it applies, when it doesn't, and what the
design implication is. **Do not reinvent these rules — use that document.**

Patterns to evaluate (grouped as in the reference doc):

| Group | Patterns |
|---|---|
| **A — Data isolation** | Database-per-service |
| **B — Command/Query separation** | CQRS |
| **C — Distributed transactions** | Saga (Choreography), Saga (Orchestration), Outbox, Idempotency |
| **D — Resilience** | Timeouts, Retries with Backoff, Circuit Breaker, Bulkheads |
| **E — Caching** | Cache-aside, Read-through, Write-through, Cache Invalidation |

### 0.2 — Extract architectural context

From the inputs, establish: service topology, messaging infrastructure,
data stores per service, existing resilience patterns, caching
infrastructure, explicit constraints or non-goals.

### 0.3 — Decide per pattern

For every pattern above, record: **Applied**, **Not applicable**, or
**Already in place** (existing infrastructure covers it — no new spec
work), plus a one-sentence rationale referencing
`docs/architecture/microservice-patterns.md`.

### 0.4 — Pattern Selection Log (first section of design.md)

```markdown
## Pattern Selection Log

| Pattern | Decision | Rationale |
|---|---|---|
| Database-per-service | Applied / Not applicable / Already in place | <one sentence> |
| CQRS | ... | |
| Saga (Choreography) | ... | |
| Saga (Orchestration) | ... | |
| Outbox | ... | |
| Idempotency | ... | |
| Timeouts | ... | |
| Retries | ... | |
| Circuit Breaker | ... | |
| Bulkheads | ... | |
| Cache-aside | ... | |
| Read-through | ... | |
| Write-through | ... | |
| Cache Invalidation | ... | |

**Applied patterns**: <comma-separated list>
**Architectural assumptions**: <list or "None">
```

Every **Applied** pattern must have a dedicated section in `design.md` and
at least one SHALL + scenario in the delta spec.

---

## Output layout

```
openspec/changes/<change-slug>/
├── proposal.md
├── design.md
├── specs/
│   └── <openspec-domain>/
│       └── spec.md
└── tasks.md
```

---

## Artifact skeletons

### `proposal.md`

```markdown
# Proposal: <Sub-Module Human Name>

## Intent
<Why this exists — business or user goal.>

## Scope
### In Scope
- <item>
### Out of Scope
- <item — prevents scope creep>

## Approach
<High-level description. Name the patterns selected and why they fit.>

## Microservice Patterns Applied
| Pattern | Justification |
|---|---|

## Assumptions
- <System, data, or environment assumptions.>

## Open Questions
- <Decisions needed before or during implementation.>
```

### `design.md`

```markdown
# Design: <Sub-Module Human Name>

## Pattern Selection Log
<Section 0.4 table — always first.>

## Architecture Overview
<Text diagram or prose: this service, its data store, interactions with
other services / queues / caches.>

## Data Model / Schema Changes
<Tables, types, outbox tables, read-model projections, cache-key schemas.
Note ownership boundaries if Database-per-service applies.>

## API / Interface Contracts
<Endpoints, message schemas, event shapes, command/query interfaces.
Separate command API from query API if CQRS applies.>

## Resilience Design
<Only if Timeouts / Retries / Circuit Breaker / Bulkheads applied. Per
pattern: configuration values, fallback behaviour, failure scenarios.>

## Transaction & Consistency Design
<Only if Saga / Outbox / Idempotency applied.
  Saga: step-by-step flow + compensating transactions.
  Outbox: table schema, relay mechanism, consumer deduplication.
  Idempotency: key strategy, dedup store, TTL.>

## Caching Design
<Only if any caching pattern applied. Per pattern: key schema, TTL,
eviction, invalidation triggers, consistency window, cache-unavailability
fallback.>

## Error Handling
<Transient vs. permanent, caller-facing responses, logging, alerting.>

## Security Considerations
<Auth, input validation, data exposure, secrets.>

## Observability
<Metrics, traces, log events. Must cover pattern-specific signals: retry
counts, cache hit/miss rates, circuit-breaker state, outbox relay lag,
saga step completion/failure.>

## Dependencies on Other Changes
<SM-NN references and what specifically is needed from each.>
```

### `specs/<domain>/spec.md` (delta spec)

Use only `ADDED` / `MODIFIED` / `REMOVED` sections. Include
pattern-specific requirements **only for Applied patterns**, substituting
concrete values from the design.

```markdown
# Delta for <OpenSpec Domain> — <Sub-Module Human Name>

## ADDED Requirements

### Requirement: <Functional Requirement>
The system SHALL <concrete, testable behaviour>.

#### Scenario: <Happy path>
- GIVEN <precondition>
- WHEN <action>
- THEN <observable outcome>

#### Scenario: <Failure / edge case>
- GIVEN ...
- WHEN ...
- THEN ...

## MODIFIED Requirements
<!-- Only if modifying existing source-of-truth requirements. -->

## REMOVED Requirements
<!-- Only if explicitly removing behaviour. -->
```

**Pattern-specific requirements** — one example shown below; replicate the
same shape for every Applied pattern, with THENs that are directly
observable (metric emitted, state transition, event published, etc.):

```markdown
### Requirement: Idempotent <Operation>   [Idempotency]
The system SHALL process a duplicate <operation> with the same idempotency
key without re-executing it, and SHALL return the original response.

#### Scenario: Duplicate within TTL
- GIVEN <operation> succeeded with idempotency key K
- WHEN the same request arrives again with key K within TTL T
- THEN the original response is returned
- AND no side effects (DB writes, events, external calls) are produced

#### Scenario: Key expired
- GIVEN key K's TTL has elapsed
- WHEN the same request arrives with key K
- THEN the system treats it as a new request
```

Analogous pattern requirement shapes:

| Pattern | Requirement name | Key scenarios |
|---|---|---|
| Circuit Breaker | `<Downstream> Circuit Breaker` | Circuit opens after N failures; fallback returned; half-open probe closes circuit |
| Cache-aside / Read-through | `<Entity> Cache Consistency` | Cache hit; cache miss repopulates; invalidation on write (if applied) |
| Write-through | `<Entity> Write-through Consistency` | Write updates both cache and DB; failure path defined |
| Saga | `<Saga> Atomicity` | All steps succeed; step N fails → compensation in reverse order; crash mid-saga resumes |
| Outbox | `Reliable <Event> Publication` | Same-tx outbox write; crash-before-relay → exactly-once; consumer deduplicates |
| Retries | `<Operation> Transient Failure Retry` | Transient → retry succeeds; all retries exhausted → error; non-retryable → immediate failure |
| Bulkheads | `<Caller> / <Dependency> Isolation` | One pool saturated does not starve others; overflow behaviour defined |

### `tasks.md`

```markdown
# Tasks: <Sub-Module Human Name>

## Implementation Checklist
- [ ] T01: <task>
- [ ] T02: <task>
- ...

## Task Details

> Every task below MUST follow the AC Verification Policy
> (`docs/workflow/acceptance-criteria.md`): every Acceptance Criterion
> must be paired with a named, automatically executable verification
> artifact with a "Must fail if" note describing the THEN mutation it
> would detect.

### T01: <Functional Task>
**Files affected**: `<path>`
**Description**: <Concrete implementation detail.>
**Acceptance criteria**:
- AC-01: <Testable condition tied to a spec scenario — phrased so the
  THEN is directly observable.>

**Verification artifacts** (one per AC):
- AC-01 → `<test-file-path>::<test-case-name>` (layer: unit | integration | contract | property-based)
  - Must fail if: <one sentence describing how the THEN is violated>
```

**Pattern tasks** — include one per Applied pattern. Each task specifies
files affected, concrete implementation detail, ACs tied to the pattern's
spec scenarios, and verification artifacts per AC. Use the scenario names
in the pattern table above as the ACs to verify (e.g., for Outbox: same-tx
write, crash-before-relay exactly-once, consumer dedup).

Always include a final **Observability Instrumentation** task covering
every pattern-specific signal identified in `design.md`: retry counters,
cache hit/miss, circuit-breaker state, outbox relay lag, saga step
start/complete/fail.

---

## Workflow

1. Read all inputs (including architecture context).
2. Run Pattern Selection — produce the Pattern Selection Log.
3. Draft `proposal.md`.
4. Draft `design.md` (Pattern Selection Log first, then each Applied-pattern
   section with concrete values: thresholds, TTLs, table names).
5. Draft delta `spec.md` — functional requirements first, then one
   requirement-block per Applied pattern using the table above.
6. Draft `tasks.md` — functional tasks first, pattern tasks second,
   observability task last. **Every AC has a verification artifact and a
   "Must fail if" note.**
7. Run the self-review checklist below.
8. Present all files to the user, labelled by path.
9. Hand off to the reviewer council.

---

## Self-review checklist

- [ ] Pattern Selection Log is the first section of `design.md`.
- [ ] Every **Applied** pattern has a design section with concrete values.
- [ ] Every **Applied** pattern has at least one SHALL + scenario in the
      delta spec.
- [ ] Every pattern scenario has a task with traceable ACs.
- [ ] All scope items in `proposal.md` appear in at least one task.
- [ ] Tasks are ordered with no forward dependencies.
- [ ] Delta spec uses only ADDED / MODIFIED / REMOVED.
- [ ] Out of Scope covers all ambiguous items.
- [ ] Observability task covers all Applied-pattern signals.
- [ ] **Every AC in `tasks.md` has a named verification artifact (test file
      path + test case name)** — per `docs/workflow/acceptance-criteria.md`.
- [ ] **Each verification artifact has a "Must fail if" note** so
      `qa-reviewer` and `dev-reviewer` can confirm it fails on THEN
      violation.

---

## Handoff

> "Commit these artifacts under `openspec/changes/<change-slug>/` and run
> `openspec validate <change-slug>`. Then run the reviewer council in
> order: `ba-reviewer` → `architect-reviewer` → `qa-reviewer` →
> `dev-reviewer` → `review-synthesizer`. Address all FAIL verdicts before
> `/opsx:apply`."
