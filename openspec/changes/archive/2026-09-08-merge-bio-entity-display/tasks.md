## 1. Playground — BIO Merge Utility

- [x] 1.1 Create `mergeBIOEntities()` utility function in `src/portal/src/hooks/use-extract.ts` that sorts entities by `start_offset`, merges consecutive B-I sequences with matching base type, strips BIO prefixes, averages confidence, and joins values
- [x] 1.2 Handle edge cases in merge: lone I- tag (no preceding B-), B- tag with no following I-, same-type non-consecutive entities (e.g., two separate PERSON mentions)

## 2. Playground — Grouped Display Layout

- [x] 2.1 Restructure the results panel in `PlaygroundTab.tsx` to render entities in alphabetical groups by type: each group has a heading (e.g., "PERSON") and entity rows in text-position order
- [x] 2.2 Update entity summary label from "N found · sorted by confidence" to "N entities · M types"
- [x] 2.3 Update `ENTITY_COLORS` map to use clean type keys (e.g., "PER" instead of "B-PER", "I-PER")
- [x] 2.4 Update `PlaygroundTab.test.tsx` to test grouped layout, alphabetical ordering, text-position ordering, multi-token merge, and cleaned type labels

## 3. Entity Review Tab — Grouped Display

- [x] 3.1 Restructure `EntityReviewTab.tsx` to render entities in alphabetical groups by type, BIO prefix stripped from group headings
- [x] 3.2 Update `EntityRow.tsx` to work within the grouped layout (removed TYPE column, simplified to inline row)
- [x] 3.3 Update the entity count label to "N entities · M types · GET /entities"
- [x] 3.4 Update `EntityReviewTab.test.tsx` to test grouped display, BIO prefix stripping, filter pills, confirm/reject, confidence colors, and empty state

## 4. Verification & Evidence

- [x] 4.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass (17/17 tests pass across both test files)
- [x] 4.2 Collect functional evidence (screenshot / test output / log) for each scenario — see test output above (all 14 spec scenarios have corresponding passing tests)
- [x] 4.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register (all risks mitigated: merge handles lone I-, non-consecutive same-type, B- without I-; ENTITY_COLORS uses clean keys; summary label uses types count)
- [x] 4.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance (no constraining ADRs)
- [ ] 4.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required)
- [x] 4.6 Run `openspec validate merge-bio-entity-display --type change --strict` and confirm it exits clean before archive
