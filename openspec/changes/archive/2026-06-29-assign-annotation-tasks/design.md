## Context

The annotation workspace (`/annotation`) is the primary interface for document labeling. The Task Queue panel (left column, 228 px wide in 3-pane mode) currently renders a read-only list of tasks fetched from `GET /api/v1/annotation-tasks`. Tenant admins can see all tasks; annotators see only their own.

The backend already supports task creation via `POST /api/v1/annotation-tasks` (role-gated to `tenant_admin`), user listing via `GET /api/v1/users`, and document listing via `GET /api/v1/documents`. No new backend endpoints are needed.

The feature must remain invisible to `annotator` role users. All gate logic lives in the frontend, relying on the `user.role` value from the existing `useAuth()` hook.

## Goals / Non-Goals

**Goals:**

- Tenant admins can create annotation tasks directly from the Task Queue panel without leaving the annotation workspace.
- The assignment UI surfaces a filtered list of unassigned (or selectable) documents and a list of annotator-role users.
- A successful task creation immediately adds the task to the local task list.
- The UI is invisible to non-admin users.

**Non-Goals:**

- Bulk task assignment (assigning the same document to multiple annotators at once).
- Re-assigning or transferring an existing active task to a different annotator.
- Backend changes — all required API endpoints already exist.
- A dedicated task-management admin page or full CRUD for tasks (out of scope for this change).

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001-tenant-data-isolation | All data is scoped to a tenant via JWT claim; no cross-tenant reads | Annotator list and document list must be fetched using the tenant admin's JWT (existing `authFetch` already handles this) |
| ADR-004-openspec-governance | Spec-driven workflow; all new capabilities need a spec | New `task-assignment-ui` spec must be written before implementation |
| ADR-005-opencode-agent-boundaries | Agent/frontend boundary: frontend only calls defined API contracts | No new backend endpoints; frontend must not bypass the API contract |

## Decisions

### Decision 1: Inline expandable form in the Task Queue panel (not a modal)

**Choice:** Add a role-gated "＋ Assign Task" button at the top of the Task Queue panel. Clicking it expands an inline form below the header, within the same panel. Submitting collapses the form and adds the task to the list.

**Rationale:** The Task Queue panel is narrow (228 px). An inline form keeps context local — the admin can see the existing task list while creating a new one. Modals require overlay management and interrupt the annotation workspace flow.

**Alternatives considered:**
- Modal/drawer — ruled out: breaks the 3-pane spatial model, heavier implementation, and more disruptive to annotators mid-session if the admin opens it accidentally.
- Separate admin route — ruled out: the proposal scopes this to the annotation page; a separate route is out of scope.

### Decision 2: Fetch annotator list and document list on-demand (when form opens)

**Choice:** `GET /api/v1/users` (filtered client-side to `role === "annotator"`) and `GET /api/v1/documents` are fetched only when the admin opens the assignment form, using React Query with `enabled: isFormOpen`.

**Rationale:** Avoids unnecessary fetches for annotator users (who never see the form) and for admin users who never open the form. Keeps startup load unchanged.

**Alternatives considered:**
- Fetch on workspace mount for all tenant admins — ruled out: wastes bandwidth, adds latency to workspace load for a feature used infrequently.

### Decision 3: Client-side document filter — only show `processed` documents

**Choice:** The document list returned from `GET /api/v1/documents` is filtered client-side to include only documents with `status: "processed"`. Documents with `status: "pending"` or `"failed"` are excluded from the dropdown.

**Rationale:** Only processed documents have extractable text and can be meaningfully annotated. Assigning an unprocessed document would create a task the annotator cannot act on.

**Alternatives considered:**
- Show all documents and let the backend return a 422 — ruled out: a 422 on create is a worse UX than pre-filtering the options.

### Decision 4: Optimistic task list update on successful creation

**Choice:** On a 201 response from `POST /api/v1/annotation-tasks`, the new task is prepended to the local task list state without refetching. The task queue React Query cache is invalidated in the background so subsequent mounts are consistent.

**Rationale:** Keeps the UI responsive. The returned task object from the 201 response contains all fields needed to render a task row (`id`, `document_id`, `annotator_user_id`, `status`, `filename`, etc.).

**Alternatives considered:**
- Refetch on create — ruled out: introduces a loading flash; the 201 response already has the full task payload.

## Risks / Trade-offs

- [Document already has an active task (409 from backend)] → Show the 409 error message in the form as an inline validation error; do not close the form so the admin can pick a different document.
- [Annotator list is empty (no annotator users yet)] → Show a "No annotators available — invite users first" message in the dropdown with a disabled submit button.
- [Form stays open while annotation is ongoing] → Form is collapsible; pressing "Cancel" or clicking away closes it. Annotator column scroll is independent so an open form does not interfere with the task list scroll.

## Migration Plan

Frontend-only change. No database migrations or backend deployments required.

1. Ship frontend changes behind the existing `user.role === "tenant_admin"` gate.
2. Verify in staging that the form is invisible for annotator accounts.
3. Confirm 409 error handling works correctly when an active task already exists for a document.
4. Deploy to production.

Rollback: revert the frontend component changes; no data side-effects.

## Open Questions

- Should the document dropdown exclude documents that already have an active (non-completed) task, or rely solely on the 409 response from the backend? Proposal defers to the 409 for now; a future iteration could add a backend filter param.
- Should the form auto-select the first available document/annotator, or require explicit selection?
