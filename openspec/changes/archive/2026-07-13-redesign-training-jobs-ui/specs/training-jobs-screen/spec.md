## ADDED Requirements

### Requirement: Design token compliance

The Training Jobs screen (`/training-jobs`, all components under `src/portal/src/components/training-jobs/`) SHALL use the design tokens declared in `src/portal/src/app/globals.css` (`--ink`, `--ink-2`, `--ink-3`, `--surface-2`, `--surface-3`, `--line`, `--line-2`, `--primary`, `--primary-2`, `--primary-soft`, `--primary-line`, `--bad`, `--bad-soft`, plus existing `--color-status-*` tokens via `Badge`) and the `font-display` (Hanken Grotesk), `font-body` (Inter), and `font-mono` (JetBrains Mono) font families exposed by `tailwind.config.ts`. The screen SHALL NOT use generic Tailwind gray-scale utilities (`text-gray-*`, `bg-gray-*`, `border-gray-*`) or hardcoded hex colors.

#### Scenario: No generic gray utility classes remain

- **GIVEN** the training-jobs component directory
- **WHEN** its source files are searched for `text-gray-`, `bg-gray-`, or `border-gray-` class name fragments
- **THEN** no match is found

#### Scenario: Page heading uses display font

- **GIVEN** a user navigates to `/training-jobs`
- **WHEN** the page renders
- **THEN** the `h1` "Training Jobs" heading is rendered in the `font-display` family at a weight of 700 or higher

### Requirement: Page header matches the mockup's breadcrumb, heading scale, and submit button

Per the mockup's actual computed styles, the page header SHALL show a small monospace breadcrumb (`/api/v1/training-jobs`, 11px, `var(--ink-3)`, letter-spacing `0.06em`) above the `h1`; the `h1` SHALL render at 34px / weight 800 (Hanken Grotesk) with `-0.03em` letter-spacing, not a generic Tailwind heading size; and the "Submit job" button (lowercase "job", matching the mockup's literal copy) SHALL use `var(--primary)` background, white text, `12px` border-radius, `11px 17px` padding, and a soft drop shadow, rather than a generic small rounded-lg button.

#### Scenario: Header shows the API-path breadcrumb above the heading

- **GIVEN** a user navigates to `/training-jobs`
- **WHEN** the page renders
- **THEN** a small monospace `/api/v1/training-jobs` label appears above the "Training Jobs" heading

#### Scenario: Submit button copy matches the mockup exactly

- **GIVEN** a Tenant Admin views the page
- **WHEN** the header renders
- **THEN** the submit button reads "+ Submit job" (lowercase "job")

### Requirement: Detail panel header shows the full job id and creation timestamp

The detail panel header SHALL show the job's full id (not truncated) in a larger monospace weight, the status `Badge`, and the job's creation timestamp right-aligned in the same row — matching the mockup's `dJobId` / `dStatus` / `dCreated` header row. This timestamp is shown once here rather than repeated on every list card (see "Job list card content").

#### Scenario: Detail header shows the untruncated job id and a creation date

- **GIVEN** a selected training job with a full id and a `created_at` timestamp
- **WHEN** the detail panel renders
- **THEN** the header shows the complete job id (not sliced to 8 characters)
- **AND** a formatted creation date/time appears at the right edge of the header row

### Requirement: Job list card content

The `JobCard` component SHALL display, for each job: a status-colored dot (sourced from the same status-color mapping `Badge` uses, per the `design-tokens` spec and this change's Decision 2 — not a second color map) to the left of the job ID, pulsing only when `status === "running"`; the job ID in `font-mono`; a status pill (via `Badge`); a hyperparameter summary line formatted as `lr {learning_rate} · {num_epochs}ep · bs {batch_size}`; and the job's F1 score (read from `metrics.eval_f1`, the key the training worker actually persists — see `src/training_service/worker.py`) formatted to two decimal places, or `"—"` when no F1 score is available (job has not completed evaluation). Per the mockup (`docs/NER Platform.html`), the card SHALL NOT show a separate creation-date line — the creation timestamp is shown once, in the detail panel header, not repeated on every list card.

#### Scenario: Running job card shows full summary

- **GIVEN** a training job `{id: "tj_9f2a", status: "running", hyperparams: {learning_rate: 2e-5, num_epochs: 3, batch_size: 8}, metrics: null}`
- **WHEN** its `JobCard` renders
- **THEN** the card shows the job ID "tj_9f2a" in monospace
- **AND** a pulsing status-colored dot is visible
- **AND** the hyperparameter line reads "lr 0.00002 · 3ep · bs 8"
- **AND** the F1 value reads "—"

#### Scenario: Completed job card shows F1 score

- **GIVEN** a training job `{id: "tj_7c04", status: "completed", metrics: {eval_f1: 0.90}}`
- **WHEN** its `JobCard` renders
- **THEN** the F1 value reads "0.90"
- **AND** the status dot is visible but not pulsing

#### Scenario: Non-running job still shows a status-colored dot

- **GIVEN** a training job with status "pending_approval"
- **WHEN** its `JobCard` renders
- **THEN** a dot colored per the "pending_approval" status is visible
- **AND** it does not pulse

### Requirement: Horizontal status timeline

The `JobTimeline` component SHALL render the job's lifecycle steps as a horizontal row of dot-and-label pairs connected by horizontal connector lines, rather than a vertically stacked stepper. Steps SHALL be laid out left-to-right in lifecycle order. Each step's dot and connector color SHALL be sourced from the same status-color mapping used by `Badge` (per the `design-tokens` spec's requirement that each status color correspond to a `Badge` variant). The step matching the job's current status SHALL be visually distinguished (filled dot, bold label) from completed steps (filled, non-bold) and future/unreached steps (muted/outline).

#### Scenario: Running job shows horizontal timeline with current step highlighted

- **GIVEN** a training job with status "running" whose lifecycle is `pending_approval → queued → running → completed`
- **WHEN** the `JobTimeline` renders
- **THEN** the four steps are arranged in a single horizontal row, left to right
- **AND** "running" is shown with a distinguished (bold/filled) dot and label
- **AND** "pending_approval" and "queued" are shown as completed (filled, non-bold)
- **AND** "completed" is shown as a future step (muted)

#### Scenario: Failed job shows the failure branch, not the full lifecycle

- **GIVEN** a training job with status "failed"
- **WHEN** the `JobTimeline` renders
- **THEN** the row shows `pending_approval → queued → running → failed`
- **AND** does not show a "completed" step

### Requirement: Dataset-to-model lineage diagram

The job detail panel SHALL render a lineage diagram showing the flow `dataset → training job → model version` as three connected boxes, using a reusable `LineageFlow` UI primitive (`src/portal/src/components/ui/LineageFlow.tsx`). Each box SHALL show a small caption label ("DATASET", "TRAINING JOB", "MODEL VERSION") and a primary value. The DATASET box's value is a static/decorative label ("Annotated Documents") since no dataset entity exists in the system (training jobs consume a tenant's entire confirmed-annotation export, not a named dataset). The TRAINING JOB box's value is the job ID, with a `dslim/bert-base-NER` sublabel (the ADR-002-mandated base model every training job actually fine-tunes from — a real, static compliance fact, not an invented field). The MODEL VERSION box's value is `v{version_number}` for the promoted model version whose `training_job_id` matches this job (resolved via the existing `/api/v1/models` list), or "pending" if no matching version exists, with a static "registry" sublabel. The training-job box SHALL be visually emphasized (primary-colored background/border) relative to the dataset and model-version boxes. Unlike the mockup, the DATASET box SHALL NOT show a span-count sublabel, since no per-job confirmed-span-count field exists on `TrainingJob` — inventing one would violate this change's Non-Goals (see design.md Decision 4).

#### Scenario: Training job and model version boxes show their sublabels

- **GIVEN** a training job detail panel renders its lineage diagram
- **WHEN** the TRAINING JOB and MODEL VERSION boxes render
- **THEN** the TRAINING JOB box shows a "dslim/bert-base-NER" sublabel
- **AND** the MODEL VERSION box shows a "registry" sublabel

#### Scenario: Lineage renders for a completed job with a promoted model

- **GIVEN** a training job `{id: "tj_7c04"}` and a model version `{training_job_id: "tj_7c04", version_number: 3}`
- **WHEN** the detail panel renders
- **THEN** the lineage diagram shows three boxes reading "Annotated Documents", "tj_7c04", and "v3" in order, connected by arrows
- **AND** the middle ("tj_7c04") box has the emphasized/primary styling

#### Scenario: Lineage renders "pending" for a job with no model version yet

- **GIVEN** a training job `{id: "tj_9f2a"}` with no matching model version in `/api/v1/models`
- **WHEN** the detail panel renders
- **THEN** the third box reads "pending" instead of a version number

### Requirement: Hyperparameters render as a single 4-column row

The hyperparameters section SHALL lay its four values (learning rate, epochs, batch size, max sequence length) out in a single row of four equal-width columns, matching the mockup's `grid-template-columns:1fr 1fr 1fr 1fr`, not a 2×2 grid.

#### Scenario: Hyperparameters grid has 4 columns

- **GIVEN** a training job with hyperparams set
- **WHEN** the detail panel renders the hyperparameters section
- **THEN** its grid container has 4 columns, not 2

### Requirement: Live running-job callout

When a job's status is "running", the detail panel SHALL render a highlighted callout (info-colored background and border) containing: a pulsing status dot with the label "Fine-tuning in progress", the current epoch relative to total epochs (e.g. "epoch 2/3"), an animated horizontal progress bar reflecting epoch completion fraction, and a stat row showing current loss, current epoch (decimal precision), and a GPU worker identifier. The GPU worker identifier MAY be a static/placeholder string since no backend field currently supplies it.

#### Scenario: Running job shows the live callout

- **GIVEN** a training job `{status: "running", current_epoch: 2, current_loss: 0.032, hyperparams: {num_epochs: 3}}`
- **WHEN** the detail panel renders
- **THEN** an info-colored callout is visible with "Fine-tuning in progress" and a pulsing dot
- **AND** the header shows "epoch 2/3"
- **AND** the progress bar width reflects approximately 2/3 completion
- **AND** the stat row shows loss "0.032" and a GPU worker value

#### Scenario: Non-running job shows no callout

- **GIVEN** a training job with status "completed"
- **WHEN** the detail panel renders
- **THEN** no running-callout element is present

### Requirement: Large-stat evaluation metrics

When a job has evaluation metrics, the detail panel SHALL render `metrics.eval_f1`, `metrics.eval_precision`, and `metrics.eval_recall` (the keys the training worker actually persists — see `src/training_service/worker.py`) as large numeric stat values labeled "f1"/"precision"/"recall" (each with its own mini horizontal progress bar sized to the metric's value as a percentage) rather than as compact list rows, plus a separate `eval_loss` line (from `metrics.eval_loss`) below the stat group.

#### Scenario: Completed job shows large-stat metrics

- **GIVEN** a training job `{status: "completed", metrics: {eval_f1: 0.90, eval_precision: 0.92, eval_recall: 0.89, eval_loss: 0.021}}`
- **WHEN** the detail panel renders
- **THEN** "0.90", "0.92", and "0.89" are each shown as large stat numbers labeled "f1"/"precision"/"recall" with their own mini progress bar
- **AND** an "eval_loss 0.021" line is shown separately below the stat group

### Requirement: MLflow run link as card

When a job has an associated MLflow run URL, the detail panel SHALL render it as a bordered card containing an icon, the label "MLflow run", and the truncated run URL, rather than as a plain inline text link.

#### Scenario: Job with MLflow URL shows link card

- **GIVEN** a training job with `mlflow_run_url: "http://localhost:5000/#/experiments/3/runs/a1b2c3d4e5f6"`
- **WHEN** the detail panel renders
- **THEN** a bordered card is visible containing an icon, the text "MLflow run", and the (possibly truncated) URL
- **AND** the card is a link that opens the URL in a new tab

### Requirement: Filter tab active state is not obscured by hover styling

`JobFilterTabs` SHALL match the mockup's (`docs/NER Platform.html`) actual computed tab styling and content, verified against its `tFilterTabs` computation: tabs in order all/running/pending_approval/completed/failed, labeled lowercase with underscores replaced by spaces ("all", "running", "pending approval", "completed", "failed"), each with a `1px solid var(--line)` border; the active tab has `background: var(--ink)` and `color: var(--surface-2)`; inactive tabs have `background: var(--surface-2)` and `color: var(--ink-2)`. The mockup's own tab template has no hover interaction at all — `JobFilterTabs` SHALL NOT introduce one, since a from-scratch imperative-hover mechanism is exactly what previously caused the active tab's fill to be obscured by a stale inline style after a click (see git history / this change's `job-filter-tabs.tsx`). Active/inactive styling SHALL be driven entirely by props on every render (no DOM mutation outside React), so there is no stale-state class of bug to guard against.

#### Scenario: Selecting a tab shows the dark/ink active fill immediately

- **GIVEN** the "all" tab is currently selected and the pointer hovers then clicks the "pending approval" tab
- **WHEN** the click is registered and `JobFilterTabs` re-renders with `selected: "pending_approval"`
- **THEN** the "pending approval" tab shows `background: var(--ink)` / `color: var(--surface-2)`
- **AND** this is correct immediately, without requiring the pointer to leave and re-enter the element

### Requirement: Filter tabs do not overflow into adjacent content

The `JobFilterTabs` row SHALL remain fully contained within its parent sidebar column at the sidebar's fixed width (`w-80`, 320px) for all five tabs. Tabs SHALL wrap to a second row, shrink, or scroll horizontally within their own container — they SHALL NOT render outside the sidebar's right edge or overlap the detail panel.

#### Scenario: All five tabs render without overlapping the detail panel

- **GIVEN** the training-jobs page is rendered at the standard sidebar width
- **WHEN** `JobFilterTabs` renders all five tabs ("all", "running", "pending approval", "completed", "failed")
- **THEN** every tab's bounding box is contained within the sidebar column's width
- **AND** no tab visually overlaps the detail panel to its right

### Requirement: Detail panel defaults to the most recent job when none is selected

When the training-jobs page loads (or a filter tab changes) with no `?selected=` job id in the URL, the page SHALL automatically select the most recent job in the current list (the first item, per the list's existing most-recent-first ordering) rather than leaving no job selected. The `JobDetailPanel`'s "Job not found" error state SHALL be reserved for a `?selected=` id that does not resolve to a real job (a genuine 404/fetch error) and SHALL NOT be shown merely because no id has been selected yet.

#### Scenario: Loading the page with no selection auto-selects the latest job

- **GIVEN** a Tenant Admin navigates to `/training-jobs` with no `selected` query parameter
- **AND** the job list returns at least one job, most recent first
- **WHEN** the page finishes loading the list
- **THEN** the first (most recent) job is automatically selected
- **AND** its details render in the detail panel instead of a "Job not found" message

#### Scenario: An explicitly-selected job id that does not exist still shows "Job not found"

- **GIVEN** the URL contains `?selected=does-not-exist`
- **WHEN** the detail fetch for that id resolves as an error (404)
- **THEN** the "Job not found" message is shown, since this is a genuine lookup failure rather than an absence of selection

### Requirement: Submit slide-over visual parity without behavior change

The `SubmitJobSlideover` component SHALL be restyled to use the screen's design tokens and fonts (borders, spacing, input styling, button styling) while preserving its existing behavior: the live annotated-span-count preflight check, the epoch range slider, and the batch-size / max-sequence-length dropdown selectors SHALL remain unchanged in function.

#### Scenario: Slide-over still performs span preflight check after restyle

- **GIVEN** a Tenant Admin opens the submit slide-over
- **WHEN** the slide-over mounts
- **THEN** it still fetches and displays the confirmed annotated span count exactly as before the restyle
- **AND** the epoch control is still a range slider (not a free-text field)
- **AND** batch size and max sequence length are still dropdown selectors with the same option sets
