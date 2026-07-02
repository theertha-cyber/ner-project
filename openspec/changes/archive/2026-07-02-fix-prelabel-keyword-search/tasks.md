## 1. Backend — Update prelabel_document() in spans.py

- [x] 1.1 Update the SQL query in `prelabel_document()` to SELECT `name, examples, base_label_mapping` instead of just `name, base_label_mapping`
- [x] 1.2 Replace the keyword derivation logic (lines 295-304): instead of inverting `base_label_mapping` values, iterate entity rows and collect examples from the `examples` JSON column into a `{example_text: entity_type_name}` dictionary
- [x] 1.3 Skip entity types where `examples` is `None`, an empty list, or contains only empty/whitespace strings (minimum 3 chars per example)
- [x] 1.4 Sort the collected `(example_text, entity_type)` pairs by example length descending (longest first) to enable longest-match-wins behavior
- [x] 1.5 Replace the case-sensitive `re.finditer(re.escape(keyword), doc_text)` with case-insensitive `re.finditer(re.escape(keyword), doc_text, re.IGNORECASE)`
- [x] 1.6 Implement overlap detection: maintain a set of kept `(start, end)` ranges; skip any new match whose range intersects any already-kept range (intersection check: `start < existing_end and end > existing_start`)
- [x] 1.7 Ensure `match.group()` preserves original document text casing (not the lowercased example)

## 2. Tests — Update test_annotation_workspace.py

- [x] 2.1 Update `seeded_entity_types` fixture to insert entity types with an `examples` column populated (e.g., `PER` with `examples: ["John Doe", "Alice"]`, `ORG` with `examples: ["Acme Corp"]`)
- [x] 2.2 Update `test_7_6_prelabel_generates_suggestions` to verify suggestions are derived from `examples` column — given document "John Doe works at Acme Corp", expect spans for "John Doe" (PER) and "Acme Corp" (ORG), each with confidence 0.85
- [x] 2.3 Add `test_prelabel_case_insensitive` — given document "JOHN DOE works at ACME CORP", POST /prelabel returns suggestions for both despite case mismatch
- [x] 2.4 Add `test_prelabel_longest_match_wins` — add entity type with overlapping examples `["Apple Inc", "Apple"]` and document "Apple Inc is based here"; verify only "Apple Inc" (0-9) is suggested
- [x] 2.5 Update `test_7_7_prelabel_replaces_existing` to insert a suggestion into `suggested_spans`, then call prelabel and verify old suggestion is gone and new ones exist with correct count
- [x] 2.6 Update `test_7_8_prelabel_list_suggestions` to insert a suggestion manually, then GET `?type=suggested` and verify it returns
- [x] 2.7 Update `test_7_9_prelabel_promote_suggestion` to insert a suggestion, promote it, and verify it moves to confirmed spans table
- [x] 2.8 Add `test_prelabel_empty_examples_skipped` — entity type with `examples: []` or `examples: null` produces no suggestions for that type (no crash)

## 3. Verification & Evidence

- [ ] 3.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass
      *Requires PostgreSQL — run `docker compose up -d db` then `pytest tests/test_annotation_workspace.py -v`*
- [ ] 3.2 Collect functional evidence (test output / log) for each scenario — record one entry per row in verification.md § Evidence Log
      *Blocked on 3.1 — requires test output*
- [x] 3.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register
      *Verified by code inspection (see below)*
- [x] 3.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance
      *No ADRs are formally in force; all 8 are Proposed per design.md*
- [ ] 3.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent)
- [x] 3.6 Run `openspec validate fix-prelabel-keyword-search --type change --strict` and confirm it exits clean before archive
