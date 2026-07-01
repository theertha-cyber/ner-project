## Context

The Training Queue page (`/training-jobs`) is accessible to both `system_admin` and `tenant_admin` roles. It renders a `+ Submit Job` button unconditionally. The button opens a `SubmitJobSlideover` that POSTs to `/api/v1/training-jobs`, an endpoint that already enforces `tenant_admin`-only access at the backend (returns 403 for any other role). The UI has no corresponding role guard, so system admins see and can attempt the submit flow — receiving an error only after the API call.

## Goals / Non-Goals

**Goals:**
- Hide the `+ Submit Job` button and `SubmitJobSlideover` for `system_admin` users
- Enforce at the UI layer what the backend already enforces at the API layer

**Non-Goals:**
- Changes to the backend API or access-control logic
- Restricting system admin from accessing the Training Queue page itself (they still need it to approve/reject jobs)
- Changes to the `SubmitJobSlideover` component internals

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| None | — | This is a frontend-only UI visibility fix with no architectural implications. |

## Decisions

### Decision 1: Role check at the page level, not inside the component

**Choice:** Add a `user?.role === "tenant_admin"` guard in `training-jobs/page.tsx` around both the button and the `SubmitJobSlideover`, rather than embedding role logic inside the `SubmitJobSlideover` component.

**Rationale:** The page already owns the `submitOpen` state and renders both the button and the slideover. Gating at the page level keeps the component reusable and free of role awareness. The component does not need to know who is using it — that's the page's concern.

**Alternatives considered:**
- Prop `canSubmit` passed into `SubmitJobSlideover` — adds surface area to a component that doesn't need it; the button that opens the slideover is also on the page, so we'd need two guards anyway.
- Route-level middleware to redirect system admins away from the page — over-engineered; system admins legitimately use the page for approvals.

## Risks / Trade-offs

- [Button visibility relies on client-side role from `useAuth`] → The backend already blocks the API call with 403, so incorrect role data on the client is a UX issue at worst, not a security issue.

## Migration Plan

Single file change to `src/portal/src/app/(auth)/training-jobs/page.tsx`. No database migrations, no API changes, no config changes. Deploy as a standard frontend build. Rollback is reverting the file change.

## Open Questions

None.
