# Verification Plan

**Change:** merge-bio-entity-display
**Generated:** 2026-07-16
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | portal-extraction-page | Playground Tab — Real-time Extraction | Running extraction displays results grouped by type | Given text in textarea, when user clicks Run, then entities are displayed grouped alphabetically by type with clean labels | `PlaygroundTab.test.tsx`: "calls POST /api/v1/extract, disables button during request, renders grouped entities on 200" | - [ ] |
| 2 | portal-extraction-page | Playground Tab — Real-time Extraction | Multi-token entities are merged into a single row | Given B-PER "Steve" and I-PER "Jobs", when displayed, then one row shows "Steve Jobs" under PERSON with confidence 0.975 | `PlaygroundTab.test.tsx`: "merges multi-token entities with average confidence" | - [ ] |
| 3 | portal-extraction-page | Playground Tab — Real-time Extraction | Groups are ordered alphabetically | Given PER, ORG, LOC entities, when rendered, then LOC group appears first, then ORG, then PER | `PlaygroundTab.test.tsx`: "renders groups in alphabetical order" | - [ ] |
| 4 | portal-extraction-page | Playground Tab — Real-time Extraction | Entities within a group are ordered by text position | Given entities at offsets 10, 5, 20, when the group renders, then order is 5 → 10 → 20 | `PlaygroundTab.test.tsx`: "orders entities within a group by start_offset" | - [ ] |
| 5 | portal-extraction-page | Playground Tab — Real-time Extraction | Playground shows spinner in results panel during in-flight request | Given a request is in-flight, when results panel renders, then a spinner is visible and previous results are hidden | `PlaygroundTab.test.tsx`: "shows spinner in results panel during in-flight; no previous results shown" | - [ ] |
| 6 | portal-extraction-page | Playground Tab — Real-time Extraction | Playground shows model version from response | Given response includes model_version "3", when displayed, then label reads "model v3 · serving" | `PlaygroundTab.test.tsx`: "updates model version label from response" | - [ ] |
| 7 | portal-extraction-page | Playground Tab — Real-time Extraction | Empty textarea prevents submission | Given textarea is empty/whitespace, when user clicks Run, then no API request is sent | `PlaygroundTab.test.tsx`: "prevents API call when textarea is empty" | - [ ] |
| 8 | portal-extraction-page | Entity Review Tab — Entity Listing and Review | Entity Review tab loads entities with default filter | Given user switches to Entity Review tab, when tab mounts, then GET /api/v1/entities is called and entities are shown grouped by type | `EntityReviewTab.test.tsx`: "GET /api/v1/entities called without reviewStatus param on mount; 'all' pill active" | - [ ] |
| 9 | portal-extraction-page | Entity Review Tab — Entity Listing and Review | Changing filter re-fetches entities | Given all entities shown, when user clicks "unreviewed" pill, then GET /api/v1/entities?reviewStatus=unreviewed is sent and display updates | `EntityReviewTab.test.tsx`: "clicking 'unreviewed' pill triggers GET with reviewStatus=unreviewed" | - [ ] |
| 10 | portal-extraction-page | Entity Review Tab — Entity Listing and Review | BIO prefix is stripped from entity type in display | Given entity with entity_id "B-ORG", when group renders, then heading reads "ORG" | `EntityReviewTab.test.tsx`: "renders entities in grouped layout with BIO prefix stripped from group heading" | - [ ] |
| 11 | portal-extraction-page | Entity Review Tab — Entity Listing and Review | Confirming an entity updates its review status optimistically | Given unreviewed entity, when user clicks confirm, then PATCH is sent and status immediately becomes "confirmed" | `EntityReviewTab.test.tsx`: "confirm button sends PATCH with review_status confirmed, updates optimistically" | - [ ] |
| 12 | portal-extraction-page | Entity Review Tab — Entity Listing and Review | Rejecting an entity updates its review status optimistically | Given unreviewed entity, when user clicks reject, then PATCH is sent and status immediately becomes "rejected" | `EntityReviewTab.test.tsx`: "reject button sends PATCH with review_status rejected, updates optimistically" | - [ ] |
| 13 | portal-extraction-page | Entity Review Tab — Entity Listing and Review | Confidence color coding reflects thresholds | Given confidences 0.94, 0.75, 0.62, when displayed, then 0.94 is green, 0.75 is amber, 0.62 is red | `EntityReviewTab.test.tsx`: "confidence colors — 0.94 good, 0.75 warn, 0.62 bad, 0.90 good (boundary)" | - [ ] |
| 14 | portal-extraction-page | Entity Review Tab — Entity Listing and Review | Empty entity list shows empty state | Given no entities for current filter, when display renders, then empty state message is shown | `EntityReviewTab.test.tsx`: "empty entity list shows empty state message" | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | BIO merge algorithm edge cases | AI may not handle lone I- tags (without preceding B-), or may incorrectly merge non-consecutive same-type entities, or may fail when confidence filtering causes gaps | Review mergeBIOEntities() with test cases: lone I-, mixed types, same-type non-consecutive, gap caused by low-confidence filter |
| 2 | Entity Review tab grouping without offsets | AI may attempt to merge per-token entities from the review tab even though stored entities lack position offsets, producing incorrect grouping | Verify Entity Review tab groups by entity type only (alphabetically) — no B/I merge is attempted unless offset data is present |
| 3 | Color mapping for clean types | AI may forget to update ENTITY_COLORS map from "B-PER"/"I-PER" keys to clean "PER"/"ORG" keys, causing grey dots | Check ENTITY_COLORS in both PlaygroundTab.tsx and EntityReviewTab.tsx for clean type keys only |
| 4 | Confidence sort label removal | AI may keep the old "sorted by confidence" label in the Playground tab instead of replacing with "N entities · M types" | Verify the entity summary label says "N entities · M types" not "sorted by confidence" |

---

## 3. Pattern & ADR Compliance

No constraining ADRs — this is a frontend-only display change.

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Test output showing PlaygroundTab tests pass: grouped display, alphabetically ordered groups, text-position ordering within groups, multi-token merge, spinner states, model version label, empty textarea guard
- [ ] Test output showing EntityReviewTab tests pass: grouped display, BIO prefix stripping, filter pills, confirm/reject, confidence colors, empty state
- [ ] Screenshot or dev server run showing the Playground with "Steve Jobs" merged under PERSON group, groups in alphabetical order
- [ ] Screenshot showing Entity Review tab with entities grouped alphabetically, BIO prefixes stripped

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (BIO merge in hook, grouped layout, average confidence, text-position sort within groups)
- [ ] All ADR compliance steps in Section 3 confirmed — N/A
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code

### Edge Case Evidence

- [ ] BIO merge handles lone I- tag (no preceding B-) — should not crash, should display as standalone entity with stripped type
- [ ] BIO merge handles same-type entities that are not consecutive (e.g., "B-PER Steve" then later "B-PER Tim" — should remain separate)
- [ ] BIO merge handles B- tag without following I- (e.g., single-token entity "B-PER Alice" — should become standalone "PER" entity)
- [ ] ENTITY_COLORS map uses clean type keys (no "B-" or "I-" prefixed keys)

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> archive is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** merge-bio-entity-display
**Proposal:** `openspec/changes/merge-bio-entity-display/proposal.md`
**Spec files reviewed:**
- specs/portal-extraction-page/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [ ] |
| All ADRs in Section 3 verified compliant | - [ ] |
| Spec Alignment table complete (no missing scenarios) | - [ ] |
| Evidence Log populated with real evidence | - [ ] |
| All functional evidence items in Section 4 checked | - [ ] |
| All structural evidence items in Section 4 checked | - [ ] |
| All edge case evidence items in Section 4 checked | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No undocumented patterns used | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause in specs has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and all mitigations confirmed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**
