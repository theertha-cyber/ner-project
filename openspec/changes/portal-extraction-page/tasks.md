## 1. Scaffold

- [x] 1.1 Create directory `src/portal/src/components/extractions/`
- [x] 1.2 Create directory `src/portal/src/hooks/` entry for extraction hooks (or add alongside existing hooks)
- [x] 1.3 Update `src/portal/src/app/(auth)/extractions/page.tsx` — replace `PlaceholderScreen` import and render with `<ExtractionPage />`

## 2. API Hooks

- [x] 2.1 Create `src/portal/src/hooks/use-extract.ts` — manages `text` state, `running` state, `result` (entity array), and `modelVersion`; exposes `run(text)` which calls `POST /api/v1/extract` via `authFetch`; clears result on new run; updates `modelVersion` from response
- [x] 2.2 Create `src/portal/src/hooks/use-batch-runs.ts` — fetches batch run list on mount; exposes `triggerBatch()` which calls `POST /api/v1/extract-batch` and prepends the new run; polls `GET /api/v1/extract-batch/{run_id}` every 3 seconds for each run with status "running" or "queued"; stops polling per run on terminal state; clears all intervals on unmount
- [x] 2.3 Create `src/portal/src/hooks/use-entities.ts` — fetches `GET /api/v1/entities` (with optional `reviewStatus` query param); exposes `confirm(id)` and `reject(id)` which call `PATCH /api/v1/entities/{id}` and optimistically update the entity's `review_status` in local state before the response resolves

## 3. ExtractionPage — Shell and Tab Navigation

- [x] 3.1 Create `src/portal/src/components/extractions/ExtractionPage.tsx` — renders page header ("Extraction" h1 + kicker label), three-tab segment control pill ("Playground" / "Batch Runs" / "Entity Review"), and conditionally renders the active tab component; active tab stored in `useState<'playground' | 'batch' | 'entities'>('playground')`
- [x] 3.2 Style the tab pill to match mockup: `background: var(--surface-2); border: 1px solid var(--line); border-radius: 12px; padding: 4px`; active button gets `background: var(--primary); color: #fff`; page content area has `padding: 28px 32px 60px; max-width: 1180px; margin: 0 auto`
- [x] 3.3 Write `src/portal/src/components/extractions/ExtractionPage.test.tsx`:
  - Test 1 (→ verification row 1): default render shows "Extraction" heading, three tabs, Playground content, Playground tab active
  - Test 2 (→ verification row 2): clicking "Batch Runs" shows batch content and Playground is absent from DOM

## 4. PlaygroundTab Component

- [x] 4.1 Create `src/portal/src/components/extractions/PlaygroundTab.tsx` — two-column grid (`1fr 1fr`, gap 18px); left card: "Input text" heading + "model v{N} · serving" label, resizable textarea (pre-filled sample text), "Run extraction" button with inline spinner when running; right card: "Entities" heading + count label, entity rows or spinner during in-flight
- [x] 4.2 Each entity row in the results panel: entity type chip (colored dot + type label in JetBrains Mono), entity value in bold, confidence label right-aligned
- [x] 4.3 Disable "Run extraction" button and show spinner inside it while `running === true`; guard against empty textarea (no request if text is empty or whitespace-only)
- [x] 4.4 Show animated circular spinner centered in the right card while `running === true`; hide previous results during in-flight state
- [x] 4.5 Update model version label from `modelVersion` state after each successful response; default to "—" or the promoted version when no extraction has been run
- [x] 4.6 Write `src/portal/src/components/extractions/PlaygroundTab.test.tsx`:
  - Test 3 (→ row 3): mock `POST /api/v1/extract`, assert call made, button disabled during request, entity rows rendered on 200
  - Test 4 (→ row 4): assert spinner visible in results panel during in-flight; no previous results shown
  - Test 5 (→ row 5): mock response with `model_version: "3"`, assert label reads "model v3 · serving"
  - Test 6 (→ row 6): assert no API call when textarea is empty

## 5. BatchRunsTab Component

- [x] 5.1 Create `src/portal/src/components/extractions/BatchRunsTab.tsx` — header row with label + "New batch run" primary button; two-column layout (`340px 1fr`); left: list of `BatchRunCard` components; right: `BatchRunDetail` panel
- [x] 5.2 Create `src/portal/src/components/extractions/BatchRunCard.tsx` — displays run ID (JetBrains Mono), status pill, progress bar (`processed/total * 100%`), footer row with "N% docs · model vM" and start timestamp; selected state adds primary-color border
- [x] 5.3 Create `src/portal/src/components/extractions/BatchRunDetail.tsx` — header row (run ID + status pill + model label), large percentage number (`font-size: 46px`, primary color), progress bar, 4-cell stats grid (TOTAL, PROCESSED in `var(--good)`, SKIPPED in `var(--warn)`, FAILED in `var(--bad)`)
- [x] 5.4 Auto-select the most recent run on tab mount; "New batch run" button calls `triggerBatch()` from `useBatchRuns`, prepends new run to list, auto-selects it
- [x] 5.5 Status pill color tokens: "completed" → `var(--good)`; "running"/"queued" → `var(--warn)`; "failed" → `var(--bad)`
- [x] 5.6 Write `src/portal/src/components/extractions/BatchRunsTab.test.tsx`:
  - Test 7 (→ row 7): assert run cards render with ID, status, progress bar, and footer
  - Test 8 (→ row 8): click a card, assert primary border and detail panel stats update
  - Test 9 (→ row 9): mock `POST /api/v1/extract-batch` 202, assert new run at top of list, auto-selected
  - Test 10 (→ row 10): use fake timers (`vi.useFakeTimers`), assert GET poll called every 3s for "running" run; assert interval clears on "completed"
  - Test 11 (→ row 11): assert correct color token applied to each status pill variant

## 6. EntityReviewTab Component

- [x] 6.1 Create `src/portal/src/components/extractions/EntityReviewTab.tsx` — filter pill row (all / unreviewed / confirmed / corrected / rejected) + entity count label; entity table with 5-column grid; calls `useEntities(filter)` on mount and filter change
- [x] 6.2 Create `src/portal/src/components/extractions/EntityRow.tsx` — TYPE column: entity type chip; VALUE column: entity text (bold) + document filename subtitle; CONFIDENCE column: value colored by threshold (≥ 0.90 `var(--good)`, 0.70–0.89 `var(--warn)`, < 0.70 `var(--bad)`); REVIEW column: review status pill; actions column: confirm (✓) and reject (✗) icon buttons
- [x] 6.3 Active filter pill: filled primary background; inactive: unstyled within row; changing filter calls `setFilter` and re-fetches via hook
- [x] 6.4 Confirm button calls `confirm(id)` from `useEntities` — optimistic update sets `review_status: "confirmed"` in local state immediately; reject button calls `reject(id)` — optimistic update sets `review_status: "rejected"`
- [x] 6.5 Show empty state message when entity list is empty after fetch
- [x] 6.6 Write `src/portal/src/components/extractions/EntityReviewTab.test.tsx`:
  - Test 12 (→ row 12): assert `GET /api/v1/entities` called without reviewStatus param on mount, "all" pill active
  - Test 13 (→ row 13): click "unreviewed" pill, assert `GET /api/v1/entities?reviewStatus=unreviewed` called
  - Test 14 (→ row 14): render with fixture entity, assert all four columns show correct values
  - Test 15 (→ row 15): click confirm button, assert PATCH called with `{review_status: "confirmed"}`, row updates optimistically
  - Test 16 (→ row 16): click reject button, assert PATCH called with `{review_status: "rejected"}`, row updates optimistically
  - Test 17 (→ row 17): render entities with confidence 0.94, 0.75, 0.62, and 0.90 — assert correct color tokens including boundary at 0.90
  - Test 18 (→ row 18): render with empty entity list, assert empty state message visible

## 7. Verification & Evidence

- [ ] 7.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass
- [ ] 7.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log
- [ ] 7.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register
- [ ] 7.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance
- [ ] 7.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent)
- [ ] 7.6 Run `openspec validate portal-extraction-page --type change --strict` and confirm it exits clean before archive
