## Why

The Submit Training Job slideover in the portal hardcodes a client-side rule that blocks the Submit button unless the tenant has 500+ confirmed annotated spans. This duplicates the backend's own minimum-entity check (`NER_MIN_TRAINING_ENTITIES`, `src/training_service/api/v1/training_jobs.py`), but the frontend threshold is a fixed literal (`500`) that cannot be tuned or disabled independently of the backend setting. In this deployment the backend threshold is effectively 0 (unset), so the frontend gate is the only thing actually blocking Tenant Admins from submitting jobs — with no way to adjust it short of a code change. The backend remains the correct place to enforce a minimum, since it can be tuned per environment via `NER_MIN_TRAINING_ENTITIES` and is authoritative regardless of client. We want the frontend to stop making its own pass/fail judgment and instead simply report the current confirmed span count, letting the backend's response be the source of truth on whether a job can be submitted.

## What Changes

- Remove the hardcoded `spanCount >= 500` threshold check (`meetsThreshold`) from `SubmitJobSlideover` (`src/portal/src/components/training-jobs/submit-job-slideover.tsx`).
- `canSubmit` no longer depends on span count — it is now solely gated on form validation errors (learning rate, epochs, batch size, sequence length) and submit-in-flight state.
- The preflight banner no longer renders a pass/fail judgment ("meets the 500-span minimum" / "requires 500 minimum"); it displays the confirmed span count as neutral, informational text (or a loading/unavailable state), with neutral styling instead of success/failure colors.
- If the backend rejects a submission for insufficient entities (422 from `POST /api/v1/training-jobs`), that error surfaces through the existing `serverError` display — this path is unchanged.
- **BREAKING**: Tenant Admins with fewer than 500 confirmed spans can now attempt submission from the UI. Whether the job is actually accepted still depends entirely on the backend's `NER_MIN_TRAINING_ENTITIES` check, which is unchanged and out of scope for this change.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `training-jobs`: The "Submit training job" requirement gains a clarification that the client SHALL NOT impose its own minimum-span threshold on the submit action — the preflight display becomes informational only, and enforcement of any minimum remains solely a backend responsibility.

## Impact

- **Affected file**: `src/portal/src/components/training-jobs/submit-job-slideover.tsx` (removes `meetsThreshold`, updates `canSubmit`, updates preflight banner JSX/copy).
- **Not affected**: `src/training_service/api/v1/training_jobs.py` and the `NER_MIN_TRAINING_ENTITIES` backend check — left untouched.
- **Not affected**: `src/gateway/api/v1/dashboard.py` "/ 500 spans" dashboard progress bar — this is a separate, cosmetic display on the annotator dashboard and is out of scope.
- **Tests**: `src/portal/src/components/training-jobs/submit-job-slideover.test.tsx` likely has assertions tied to the 500-span gate (disabled button, banner copy) and will need updating.
- **Downstream**: Tenant Admins may now see a submission attempt fail server-side (422) where previously the UI silently disabled the button. This is the intended behavior — the backend error message is already descriptive.

## Open Questions

- Should the preflight banner still surface the backend's configured minimum (if any) so users get advance warning instead of a submit-then-fail experience? For now, this proposal keeps the banner purely informational (span count only) since the backend does not currently expose its configured threshold via any read endpoint. This can be revisited in a follow-up change if desired.