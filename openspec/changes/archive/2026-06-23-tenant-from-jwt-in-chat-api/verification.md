# Verification Plan

**Change:** `tenant-from-jwt-in-chat-api`
**Generated:** 2026-06-23
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | chat-api | RAG chat endpoint | Chat with simple entity count query | Given a tenant with extracted entities, when POST `/api/v1/chat` with a valid JWT, then 200 with reply, sources, conversation_id | | - [ ] |
| 2 | chat-api | RAG chat endpoint | Chat with document context query | Given document chunks with embeddings, when a question is sent, then 200 with document chunk sources | | - [ ] |
| 3 | chat-api | RAG chat endpoint | Chat with NER query | Given a promoted NER model, when NER query is sent, then sources include entity_type, value, confidence | | - [ ] |
| 4 | chat-api | RAG chat endpoint | Chat with existing conversation | Given conversation `conv-abc`, when message with conversation_id sent, then 200 and message appended | | - [ ] |
| 5 | chat-api | RAG chat endpoint | Chat without authentication | Given no JWT token, when POST `/api/v1/chat`, then 401 | | - [ ] |
| 6 | chat-api | Conversation CRUD | List conversations for a user | Given user with 3 conversations, when GET `/api/v1/chat/conversations`, then 200 with 3 conversations | | - [ ] |
| 7 | chat-api | Conversation CRUD | Get conversation messages | Given conversation with 5 messages, when GET `/api/v1/chat/conversations/{conv_id}`, then 200 with 5 messages | | - [ ] |
| 8 | chat-api | Conversation CRUD | Delete conversation | Given conversation owned by user A, when DELETE `/api/v1/chat/conversations/{conv_id}`, then 204 | | - [ ] |
| 9 | chat-api | Conversation CRUD | Delete another user's conversation returns 404 | Given conversation owned by user A, when user B deletes it, then 404 | | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Route prefix change | AI may forget to update the router prefix in one of the two router files (chat.py, widget_keys.py) | Verify both `chat.py` and `widget_keys.py` have the updated prefix |
| 2 | Proxy URL mismatch | AI may update the gateway proxy path pattern but forget to update the internal proxy URL string | Verify each proxy route's forwarded URL matches the new chat service route |
| 3 | Stale `tid` references in handler body | AI may remove `tid` from function signature but leave a reference to `tid` in the handler body (e.g., `_schema(tid)`) | Grep for `tid` in all modified files after changes |
| 4 | Widget key route moved without auth consideration | AI may move widget-key routes but assume they don't need JWT auth | Widget-key routes still require JWT — verify middleware is not bypassed |
| 5 | Portal UI URL staleness | AI may not update frontend client code that constructs these URLs | Check portal UI for hardcoded `/api/v1/tenants/{tid}/chat` references |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-007 — Chatbot Architecture with Full RAG and Guardrails | All chatbot interactions MUST be tenant-scoped | Tenant scoping is preserved via `request.state.tenant_id` from JWT — no tenant data leakage | Confirm that all routes still extract `tenant_id` from `request.state` and use it for schema resolution |
| ADR-001 — Tenant Data Isolation via Separate Database Schemas | Separate PostgreSQL schemas per tenant | Schema resolution must still derive from tenant_id | Verify `_schema(tenant_id)` still uses the JWT-derived tenant_id |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1: Test output showing POST `/api/v1/chat` with valid JWT returns 200 and a ChatResponse with reply, sources, conversation_id
- [ ] Scenario 2: Test output showing document chunk sources with document_id, chunk_index, relevance_score in response
- [ ] Scenario 3: Test output showing NER sources with entity_type, value, confidence
- [ ] Scenario 4: Test output showing message appended to existing conversation
- [ ] Scenario 5: Test output showing POST `/api/v1/chat` without JWT returns 401
- [ ] Scenario 6: Test output showing GET `/api/v1/chat/conversations` returns 200 with conversation list
- [ ] Scenario 7: Test output showing GET `/api/v1/chat/conversations/{conv_id}` returns 200 with messages
- [ ] Scenario 8: Test output showing DELETE `/api/v1/chat/conversations/{conv_id}` returns 204
- [ ] Scenario 9: Test output showing cross-user delete returns 404

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 (Route prefix): Both router files updated — verified by grep for old prefix
- [ ] Risk 2 (Proxy URL): All gateway proxy URLs updated — verified by grep for old paths
- [ ] Risk 3 (Stale `tid`): No remaining references to `tid` in modified files — verified by grep
- [ ] Risk 4 (Widget auth): Widget-key routes still require JWT in middleware — verified
- [ ] Risk 5 (Portal UI): Portal UI checked for hardcoded old URLs — updated if found

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching
entry. Do not pre-fill — entries must describe real observations.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** `tenant-from-jwt-in-chat-api`
**Proposal:** `openspec/changes/tenant-from-jwt-in-chat-api/proposal.md`
**Spec files reviewed:**
  - specs/chat-api/spec.md

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
