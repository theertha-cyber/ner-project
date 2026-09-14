## 1. Stepper restructure

- [x] 1.1 Remove the "Retraining" tile from `automated/layout.tsx`'s `steps` array; drop the
  now-unused `useRetrainingDecision` call and `accumulation` variable.
- [x] 1.2 Hide the stepper entirely on the `/annotate/automated/retrain` route (checked via
  `usePathname`), since Retraining is no longer one of the 3 steps it would otherwise imply.
- [x] 1.3 Drop the "4 · " prefix from the "Retraining" nav child's label in `nav-config.ts`.

## 2. New entry point

- [x] 2.1 Add a "Retraining & promotion evidence" link to the Training Jobs screen's Model
  Versions view header, `tenant_admin` only, navigating to `/annotate/automated/retrain`.

## 3. Copy clarification

- [x] 3.1 Automated landing page: rewrite the explanatory paragraph to stop describing
  retraining as something that "unlocks" after review, and name it as a separate, optional
  decision reachable from Models & Training.
- [x] 3.2 `RetrainingDecisionPage.tsx`: add a "no schedule and no required order" line to the
  intro; rename "Reviewed material since this model was trained" to "Production-review
  evidence" with an explanatory line; add a bridging explanatory line to the "Training-eligible
  and waiting" section.

## 4. Tests

- [x] 4.1 New `annotate/automated/layout.test.tsx`: exactly 3 numbered steps, no "Retraining"
  tile, stepper hidden on the retrain route, children still render.
- [x] 4.1b Extend `annotate/automated/page.test.tsx`: the trailing paragraph names retraining as
  a separate, optional decision reachable from Models & Training, and no longer says retraining
  "unlocks".
- [x] 4.2 Extend `training-jobs/page.test.tsx`: the new link appears in Model Versions for
  tenant_admin and routes correctly, is absent from the Training Jobs view, and is absent for
  system_admin.
- [x] 4.3 Extend `nav-config.test.ts`: the Automated leaf's Retraining child has no step-number
  prefix, unlike its three siblings.
- [x] 4.4 Extend `RetrainingDecisionPage.test.tsx`: the "no schedule" statement, the
  "Production-review evidence" heading and its explanation, and the eligible-overview's
  bridging explanation all render.

## 5. Verification & Evidence

- [x] 5.1 Run every new/updated test file against the portal test container; confirm all pass
  except the one already-confirmed pre-existing baseline failure
  (`training-jobs/page.test.tsx`'s "Approve & queue" timeout).
- [x] 5.2 Run the full portal test suite; confirm the failing-file set is exactly the known
  pre-existing 6-file baseline, with no new regressions.
- [x] 5.3 Rebuild and restart the `portal` container (three times over the course of this
  change, as each successive fix — stepper removal, then hiding it on `/retrain`, then the
  breadcrumb label — was verified live before moving to the next).
- [x] 5.4 Live-verify in the browser: the Automated landing page's stepper reads "1 / 3" through
  "3 / 3" with no Retraining tile; the Models & Training screen's Model Versions view shows
  "Retraining & promotion evidence →" and it navigates to `/annotate/automated/retrain`; that
  page shows no stepper and a breadcrumb reading "Annotate / Automated / Retraining" (no "4 ·");
  the clarified copy (Production-review evidence heading, explanatory lines, "no schedule"
  sentence) all render as written.
