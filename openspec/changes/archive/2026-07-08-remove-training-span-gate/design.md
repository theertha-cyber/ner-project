## Context

`SubmitJobSlideover` (`src/portal/src/components/training-jobs/submit-job-slideover.tsx`) fetches the tenant's confirmed span count from `/api/v1/annotation-export` on open, and locally computes `meetsThreshold = spanCount >= 500`. This value both colors/labels a preflight banner and gates `canSubmit`, disabling the Submit button below 500 spans.

Separately, the backend's `POST /api/v1/training-jobs` endpoint (`src/training_service/api/v1/training_jobs.py`) independently counts annotated entities and rejects the request with a 422 if the count is below `NER_MIN_TRAINING_ENTITIES` (an env var, currently unset/`0` in this deployment's `.env` and `docker-compose.yml`).

These are two independent implementations of "is there enough data to train": one hardcoded in the client, one configurable server-side. They can drift (as they already have — the client is stuck at `500` while the server's effective minimum is `0`), and only the server-side one is authoritative for whether a job is actually accepted.

## Goals / Non-Goals

**Goals:**

- Remove the frontend's independent, hardcoded `500` threshold and its pass/fail judgment.
- Make the backend response (success or 422) the single source of truth for whether a tenant has enough data to train.
- Preserve the informational value of showing span count in the preflight banner.

**Non-Goals:**

- Changing the backend's `NER_MIN_TRAINING_ENTITIES` check, its default, or how it's configured.
- Changing the dashboard's "/ 500 spans" progress indicator (`src/gateway/api/v1/dashboard.py`) — a separate, cosmetic annotator-facing display, not a submission gate.
- Exposing the backend's configured threshold via a new API so the frontend can show it in advance (see Open Questions).

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-006: Training Infrastructure with Asynchronous GPU Workers | Compliance section mandates: "Training Orchestrator MUST enforce 500-entity minimum dataset threshold before accepting a job." | This is a backend/orchestrator obligation, not a UI obligation. This design does not touch backend enforcement — it only removes a duplicate client-side copy of the same rule. ADR-006 is satisfied (or not) independently of this change; see Open Questions for the pre-existing gap where the deployed default leaves this unenforced today. |

## Decisions

### Decision 1: Delete the client-side threshold instead of syncing it to the backend's configured value

**Choice:** Remove `meetsThreshold` entirely rather than fetching `NER_MIN_TRAINING_ENTITIES` (or a derived value) from the backend to keep the frontend threshold in sync.

**Rationale:** ADR-006 assigns threshold enforcement to the "Training Orchestrator" (backend), and the backend already re-validates on every submit regardless of what the client shows. Duplicating the value client-side reintroduces the same drift risk this change is meant to eliminate, for a check that has no effect on correctness (the backend enforces it either way). The simplest design that satisfies "backend is the single source of truth" is to stop asserting a threshold client-side at all.

**Alternatives considered:**
- Fetch the configured minimum from a new/existing backend endpoint and keep a client-side gate in sync — ruled out: requires a new API surface (or repurposing an existing one) for a value whose only consumer would immediately re-check it server-side anyway; adds a network dependency to a simple form-enablement decision.
- Keep `500` as a client-side soft warning (non-blocking) — ruled out as a distinct option since a non-blocking warning is exactly what the redesigned informational banner already provides, without hardcoding a number that may not match the backend's actual configured value.

### Decision 2: Preflight banner shows span count only, no pass/fail styling

**Choice:** The banner always renders in a neutral state (loading / count / unavailable) — it never turns "success" or "failure" colored based on a threshold comparison.

**Rationale:** Once there is no client-side threshold, there is nothing correct to compare the count against for coloring purposes. Removing the judgment avoids implying a threshold (e.g., "500") that may not reflect the backend's actual configured minimum.

**Alternatives considered:**
- Drop the span-count preflight fetch/banner entirely — ruled out: the count itself is still useful context for the Tenant Admin before submitting, per the proposal's intent to keep it informational rather than remove it outright.

## Risks / Trade-offs

- [Tenant Admins can now click Submit with very few spans and receive a server-side 422 instead of a disabled button] → Acceptable per proposal: the backend error message already states the shortfall; this trades a silent disabled state for an explicit error, which is a net improvement in clarity (previously the "500" was disconnected from whatever the backend actually required).
- [ADR-006 mandates backend enforcement, but the deployed default (`NER_MIN_TRAINING_ENTITIES` unset → 0) does not actually enforce anything today] → Pre-existing gap, unrelated to this change (this change touches only the frontend). Flagged under Open Questions rather than fixed here, since setting the env var is an operational/config decision outside this change's scope.
- [Existing frontend tests assert on the old threshold behavior (disabled button below 500, banner copy)] → Addressed directly in tasks.md; tests must be updated alongside the component change.

## Migration Plan

1. Update `submit-job-slideover.tsx`: remove `meetsThreshold`, simplify `canSubmit`, update banner JSX/copy to neutral informational text.
2. Update `submit-job-slideover.test.tsx` to match the new behavior (button enabled regardless of span count; banner shows count without pass/fail language).
3. No backend, database, or API contract changes — no coordinated deploy required. This is a self-contained frontend deploy.
4. Rollback: revert the component/test changes; no data migration or backend state is affected either direction.

## Open Questions

- Should a follow-up change expose the backend's configured `NER_MIN_TRAINING_ENTITIES` (or a boolean "ready to train") via an API so the frontend can warn in advance instead of failing on submit? Left open — not required for this change, since the 422 error path already communicates the shortfall.
- ADR-006 compliance ("Training Orchestrator MUST enforce 500-entity minimum") is not actually met in the current deployment because `NER_MIN_TRAINING_ENTITIES` defaults to unset/0. This predates and is independent of this change, but is worth flagging to whoever owns ADR-006 compliance — this design does not attempt to resolve it.