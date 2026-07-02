## Why

The pre-label feature currently uses the entity type name (e.g., `"institute"`) as the keyword to search for in documents, instead of using the actual examples the user provided during entity type creation (e.g., `"Vellore Institute of Technology"`). This makes pre-labeling produce no meaningful results — it searches for the wrong thing entirely.

## What Changes

- Modify `POST /api/v1/documents/{doc_id}/prelabel` to read the `examples` column from `entity_definitions` instead of deriving keywords from `base_label_mapping` values
- Change regex matching from case-sensitive to case-insensitive (`re.IGNORECASE`)
- Implement longest-match-wins deduplication: when multiple examples overlap at the same position, the longest matching phrase is kept and shorter ones are discarded
- Update the portal-annotation frontend spec if needed to reflect changed behavior
- Update tests to match the new keyword source and matching behavior

## Capabilities

### New Capabilities

*(none — this is a fix to an existing capability)*

### Modified Capabilities

- `annotation-workspace`: Pre-labeling requirement changes — the keyword source changes from `base_label_mapping` values to the entity type's `examples` field, and matching becomes case-insensitive with longest-match-wins overlap resolution.

## Impact

| Area | Impact |
|---|---|
| `src/annotation_service/api/v1/spans.py` | `prelabel_document()` — SQL query changes, keyword extraction logic changes, regex flags change |
| `tests/test_annotation_workspace.py` | Pre-label tests (`test_7_6` through `test_7_9`) need updated fixtures and assertions to use `examples` instead of `base_label_mapping` |
| `openspec/specs/annotation-workspace/spec.md` | Pre-labeling requirement text and scenarios updated to reflect new keyword source |
| Portal UI | No changes needed — the UI already sends `examples` in the entity type payload, and the pre-label button flow is unchanged |

## Open Questions

- Should a minimum example length be enforced (e.g., ignore examples shorter than 3 characters) to avoid noise from single-letter or very short matches?
