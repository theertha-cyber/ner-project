## Context

The pre-label endpoint (`POST /api/v1/documents/{doc_id}/prelabel`) currently derives search keywords from the `base_label_mapping` JSON column on `entity_definitions`. This column maps CoNLL classes (PER, ORG, LOC, MISC) to entity type names — it was designed for the real ML pipeline where a model outputs CoNLL labels and the mapping translates them to tenant entity types.

However, the MVP mock uses these mapped entity type names as literal keywords to search for in document text. Since entity type names are typically single, generic words (e.g., `"institute"`, `"vendor_name"`), they rarely appear verbatim in documents with the correct casing. The `examples` column on `entity_definitions` already stores the actual phrases users want to match (e.g., `"Vellore Institute of Technology"`), but it is never read by the pre-label endpoint.

## Goals / Non-Goals

**Goals:**

- Make the MVP pre-label mock use the `examples` column as its keyword source
- Change regex matching from case-sensitive to case-insensitive
- Implement longest-match-wins overlap resolution so overlapping examples produce one suggestion (the longest)
- Update existing test fixtures and assertions to match the new behavior

**Non-Goals:**

- No changes to the `base_label_mapping` column or its schema — it remains for future ML integration
- No changes to the portal UI — the entity type form already sends `examples`
- No changes to the promote, list-suggestions, or replace-suggestions behavior — those stay identical
- No changes to the confirmation confidence value (still `0.85`)

## Currently-In-Force ADRs

No ADRs are formally `ACCEPTED`. All 8 ADRs in `docs/adr/` are in `Proposed` status and represent the team's current design intent. None constrain this design change.

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-002 — Base Model Strategy | Single curated base model (`dslim/bert-base-NER`) | Informational — this change does not affect model strategy |
| ADR-004 — OpenSpec Governance | Mandatory artifact gates | This change follows the spec-driven process |

## Decisions

### Decision 1: Keyword source — use `examples` column instead of `base_label_mapping` values

**Choice:** Read the `examples` JSON column from `entity_definitions` and use each example as a keyword to search for in the document text.

**Rationale:** The `examples` column contains the actual phrases users want to match (entered during entity type creation). The `base_label_mapping` values are entity type names (e.g., `"institute"`), which are useless as search terms. This aligns the MVP mock with user expectations — what you type as an example is what gets found.

**Alternatives considered:**
- Concatenate `examples` + `description` + `name` — adds noise; descriptions are prose, not search terms
- Keep using `base_label_mapping` values but expand them — would require a new UI field, duplicating `examples`

### Decision 2: Case-insensitive matching

**Choice:** Add `re.IGNORECASE` flag to the regex search.

**Rationale:** Document text may have arbitrary capitalization (OCR output, mixed-case user input). "Vellore Institute of Technology" should match whether the document has "Institute" or "institute". Users should not have to predict casing when entering examples.

### Decision 3: Longest-match-wins overlap resolution

**Choice:** Sort examples by descending length before searching. Keep a set of occupied `(start, end)` ranges. Skip any match that overlaps an already-kept match.

**Rationale:** If examples are `["Apple Inc", "Apple"]` and the document says "Apple Inc", we want the full "Apple Inc" span, not two overlapping spans. Processing longest-first ensures the more specific phrase wins naturally without complex interval math.

**Alternatives considered:**
- Fuzzy matching / Levenshtein distance — over-engineered for MVP
- Allow all overlapping matches — creates visual noise and redundant suggestions
- Whole-word boundary (`\b`) — could be added later but may miss legitimate sub-word matches (e.g., "AT&T" has no word boundary before the &)

## Risks / Trade-offs

- [**Short examples produce noisy matches**] → An example like `"a"` or `"an"` would match every occurrence in English text. Mitigation: implicitly enforce a minimum example length (>= 3 characters) in the pre-label code, skipping shorter examples.
- [**Case-insensitive matching may over-match**] → "apple" matching "Apple" is desired; "apple" matching "APPLE" is also desired. This is correct behavior for pre-label suggestions (the annotator reviews and promotes or dismisses).
- [**Performance with many long examples**] → Regex over a full document with dozens of examples is O(n * m) worst case. For MVP document sizes (pages, not books) and typical example counts (< 50), this is negligible.

## Migration Plan

1. Update `prelabel_document()` in `spans.py` to also SELECT `examples` and use those as keywords
2. Apply `re.IGNORECASE` to all regex searches
3. Sort examples by descending length and apply range-based overlap skipping
4. Update test fixtures to populate `examples` instead of relying solely on `base_label_mapping`
5. Run existing tests to confirm they pass with updated fixtures
6. No rollback needed — this is purely an improvement to an MVP feature; old behavior had no users depending on it

## Open Questions

- Should minimum example length be hardcoded (3) or configurable? Hardcoded is simpler for MVP.
Answer: whatever the example is given.
