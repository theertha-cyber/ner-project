## Why

The Automated flow's stepper presented "Retraining" as step 4 of 4, alongside "Suggest Entity
Types", "Batch Pre-labeling", and "Review Sample" — three steps that form a real, one-time,
linear pipeline each of which reaches a "done" state. Retraining is neither: it is a recurring,
optional decision (the code itself could never mark it "done" — its state was hardcoded to never
resolve past "ready"/"blocked"), reachable at any time once there is a serving model or reviewed
material to weigh. Presenting it as "4/4" told a tenant admin it was the mandatory next thing to
do after Review Sample, which is false, and user feedback on the live screen confirmed it read
that way.

Separately, the Retraining page itself was hard to follow: its top figure ("N confirmed spans
from production review since this model was trained") and its "training-eligible and waiting"
breakdown are two unrelated measures — the first counts only spans confirmed through the
production-review queue, the second counts new material from any workflow not yet consumed by a
training run — but nothing on the page explained that, so a "0" next to a "1" read as a
contradiction rather than two different questions with two different answers.

## What Changes

- Remove "Retraining" from the Automated flow's numbered stepper. The stepper now shows 3 steps
  (Suggest Entity Types, Batch Pre-labeling, Review Sample); the stepper itself no longer renders
  at all on the `/annotate/automated/retrain` route, since that page is not one of those 3 steps.
- Drop the "4 · " step-number prefix from the "Retraining" nav item nested under "Automated" in
  the sidebar (used for breadcrumb derivation) — it now reads plainly as "Retraining".
- Add a "Retraining & promotion evidence" link to the Models & Training screen's Model Versions
  view (`tenant_admin` only), since retraining is a decision made in the context of the model
  registry, not a step following batch review. This is now the retrain page's primary,
  always-available entry point, replacing its former (mandatory-looking) stepper tile.
- Clarify the Retraining page's copy: rename "Reviewed material since this model was trained" to
  "Production-review evidence" with an explanatory line distinguishing it from the
  "Training-eligible and waiting" breakdown below it (itself given its own bridging sentence), and
  add a line to the page's intro stating there is no schedule or required order.
- Update the Automated landing page's explanatory paragraph to stop describing retraining as
  something that "unlocks" after review, and instead name it as a separate, optional decision
  reachable from Models & Training.

## Capabilities

### New Capabilities

- `retraining-decision-screen`: the `/annotate/automated/retrain` page's own presentation — its
  framing as an optional, recurring decision rather than a pipeline step, and the wording that
  distinguishes its two independent evidence sections. Mirrors the existing `human-gated-
  retraining` capability, which covers only the backend data contract this page renders.

### Modified Capabilities

- `automated-annotation-landing`: the stepper shown on `/annotate/automated` and its step routes
  now has 3 entries, not 4; the page's explanatory copy no longer frames retraining as unlocking
  after review.
- `training-jobs-screen`: the Model Versions view gains a "Retraining & promotion evidence" link
  for `tenant_admin`.
- `nav-config`: the "Automated" nav leaf's `Retraining` child no longer carries a step-number
  prefix in its label.

## Impact

- Frontend: [app/(auth)/annotate/automated/layout.tsx](src/portal/src/app/(auth)/annotate/automated/layout.tsx)
  (3-step stepper, hidden on the retrain route),
  [app/(auth)/annotate/automated/page.tsx](src/portal/src/app/(auth)/annotate/automated/page.tsx)
  (copy), [app/(auth)/training-jobs/page.tsx](src/portal/src/app/(auth)/training-jobs/page.tsx)
  (new link), [lib/nav-config.ts](src/portal/src/lib/nav-config.ts) (label),
  [components/retraining/RetrainingDecisionPage.tsx](src/portal/src/components/retraining/RetrainingDecisionPage.tsx)
  (copy).
- Tests: new [annotate/automated/layout.test.tsx](src/portal/src/app/(auth)/annotate/automated/layout.test.tsx);
  extended [training-jobs/page.test.tsx](src/portal/src/app/(auth)/training-jobs/page.test.tsx),
  [annotate/automated/page.test.tsx](src/portal/src/app/(auth)/annotate/automated/page.test.tsx);
  existing [nav-config.test.ts](src/portal/src/lib/nav-config.test.ts) and
  [RetrainingDecisionPage.test.tsx](src/portal/src/components/retraining/RetrainingDecisionPage.test.tsx)
  reconfirmed unaffected (they assert on structure/behavior, not the relabeled/rewritten text).
- No backend, database, or data-contract changes — `human-gated-retraining`'s endpoint responses
  are untouched; only how the portal presents them changed.
