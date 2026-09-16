# Verification Plan

**Change:** chat-export-ux-refinements
**Generated:** 2026-09-16
**Status:** 🟢 Implementation complete, all evidence collected, Audit Record signed off by theertha@inapp.com (2026-09-16) — ready to archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | chat-ui | Inline preview truncation is independent of export availability | A reply that visually overflows truncates with a See more toggle | Given an assistant message whose rendered reply exceeds the bounded display height, when the message thread renders it, then the reply is visually clipped to that height and a "See more" toggle appears below it | tasks.md 1.4 — `MessageThread.test.tsx`/`TruncatableReply.test.tsx` | - [ ] |
| 2 | chat-ui | Inline preview truncation is independent of export availability | Clicking See more reveals the full reply | Given a truncated assistant message, when the user clicks "See more", then the full reply renders in place, the toggle reads "See less", and clicking again re-collapses it | tasks.md 1.5 — `MessageThread.test.tsx`/`TruncatableReply.test.tsx` | - [ ] |
| 3 | chat-ui | Inline preview truncation is independent of export availability | A reply that fits within the bounded height is never truncated, regardless of export.row_count | Given an assistant message whose rendered reply does not exceed the bounded height, with `export.row_count = 28`, when the message thread renders it, then the full reply shows with no "See more" toggle | tasks.md 1.6 — `MessageThread.test.tsx`/`TruncatableReply.test.tsx` | - [ ] |
| 4 | chat-ui | Inline preview truncation is independent of export availability | A long reply with no structured result behind it still truncates on overflow | Given an assistant message whose `export` field is absent and whose rendered reply exceeds the bounded height, when the message thread renders it, then the reply is clipped and a "See more" toggle appears, exactly as it would with an export | tasks.md 1.7 — `MessageThread.test.tsx`/`TruncatableReply.test.tsx` | - [ ] |
| 5 | chat-ui | Inline preview truncation is independent of export availability | Truncation is suppressed while a message is still streaming | Given an assistant message still `isThinking`/`isStreaming`, when the message thread renders it, then no truncation or "See more" toggle appears until the message finishes | tasks.md 1.8, 4.1 — `MessageThread.test.tsx` | - [ ] |
| 6 | chat-ui | Export offer appears whenever structured data exists, regardless of result count | A small result still gets an export prompt | Given an assistant message with `export.row_count = 1`, when the message thread renders it, then an export prompt appears below the reply stating "1 result", even though the reply itself is not truncated | tasks.md 2.2 — `MessageThread.test.tsx` | - [ ] |
| 7 | chat-ui | Export offer appears whenever structured data exists, regardless of result count | A large result gets an export prompt stating the count | Given an assistant message with `export.row_count = 45`, when the message thread renders it, then an export prompt appears below the reply stating "45 results" | tasks.md 2.3 — `MessageThread.test.tsx` | - [ ] |
| 8 | chat-ui | Export offer appears whenever structured data exists, regardless of result count | No export prompt when there is no structured result | Given an assistant message whose `export` field is absent, when the message thread renders it, then no export prompt appears | tasks.md 2.4 — `MessageThread.test.tsx` | - [ ] |
| 9 | chat-ui | Export offer appears whenever structured data exists, regardless of result count | The export prompt is suppressed while a message is still streaming | Given an assistant message still `isThinking`/`isStreaming`, with `export.row_count = 8`, when the message thread renders it, then no export prompt appears until the message finishes | tasks.md 2.5, 4.1 — `MessageThread.test.tsx` | - [ ] |
| 10 | chat-ui | Export prompt reveals download actions only after the user opts in | The prompt does not show download actions before the user responds | Given an assistant message with `export.row_count = 12`, when the message thread renders it, then an export prompt stating "12 results" appears with no "Download CSV"/"Download XLSX" action visible yet | tasks.md 3.2 — `ExportCard.test.tsx` | - [ ] |
| 11 | chat-ui | Export prompt reveals download actions only after the user opts in | Responding to the prompt reveals the format actions | Given a rendered export prompt, when the user clicks it, then "Download CSV" and "Download XLSX" actions appear in its place | tasks.md 3.3 — `ExportCard.test.tsx` | - [ ] |
| 12 | chat-ui | Authenticated download from the revealed format actions | Clicking download triggers an authenticated fetch | Given a revealed "Download CSV" action, when the user clicks it, then a fetch is sent to `/api/v1/chat/messages/{message_id}/export?format=csv` with an `Authorization: Bearer <token>` header, and the file is saved via a blob URL, not a token-bearing direct link | tasks.md 3.5 — `ExportCard.test.tsx` | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Truncation and export-offer re-coupled by habit (design Decisions 1-3) | The previous implementation combined both conditions into a single `isTruncatable` boolean. An agent adjusting that code for this change could take the path of least resistance and just tweak the existing combined condition rather than fully splitting it into two independent ones — e.g. leaving a stray `export.row_count` check inside the truncation logic, or a line-count check inside the export-prompt logic. | Read the truncation logic: confirm it reads only the overflow measurement (`scrollHeight`/`clientHeight`), with no reference to `export`/`row_count` anywhere in that code path. Read the export-prompt logic: confirm it reads only `export != null` (or `row_count >= 1`), with no reference to line count or overflow state. Run scenario 3 (high row count, short reply, no truncation) and scenario 6 (small row count, gets a prompt) together — both must pass simultaneously, which is only possible if the two conditions are genuinely independent. |
| 2 | Overflow measurement in `useEffect` instead of `useLayoutEffect` (design Risks) | `useEffect` is the far more commonly reached-for hook; an agent implementing the overflow check without deliberately choosing `useLayoutEffect` will very likely default to `useEffect` out of habit, reintroducing the layout-flash bug design.md explicitly calls out. | Confirm the overflow-measurement hook is `useLayoutEffect`. Exercise scenario 1 with a slow/throttled render (or a snapshot of the very first paint) and confirm the content never briefly renders unclamped before settling into its clamped state. |
| 3 | Wrong default before measurement resolves (design Decision 1, Risks) | Design specifies defaulting to "clamped" and only removing the clamp once measurement confirms the content fits — never the reverse. An agent could default to "unclamped, add clamp if overflow detected," which is the opposite of what avoids the flash and reintroduces it in the other direction (a flash of full-height content before it clamps). | Read the initial render state: confirm the clamping CSS class/style is present by default (before any measurement effect has run), and is only removed once the layout-effect measurement confirms the content fits within the bounded height. |
| 4 | Additive reveal instead of in-place swap (design Decision 2) | Decision 2 explicitly rejects showing the format buttons *in addition to* the still-visible prompt, in favor of replacing it. Conditionally rendering an extra block below existing content is often the simpler code path than conditionally swapping content in the same slot, so an agent could implement the rejected alternative without realizing it contradicts the design. | Read the export-prompt component: confirm clicking it replaces the prompt's rendered content with the format buttons (one DOM slot, two states), not that the buttons appear as a new element alongside a prompt that remains visible. Run scenario 10 and 11 in sequence and confirm the prompt text is gone once the buttons appear. |
| 5 | Streaming suppression dropped on one of the two now-independent code paths (design Context) | The original implementation gated one combined condition on `showTrailers` (`!isThinking && !isStreaming`). Splitting that into two independent conditions (truncation, export-offer) means the streaming gate now needs to be applied twice, independently — an agent restructuring the code could correctly gate one path and forget the other. | Run scenario 5 (truncation suppressed while streaming) and scenario 9 (export prompt suppressed while streaming) as two separate test cases, not one — confirm both pass independently, not just "the combined UI looks right" on a single manual check. |
| 6 | Singular/plural grammar in the prompt copy (spec scenarios 6-7) | A naive template (e.g. `` `${count} results` ``) produces the grammatically wrong "1 results" for a single-result count. The spec's own scenario 6 explicitly expects "1 result" (singular). | Read the prompt copy logic: confirm it pluralizes correctly (singular "result" only when `row_count === 1`, "results" otherwise). Run scenario 6 specifically and confirm the rendered text reads "1 result", not "1 results". |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-------------------|--------------------------|-------------------|
| ADR-014 Chat Export: Persisted Row Snapshot, Rendered On-Demand | Snapshot stored as JSONB on the owning `chat_messages` row; CSV/XLSX rendered on-demand at request time from that snapshot; no pre-generation or caching. | This change is frontend-only and must not touch the snapshot, the export endpoint, or its rendering/sanitization behavior — it only changes when and how the *existing* download capability is surfaced in the UI. | Confirm the diff touches no file under `src/chat_api/services/export_rendering.py`, `src/chat_api/api/v1/chat.py`'s export route, or the `chat_messages.export_rows`/`export_row_count` columns. Confirm `ChatResponse.export`/`MessageResponse.export`'s shape (`message_id`, `row_count`, `formats`) is unchanged — this change only reads those fields differently on the frontend. |

> ADR-014 is recorded as **proposed**, not accepted (matching this repo's existing convention where several other in-force ADRs are also proposed). It is verified regardless, since its snapshot/rendering mechanism is live in the codebase and this change must not weaken it.

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

- [x] Scenario 1 (Overflow truncates with See more): test output asserting a visually-overflowing reply clips and shows the toggle
- [x] Scenario 2 (Clicking See more expands): test output asserting full reply renders and toggle reads "See less"
- [x] Scenario 3 (No truncation when content fits, regardless of row count): test output asserting a short reply with `row_count = 28` renders in full with no toggle
- [x] Scenario 4 (Long reply truncates even with no export): test output asserting truncation applies when `export` is absent
- [x] Scenario 5 (Truncation suppressed while streaming): test output asserting no truncation/toggle appears mid-stream
- [x] Scenario 6 (Small result gets a prompt): test output asserting `row_count = 1` renders a prompt stating "1 result"
- [x] Scenario 7 (Large result prompt states the count): test output asserting `row_count = 45` renders a prompt stating "45 results"
- [x] Scenario 8 (No prompt without export data): test output asserting no prompt when `export` is absent
- [x] Scenario 9 (Prompt suppressed while streaming): test output asserting no prompt appears mid-stream
- [x] Scenario 10 (No download actions before responding): test output asserting the prompt shows no format buttons initially
- [x] Scenario 11 (Responding reveals format actions): test output asserting clicking the prompt reveals "Download CSV"/"Download XLSX"
- [x] Scenario 12 (Authenticated download fetch): test output asserting the fetch call includes the Bearer token and saves via a blob URL

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions, including Decision 3's outcome once confirmed with the user (no undocumented deviations)
- [x] ADR-014 compliance step in Section 3 confirmed — no backend/endpoint/snapshot files touched
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)
- [x] Confirmed no new runtime dependency was added to `src/portal/package.json` (this change should need none — CSS + a DOM measurement, no new library)

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — truncation and export-offer logic are genuinely independent (scenarios 3 and 6 both pass together)
- [x] Risk 2 mitigation confirmed — overflow measurement uses `useLayoutEffect`, not `useEffect`; no visible flash observed
- [x] Risk 3 mitigation confirmed — clamp is the default state before measurement, never the reverse
- [x] Risk 4 mitigation confirmed — prompt-to-buttons is an in-place swap, not an additive reveal
- [x] Risk 5 mitigation confirmed — streaming suppression verified independently on both the truncation and export-offer code paths
- [x] Risk 6 mitigation confirmed — prompt copy correctly pluralizes "1 result" vs "N results"

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching
entry. Do not pre-fill — entries must describe real observations.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Automated test | `TruncatableReply.test.tsx` (5 tests) — overflow clip/toggle, expand/collapse, default-clamped, mocked `scrollHeight`/`clientHeight`; run via `vitest run` in `ner-portal-test`, all passing | 1, 2 | Claude | 2026-09-16 |
| 2 | Automated test | `MessageThread.test.tsx` "overflow-based truncation" describe block (5 tests) — overflow truncates, expand toggle, fits-regardless-of-row_count, no-export-still-truncates, streaming suppression; `vitest run`, all passing | 1, 2, 3, 4, 5 | Claude | 2026-09-16 |
| 3 | Automated test | `MessageThread.test.tsx` "export offer, decoupled..." describe block (5 tests) — small result gets prompt, large result states count, no export → no offer, streaming suppression, click-to-reveal; `vitest run`, all passing | 6, 7, 8, 9, 10 | Claude | 2026-09-16 |
| 4 | Automated test | `ExportCard.test.tsx` (6 tests) — prompt-first render, singular "1 result" grammar, click-to-reveal swap (prompt text gone), CSV/XLSX fetch + blob-URL save, error path; `vitest run`, all passing | 6, 10, 11, 12 | Claude | 2026-09-16 |
| 5 | Full suite run | `vitest run` (no filter) inside `ner-portal-test`: 6/6 chat suites, 71/71 chat tests pass; 5 unrelated pre-existing failures in `AnnotationImportPreview`/`AnnotationPage`/`StatusFilterTabs`/`EntityTypesPage`/`training-jobs page` — none touch `MessageThread`/`ExportCard`/`TruncatableReply`, confirming no regression from this change | all | Claude | 2026-09-16 |
| 6 | Live browser verification | Ran the portal dev server against the real `chat_api`/`gateway` stack, signed in as `tenant_admin`, asked "List all entity types" (real `row_count = 1` response). Observed: export prompt read "1 result — want a downloadable version?" (correct singular grammar, scenario 6); no Download buttons visible before click (scenario 10); clicking the prompt swapped it in-place for "1 result" + Download CSV/XLSX buttons, prompt text gone (scenario 11, Risk 4); clicking Download CSV produced a real `GET /api/v1/chat/messages/{id}/export?format=csv → 200 OK` network request (scenario 12) | 6, 10, 11, 12 | Claude | 2026-09-16 |
| 7 | Live browser verification | `getComputedStyle` on the rendered reply element confirmed class `chat-markdown chat-doc chat-reply-clamp` and computed `webkitLineClamp: "12"` applied by default on initial render, before any user interaction (Risk 3) | 1, Risk 3 | Claude | 2026-09-16 |
| 8 | Code reading | `TruncatableReply.tsx` confirmed to use `useLayoutEffect` (not `useEffect`) for the overflow measurement, and to default `expanded` to `false` (clamp class present) before the effect runs (Risk 2, Risk 3) | Risk 2, Risk 3 | Claude | 2026-09-16 |
| 9 | Diff review | `git diff --stat` confirms only `src/portal/src/app/globals.css`, `src/portal/src/components/chat/{ExportCard,MessageThread}.{tsx,test.tsx}`, plus new `TruncatableReply.{tsx,test.tsx}` — no `src/chat_api/**`, `src/gateway/**`, `package.json`, or `package-lock.json` changes | ADR-014 compliance, structural evidence | Claude | 2026-09-16 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** chat-export-ux-refinements
**Proposal:** `openspec/changes/chat-export-ux-refinements/proposal.md`
**Spec files reviewed:**

- specs/chat-ui/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [x] |
| All ADRs in Section 3 verified compliant | - [x] |
| Spec Alignment table complete (no missing scenarios) | - [x] |
| Evidence Log populated with real evidence | - [x] |
| All functional evidence items in Section 4 checked | - [x] |
| All structural evidence items in Section 4 checked | - [x] |
| All edge case evidence items in Section 4 checked | - [x] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [x] |
| No hallucinated requirements introduced | - [x] |
| No undocumented patterns used | - [x] |
| No AI-invented fields, endpoints, or behaviours present | - [x] |
| Every THEN clause in specs has a corresponding evidence entry | - [x] |
| Hallucination risk register reviewed and all mitigations confirmed | - [x] |

**Archive approved by:** theertha@inapp.com

**Date:** 2026-09-16

**Notes:** Decision 3 (two-step reveal, both CSV/XLSX formats on confirm rather than an auto-download of a default) was explicitly confirmed by the reviewer before implementation began.
