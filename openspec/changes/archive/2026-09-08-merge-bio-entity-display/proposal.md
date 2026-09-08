## Why

The Playground tab displays extracted entities as individual BIO-tagged tokens (e.g., "B-PER", "I-PER" as separate rows), making multi-token entities like "Steve Jobs" appear as two disconnected rows. This is confusing and doesn't match user expectations — the I- prefix is an implementation detail of the tagging scheme, not something a user should see.

## What Changes

- **BIO tag merge**: In the `use-extract` hook, merge consecutive B-I token sequences into single entities (strip the B-/I- prefix, join values)
- **Grouped display**: The Playground tab will group entities alphabetically by type, with entities within each group ordered by their position in the source text
- **Entity Review tab**: Same grouped layout instead of the flat table — entities grouped alphabetically by type, ordered by position, BIO prefixes stripped
- **No API contract change**: The backend still returns raw BIO labels; merge and grouping happen on the frontend
- **Confidence for merged entities**: Average of the merged token confidences

## Capabilities

### Modified Capabilities

- `portal-extraction-page`: The Playground and Entity Review tab entity display requirements are changing — from a flat sorted list to a grouped-by-type layout with BIO tags merged

## Impact

- `src/portal/src/hooks/use-extract.ts` — add BIO merge logic
- `src/portal/src/components/extractions/PlaygroundTab.tsx` — restructure render to grouped layout
- `src/portal/src/components/extractions/EntityReviewTab.tsx` — restructure render to grouped layout
- `src/portal/src/components/extractions/EntityRow.tsx` — may be simplified or replaced by group rendering
- `src/portal/src/hooks/use-entities.ts` — may need BIO merge logic if entities come with BIO-prefixed types
- Tests in `PlaygroundTab.test.tsx` and `EntityReviewTab.test.tsx` — update to match new layout

## Open Questions

- Should the Entity Review tab's filter pills apply before or after grouping? (e.g., filter by "unreviewed" → only show groups that have unreviewed entities, or show all groups with only unreviewed entities listed)
- Existing batch extraction data has per-token entities stored with BIO-prefixed entity_ids — should we migrate them or leave as-is until re-extraction?
