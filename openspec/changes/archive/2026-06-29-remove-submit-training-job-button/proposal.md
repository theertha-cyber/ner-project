## Why

The Training Queue page renders a "+ Submit Job" button for all roles that can access `/training-jobs`, including System Admin. Submitting a training job is a Tenant Admin action — System Admin's role on this page is to approve or reject jobs submitted by tenants. The button appearing for System Admin is a role-access mismatch that must be corrected.

## What Changes

- The `+ Submit Job` button on the Training Queue page is hidden when the authenticated user is a `system_admin`
- The `SubmitJobSlideover` component is not rendered for `system_admin` sessions

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `training-jobs`: The UI requirement for job submission now explicitly constrains visibility of the submit action to `tenant_admin` only. The backend already enforces this at the API level (403 for non-tenant-admin); this change closes the UI gap.

## Impact

- `src/portal/src/app/(auth)/training-jobs/page.tsx` — add a role guard around the submit button and slideover
- No backend changes required; the API already returns 403 if a system admin attempts to POST to `/api/v1/training-jobs`
- No spec changes to the `training-approval` spec; approve/reject flows are unaffected

## Open Questions

- None. The backend already enforces the correct access control; this is purely a UI visibility fix.
