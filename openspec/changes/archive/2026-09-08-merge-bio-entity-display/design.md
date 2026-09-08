## Context

The extraction Playground tab currently renders entities as a flat list sorted by confidence, showing raw BIO labels (e.g., "B-PER", "I-PER") as entity types. Multi-token entities like "Steve Jobs" appear as two disconnected rows. The Entity Review tab has the same problem — a flat table where "B-PER" and "I-PER" rows for the same entity are separate. Users shouldn't see BIO tagging internals.

## Goals / Non-Goals

**Goals:**
- Merge consecutive B-I token sequences into single entities in the Playground display
- Group entities by type (alphabetically) in both Playground and Entity Review tabs
- Within each group, order entities by their position in the source text
- Strip B-/I- prefixes from entity type labels in the UI
- Show average confidence for merged multi-token entities

**Non-Goals:**
- Changing the backend API response format — the wire format stays as-is
- Modifying how entities are stored in batch extraction
- Adding position/offset tracking to the `extracted_entities` table
- Confidence sort — the current "sorted by confidence" label and sort are being replaced

## Currently-In-Force ADRs

None of the existing ADRs constrain this frontend display change.

## Decisions

### Decision 1: Merge in the frontend hook, not the component

**Choice:** Add a `mergeBIOEntities()` utility function in the `use-extract` hook that transforms the API response before it reaches the component.

**Rationale:** Keeping merge logic in the hook keeps the component pure/declarative. The same utility can be reused in `use-entities` for the Entity Review tab if needed later.

**Alternatives considered:**
- Merge in the backend (`extraction.py`) — would require changing the API contract; ruled out for this phase
- Merge in the component — clutters rendering logic; harder to test

### Decision 2: Grouped layout replaces flat list, not layered on top

**Choice:** The Playground tab will render entity groups as collapsible sections. Each group has an alphabetical heading (e.g., "PERSON") with entities listed underneath in text position order. The old flat-list render path is removed entirely.

**Rationale:** The flat sorted list was the only rendering mode. A grouped layout is a fundamentally different structure — keeping both would add complexity without benefit.

### Decision 3: Average confidence for merged tokens

**Choice:** When merging B-I sequences, the entity confidence is the arithmetic mean of the individual token confidences.

**Rationale:** Fair representation of the whole span. Max would over-represent a single high-confidence token; min would under-represent. Average is intuitive and matches user expectation of "overall" confidence.

**Alternatives considered:**
- Max — could be misleading if one token is confident and another is not
- Min — too pessimistic
- Product of confidences — less intuitive than mean

### Decision 4: Sort within groups by start_offset ascending (text order)

**Choice:** Within a group, entities are ordered by their `start_offset` field (the position of the first token in the source text).

**Rationale:** Natural reading order. A user looking at entities in context can find them in the order they appear.

## Risks / Trade-offs

- [Existing per-token entities in `extracted_entities` table lack position offsets, so the Entity Review tab cannot reliably reconstruct which B-I tokens belong together until the batch worker is fixed to merge before inserting] → For this phase, the Entity Review tab will show entities as-is (per-token) but strip BIO prefixes and group by type. Multi-token entities from old batch runs will still appear as separate rows within the group.

## Migration Plan

Deployable in one frontend PR:
1. Add `mergeBIOEntities()` utility
2. Update `use-extract` hook to use it
3. Rewrite PlaygroundTab render
4. Update tests
5. Deploy — no backend changes needed

Rollback: revert the PR.

## Open Questions

- Entity Review tab filter pills: Does filtering apply before grouping (only showing groups that have matching entities) or after (showing all groups with only matching entities listed)? Needs user input.
