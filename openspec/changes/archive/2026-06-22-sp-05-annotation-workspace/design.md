## Context

The annotation workspace backend (span CRUD, pre-labeling, task management, export) is fully implemented. The frontend portal (SP-01 through SP-04) has been scaffolded with a shared design system, auth flow, app shell, and dashboard. SP-05 adds the `/annotation` route — the most complex frontend screen in the platform — which involves real-time span state management, char-offset arithmetic, optimistic UI updates, and two distinct layout modes.

The document viewer encodes a token-click labeling model where the frontend must bridge a word-granular UI with a character-offset storage model. This conversion is entirely client-side; no backend changes are required.

## Goals / Non-Goals

**Goals:**

- Deliver the full annotation workspace screen at `/annotation` accessible to `annotator` and `tenant_admin` roles
- Support both 3-pane and focus layout modes with `localStorage` persistence
- Implement token-click span creation with optimistic UI and rollback on error
- Implement span inspector (retype, delete) and suggestion flow (promote, dismiss)
- Implement task status lifecycle transitions (unannotated → in-progress → completed)
- Keep all span state in a single `useReducer` for predictable optimistic updates

**Non-Goals:**

- Backend API changes — all required endpoints exist
- Multi-token drag-selection (single-token click only for MVP, matching the mockup)
- Virtualization of the document token list (CSS flex-wrap, documents ≤1,000 words)
- Collaborative real-time annotation (no websocket/SSE)
- Document preview / PDF rendering — text content only

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001: Tenant Data Isolation | All data is isolated per tenant via separate DB schemas | All API calls include the tenant's auth token; no cross-tenant data must appear in the UI |
| ADR-004: OpenSpec Governance | All capability changes go through spec-driven workflow | This design is recorded here; no ad-hoc implementation decisions |
| ADR-005: OpenCode Agent Boundaries | Agent edits are scoped to the repo; no external system calls during implementation | Implementation stays within `src/portal/` |

## Decisions

### Decision 1: Span state managed by `useReducer`, not TanStack Query cache

**Choice:** All span state (confirmed spans, suggested spans, armed type, selected span) is managed in a single `useReducer` inside the annotation page. TanStack Query is used for initial fetches and invalidation only, not as the live state store.

**Rationale:** Span state requires optimistic updates with rollback — when a user clicks a token, the highlight must appear immediately. TanStack Query's optimistic mutation API (`onMutate` / `onError` / `onSettled`) becomes complex when multiple concurrent mutations are possible (e.g. rapid span creation). A `useReducer` with actions like `SPAN_ADD_OPTIMISTIC`, `SPAN_CONFIRM`, `SPAN_REVERT`, `SPAN_DELETE` gives synchronous, predictable state transitions that React can batch in a single render. On mount, the reducer initializes from the TanStack Query fetched data; after each mutation settles, the server response updates the reducer to replace optimistic IDs with real IDs.

**Alternatives considered:**
- TanStack Query mutation + optimistic updates: viable but the `onMutate`/`onError`/`onSettled` triplet becomes difficult to reason about when the same token can be clicked again before the first mutation resolves
- Zustand store: overkill for a single-screen concern; `useReducer` is built in and sufficient

### Decision 2: Char-offset ↔ token-index conversion via cumulative-offset map

**Choice:** On document load, compute a `tokenMap: Array<{ token: string, charStart: number, charEnd: number }>` by splitting the document text on whitespace and accumulating offsets. This map is computed once (memoized with `useMemo`) and used bidirectionally: token click → char offsets (read from map), span from API → token indices (binary search or linear scan on charStart/charEnd).

**Rationale:** The annotation service stores char offsets; the document viewer works in token indices. The mapping must be bijective and stable for the lifetime of a document load. Pre-computing the full map avoids per-click arithmetic and makes both directions O(1) (array index) or O(n) (range scan, n = number of tokens, acceptable for ≤1,000 words). The whitespace-split rule matches the backend export tokenizer exactly (confirmed in annotation-workspace backend spec).

**Alternatives considered:**
- Compute offsets on each token click: simpler code but repeated work; creates risk of drift if the text is ever re-fetched mid-session
- Server-computed token map via a dedicated endpoint: adds a round-trip and a new backend endpoint; unnecessary given client-side is straightforward

### Decision 3: Escape key disarms via a global `keydown` listener on the annotation page

**Choice:** A single `useEffect` on the annotation page component adds a `document.addEventListener('keydown', ...)` that dispatches `DISARM` to the reducer when `event.key === 'Escape'`. The listener is removed in the cleanup function.

**Rationale:** The armed-type state lives in the reducer; the simplest way to respond to a global keydown is a single page-level listener rather than threading a callback through the entity palette component. The listener is scoped to the annotation page's mount lifecycle, so it cannot interfere with other routes.

**Alternatives considered:**
- `onKeyDown` on a focusable container: requires the container to hold focus; unreliable when the user clicks document tokens
- A keyboard hook library: unnecessary abstraction for a single key

### Decision 4: Component directory structure under `src/portal/src/components/annotation/`

**Choice:**
```
components/annotation/
  AnnotationPage.tsx       ← page-level component (owns the reducer, layout toggle, task selection)
  TaskQueue.tsx            ← left panel, receives tasks + onSelect callback
  DocumentViewer.tsx       ← center panel, receives tokenMap + spanState + armedType
  Token.tsx                ← individual word token, receives highlight props
  EntityPalette.tsx        ← right panel, receives entityTypes + spanCounts + armedType
  SpanInspector.tsx        ← inspector overlay, receives selectedSpan + mutation callbacks
  SuggestionPanel.tsx      ← suggestion rows, receives suggestions + onPromote + onDismiss
```

**Rationale:** Each component has a single job and receives its state as props from the reducer-owning page. This avoids context threading and makes each component independently testable. The page component orchestrates all interactions.

**Alternatives considered:**
- Context API for annotation state: avoids prop drilling but hides data flow; the annotation page is a single screen with a bounded lifetime, making prop threading acceptable

### Decision 5: Optimistic highlight via a transient `optimistic` flag in the reducer

**Choice:** When a span creation fires, the reducer immediately adds a span with `id: "optimistic-<uuid>"` and `optimistic: true`. On API success, the action `SPAN_CONFIRM` replaces the optimistic entry with the server-returned span (copying the real ID). On API error, `SPAN_REVERT` removes the optimistic entry and dispatches `TOAST_ERROR`.

**Rationale:** The reducer can identify optimistic entries by their special ID prefix. If the user clicks a second token before the first request settles, each click generates an independent optimistic entry — they do not interfere. When multiple requests are in-flight, each resolves independently without coordination logic.

**Alternatives considered:**
- Boolean `isCreating` flag that blocks further clicks: degrades UX on fast networks; unnecessary restriction

## Risks / Trade-offs

- [Char-offset boundary mismatch if the backend uses a different tokenizer for some documents] → Integration test: compare client-computed offsets against the annotation export output for the same document. Flag any discrepancy before shipping.
- [1,000-token limit for CSS flex-wrap may be exceeded by large documents] → Add a warning toast if `document.text.split(/\s+/).length > 1000` and suggest splitting the document upstream. Do not implement virtualization in this spec.
- [Rapid token clicks may cause multiple in-flight mutations that settle out of order] → Each optimistic entry carries a unique ID; out-of-order settlement replaces/reverts individual entries without corrupting adjacent span state.
- [Task auto-selection on completion may confuse users who wanted to review the completed task] → The auto-selection is immediate but the completed task remains visible in the queue (dimmed/badged), so the user can click back to it.

## Migration Plan

This is a net-new frontend route with no data migration required. Deployment steps:
1. Build and start the portal (`npm run dev` or production build in Docker).
2. The `/annotation` route is live immediately for authenticated `annotator` and `tenant_admin` users.
3. No backend service changes. All endpoints consumed by this screen are already implemented.
4. Rollback: remove the route from `app/(auth)/annotation/page.tsx` — the rest of the portal continues to function.

## Open Questions

1. **`GET /documents/{id}/text` endpoint location**: The decomposition document references this endpoint at the document service (port 8001), but the extraction service also handles document content. Confirm the exact service and response shape before writing the `authFetch` call. (Tracked as Open Question 1 in proposal.md.)
2. **Suggestion dismiss behavior**: The spec says dismiss is local-only (no API call). If the user triggers pre-label again, all existing suggestions are replaced server-side anyway. Confirm this is acceptable UX — a dismissed suggestion will "come back" if pre-label is re-run.
3. **Entity type colors**: The entity palette assigns a color per entity type. The mockup cycles through a fixed color palette. Confirm whether colors are server-assigned (stored in the entity type record) or client-assigned (derived from index position in the entity type list).
