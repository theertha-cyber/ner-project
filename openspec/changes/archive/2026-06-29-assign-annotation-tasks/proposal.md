## Why

Tenant admins currently have no UI to assign annotation tasks to annotators within the annotation page — the task queue only displays existing tasks, leaving admins with no self-service path for task assignment. Adding an "Assign Task" flow directly in the annotation page's task queue panel removes this gap and keeps the annotation workflow self-contained.

## What Changes

- A tenant-admin-only "Assign Task" button appears at the top of the Task Queue panel in the annotation workspace.
- Clicking the button opens an inline form (or modal) that lets the admin pick an unassigned document and an annotator from a dropdown.
- Submitting the form calls `POST /api/v1/annotation-tasks` and adds the new task to the queue immediately.
- The button and form are hidden for `annotator` role users; they remain invisible to anyone who is not a tenant admin.
- The annotator list is fetched from `GET /api/v1/users` and filtered to the `annotator` role.

## Capabilities

### New Capabilities

- `task-assignment-ui`: Tenant-admin-only inline assignment UI embedded in the Task Queue panel on the annotation page — lets admins pick a document and an annotator and create a task without leaving the annotation workspace.

### Modified Capabilities

- `portal-annotation`: Task Queue panel gains a role-gated "Assign Task" control that is visible and interactive only for `tenant_admin` users.

## Impact

- **Frontend**: `AnnotationPage.tsx`, `TaskQueue.tsx` — new conditional UI block gated on `user.role === "tenant_admin"`.
- **API (read-only)**: Existing `GET /api/v1/users` (annotator list) and `GET /api/v1/documents` (unassigned documents); `POST /api/v1/annotation-tasks` (task creation). No new backend endpoints required.
- **Specs**: `portal-annotation` delta spec; new `task-assignment-ui` spec.

## Open Questions

- Should documents already assigned to an active task be excluded from the "document" dropdown, or is that filtering done by the backend (409 response)?
- Should the assignment form appear as an inline expandable section within the task queue panel, or as a modal/drawer?
- Are there additional document status filters required (e.g. only show `processed` documents)?
