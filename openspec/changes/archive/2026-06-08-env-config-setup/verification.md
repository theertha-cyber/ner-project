# Verification Plan

**Change:** env-config-setup
**Generated:** 2026-06-08
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | env-config | Environment Configuration Loading | Settings load from .env file | Given a .env with `NER_DATABASE_URL=custom:url`, when `settings.database_url` is accessed, then the value matches the .env entry. | `tests/test_env_config.py::test_settings_load_from_env` | - [ ] |
| 2 | env-config | Environment Configuration Loading | Settings fall back to defaults when .env missing | Given no .env file exists, when `settings.database_url` is accessed, then the value is the hardcoded default `postgresql+asyncpg://ner:ner@localhost:5432/ner`. | `tests/test_env_config.py::test_settings_fallback_defaults` | - [ ] |
| 3 | env-config | Environment Variable Documentation | .env.example documents all settings | Given the Settings class fields, when `.env.example` is read, then every `NER_*` variable appears with a comment and example. | Code review: compare `.env.example` against `src/shared/config.py` field names | - [ ] |
| 4 | env-config | .env Excluded from Version Control | .env is gitignored | Given a fresh clone, when `git check-ignore .env`, then exit code is 0. | `git check-ignore .env` returns 0 | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Missing env vars | AI may add env vars to `.env.example` that don't exist in `config.py`, or forget to update `.env.example` when adding new settings fields. | Compare every field name in `src/shared/config.py` Settings class against `NER_*` entries in `.env.example`. Every field must have a matching entry. |
| 2 | Default drift | AI may change a default in `config.py` without updating the corresponding entry in `.env.example` or without documenting the change in the tasks. | Verify that any default value change in this change is reflected in `.env.example`'s example value and noted in tasks.md. |
| 3 | .env committed to git | AI may forget to add `.env` to `.gitignore`, leaking secrets into version history. | Verify `.env` appears in `.gitignore`. Run `git check-ignore .env` to confirm. |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-004 OpenSpec Governance | All changes follow proposal → design → spec → tasks → evidence → archive pipeline. | All pipeline artifacts must be complete before archive. | Confirm `openspec validate --type change --strict` exits clean before archive. |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1: Test output showing `test_settings_load_from_env` passes — asserted custom database URL is read from `.env`
- [ ] Scenario 2: Test output showing `test_settings_fallback_defaults` passes — asserted default value when no `.env` exists
- [ ] Scenario 3: Code review confirming `.env.example` documents all `NER_*` variables matching `Settings` fields in `config.py`
- [ ] Scenario 4: Shell output of `git check-ignore .env` returning exit code 0

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 mitigation confirmed — every field in `Settings` class has a matching `NER_*` entry in `.env.example`
- [ ] Risk 2 mitigation confirmed — any default changes have corresponding `.env.example` and `tasks.md` updates
- [ ] Risk 3 mitigation confirmed — `.env` is listed in `.gitignore` and `git check-ignore .env` returns 0

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `tests/test_env_config.py::test_settings_load_from_env` PASSED — custom database URL read from .env file | 1 | Agent (test run) | 2026-06-08 |
| 2 | Functional | `tests/test_env_config.py::test_settings_fallback_defaults` PASSED — hardcoded defaults used when no .env present | 2 | Agent (test run) | 2026-06-08 |
| 3 | Code Review | `.env.example` documents all 11 `NER_*` variables matching `Settings` fields in `src/shared/config.py` — cross-checked field names | 3 | Agent (code review) | 2026-06-08 |
| 4 | Functional | `git check-ignore .env` returns exit code 0 — verified `.env` is gitignored | 4 | Agent (shell) | 2026-06-08 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** env-config-setup
**Proposal:** `openspec/changes/env-config-setup/proposal.md`
**Spec files reviewed:**
  - specs/env-config/spec.md

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


