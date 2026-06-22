## Context

The annotation workspace (sp-05) stores spans as character-offset tuples `(char_start, char_end, entity_type)` and derives BIO tags at export time. The frontend allows single-token annotation via a click after arming an entity type. Several UX controls — focus mode, mark-complete button, navbar stickiness, task naming — have gaps that emerged during first use. This design covers the technical approach for all 8 fixes.

## Goals / Non-Goals

**Goals:**

- Replace single-token click annotation with click-and-drag multi-token span creation
- Store pre-computed BIO tags on spans at write time; simplify export to a read
- Fix deselect, mark-complete visibility, sticky navbar, focus toggle, fullscreen, and task labels

**Non-Goals:**

- Changing the AnnotationTask API shape or adding a `task_number` field to the DB
- Modifying training, extraction, or model-serving services
- Changing span-reducer action types or the optimistic update strategy
- Support for non-whitespace tokenizers (BIO computation uses same `text.split()` as export)

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001-tenant-data-isolation | Tenant data lives in per-tenant schemas | BIO migration must target `tenant_template.spans`, not a shared table |
| ADR-004-openspec-governance | Changes tracked via OpenSpec artifacts | This change follows spec-driven-verified schema |
| ADR-005-opencode-agent-boundaries | Agents must not modify gateway auth or shared infra | No changes to gateway, auth, or shared middleware |

## Decisions

### Decision 1: Drag-to-annotate interaction model

**Choice:** ARM entity type first (existing palette click), then mousedown → drag → mouseup to select a token range. Single-click (mousedown + mouseup on same token) preserves existing behavior (open inspector for spanned token, create single-token span if armed).

**Rationale:** Keeps the armed-mode concept intact. Annotators already know to arm first; changing to select-first would require a floating entity picker popup which is more complex and breaks existing muscle memory. Single-token behavior must still work for annotators who click individual words.

**Alternatives considered:**
- Select-first then pick type (Label Studio pattern) — rules out because it requires a floating popup and breaks backward compatibility with armed-mode workflow
- Replace click entirely with drag (no single-click) — rules out because single-word entities are common and click is faster than drag for them

**Implementation:** Add `isDragging: boolean`, `dragStartIndex: number | null`, `dragEndIndex: number | null` state to `AnnotationPage`. Pass `onMouseDown` and `onMouseEnter` props down through `DocumentViewer` to `Token`. On `mouseup` (listened at document level to handle drag-out-of-viewer), if `dragStartIndex !== dragEndIndex`, compute `charStart = tokenMap[min].charStart`, `charEnd = tokenMap[max].charEnd`, then POST span for the range. If same token, fall through to existing click logic.

### Decision 2: BIO tag storage — column on spans table

**Choice:** Add `bio_tags TEXT[]` (nullable) to `tenant_template.spans`. Compute and store at `POST /spans` and `PATCH /spans` (entity_type retype). Export reads stored tags; falls back to computed for NULL rows.

**Rationale:** The spans table is the natural owner of this data — BIO is a property of a span's relationship to document tokens. A separate `token_annotations` table would require tracking O tags for every unspanned token, which is expensive to maintain on every span CRUD. The `TEXT[]` column stores only the B/I sequence for the span's own tokens (e.g. `["B-PER", "I-PER"]`), keeping it compact.

**Computation at write time:** The annotation service already queries `document_text_spans` in the prelabel endpoint. The same pattern applies: query text, `.split()`, walk tokens to find those in `[char_start, char_end)`, assign `B-{type}` to first hit, `I-{type}` to rest.

**Alternatives considered:**
- Materialized `token_annotations` table (one row per doc per token) — rules out because O-tag maintenance on every span change requires scanning the entire token list; overly complex
- Compute BIO only at export (status quo) — rules out because the stated requirement is to persist BIO in the DB
- Store as JSONB — rules out because `TEXT[]` is simpler to query and sufficient for a flat array of tag strings

**Backward compatibility:** Existing spans have `bio_tags = NULL`. Export falls back to the existing `_bio_tags()` computation for NULL rows, so old data exports correctly without a required backfill. A backfill migration can be run separately if needed.

### Decision 3: Fullscreen via browser Fullscreen API

**Choice:** `document.documentElement.requestFullscreen()` on focus mode entry; `document.exitFullscreen()` on exit. Sync `layoutMode` state via `fullscreenchange` event listener so Escape (browser's native fullscreen exit) automatically flips the toggle back.

**Rationale:** Browser Fullscreen API is the standard approach; it hides browser chrome and OS taskbar, which is what "fullscreen" means to users. A CSS-only overlay (`position: fixed; inset: 0; z-index: 9999`) would not hide the browser chrome.

**Alternatives considered:**
- CSS full-viewport overlay — rules out because it doesn't hide the browser toolbar; user explicitly asked for fullscreen
- Separate fullscreen button alongside focus toggle — rules out because the requirement is that focus mode IS fullscreen, not a separate control

**Interaction with Escape key:** The existing Escape handler dispatches `DISARM`. The `fullscreenchange` event is separate and handles toggling `layoutMode` back to `"3pane"` when the browser exits fullscreen. Both coexist without conflict.

### Decision 4: Sticky navbar — height chain fix

**Choice:** Change `minHeight: "100vh"` to `height: "100vh"` on the AppShell outer div, and add `position: "sticky"; top: 0` to the Topbar `<header>`.

**Rationale:** `minHeight` allows the outer div to grow beyond viewport height when content is tall, causing the browser to scroll the page body rather than the `<main>` scroll container. Changing to `height: 100vh` pins the layout, forcing `<main overflow: auto>` to contain scrolling internally. The sticky on Topbar is a defensive second layer.

**Risk:** Other pages that currently rely on body scroll will now scroll via `<main>` — this is actually the desired behavior (nav stays visible everywhere). All pages use the same AppShell, so the fix is global.

### Decision 5: Task display name — frontend queue index

**Choice:** Display `Task {index + 1}` where `index` is the task's position in `filteredTasks` (the list already rendered in the sidebar). No backend changes.

**Rationale:** Avoids a DB schema change (`task_number` column) for a display-only concern. The queue order is exactly what the annotator sees, making the label directly meaningful. Backend returns tasks `ORDER BY created_at DESC`; index 0 = top of visible list = "Task 1".

**Alternatives considered:**
- Backend `task_number` auto-increment per tenant — rules out as over-engineering for a display label; changes the API shape and requires a migration
- Reverse-order numbering (oldest = Task 1) — rules out because it's counterintuitive to the annotator viewing the queue

### Decision 6: Focus mode as single toggle

**Choice:** Replace the `[3-pane] [Focus]` radio button group with a single `[Focus]` toggle button. State remains `layoutMode: "3pane" | "focus"`.

**Rationale:** A single toggle is simpler and matches the requirement. The LayoutMode type and localStorage persistence key are unchanged; only the rendering of the control changes.

## Risks / Trade-offs

- [BIO computation on every span write adds a DB query per POST/PATCH] → Acceptable: the text query hits `document_text_spans` which is small and indexed by `document_id`; annotation is not high-throughput
- [height: 100vh may clip content on pages with dynamic-height content] → Low risk: all existing pages already expect `<main>` to be the scroll container; the AppShell was always intended to fill the viewport
- [Fullscreen API may be blocked by browser permissions or iframes] → Fail gracefully: catch the rejected promise and fall back to CSS focus mode (task queue hidden, entity palette floating) without fullscreen
- [Drag interaction on touch devices not covered] → Out of scope; annotation is desktop-only per existing design
- [NULL bio_tags on legacy spans] → Handled by export fallback to computed BIO; no data loss

## Migration Plan

1. Deploy DB migration `009_add_bio_tags_to_spans.py` (nullable column, zero downtime)
2. Deploy updated annotation service (spans.py + export.py) — new spans get bio_tags; existing rows remain NULL and export falls back correctly
3. Deploy updated portal (all 7 frontend fixes)
4. Optional: run backfill script to populate bio_tags for existing spans (can be deferred)

**Rollback:** Drop the `bio_tags` column (migration downgrade). Frontend changes are additive/visual — no rollback needed. Annotation service change is backward-compatible (NULL bio_tags → computed fallback).

## Open Questions

- None outstanding. All design decisions resolved during exploration phase.
