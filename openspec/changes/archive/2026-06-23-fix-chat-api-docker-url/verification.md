# Verification Plan

**Change:** fix-chat-api-docker-url
**Generated:** 2026-06-23
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | chat-api | Configurable chat API service URL | Gateway proxies to configured URL | Given gateway with `chat_api_url=http://chat_api:8000`, when a chat request is proxied, then the request goes to `http://chat_api:8000/api/v1/chat/...` | - [ ] |
| 2 | chat-api | Configurable chat API service URL | Default URL works for local dev | Given gateway with default config, when a chat request is proxied, then the request goes to `http://localhost:8006/api/v1/chat/...` | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required | Confirmed |
|---|-----------|-------------------|----------------------|-----------|
| 1 | Config default value | AI may set a default other than `http://localhost:8006` which would break local dev | Confirm `config.py` default is `"http://localhost:8006"` | ✅ `src/shared/config.py:32: chat_api_url: str = "http://localhost:8006"` |
| 2 | Inconsistent env prefix | AI may use a different env prefix for the setting (not `NER_`) | Confirm the setting uses `NER_CHAT_API_URL` since all settings use `NER_` prefix | ✅ `docker-compose.yml:93: NER_CHAT_API_URL: "http://host.docker.internal:8006"` |
| 3 | Docker compose env key | AI may use the wrong env var name (`CHAT_API_URL` instead of `NER_CHAT_API_URL`) | Confirm docker-compose uses `NER_CHAT_API_URL` matching the config env_prefix | ✅ Matches `NER_` prefix convention used by all other settings |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step | Confirmed |
|-----|-----------------|--------------------------|-------------------|-----------|
| ADR-007 | Chatbot Architecture — Full RAG with Guardrails | Chat API is proxied through the gateway | Confirm gateway proxy can reach chat-api after the fix | ✅ Proxy uses `settings.chat_api_url` which defaults to `http://localhost:8006` for local dev and can be overridden to `http://host.docker.internal:8006` in Docker |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1: Gateway log showing chat request proxied to configured URL (Docker env)
- [ ] Scenario 2: Gateway log showing chat request proxied to `localhost:8006` (local env)

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions
  - `config.py`: added `chat_api_url` with default `http://localhost:8006` ✓
  - `chat_proxy.py`: `CHAT_API_BASE = settings.chat_api_url` — uses full URL ✓
  - `docker-compose.yml`: `NER_CHAT_API_URL: "http://host.docker.internal:8006"` on gateway service ✓
- [x] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced

### Edge Case Evidence

- [ ] Risk 1 confirmed — default is `http://localhost:8006`
- [ ] Risk 2 confirmed — env prefix is `NER_`
- [ ] Risk 3 confirmed — docker-compose uses `NER_CHAT_API_URL`

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Code review | `config.py` default `chat_api_url = "http://localhost:8006"` — local dev path works | Scenario 2 | AI | 2026-06-23 |
| 2 | Code review | `chat_proxy.py` uses `settings.chat_api_url` — configurable at runtime | Both scenarios | AI | 2026-06-23 |
| 3 | Code review | `docker-compose.yml` has `NER_CHAT_API_URL=http://host.docker.internal:8006` — Docker path works | Scenario 1 | AI | 2026-06-23 |
| 4 | Functional test | Direct curl to chat_api returned `[{"id":"e12aa6b7-...","message_count":5},...]` — 200 OK with conversations | Scenario 1 | Human | 2026-06-23 |
| 5 | Log evidence | Gateway logs show 200 OK for `/api/v1/chat/conversations` after rebuild | Scenario 1 | Human | 2026-06-23 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.**

**Change slug:** fix-chat-api-docker-url
**Proposal:** `openspec/changes/fix-chat-api-docker-url/proposal.md`
**Spec files reviewed:**
- specs/chat-api/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [ ] |
| All ADRs in Section 3 verified compliant | - [ ] |
| Spec Alignment table complete | - [ ] |
| Evidence Log populated with real evidence | - [ ] |
| All functional evidence items checked | - [ ] |
| All structural evidence items checked | - [ ] |
| All edge case evidence items checked | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No undocumented patterns used | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause in specs has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________


