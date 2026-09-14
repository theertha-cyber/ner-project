## MODIFIED Requirements

### Requirement: Detail panel header shows the full job id and creation timestamp

The detail panel header SHALL show the job's `run_name` (e.g. `run-003-20260729`) as the primary identifier in a larger monospace weight, falling back to the job's full id (not truncated) when `run_name` is absent (legacy jobs with no `run_number`), the status `Badge`, and the job's creation timestamp right-aligned in the same row — matching the mockup's `dJobId` / `dStatus` / `dCreated` header row. This timestamp is shown once here rather than repeated on every list card (see "Job list card content").

#### Scenario: Detail header shows the run name and a creation date

- **GIVEN** a selected training job with `run_name: "run-003-20260729"` and a `created_at` timestamp
- **WHEN** the detail panel renders
- **THEN** the header shows "run-003-20260729" as the primary identifier
- **AND** a formatted creation date/time appears at the right edge of the header row

#### Scenario: Detail header falls back to the full job id for legacy jobs

- **GIVEN** a selected training job with `run_name: null` and a full UUID `id`
- **WHEN** the detail panel renders
- **THEN** the header shows the complete job id (not sliced to 8 characters) in place of a run name

### Requirement: Job list card content

The `JobCard` component SHALL display, for each job: a status-colored dot (sourced from the same status-color mapping `Badge` uses, per the `design-tokens` spec and this change's Decision 2 — not a second color map) to the left of the job identifier, pulsing only when `status === "running"`; the job's `run_name` (falling back to its id when `run_name` is absent) in `font-mono`; a status pill (via `Badge`); a hyperparameter summary line formatted as `lr {learning_rate} · {num_epochs}ep · bs {batch_size}`; and the job's F1 score (read from `metrics.eval_f1`, the key the training worker actually persists — see `src/training_service/worker.py`) formatted to two decimal places, or `"—"` when no F1 score is available (job has not completed evaluation). Per the mockup (`docs/NER Platform.html`), the card SHALL NOT show a separate creation-date line — the creation timestamp is shown once, in the detail panel header, not repeated on every list card.

#### Scenario: Running job card shows full summary with run name

- **GIVEN** a training job `{id: "tj_9f2a", run_name: "run-005-20260729", status: "running", hyperparams: {learning_rate: 2e-5, num_epochs: 3, batch_size: 8}, metrics: null}`
- **WHEN** its `JobCard` renders
- **THEN** the card shows "run-005-20260729" in monospace
- **AND** a pulsing status-colored dot is visible
- **AND** the hyperparameter line reads "lr 0.00002 · 3ep · bs 8"
- **AND** the F1 value reads "—"

#### Scenario: Completed job card shows F1 score

- **GIVEN** a training job `{id: "tj_7c04", run_name: "run-006-20260729", status: "completed", metrics: {eval_f1: 0.90}}`
- **WHEN** its `JobCard` renders
- **THEN** the F1 value reads "0.90"
- **AND** the status dot is visible but not pulsing

#### Scenario: Non-running job still shows a status-colored dot

- **GIVEN** a training job with status "pending_approval"
- **WHEN** its `JobCard` renders
- **THEN** a dot colored per the "pending_approval" status is visible
- **AND** it does not pulse

#### Scenario: Legacy job card falls back to job id when run_name is absent

- **GIVEN** a training job `{id: "tj_1a2b", run_name: null, status: "completed", metrics: {eval_f1: 0.85}}`
- **WHEN** its `JobCard` renders
- **THEN** the card shows the job id "tj_1a2b" in monospace in place of a run name

### Requirement: Dataset-to-model lineage diagram

The job detail panel SHALL render a lineage diagram showing the flow `dataset → training job → model version` as three connected boxes, using a reusable `LineageFlow` UI primitive (`src/portal/src/components/ui/LineageFlow.tsx`). Each box SHALL show a small caption label ("DATASET", "TRAINING JOB", "MODEL VERSION") and a primary value. The DATASET box's value is a static/decorative label ("Annotated Documents") since no dataset entity exists in the system (training jobs consume a tenant's entire confirmed-annotation export, not a named dataset). The TRAINING JOB box's value is the job's `run_name` (falling back to the job id for legacy jobs), with a `dslim/bert-base-NER` sublabel (the ADR-002-mandated base model every training job actually fine-tunes from — a real, static compliance fact, not an invented field). The MODEL VERSION box's value is the resolved model version's `run_name` (falling back to `v{version_number}` for legacy model versions) for the promoted model version whose `training_job_id` matches this job (resolved via the existing `/api/v1/models` list), or "pending" if no matching version exists, with a static "registry" sublabel. The training-job box SHALL be visually emphasized (primary-colored background/border) relative to the dataset and model-version boxes. Unlike the mockup, the DATASET box SHALL NOT show a span-count sublabel, since no per-job confirmed-span-count field exists on `TrainingJob` — inventing one would violate this change's Non-Goals (see design.md Decision 4).

#### Scenario: Training job and model version boxes show their sublabels

- **GIVEN** a training job detail panel renders its lineage diagram
- **WHEN** the TRAINING JOB and MODEL VERSION boxes render
- **THEN** the TRAINING JOB box shows a "dslim/bert-base-NER" sublabel
- **AND** the MODEL VERSION box shows a "registry" sublabel

#### Scenario: Lineage renders for a completed job with a promoted model, using matching run names

- **GIVEN** a training job `{id: "tj_7c04", run_name: "run-006-20260729"}` and a model version `{training_job_id: "tj_7c04", version_number: 3, run_name: "run-006-20260729"}`
- **WHEN** the detail panel renders
- **THEN** the lineage diagram shows three boxes reading "Annotated Documents", "run-006-20260729", and "run-006-20260729" in order, connected by arrows
- **AND** the middle box has the emphasized/primary styling

#### Scenario: Lineage renders "pending" for a job with no model version yet

- **GIVEN** a training job `{id: "tj_9f2a", run_name: "run-009-20260729"}` with no matching model version in `/api/v1/models`
- **WHEN** the detail panel renders
- **THEN** the third box reads "pending" instead of a run name

#### Scenario: Lineage falls back to job id and version-number label for legacy entries

- **GIVEN** a legacy training job `{id: "tj_0001", run_name: null}` and its legacy model version `{version_number: 1, run_name: null}`
- **WHEN** the detail panel renders
- **THEN** the TRAINING JOB box shows "tj_0001"
- **AND** the MODEL VERSION box shows "v1"
