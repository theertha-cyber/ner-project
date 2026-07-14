## Why

The Training Jobs screen (`/training-jobs`) was never carried through the mockup-fidelity design pass already applied to the Dashboard, Login, Widget Keys, Extractions pages, and the app shell (Sidebar/Topbar). Those pages consume the `--ink` / `--surface-2` / `--primary` design tokens and JetBrains Mono / Hanken Grotesk fonts defined in `globals.css`; Training Jobs still renders with generic Tailwind gray-scale utility classes. Beyond the visual mismatch, the screen is also missing content the mockup (`docs/NER Platform.html`) treats as core to the job-monitoring workflow: per-job hyperparameter/F1 summaries on the list cards, a dataset → job → model-version lineage trail, and a more legible running-job callout. This change closes both gaps so System Admins reviewing the approval queue and Tenant Admins tracking their runs get the same fidelity as the rest of the product.

## What Changes

- Re-skin `page.tsx` and all `components/training-jobs/*` to use the existing `--ink`/`--surface-2`/`--surface-3`/`--line`/`--primary`/`--bad` tokens and JetBrains Mono / Hanken Grotesk / Inter fonts in place of generic Tailwind gray classes, matching the visual language already used on Dashboard/Extractions/Widget Keys.
- `JobCard`: add the monospace job ID, hyperparameter summary line (`lr {lr} · {epochs}ep · bs {batch}`), and F1 score (or "—" when absent) alongside the existing status pill and pulsing running-dot.
- `JobTimeline`: reorient from a vertical stepper to the mockup's horizontal stepper (dots connected by horizontal lines, labels beneath/inline).
- Add a new lineage component rendering `dataset → training job → model version` as a three-box flow diagram in the detail panel, matching the mockup's LINEAGE section.
- `JobProgress`: restyle the running state as a highlighted info-colored callout with a pulsing status dot, a larger animated progress bar, and a loss / epoch / GPU-worker stat row (GPU worker label is decorative/static, matching the mockup — no new backend field required).
- `JobMetrics`: restyle evaluation metrics as large stat numbers (F1, precision, recall) each with its own mini progress bar, plus a separate `eval_loss` line, replacing the current compact list rows.
- Restyle the MLflow link as a card with an icon and truncated run URL instead of a plain text link.
- Re-skin `SubmitJobSlideover`, `JobFilterTabs`, `JobActions`, and `JobDetailPanel` chrome (spacing, borders, shadows, pill badges) to match tokens — **no behavioral change** to the slide-over's span-count preflight check, epoch slider, or batch/seq dropdowns, which are being kept as-is because they're better UX than the mockup's free-text fields.

## Capabilities

### New Capabilities

- `training-jobs-screen`: The Training Jobs / Training Queue page UI — list cards, filter tabs, detail panel (timeline, lineage, live progress, metrics, MLflow link, actions), and submit slide-over — styled to the mockup's design tokens and including the lineage/timeline/card-summary content it currently lacks.

### Modified Capabilities

*(none — the existing `training-jobs` spec covers the backend API and is unaffected; this change is presentation-only and introduces no new endpoints or payload fields)*

## Impact

- **Frontend only.** No API, schema, or Celery changes.
- Files: `src/portal/src/app/(auth)/training-jobs/page.tsx` and all of `src/portal/src/components/training-jobs/*.tsx` (`job-card`, `job-list`, `job-filter-tabs`, `job-timeline`, `job-metrics`, `job-progress`, `job-detail-panel`, `job-actions`, `submit-job-slideover`), plus their `*.test.tsx` files (assertions on class names / DOM structure will need updates where they hard-code the old Tailwind classes or the vertical-timeline DOM shape).
- New component: a lineage/flow-diagram component (exact file name TBD in design.md).
- Depends on tokens already present in `src/portal/src/app/globals.css` — no new tokens should be needed, but design.md should confirm during implementation.

## Open Questions

- Should the new lineage component be training-jobs-specific or built as a small reusable primitive (e.g. `components/ui/LineageFlow.tsx`) for reuse by Model Registry later? Leaning reusable primitive, to be confirmed in design.md.
- The mockup's "GPU worker-2" label in the running callout is static/decorative in the mockup itself (no real GPU-worker field in job state). Confirm we're fine hardcoding a placeholder rather than threading a real field through — assumed yes since this is presentation-only scope.
