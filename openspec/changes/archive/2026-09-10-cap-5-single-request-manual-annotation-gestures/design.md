## Context

The portal currently handles a single manual annotation through two browser
event paths: token click and document-level mouseup. A click can therefore
submit the same single-token span twice, while drag completion must continue to
submit one inclusive range. The API and persistence contract are unchanged;
the fix is confined to client-side event coordination and regression tests.

## Goals / Non-Goals

**Goals:**

- Ensure each single-token click and multi-token drag emits at most one span
  create request.
- Preserve optimistic rendering, error rollback, single-token boundaries, and
  direction-agnostic inclusive drag ranges.
- Test the actual click/mouseup and drag browser-event sequences.

**Non-Goals:**

- No API, database, idempotency-table, migration, authentication, or annotation
  semantic changes.
- No historical duplicate cleanup or UI redesign.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|------------------|--------------------------|
| ADR-004 | OpenSpec governs implementation through reviewed artifacts and verification. | Implement only after the change tasks and verification are complete. |
| ADR-011 | Annotation saves use layered idempotency, with client coordination as an early layer. | Remove duplicate client dispatch without replacing the API contract. |
| ADR-012 | Annotation save fixes require the annotation deployment to be recreated. | No new deployment topology is introduced by this client-only fix. |

## Decisions

### Decision 1: Keep one canonical save path per gesture

**Choice:** Treat a multi-token range as the document mouseup path's responsibility
and ensure the token click path is not also eligible after a drag. Treat a
same-token gesture as the token click path's responsibility and do not invoke it
again from mouseup.

**Rationale:** This preserves the existing range calculation and optimistic
save behavior while removing only the duplicate dispatch. It also avoids API
changes and keeps failure handling identical.

**Alternatives considered:**
- Add API/database idempotency keys — out of scope for this capability and would
  not prevent redundant client requests.
- Remove click handling entirely — would make a normal single-token click
  dependent on drag state and risk changing established behavior.

## Risks / Trade-offs

- [Browser event ordering differs across input devices] → Regression tests
  explicitly dispatch the click/mouseup sequence and the drag sequence; guard
  state is reset after each mouseup.
- [A failed optimistic save could leave stale coordination state] → Keep the
  existing `finally` cleanup and reset gesture state before network work.

## Migration Plan

Update `AnnotationPage.tsx`, add focused browser-event regression tests, run the
portal test command and strict OpenSpec validation, then archive and merge the
change branch. Rollback is a normal revert of the client commit; no migration
or data rollback is required.

## Open Questions

None.
