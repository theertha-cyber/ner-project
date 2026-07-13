## Context

`/training-jobs` (labeled "Training Queue" for `system_admin`, "Training Jobs" for `tenant_admin` per `nav-config.ts`) already has the correct information architecture: a two-column layout (job list | detail panel), filter tabs, status timeline, hyperparameters, metrics, MLflow link, role-gated actions, and a submit slide-over. What it lacks is (a) the visual treatment the rest of the app has already adopted from `docs/NER Platform.html`, and (b) a handful of content elements the mockup includes that the current build doesn't: job-card hyperparameter/F1 summaries, a lineage diagram, and a richer running/metrics presentation.

The design tokens this needs already exist in `src/portal/src/app/globals.css` (`--ink`, `--ink-2`, `--ink-3`, `--surface-2`, `--surface-3`, `--line`, `--line-2`, `--primary`, `--primary-2`, `--primary-soft`, `--primary-line`, `--bad`, `--bad-soft`) and are exposed through `tailwind.config.ts` as `font-display` (Hanken Grotesk), `font-body` (Inter), `font-mono` (JetBrains Mono). `Sidebar`, `Topbar`, `Dashboard`, `Login`, `Widget Keys`, and `Extractions` already consume these; this change brings Training Jobs to parity using the same tokens rather than introducing new ones. The `entity-types-screen` spec (`openspec/specs/entity-types-screen/spec.md`) is the closest precedent for how a mockup-fidelity screen spec is written in this repo (concrete pixel/font/color values tied to mockup source) and this change follows that convention.

## Goals / Non-Goals

**Goals:**

- Re-skin every component under `src/portal/src/components/training-jobs/` and `page.tsx` to use existing design tokens/fonts, matching the mockup's visual language for this screen.
- Add the mockup content currently missing: job-card ID/hyperparameter/F1 summary, horizontal status timeline, dataset → job → model-version lineage diagram, richer running-state callout, large-stat metrics display, card-styled MLflow link.
- Keep the component boundaries and data-fetching hooks (`useTrainingJobs`, `useTrainingJob`, `useSubmitTrainingJob`, etc.) unchanged — this is a presentation-layer change.

**Non-Goals:**

- No backend, API, or Celery changes. No new fields threaded from the training-worker (e.g. no real "GPU worker id" — the mockup's "GPU worker-2" text is decorative and will remain a static/placeholder string, exactly as it is in the mockup itself).
- No change to `SubmitJobSlideover`'s span-count preflight check, epoch range-slider, or batch/seq dropdowns — those are being kept because they're better UX than the mockup's free-text inputs. Only their visual chrome (spacing, borders, fonts, colors) changes.
- No design-token additions to `globals.css` unless implementation discovers a genuinely missing token — expected to be zero, since every value this screen needs (status colors, ink/surface scale, pill styling) is already defined and used elsewhere.
- Not touching Documents, Entity Types, Users, Models, Tenants, or Audit pages — those remain generic-Tailwind and are out of scope per explicit user decision.

## Currently-In-Force ADRs

None. ADR-001 through ADR-008 govern tenant data isolation, base-model strategy, model-serving topology, OpenSpec governance, agent boundaries, training infrastructure, chatbot architecture, and default inference model — none constrain frontend presentation. This is a presentation-only change with no backend surface.

## Decisions

### Decision 1: Lineage diagram is a new reusable primitive, not a training-jobs-local component

**Choice:** Build the `dataset → training job → model version` flow diagram as `src/portal/src/components/ui/LineageFlow.tsx`, a generic three-(or-N)-box connector component that accepts an ordered list of `{ label, value, sublabel? }` nodes, rather than hardcoding it inside `job-detail-panel.tsx`.

**Rationale:** The mockup uses the identical box→arrow→box→arrow→box visual pattern for lineage; Model Registry is a natural future consumer (model version ← training job ← dataset, viewed from the other direction) and duplicating the diagram markup there later would be wasteful. Keeping it a `ui/` primitive costs nothing extra here (it's still only used once) and avoids a near-certain follow-up refactor.

**Alternatives considered:**
- Inline markup directly in `JobDetailPanel` — simplest for this change alone, but the entity-types/model-registry precedent in this codebase (shared `Badge`, `Spinner`, `SlideOver` in `components/ui`) suggests visual-pattern components belong in `ui/`, and the proposal's own Open Questions flagged this reuse question.

### Decision 2: Job-status color/pill logic stays centralized in the existing `Badge` component

**Choice:** Extend the existing `Badge` component's status-to-color mapping (already used by `JobCard`, `JobDetailPanel`) rather than hand-rolling pill styles per component, and drive the new horizontal timeline's dot/line colors off the same status-color source used by `Badge`.

**Rationale:** `design-tokens` spec already requires "Each status colour SHALL correspond to a `Badge` variant of the same name" — introducing a second, parallel status-color map (as the mockup's raw JS `statusColors()` does) would violate that existing spec and create drift risk between the card pill and the timeline dots.

**Alternatives considered:**
- Port the mockup's `statusColors()` function verbatim into a training-jobs-local helper — rejected because it duplicates `Badge`'s existing mapping and risks the two falling out of sync as statuses are added.

### Decision 3: `JobTimeline` reorientation is a rewrite, not a CSS-only flip

**Choice:** Rewrite `JobTimeline` (`src/portal/src/components/training-jobs/job-timeline.tsx`) as a horizontal flex row of `{dot + label}` pairs joined by flexible connector lines (`flex:1; height:2px`), mirroring the mockup's structure, rather than attempting to reuse the current vertical DOM with a CSS `flex-direction` swap.

**Rationale:** The current vertical implementation renders the connecting line as a `width: 0.5px` column between stacked dots (`mt-0.5 w-0.5 flex-1`); the mockup's horizontal version needs the connector as a `flex:1` horizontal line between inline dot+label groups, with the whole row `display:flex;align-items:center`. These are different enough DOM shapes that a straight orientation flip would leave dead/wrong CSS. Existing `job-timeline.test.tsx` assertions on step state classes will need updating to match the new DOM.

**Alternatives considered:**
- CSS Grid with `grid-auto-flow: column` reusing the same step-state class map — possible, but the mockup's per-step inline style computation (`dotStyle`, `textStyle` built per timeline entry) maps more directly onto a flat row of styled `div`s than a grid reinterpretation of the current stacked markup.

## Risks / Trade-offs

- [Re-skinning 9 components risks visual regressions in states not covered by existing tests (e.g. failed/rejected/cancelled job detail views)] → Manually walk every `JobStatus` value (`pending_approval`, `queued`, `running`, `completed`, `failed`, `rejected`, `cancelled`) in both roles (`system_admin`, `tenant_admin`) during implementation, per the `run`/`verify` skill, before marking the change done.
- [Extracting `LineageFlow` as a shared primitive up front, before a second consumer exists, could over-engineer the API] → Keep its prop shape minimal (label/value/sublabel triples) and resist adding configurability (icons, custom colors per node) until Model Registry actually needs it.
- [Existing `*.test.tsx` files assert on current Tailwind class names and the vertical timeline's DOM shape; re-skinning will break them] → Treat test updates as part of this change's task list, not a follow-up; a re-skin that breaks the test suite without fixing it is not done.

## Migration Plan

Purely additive/presentational — no data migration, no feature flag needed. Ship as a single PR touching only `src/portal/src/{app/(auth)/training-jobs,components/training-jobs,components/ui}`. Rollback is a plain revert; no backend or database state depends on this change.

## Open Questions

None outstanding — the proposal's two open questions (lineage-component reuse, GPU-worker field) are resolved above (reusable `ui/` primitive; static placeholder text, no new field).
