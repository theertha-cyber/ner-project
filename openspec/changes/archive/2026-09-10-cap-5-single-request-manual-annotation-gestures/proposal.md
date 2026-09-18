## Why

A single manual annotation gesture currently reaches the portal save path twice: token click handling and document mouseup handling both create the same span. This causes duplicate persisted annotations and must be corrected without changing annotation semantics.

## What Changes

- Coordinate token click and document mouseup handling so each click or drag gesture creates at most one span.
- Preserve single-token and inclusive, direction-agnostic multi-token range behavior, optimistic rendering, and existing errors.
- Add browser-event regression tests for the actual click/mouseup and drag event sequences.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `annotation-workspace`: manual annotation gestures issue one create-span request per gesture.
- `drag-annotation`: multi-token drag completion remains inclusive and emits one request.
- `portal-annotation`: portal event coordination prevents duplicate span creation.

## Impact

Changes are limited to `src/portal/src/components/annotation/AnnotationPage.tsx` and its focused tests. The existing span API contract and backend persistence are unchanged.

## Open Questions

- None; the approved decomposition defines the required behavior and out-of-scope boundaries.
