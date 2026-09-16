## 1. Overflow-based truncation

- [x] 1.1 Extract the assistant-reply-text rendering out of `MessageThread.tsx`'s inline `.map()` body into its own small component (e.g. `TruncatableReply`) that owns a `ref`, a `useLayoutEffect`-driven overflow measurement (`scrollHeight > clientHeight` against a bounded max-height), and its own `expanded` boolean state — replaces the current thread-level `expandedIds: Set<string>` plus the `contentLines`/`PREVIEW_LINE_LIMIT`/`lines.slice(...)` text-splitting logic entirely. The full `msg.content` is always passed to `ReactMarkdown` unmodified; visual clipping is CSS-driven, not string-slicing.
- [x] 1.2 Apply the clamp via a CSS class (`-webkit-line-clamp: N` + `overflow: hidden`, `N` a small display constant — see design.md Decision 1 and Open Questions for picking the actual value) on the wrapping element by default. The `useLayoutEffect` measurement removes the clamp class only once it confirms the un-clamped content still fits — the default state before measurement runs is clamped, never the reverse (design.md Risks).
- [x] 1.3 Render the "See more"/"See less" toggle only when the measurement confirms the content actually overflows — not unconditionally, and not based on `export.row_count` or any line count.
- [x] 1.4 Verifies scenario 1 — test in `MessageThread.test.tsx` (or a new `TruncatableReply.test.tsx`) asserting a reply tall enough to overflow the bounded height clips and shows "See more".
- [x] 1.5 Verifies scenario 2 — test asserting clicking "See more" reveals the full reply and the toggle reads "See less"; clicking again re-collapses it.
- [x] 1.6 Verifies scenario 3 — test asserting a short reply (fits within the bounded height) with `export.row_count = 28` renders in full with no toggle.
- [x] 1.7 Verifies scenario 4 — test asserting a long, overflowing reply with `export` absent still clips and shows "See more", identical to one with an export.
- [x] 1.8 Verifies scenario 5 — test asserting no truncation/toggle appears while `isThinking`/`isStreaming` is true.
- [x] 1.9 Verifies Hallucination Risk 2 — test or manual verification confirming the measurement hook is `useLayoutEffect`, not `useEffect`, and that no unclamped-then-clamped flash is observable.
- [x] 1.10 Verifies Hallucination Risk 3 — test asserting the clamp class is present in the very first render output (before any effect has run), not added only after an overflow check.

## 2. Decoupled export-offer visibility

- [x] 2.1 In `MessageThread.tsx`, replace the current `isTruncatable && msg.export && <ExportCard .../>` gate with a condition based solely on `showTrailers && msg.export` (i.e. `export.row_count >= 1`, since `export` is only ever present with at least one row per the `chat-api`/`chat-export` capabilities) — no comparison against `PREVIEW_LINE_LIMIT` or any row-count threshold anywhere in this condition.
- [x] 2.2 Verifies scenario 6 — test asserting `export.row_count = 1` renders the export prompt (stating "1 result"), even though that reply is not truncated (task 1.6-adjacent case).
- [x] 2.3 Verifies scenario 7 — test asserting `export.row_count = 45` renders the export prompt stating "45 results".
- [x] 2.4 Verifies scenario 8 — test asserting no export prompt when `export` is absent.
- [x] 2.5 Verifies scenario 9 — test asserting no export prompt appears while `isThinking`/`isStreaming` is true.
- [x] 2.6 Verifies Hallucination Risk 1 — test running scenario 3 (high row count, short reply, no truncation) and scenario 6 (small row count, gets a prompt) together, confirming truncation and export-offer are genuinely independent, not still cross-referencing each other.
- [x] 2.7 Verifies Hallucination Risk 6 — test asserting the prompt copy pluralizes correctly: "1 result" (singular) for `row_count = 1`, "N results" (plural) otherwise.

## 3. Two-step reveal (prompt, then format actions)

- [x] 3.1 Restructure `ExportCard.tsx` into two visual states behind one local `confirmed` boolean: (a) unconfirmed — a lightweight, low-visual-weight prompt stating the result count (e.g. "This includes 45 results — want a downloadable version?" — exact copy per design.md Open Questions); (b) confirmed — the existing "Download CSV"/"Download XLSX" buttons and their download mechanics (`authFetch`, blob URL, pending/error state), unchanged from the current implementation. Clicking the prompt sets `confirmed = true`, swapping the rendered content in place (design.md Decision 2) rather than rendering the buttons additively below a still-visible prompt.
- [x] 3.2 Verifies scenario 10 — test asserting the initial render shows the count-stating prompt with no "Download CSV"/"Download XLSX" action visible.
- [x] 3.3 Verifies scenario 11 — test asserting clicking the prompt reveals both format actions in its place.
- [x] 3.4 Verifies Hallucination Risk 4 — test asserting the prompt text is no longer present once the format actions appear (confirms an in-place swap, not an additive reveal).
- [x] 3.5 Verifies scenario 12 — test asserting clicking "Download CSV" (once revealed) sends an authenticated fetch to `/api/v1/chat/messages/{message_id}/export?format=csv` and saves via a blob URL, not a token-bearing direct link. (Unchanged mechanics from the existing implementation — re-verify after the restructuring in 3.1 to confirm nothing broke.)
- [x] 3.6 Decision 3 confirmed by the user: reveal both format choices on confirm (task 3.1), not an auto-download of a default format. No further sign-off needed before implementing 3.1 as written.

## 4. Regression sweep

- [x] 4.1 Verifies Hallucination Risk 5 — run scenario 5 (truncation suppressed while streaming) and scenario 9 (export prompt suppressed while streaming) as two separate test cases and confirm both pass independently.
- [x] 4.2 Run the existing portal chat test suite (`CitationCard.test.tsx`, `ConversationList.test.tsx`, `chat/page.test.tsx`) unchanged and confirm all pass — this change touches only `MessageThread.tsx`/`ExportCard.tsx` internals, not their external props/contracts.
- [x] 4.3 Confirm no new runtime dependency was added to `src/portal/package.json` (`git diff --stat`) — this change needs only CSS and a DOM measurement, no new library.
- [x] 4.4 Confirm no backend file was touched (`src/chat_api/**`, `src/gateway/**`) — this change is frontend-only per design.md Non-Goals; `git diff --stat` should show only `src/portal/**` files.

## 5. Verification & Evidence

- [x] 5.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 5.2 Collect functional evidence (test output / log) for each scenario — one entry per row in verification.md § Evidence Log.
- [x] 5.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 5.4 Confirm the ADR-014 compliance step in verification.md § Pattern & ADR Compliance.
- [ ] 5.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 5.6 Run `openspec validate chat-export-ux-refinements --type change --strict` and confirm it exits clean before archive. Note: archiving this change requires `export-chat-results` to be archived first (or alongside it) — see this change's proposal.md Impact section.
