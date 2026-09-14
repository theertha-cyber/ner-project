# Ralph Run Report

**Run ID:** run_20260910T075640
**Status:** Completed
**Integration Branch:** `attachment-in-chat`

---

## Completed Capabilities

- **CAP-3: Conversation-Scoped Attachment Persistence**
  - **Branch:** `change/cap-3-conversation-scoped-attachment-persistence`
  - **Commit:** `10098661`
  - **Specs Archived:** Yes (proposed/validated/archived)
- **CAP-4: CSV Ingestion Branch for Chat Attachments**
  - **Branch:** `change/cap-4-csv-ingestion-branch-for-chat-attachments`
  - **Commit:** `fc271ef1`
  - **Specs Archived:** Yes (proposed/validated/archived)
- **CAP-2: Chat Composer Attachment UX**
  - **Branch:** `change/cap-2-chat-composer-attachment-ux`
  - **Commit:** `054eef3e`
  - **Specs Archived:** Yes (proposed/validated/archived)
- **CAP-5: Documents Library Exclusion and Hard-Delete Cleanup**
  - **Branch:** `change/cap-5-documents-library-exclusion-and-hard-delete-cleanup`
  - **Commit:** `ca3556fa` (integrated merge commit)
  - **Specs Archived:** Yes (proposed/validated/archived)

---

## Blocked & Skipped Capabilities

- **Blocked:** None
- **Skipped:** None

---

## Test Baseline

This run was measured against a **known red-code baseline**:
- **Baseline Status:** `red-code`
- **Baseline Note:** Pre-existing failure in `tests/test_chat_api_rag.py::TestGuardrailEnforcement::test_chat_response_sources`. Additionally, Portal suite carries pre-existing UI-test drift in annotation/document/training-jobs components (18 failed / 648 passed at 2026-09-14, from committed code untouched by this run's working tree).
- **CAP-5 Execution Outcome:** All 8 custom test scenarios for CAP-5 passed cleanly.

---

## Spec Overrides & Rewrites

- **Spec Rewrites:** 0 (No specification rewrites or overrides were requested or performed).

---

## Demo & Seed Data Reconciliation

- **Reconciliation Status:** Clean. The primary views and test schemas do not contain any leak of test fixtures or random/extraneous database records. Verified that primary tables on target schemas contain only expected seeded records and no leftover test artifacts.

---

## UI Design Contract

*This run included a UI contract section for CAP-2.*

- **Design System:** Custom CSS (Tailwind/Next.js theme)
- **Target Platform:** Web (Next.js App)
- **Theme File Path:** `src/portal/tailwind.config.ts`

### Per-Capability UI Verification

#### CAP-2: Chat Composer Attachment UX
- **Screens Implemented:** `SCR-2` (Chat Composer input and thread view)
- **Static Lint (ui-lint):** 0 P0 violations, 0 P1 violations in files touched by CAP-2.
- **Screenshot Comparison:** Deferred per policy. Screenshot comparison against `docs/design/mockup/chat-thread.html` is deferred because the chat route is auth-gated and has no headless browser path in this environment.
