# Verification Plan

**Change:** fix-chat-page-auth
**Generated:** 2026-06-23
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | chat-ui | Authenticated API calls | Chat page sends authenticated requests | Given an authenticated tenant_admin on the chat page, when the page loads and fetches conversations, then the request includes `Authorization: Bearer <token>` and the gateway accepts it | - [ ] |
| 2 | chat-ui | Authenticated API calls | Unauthenticated chat request returns 401 | Given no valid JWT token, when a fetch is sent to `/api/v1/chat/conversations`, then response has status 401 | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Import path | AI may import from wrong path (e.g., `../../lib/auth-fetch` instead of `@/lib/auth-fetch`) | Verify the import line matches the `@/lib/auth-fetch` alias used by every other page |
| 2 | Incomplete replacement | AI may miss one of the 4 fetch calls (list, get, delete, send) | Run a diff of the file — confirm all 4 `fetch(` calls in the original are replaced with `authFetch(` |
| 3 | `credentials: "include"` | AI may leave `credentials: "include"` in authFetch calls (authFetch already adds it) | Check no `credentials` option is passed to `authFetch` — it's redundant and harmless but inconsistent |
| 4 | Transparent refresh breakage | AI may not handle the case where authFetch itself fails (e.g., session expired) | Verify the existing catch blocks still handle errors gracefully (they already ignore errors with `/* ignore */`) |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-005 | OpenCode Agent Boundaries | AI agents follow established code patterns; no new auth infrastructure | Confirm the fix uses the existing `authFetch` pattern, not a new auth wrapper or cookie-based approach |
| ADR-007 | Chatbot Architecture — Full RAG with Guardrails | Chat API endpoints are authenticated via gateway middleware | Confirm that after the fix, the gateway receives a valid Bearer token for all chat API requests |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1: Browser DevTools network tab capture showing `GET /api/v1/chat/conversations` request with `Authorization: Bearer <token>` header and 200 response
- [ ] Scenario 2: Browser DevTools network tab capture showing `GET /api/v1/chat/conversations` request without `Authorization` header and 401 response

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 confirmed — import uses `@/lib/auth-fetch` alias
- [ ] Risk 2 confirmed — all 4 fetch calls replaced (list, get messages, delete, send)
- [ ] Risk 3 confirmed — no redundant `credentials: "include"` passed to authFetch
- [ ] Risk 4 confirmed — error handling (`/* ignore */` catch blocks) preserved for all calls

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
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** fix-chat-page-auth
**Proposal:** `openspec/changes/fix-chat-page-auth/proposal.md`
**Spec files reviewed:**
- specs/chat-ui/spec.md

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


