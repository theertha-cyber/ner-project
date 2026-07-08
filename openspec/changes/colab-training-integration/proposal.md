## Why

Platform GPU capacity is limited and shared across tenants, and every training job today waits on both the platform's GPU node pool and System Admin approval. Some tenant admins have their own Google Colab GPU access and would rather use it for their own tenant's training runs instead of competing for platform capacity or waiting on approval. This change lets a tenant admin optionally opt into running a training job on their own Colab session, while leaving the existing platform-GPU path untouched.

## What Changes

- Add an optional `compute_backend` choice (`platform` default, or `colab`) to training job creation, selectable only by the Tenant Admin at submit time.
- For `compute_backend=colab`, the system generates a self-contained Jupyter notebook (dataset fetch, training, and callback cells mirroring the existing worker's training logic) plus a scoped, single-job, expiring credential, and makes both available to the Tenant Admin immediately — **skipping the System Admin `pending_approval` gate**, since no platform GPU pool is consumed. The existing `platform` backend path (submit → System Admin approval → Celery dispatch) is unchanged.
- The Tenant Admin manually downloads and runs the notebook in their own Colab session. The notebook calls back into a new public-facing endpoint on `training_service` to report heartbeats, progress, and final artifacts/metrics; `training_service` relays those into MinIO/MLflow server-side (MinIO/MLflow themselves remain internal-only).
- Add heartbeat-driven stall detection: if a `colab` job's notebook stops calling back within a configurable timeout window, the job automatically transitions to `failed` with an explanatory error, since nothing else can detect a closed browser tab or an expired Colab session.
- Extend job cancellation to cover `colab` jobs: cancelling revokes the job's scoped credential (instead of revoking a Celery task, since none exists for this path).
- **BREAKING**: none to existing behavior — `compute_backend` defaults to `platform` and every existing scenario in `training-jobs` continues to apply unchanged for that default.

## Capabilities

### New Capabilities

- `colab-training-integration`: Notebook generation, the scoped per-job credential lifecycle, the public callback/heartbeat endpoint, and the human-in-the-loop job lifecycle (awaiting launch → running → completed/failed via callback, with stall-timeout handling) for Colab-backed training jobs.

### Modified Capabilities

- `training-jobs`: "Submit training job" gains an optional `compute_backend` field; when set to `colab`, the job SHALL skip the `pending_approval` gate and SHALL NOT be enqueued to Celery. "Cancel training job" gains colab-specific behavior (revoke credential instead of revoking a Celery task). "Approve training job" and "Reject training job" SHALL continue to apply only to `platform`-backed jobs; attempting to approve/reject a `colab`-backed job SHALL be rejected, since it never enters `pending_approval`.

## Impact

- **Database**: new migration adding `compute_backend VARCHAR(20) NOT NULL DEFAULT 'platform'` to `training_jobs` (all tenant schemas); new table for scoped per-job Colab credentials (modeled on, but distinct from, `public.widget_api_keys`); new columns/values supporting the human-in-the-loop status lifecycle (`awaiting_notebook_launch`, heartbeat timestamp) either on `training_jobs` directly or a companion table.
- **Backend** (`src/training_service`): `TrainingJobCreate` schema gains `compute_backend`; `POST /api/v1/training-jobs` branches on it; new notebook-generation endpoint; new public callback/heartbeat endpoint (`POST /api/v1/training-jobs/{id}/colab-callback` or similar); a new background check (Celery beat or equivalent) for stall-timeout detection; `cancel` branches on `compute_backend`.
- **Networking**: a new externally-reachable route must be added — either a new gateway proxy route for `training_service` (which the gateway does not currently provide at all) or a direct public exposure of `training_service`'s new callback endpoint. This is a deployment-topology decision, addressed in design.md.
- **Frontend** (`src/portal`): `submit-job-slideover.tsx` gains a compute-backend choice; a new UI surface for downloading the generated notebook and viewing colab-job status (including "waiting for notebook launch" and stalled/timeout states not present in the current status vocabulary).
- **Not affected**: the existing `platform`/Celery/K8s-GPU execution path, `worker.py`'s in-cluster training logic, and MinIO/MLflow's internal-only reachability.

## Open Questions

- Exact new status value(s) for the pre-launch and stalled states, and whether they're modeled as new `training_jobs.status` strings or a separate sub-status field — left to design.md.
- Heartbeat interval and timeout window defaults — left to design.md, expected to be an env-var-configurable setting following the existing `NER_`-prefixed settings convention.
- Whether the generated notebook embeds the scoped credential directly (simpler, but the credential travels with the downloaded file) or requires a separate copy-paste step — left to design.md to weigh the security trade-off.
