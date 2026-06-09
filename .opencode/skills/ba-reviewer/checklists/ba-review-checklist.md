---
# BA Review Checklist
# Version: 1.0
#
# HOW THIS FILE IS USED
# The ba-reviewer skill loads this file at the start of every review session.
# Each checklist item is evaluated against the change folder artifacts and the
# original requirement documents. The skill records a status for each item:
#   PASS   — criterion is satisfied
#   WARN   — criterion is partially satisfied or unclear
#   FAIL   — criterion is not satisfied
#
# HOW TO CUSTOMISE
# Add, remove, or modify items to reflect your project's standards.
# - severity: BLOCKER → a FAIL on this item forces the overall verdict to FAIL
# - severity: WARNING → a FAIL on this item forces PASS WITH WARNINGS at most
# - severity: INFO    → recorded but does not affect the verdict
# Do not change item IDs once the checklist is in use — they are referenced
# in review reports. Add new items with the next sequential ID in each section.
#
# SECTIONS
# BA-FR  — Functional Requirements
# BA-NFR — Non-Functional Requirements
# BA-US  — User Story Coverage
# BA-BR  — Business Rules
# BA-SC  — Scope Alignment
# BA-EP  — Existing Feature Parity
# BA-LA  — Stakeholder Language
# BA-AC  — Acceptance Criteria (business perspective)
---

# BA Review Checklist

## Section BA-FR — Functional Requirements

> Verify that every functional requirement falling within the declared
> sub-module scope is represented in the delta spec as a SHALL statement
> with at least one scenario.

| ID | Severity | Checklist Item |
|---|---|---|
| BA-FR-01 | BLOCKER | Every functional requirement from the source documents that falls within the sub-module scope has a corresponding SHALL statement in the delta spec. |
| BA-FR-02 | BLOCKER | No in-scope functional requirement is represented only in `proposal.md` or `design.md` — it must be in the delta spec. |
| BA-FR-03 | BLOCKER | Each SHALL statement is traceable to a specific section or ID in the source requirement documents. |
| BA-FR-04 | WARNING | SHALL statements use precise, unambiguous language — no vague verbs like "handle", "manage", "support", or "deal with". |
| BA-FR-05 | WARNING | Each SHALL statement has at least one GIVEN/WHEN/THEN scenario that exercises the primary success flow. |
| BA-FR-06 | WARNING | Conditional requirements ("if the user is X, then Y") are broken into separate requirements or captured as distinct scenarios, not merged into a single vague statement. |
| BA-FR-07 | INFO | The delta spec does not contain SHALL statements for requirements that belong to a different sub-module's declared scope. |

## Section BA-NFR — Non-Functional Requirements

> Verify that non-functional requirements (performance, reliability,
> availability, compliance, accessibility) in scope are captured.

| ID | Severity | Checklist Item |
|---|---|---|
| BA-NFR-01 | BLOCKER | Every NFR that is explicitly stated in the source documents and falls within this sub-module's scope has a corresponding SHALL statement in the delta spec. |
| BA-NFR-02 | BLOCKER | Performance NFRs include measurable targets (e.g., "P99 latency SHALL be under 200ms at 1000 RPS") — not qualitative statements ("the system SHALL be fast"). |
| BA-NFR-03 | BLOCKER | Availability or reliability NFRs include an explicit SLA figure (e.g., "the service SHALL achieve 99.9% uptime measured monthly"). |
| BA-NFR-04 | WARNING | Compliance or regulatory NFRs (GDPR, PCI-DSS, HIPAA, etc.) are explicitly stated and have scenarios that verify compliance — not just mentioned in passing. |
| BA-NFR-05 | WARNING | Accessibility NFRs for user-facing features (WCAG level, screen reader support) are present if the feature has a UI component. |
| BA-NFR-06 | WARNING | Security NFRs (authentication required, data encryption at rest/in transit, audit logging) are present for any feature handling sensitive data. |
| BA-NFR-07 | INFO | NFRs that cannot be verified at spec time (e.g., load testing targets) are flagged as confirmation criteria in `proposal.md`, not omitted entirely. |

## Section BA-US — User Story Coverage

> Verify that every user story and its acceptance criteria in scope
> are addressed in the delta spec.

| ID | Severity | Checklist Item |
|---|---|---|
| BA-US-01 | BLOCKER | Every user story ("As a <role>, I want <goal>, so that <benefit>") within the sub-module scope has at least one SHALL requirement that covers the stated goal. |
| BA-US-02 | BLOCKER | Every acceptance criterion listed in the original user story has a corresponding GIVEN/WHEN/THEN scenario in the delta spec. |
| BA-US-03 | WARNING | Scenarios are written from the perspective of the user or the observable system outcome — not from the perspective of the implementation ("the database stores…"). |
| BA-US-04 | WARNING | All user roles mentioned in the user stories ("admin", "customer", "guest") appear as explicit GIVEN preconditions in the relevant scenarios. |
| BA-US-05 | INFO | User stories with multiple acceptance criteria have separate, named scenarios for each criterion rather than one omnibus scenario. |

## Section BA-BR — Business Rules

> Verify that domain rules, validation logic, workflow constraints,
> and state machine transitions are explicitly captured.

| ID | Severity | Checklist Item |
|---|---|---|
| BA-BR-01 | BLOCKER | Every business rule stated or implied in the source documents (e.g., "an order cannot be placed if the user's account is suspended") has a SHALL statement in the delta spec. |
| BA-BR-02 | BLOCKER | Every validation rule (field required, format, min/max value, allowed values) has a scenario where invalid input is submitted and the system's rejection response is specified. |
| BA-BR-03 | BLOCKER | State machine transitions are fully specified: every valid transition has a scenario, and at least one invalid transition (attempting to move from an illegal state) has a rejection scenario. |
| BA-BR-04 | WARNING | Boundary values for validation rules are tested in scenarios (e.g., length = exactly max allowed, amount = exactly zero). |
| BA-BR-05 | WARNING | Business rules that interact with each other (e.g., rule A applies unless rule B is also true) are covered by a combined scenario, not just individual scenarios for each rule in isolation. |
| BA-BR-06 | WARNING | Authorisation rules ("only admin users may do X") are present as explicit preconditions in scenarios and as rejection scenarios for unauthorised access. |
| BA-BR-07 | INFO | Business rules that are enforced by the UI only (client-side validation with no server-side enforcement) are flagged as a risk in `proposal.md`. |

## Section BA-SC — Scope Alignment

> Verify that the spec's scope exactly matches the decomposition entry —
> no drift in either direction.

| ID | Severity | Checklist Item |
|---|---|---|
| BA-SC-01 | BLOCKER | Every item listed as "In Scope" in `proposal.md` has at least one SHALL requirement in the delta spec. |
| BA-SC-02 | BLOCKER | The delta spec contains no SHALL requirements for items listed as "Out of Scope" in `proposal.md`. |
| BA-SC-03 | BLOCKER | The scope in `proposal.md` matches the SM-NN entry in the feature decomposition — no new scope has been added without decomposition update. |
| BA-SC-04 | WARNING | The "Out of Scope" section in `proposal.md` explicitly names items that could be ambiguously interpreted as in scope (the "close calls"). |
| BA-SC-05 | WARNING | Open questions in `proposal.md` that affect scope have been resolved or escalated — they are not silently assumed in one direction. |
| BA-SC-06 | INFO | If scope was intentionally narrowed from the decomposition entry, the narrowing is documented in `proposal.md` with a reason. |

## Section BA-EP — Existing Feature Parity

> Verify that existing application features touched by this sub-module
> are not silently broken or omitted.

| ID | Severity | Checklist Item |
|---|---|---|
| BA-EP-01 | BLOCKER | Any existing behaviour that this sub-module's code will touch or replace has a MODIFIED requirement in the delta spec (or an explicit statement in `proposal.md` that the existing behaviour is intentionally removed). |
| BA-EP-02 | BLOCKER | Any existing feature that is "out of scope" but could be affected by this change (e.g., shared data model, shared API endpoint) is listed in `proposal.md`'s assumptions or risks. |
| BA-EP-03 | WARNING | The delta spec does not silently re-implement existing behaviour with different semantics (e.g., changing the meaning of an existing field or status value). |
| BA-EP-04 | WARNING | If the sub-module modifies a shared contract (API response shape, event schema, DB column), the impact on existing consumers is noted in `proposal.md`. |
| BA-EP-05 | INFO | Known regressions that are accepted as part of this change are explicitly documented as "Accepted Regressions" in `proposal.md` with a mitigation plan. |

## Section BA-LA — Stakeholder Language

> Verify that the spec is written in business language that non-technical
> stakeholders can review and validate.

| ID | Severity | Checklist Item |
|---|---|---|
| BA-LA-01 | WARNING | SHALL statements avoid implementation-specific language (no mention of database tables, HTTP methods, queue names, class names) unless the requirement is specifically about that interface. |
| BA-LA-02 | WARNING | GIVEN/WHEN/THEN scenarios are written from the perspective of an actor (user, system, external service) performing an observable action — not from the perspective of internal code execution. |
| BA-LA-03 | WARNING | Domain terms (entity names, status values, role names) are used consistently and match the project's GLOSSARY.md where one exists. |
| BA-LA-04 | INFO | Acronyms and domain-specific terms used in the spec are either self-evident in context or defined in GLOSSARY.md. |
| BA-LA-05 | INFO | The `proposal.md` Intent section is readable by a product manager or business stakeholder with no engineering background. |

## Section BA-AC — Acceptance Criteria (Business Perspective)

> Verify that acceptance criteria in `tasks.md` reflect the business
> requirements — not just technical correctness.

| ID | Severity | Checklist Item |
|---|---|---|
| BA-AC-01 | BLOCKER | Every in-scope functional requirement has at least one acceptance criterion in `tasks.md` that a business stakeholder could independently verify (not just "unit tests pass"). |
| BA-AC-02 | WARNING | Acceptance criteria reference the specific scenario from the delta spec they are verifying (by scenario name or requirement ID). |
| BA-AC-03 | WARNING | Acceptance criteria for user-facing features describe the observable user outcome, not the internal system state (e.g., "the user sees a confirmation message" not "the response body contains `{ success: true }`"). |
| BA-AC-04 | INFO | Each task's acceptance criteria are sufficient to drive a UAT (user acceptance test) session without additional specification. |

---

## Verdict Calculation

The skill applies this logic after evaluating all items:

| Condition | Verdict |
|---|---|
| Any item with severity BLOCKER has status FAIL | **FAIL** |
| One or more items with severity WARNING have status FAIL, no BLOCKER failures | **PASS WITH WARNINGS** |
| All BLOCKER and WARNING items have status PASS | **PASS** |

INFO items are recorded in the report but do not affect the verdict.

---

## Customisation Notes

- To **add** a project-specific rule: append a new row to the relevant section
  table with the next sequential ID (e.g., `BA-FR-08`).
- To **disable** an item that does not apply to your project: add a `disabled`
  column and set it to `true`, or delete the row. Do not change the ID of
  remaining items.
- To **change severity**: edit the Severity column. Document the reason in a
  comment above the row.
- To **add a new section**: follow the existing section format. Register the
  new section prefix in this header comment.
