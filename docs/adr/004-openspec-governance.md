# ADR-004: OpenSpec Spec-Driven Development Governance

**Status**: Proposed

**Date**: 2026-06-04

## Context

The project mandates AI-native delivery: every feature, fix, and enhancement must be traceable from business intent through implementation evidence. Multiple contributors (agents and humans) will work concurrently. Without structured governance, traceability and quality assurance degrade.

We evaluated three approaches:

- **(a) Ad-hoc documentation with code comments**: Lowest overhead but no traceability enforcement. Quality depends on individual discipline.
- **(b) OpenSpec SDD with mandatory artifacts and gates**: Structured pipeline with proposal → design → spec → tasks → evidence → archive. Each gate has entry/exit criteria.
- **(c) Fully formalized specification with formal verification**: Maximum rigor but unsustainable overhead for an agile delivery model.

## Decision

**Adopt OpenSpec Spec-Driven Development (SDD) with mandatory artifact gates** (strategy b).

Pipeline:

| Gate | Artifact | Owner | Exit Criteria |
|---|---|---|---|
| Intent | `proposal.md` | Product Owner + Architect | Success metrics and scope boundaries accepted |
| Design | `design.md` | Architect + Security + MLOps | Covers data isolation, APIs, runtime, model lifecycle, risks, rollback, observability |
| Spec | `spec.md` | Seed Engineer | Testable SHALL statements, Given/When/Then ACs |
| Implementation | `tasks.md` | Seed Engineer | Tasks map to spec; contains tests/migrations/contracts |
| Evidence | `evidence/` | QA + Security + Architect | Test results, validation outputs, model metrics, review notes |
| Archive | — | Architect + Product Owner | Change archived; source-of-truth specs updated |

Trivial changes (typo fixes, dependency bumps) may bypass the full pipeline via an exception list documented in `docs/workflow/sdd-pipeline.md`. Delta-specs handle iterative changes to existing features.

## Consequences

### Positive
- Every delivered slice traceable to approved artifacts.
- Evidence-based quality gates prevent incomplete or untested changes from reaching production.
- New team members can understand feature context from proposal through evidence.
- OpenCode agents automate artifact creation and gate checks.

### Negative
- Overhead for small changes mitigated by exception list.
- Requires discipline to update artifacts as design evolves during implementation.
- Gate review process adds latency to delivery.

### Mitigations
- Exception list for trivial changes documented in SDD pipeline policy.
- Delta-spec mechanism for iterative changes.
- OpenCode agents automate artifact creation and reduce manual overhead.

## Compliance

- Every change MUST have a folder under `openspec/changes/<change-id>/` with required artifacts.
- No code shall be merged to `staging` or `main` without passing the Evidence Gate.
- Archive Gate MUST update source-of-truth specs in `openspec/specs/`.
- Exceptions to the pipeline MUST be documented in `docs/workflow/sdd-pipeline.md`.

## References

- Technical Design Document §2 (Constraints — all feature work must follow OpenSpec SDD)
- Technical Design Document §6.2 (Branch strategy — staging requires Archive Gate)
- Technical Design Document §6.1 (CI/CD Pipeline — deployment gates)
