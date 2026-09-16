## 1. Remove the Review Queue frontend surface

- [x] 1.1 Remove `review-queue` from `manualLeaf()`'s `children` in `nav-config.ts`
- [x] 1.2 Remove the `"review-queue"` entry from `SCREEN_TITLES`
- [x] 1.3 Delete `app/(auth)/review-queue/page.tsx`
- [x] 1.4 Delete `components/review-queue/ReviewQueuePage.tsx` and its test
- [x] 1.5 Delete `hooks/use-review-queue.ts` and `types/confidence-review.ts`
- [x] 1.6 Repo-wide grep confirms no remaining import of the deleted hook/types/component

## 2. Rework the Manual annotation landing page

- [x] 2.1 Remove the "Review queue" work card, `awaitingReview` stat, and the annotator's
      "Open my queue" primary action from `annotate/manual/page.tsx`
- [x] 2.2 Fetch `/api/v1/annotation-tasks` from the landing page (same endpoint the workspace
      already uses) and derive `completedTasks`, scoped to the caller for `annotator`
- [x] 2.3 Replace the removed stat with role-appropriate ones: documents ready / annotated /
      entity types defined for `tenant_admin`; assigned to me / completed by me for `annotator`
- [x] 2.4 Build `AnnotatedDocuments` — filename + span count per completed task, empty state,
      "View" action navigating to `/annotation?task={id}`
- [x] 2.5 Build `TrainModelBanner` — hidden at zero annotated, singular/plural copy, navigates
      to `/training-jobs`, `tenant_admin` only
- [x] 2.6 Wire both new components into the page via `AnnotateLanding`'s existing `children` slot

## 3. Verification & Evidence

- [x] 3.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec
      Alignment and confirm all pass
- [x] 3.2 Collect functional evidence (screenshot / test output / log) for each scenario — one
      entry per row in verification.md § Evidence Log
- [x] 3.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination
      Risk Register
- [x] 3.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance
- [x] 3.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer
      required — see caveat: this is the implementing agent's own re-inspection, not an
      independent human review)
- [x] 3.6 Run `openspec validate manual-annotation-landing-rework --type change --strict`
      before archive
