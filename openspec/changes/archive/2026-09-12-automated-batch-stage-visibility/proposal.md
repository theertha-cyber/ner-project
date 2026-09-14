## Why

`annotation-workflow-review-simplification` moved the Batch Pre-labeling screen to a
single-`batch` display model: whichever batch was "current" (the large one if it existed, else
the initial one) replaced the other on screen. The tenant admin using it found this confusing
in practice: once the large batch appeared, the initial batch's own status — in particular its
"reviewed and approved by an Annotator Admin" confirmation — disappeared, making it look like
that stage had never happened. They also wanted the large-batch upload action to be visibly
present (locked, not hidden) before it unlocks, and an explicit signal at the moment each stage
finishes, not only the platform notification bell.

## What Changes

- The Batch Pre-labeling screen now shows **both stages at once**, each in its own persistent
  section: "1 · Initial validation batch" and "2 · Large batch". Neither replaces the other.
- The large-batch section is always visible once the initial batch exists — locked with an
  explanatory message before the initial batch is approved, and showing its own document
  picker (unlocked) once it is — rather than being absent until then.
- A toast notification fires the moment the initial batch is observed as annotator-approved,
  and again the moment the large batch is observed as finished — in addition to the existing
  persistent inline state and the platform's own notification-bell mechanism, neither of which
  changed.
- A rejected initial batch's "Start a new validation batch" recovery action moves into that
  stage's own section (unchanged in effect, relocated for the new layout).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `seed-bootstrap`: adds one requirement governing the Batch Pre-labeling screen's display —
  no existing requirement changes; this is additive UI behavior on top of the backend rules
  `annotation-workflow-review-simplification` already established.

## Impact

- **Frontend only**: `src/portal/src/components/seed-bootstrap/BatchAcceptancePage.tsx`
  restructured into two persistent stage sections for the Tenant Admin's view (the Annotator
  Admin's single-batch review view is unchanged); `src/portal/src/hooks/use-prelabel-batch.ts`'s
  `useCreatePrelabelBatch` now also invalidates the batch list query, not only the singular
  batch query, so a newly created batch's stage appears without waiting on a poll.
- **Backend: none.** No requirement from `annotation-workflow-review-simplification` changes;
  this is purely how the already-specified state is displayed.
- **No impact**: the sequencing gate, the reviewer roles, and automatic large-batch promotion
  are all unchanged — this change only touches what the tenant admin sees on screen.

## Open Questions

None.
