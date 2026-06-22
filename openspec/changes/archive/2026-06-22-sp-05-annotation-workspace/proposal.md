## Why

Annotators and tenant admins currently have no UI to perform document labeling — the annotation workspace backend is implemented but there is no frontend surface for it. SP-05 delivers the annotation screen at `/annotation`, completing the core value loop of the platform: upload a document, label it, train a model.

## What Changes

- Add the `/annotation` route to the portal as a full-screen annotation workspace
- Implement the 3-pane layout (task queue | document viewer | entity palette) with a focus-mode toggle
- Implement token-click labeling: clicking a word while an entity type is armed creates a confirmed span via `POST /documents/{id}/spans`
- Implement span inspector: clicking an existing span opens a panel showing offset details, with retype and delete actions
- Implement suggestion panel: pre-label button triggers `POST /documents/{id}/prelabel`; returned suggestions render with dashed styling; promote and dismiss actions are available per suggestion
- Implement task status transitions: task moves `unannotated → in-progress` on first span creation; `PATCH /annotation-tasks/{id}` moves to `completed` (blocked until ≥1 confirmed span exists)
- Implement char-offset ↔ token-index conversion entirely on the frontend (whitespace-split, cumulative offset arithmetic)
- Implement armed-type mode: selecting an entity type from the palette arms it; clicking any document token creates a span; `Escape` disarms

## Capabilities

### New Capabilities

- `portal-annotation`: The annotation workspace frontend screen — task queue, document viewer with token-level span coloring, entity type palette, span inspector, suggestion promotion flow, pre-label trigger, and task status lifecycle.

### Modified Capabilities

*(none — no existing spec requirements change)*

## Impact

- **New files**: `src/portal/src/app/(auth)/annotation/page.tsx` and components under `src/portal/src/components/annotation/`
- **APIs consumed (all existing)**: `GET /api/v1/annotation-tasks`, `GET /api/v1/documents/{id}/text`, `GET /api/v1/documents/{id}/spans`, `POST /api/v1/documents/{id}/spans`, `PATCH /api/v1/documents/{id}/spans/{span_id}`, `DELETE /api/v1/documents/{id}/spans/{span_id}`, `POST /api/v1/documents/{id}/prelabel`, `GET /api/v1/documents/{id}/spans?type=suggested`, `POST /api/v1/documents/{id}/spans/promote/{suggest_id}`, `PATCH /api/v1/annotation-tasks/{id}`, `GET /api/v1/entity-types`
- **Prerequisites**: SP-03 App Shell (route, `<RequireAuth>`, `<AppShell>` wrapper), SP-01 primitives (`<SlideOver>`, `<Badge>`, `useToast`)
- **Roles**: `annotator` and `tenant_admin` only

## Open Questions

1. **Document text endpoint**: `GET /api/v1/documents/{id}/text` is specified in the decomposition but needs verification that it exists in `src/extraction_service/` or another document service. If it returns the raw text as a string, the token split is straightforward; if it returns structured data, the tokenization contract changes.
2. **Span promote endpoint shape**: `POST /documents/{id}/spans/promote/{suggest_id}` — confirm this endpoint exists in `src/extraction_service/api/v1/entities.py` or the annotation service before designing the mutation hook.
3. **Task queue filtering**: Should the task queue show only tasks assigned to the current user (`annotator`), or all tasks for `tenant_admin`? The decomposition says "assigned tasks for the current user" — confirm this matches backend filter behavior (`GET /annotation-tasks?assignee_id=me` or similar).
4. **Focus mode layout**: In focus mode the entity palette becomes a floating `position: fixed` panel. Should it be always visible or toggled by a button? The mockup shows it always present in focus mode; confirm this is the desired UX before building.
