## Context

`export-chat-results` shipped with one number (`PREVIEW_LINE_LIMIT`, default 5) doing three jobs at once: deciding whether the reply text truncates, whether "See more" appears, and whether the download option shows at all — compared against both `export.row_count` and a `\n`-delimited count of the reply's text lines. Live testing found this conflation actively wrong in two ways: a verbose single-result answer got wrongly truncated (many *text* lines, one *result*), and small-but-real results couldn't be downloaded at all just because they were short. This change splits "should this truncate visually" from "is there something to export" into two independent questions, and makes the export action opt-in (a stated-count prompt, then format buttons) rather than an eagerly-rendered card.

Relevant in-force ADRs: only **ADR-014** (chat export: persisted row snapshot, rendered on-demand) bears on this change, and only as a constraint this change must *not* violate — this is a pure frontend change; it does not touch the snapshot, the endpoint, or the rendering pipeline ADR-014 governs. ADR-001 (tenant isolation) and ADR-007 (chatbot architecture) are ADR-014's own dependencies, not directly relevant here since nothing about tenant scoping or the RAG pipeline changes. No other ADR in `docs/adr/` touches chat UI or export.

## Goals / Non-Goals

**Goals**
- Make "does this reply visually need a See more toggle" and "is there something worth exporting" fully independent conditions, each evaluated on its own terms.
- Make the export action opt-in: a lightweight, count-stating prompt first, format choices only after the user confirms.
- Do this without touching the backend — `export.row_count`/`formats` already carry everything the frontend needs.

**Non-Goals**
- Not changing the export snapshot, the download endpoint, its ownership checks, or its formula-injection sanitization (ADR-014's territory, untouched).
- Not solving the pre-existing "`LIMIT`-truncated but under threshold" gap noted in `export-chat-results` design.md — unrelated, still accepted.
- Not adding a "remember my format choice" or similar personalization — out of scope for this pass.

## Decisions

### Decision 1: Overflow detection — CSS line-clamp + a measured "is it actually clamped" check

**Important honesty check on the proposal's own framing**: this does not eliminate "a number" entirely — CSS's `-webkit-line-clamp` still takes a line-count parameter (e.g. clamp after 4 lines). What it actually fixes is *what the number measures*. The old logic counted `\n`-delimited text lines in the raw reply string — which has no reliable relationship to how much vertical space the reply actually takes on screen: a single long unwrapped sentence can visually wrap into 3-4 lines, while several short `\n`-separated items might together take less room than the line-count suggested. `line-clamp`'s line count is expressed in actual rendered lines (post-wrapping, respecting the active font size), so it measures the thing that actually matters — how much room this takes up on screen — rather than a proxy (raw text structure) that was never really that.

Mechanically: apply `-webkit-line-clamp: N` (a small constant, e.g. 4-5, tuned for the chat bubble's width) via CSS to do the visual clipping. Separately, after render, compare the element's `scrollHeight` to its `clientHeight` (a `useLayoutEffect`-driven check, not `useEffect` — see Risks) to determine *whether* clamping actually took effect, and only then render the "See more" toggle. `line-clamp` alone clips visually but doesn't tell React whether anything was hidden; the measurement is what decides whether the toggle appears at all.

Alternative considered: a hand-rolled `max-height` in pixels instead of `line-clamp`. Rejected — a raw pixel cap can cut off mid-line (ugly, mid-word truncation without a fade/ellipsis), where `line-clamp` respects line boundaries and can add its own ellipsis. `line-clamp`'s line-count-in-CSS unit also scales naturally with font-size/zoom (larger font → each "line" is taller, but still N lines), which a fixed pixel value would not without extra `em`/`rem` unit juggling.

### Decision 2: Two-step reveal is an in-place swap, not an additive reveal

The prompt and the format-choice buttons occupy the same slot in the layout — clicking the prompt replaces it with the buttons, rather than the buttons appearing in addition to a prompt that stays visible. Keeps the export affordance's footprint constant (one row either way) instead of growing the message when the user opts in.

### Decision 3: Confirming reveals both format choices (CSV and XLSX), not an immediate default-format download

**Confirmed by the user.** Clicking the prompt swaps it for "Download CSV" / "Download XLSX" (Decision 2's swap); a second click actually downloads. This was chosen over auto-downloading a default format because it preserves the existing choice between two formats (some users specifically need XLSX for further spreadsheet work) and because a visible confirm-then-choose flow means the user always knows what they're about to get before a file lands on their machine — a click that silently triggers a file download with no visible confirmation of *what* just happened would have been a rougher interaction. It's also a strict superset of capability versus the auto-download alternative (still just as fast to click twice as the original single-card version was to click once). The accepted cost is one extra click for users who always want CSV — real but small, and not mitigated in this change (see Risks/Trade-offs).

## Risks / Trade-offs

- **[Risk] A layout "flash"** if the overflow check runs after first paint: content could render at full height for one frame, then jump to clamped height once the `scrollHeight`/`clientHeight` check resolves. → **Mitigation**: run the check in `useLayoutEffect` (fires before the browser paints, not after like `useEffect`), and default to the clamped CSS class being applied from the very first render (assume truncated), only removing it once the measurement confirms the content actually fits — never the other way around, so the worst case is a very brief over-clamp, never an unclamped flash.
- **[Trade-off] Every message with any export data now shows a prompt**, including trivially small ones (`row_count = 1`). Accepted deliberately — the alternative (a floor below which no prompt shows) reintroduces exactly the kind of arbitrary threshold this change is trying to remove. Revisit only if real usage feedback says the prompt feels noisy for small results.
- **[Trade-off] Two-step reveal costs one extra click** versus the old eager card, for users who reliably want to export every time. Not mitigated in this change; a "just download CSV" fast-path could be a follow-up if this turns out to matter, but isn't assumed to matter yet.
- **[Risk] `-webkit-line-clamp` browser support**: it's a long-standing, widely-supported (if technically vendor-prefixed) property across all evergreen browsers the portal already targets — not flagging as a real compatibility risk, just noting the prefix is intentional and the standard `line-clamp` (unprefixed) is not yet reliable enough across the target browser matrix to use alone.

## Migration Plan

None. Pure frontend change — no schema, no API contract change, no backend deploy sequencing. `export.row_count`/`formats` are already present on `ChatResponse`/`MessageResponse` from `export-chat-results`; nothing new is added or removed from the API surface. Ships as a normal portal rebuild/redeploy.

## Open Questions

- The exact `line-clamp` line-count constant (how many visual lines before clamping) is a small display constant, not a business threshold, but still needs an actual number picked — worth a quick look at how it reads in the real chat UI before locking it in, same as the original `PREVIEW_LINE_LIMIT` was always a placeholder pending UX input.
- Exact copy for the export prompt beyond "must state the count" (e.g. "This includes 45 results — want a downloadable version?" vs. shorter alternatives) — not resolved here.
