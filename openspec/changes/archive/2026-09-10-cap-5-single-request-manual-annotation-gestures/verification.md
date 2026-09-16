# Verification Plan

**Change:** cap-5-single-request-manual-annotation-gestures
**Generated:** 2026-09-10
**Status:** Complete for unattended implementation; evidence is collected by the focused portal test run.

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|---|---|---|---|---|---|
| 1 | annotation-workspace | Span CRUD | Create a span | Existing API span creation remains 201 with returned fields. | Existing backend span test suite | - [ ] |
| 2 | annotation-workspace | Span CRUD | List spans | Existing API list behavior remains unchanged. | Existing backend span test suite | - [ ] |
| 3 | annotation-workspace | Span CRUD | Update a span | Existing API update behavior remains unchanged. | Existing backend span test suite | - [ ] |
| 4 | annotation-workspace | Span CRUD | Delete a span | Existing API delete behavior remains unchanged. | Existing backend span test suite | - [ ] |
| 5 | annotation-workspace | Span CRUD | Invalid entity type | Existing API validation remains 422. | Existing backend span test suite | - [ ] |
| 6 | annotation-workspace | Span CRUD | Single-token annotation saved once | Click plus mouseup emits exactly one create request and confirms one span. | Focused browser-event regression test | - [ ] |
| 7 | annotation-workspace | Span CRUD | Multi-token drag saved once | Drag emits exactly one request for the inclusive range. | Focused drag regression test | - [ ] |
| 8 | drag-annotation | Multi-Token Drag Span Creation | Drag across tokens | One request carries the inclusive range and success confirms it. | Focused drag regression test | - [ ] |
| 9 | drag-annotation | Multi-Token Drag Span Creation | Drag preview | Preview appears before mouseup and no request is sent. | Existing drag preview test | - [ ] |
| 10 | drag-annotation | Multi-Token Drag Span Creation | Same-token click | Click/mousedown/mouseup emits exactly one single-token request. | Focused browser-event regression test | - [ ] |
| 11 | drag-annotation | Multi-Token Drag Span Creation | Unarmed drag | No request or preview occurs. | Existing drag guard test | - [ ] |
| 12 | drag-annotation | Multi-Token Drag Span Creation | Confirmed-token drag | Blocked range emits no request. | Existing drag guard test | - [ ] |
| 13 | drag-annotation | Multi-Token Drag Span Creation | Reverse drag | Range is normalized min-to-max. | Existing range-calculation test | - [ ] |
| 14 | portal-annotation | Token-Click Span Creation | Armed click once | Click plus document mouseup emits one request and replaces optimistic ID. | Focused browser-event regression test | - [ ] |
| 15 | portal-annotation | Token-Click Span Creation | Already-spanned token | No request is emitted. | Existing token guard test | - [ ] |
| 16 | portal-annotation | Token-Click Span Creation | API error | Optimistic span reverts and error toast remains. | Existing error-path test | - [ ] |
| 17 | portal-annotation | Token-Click Span Creation | Unarmed click | Inspector behavior remains unchanged. | Existing token click test | - [ ] |

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|---|---|---|
| 1 | Browser event ordering | A fix could remove normal clicks or still let click and mouseup race. | Dispatch the real click/mouseup sequence and count POST calls. |
| 2 | Drag range semantics | A fix could alter inclusive or reverse-direction offsets. | Assert request offsets and text for both drag directions. |
| 3 | Optimistic/error behavior | Coordination changes could skip confirmation or rollback. | Assert optimistic state, response replacement, and failed-request revert. |

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|---|---|---|---|
| ADR-004 | OpenSpec governance | Implement only from reviewed artifacts and retain executable verification. | Validate strict and inspect change lifecycle before archive. |
| ADR-011 | Layered annotation idempotency | Client coordination is an early duplicate-prevention layer; API contract stays unchanged. | Confirm only portal event handling and tests changed. |
| ADR-012 | Recreate annotation deployment for save fix | No new topology is introduced by this client-only change. | Confirm no deployment or service boundary changes are present. |

## 4. Evidence Requirements

### Functional Evidence
- [ ] Focused portal test output covers scenarios 6, 7, 8, 10, and 14.
- [ ] Existing portal/backend tests cover unchanged guards and error behavior.

### Structural Evidence
- [ ] Implementation matches design decisions.
- [ ] ADR compliance confirmed.
- [ ] No undocumented architectural patterns introduced.

### Edge Case Evidence
- [ ] Browser event ordering checked.
- [ ] Inclusive and reverse drag ranges checked.
- [ ] Optimistic confirmation and rollback checked.

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|---|---|---|---|---|
| 1 | Functional | To be populated after focused test run | 6-17 | Ralph | 2026-09-10 |

## 6. Audit Record

**Change slug:** cap-5-single-request-manual-annotation-gestures
**Spec files reviewed:** annotation-workspace, drag-annotation, portal-annotation delta specs.

| Check | Status |
|---|---|
| Design reviewed against proposal | - [ ] |
| ADRs verified compliant | - [ ] |
| Spec alignment complete | - [ ] |
| Evidence log populated | - [ ] |

**Archive approved by:** Ralph unattended gate
**Date:** 2026-09-10
