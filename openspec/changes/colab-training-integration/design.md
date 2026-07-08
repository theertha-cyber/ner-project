## Context

Today, every training job follows one path: Tenant Admin submits (`POST /api/v1/training-jobs`, hyperparameters only) → job sits in `pending_approval` → System Admin approves → `training_service` sends a Celery task (`fine_tune_model`) to a worker running inside the platform's own Docker/K8s network, with access to Redis (broker), the internal Postgres instance, internal MinIO, and internal MLflow. The worker trains in-process using a Hugging Face `Trainer`, then writes artifacts to MinIO and registers the model in MLflow/Model Registry.

This change adds a second path where the Tenant Admin runs the actual training in their own Google Colab notebook — outside the platform's network entirely. The platform cannot start, monitor, or reach into that notebook; it can only prepare inputs for it (a notebook file, a dataset access mechanism, a credential) ahead of time, and accept inbound calls from it afterward. This is a fundamentally different trust and networking boundary than anything the training pipeline has today: it's the first place in the system where an external, non-tenant-controlled-infra actor needs to authenticate *into* a backend service from the public internet.

## Goals / Non-Goals

**Goals:**
- Let a Tenant Admin choose Colab as the compute backend at job-creation time, with no System Admin involvement.
- Produce a self-contained notebook that can train the same model class as the existing worker, using the tenant's already-annotated data.
- Safely accept status/metrics/artifacts from that notebook over the public internet, without exposing MinIO or MLflow directly.
- Detect and fail jobs whose notebook goes silent, since nothing else will.
- Land the resulting model in the exact same place (S3 path convention, Model Registry) the existing platform-GPU path uses, so Model Serving (ADR-003) doesn't need to know which path trained it.

**Non-Goals:**
- Programmatically starting or supervising a Colab runtime — not possible with standard Colab; out of scope entirely.
- Supporting any Colab account other than the tenant admin's own — no shared/service Colab account.
- Real-time streaming logs from the notebook — periodic callback/heartbeat is sufficient for this change.
- Changing anything about the existing `platform` backend's Celery/K8s execution path.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-------------------|---------------------------|
| ADR-001-tenant-data-isolation | Tenant isolation via per-tenant Postgres schema; all service code must inject tenant scope via `search_path`/`tenant_context`; object storage paths use `tenant-<uuid>/` prefixes | The new callback endpoint, credential table, and notebook-generation logic must resolve and scope everything to the job's owning tenant — the callback endpoint in particular must map an inbound credential to exactly one tenant/job, never trusting a client-supplied tenant id |
| ADR-003-model-serving-topology | Model artifacts pulled from `s3://ner-platform/tenant-<uuid>/models/v<version>/`; Model Registry resolves the active version at inference time; Serving Layer is agnostic to how a model was trained | Colab-trained artifacts must land at the same S3 path convention and be registered in the Model Registry identically to platform-trained ones — Serving Layer code must not need a Colab-specific branch |
| ADR-006-training-infrastructure | Async GPU workers via Celery/RabbitMQ*, hyperparameters (`learning_rate`, `num_epochs`, `batch_size`, `max_seq_length`) submitted with the job request, checkpointing, 500-entity minimum threshold, GPU node pool autoscaling | The entity-count minimum and the submitted-hyperparameter shape still apply to `colab` jobs — a Colab job is a different *execution* path, not an exemption from data-sufficiency requirements. Celery/RabbitMQ/K8s GPU pool provisions are simply not used for this path (\*note: current code uses Redis as the Celery broker, not RabbitMQ as ADR-006 states — an existing drift between ADR and implementation, not something this change introduces or needs to resolve) |

## Decisions

### Decision 1: `compute_backend` is a field on the existing job, not a separate job type

**Choice:** Add `compute_backend VARCHAR(20) NOT NULL DEFAULT 'platform'` to `training_jobs`. `POST /api/v1/training-jobs` accepts it as an optional field; all other fields and the entity-count preflight check are unchanged regardless of backend.

**Rationale:** A training job is conceptually the same thing (a request to fine-tune a model from the tenant's annotated data) regardless of where it executes. Keeping it one table/one create-endpoint avoids duplicating hyperparameter validation, entity-count checks, and listing/status code paths.

**Alternatives considered:**
- Separate `colab_training_jobs` table/endpoint — rejected: would duplicate the 500-entity preflight, hyperparameter validation, and listing/filtering logic that already exists for `training_jobs`, for no real benefit.

### Decision 2: Colab jobs skip `pending_approval` entirely — new status `awaiting_notebook_launch`

**Choice:** When `compute_backend=colab`, job creation immediately transitions the job to a new status `awaiting_notebook_launch` (skipping `pending_approval`), generates the notebook + scoped credential synchronously in the same request, and returns both to the Tenant Admin. The existing `approve`/`reject` endpoints SHALL reject any job not in `pending_approval` (already true today) — since colab jobs never enter that status, attempting to approve/reject one simply falls through the existing "wrong status" 422 path with no new code needed there.

**Rationale:** The approval gate exists to ration the platform's own GPU pool (per ADR-006). A Colab job consumes zero platform GPU, so gating it behind System Admin approval would just be latency with no corresponding resource-protection purpose.

**Alternatives considered:**
- Keep the approval step for consistency, have "approve" trigger notebook generation instead of Celery dispatch — rejected per the explicit product decision that Colab jobs should be immediately actionable by the Tenant Admin without waiting on anyone.

### Decision 3: Job status lifecycle extension

**Choice:** Extend the status vocabulary (still a plain string column, consistent with today's non-enum implementation) with three colab-specific values:
- `awaiting_notebook_launch` — notebook generated, waiting for the Tenant Admin to run it. Entered immediately on create.
- `running` — reused from the existing vocabulary; entered when the notebook's first callback arrives (job "started" signal), also used for heartbeats.
- `completed` / `failed` — reused; `failed` gains a new cause, "stalled" (no callback within the timeout window), distinguished only by `error_message` text, not a new status value.

A new `last_heartbeat_at` timestamp column tracks the most recent callback, regardless of payload type (heartbeat, progress, or terminal).

**Rationale:** Reusing `running`/`completed`/`failed` keeps the frontend's existing status-based UI (colors, filters) working with only one net-new status (`awaiting_notebook_launch`) to add a treatment for. Distinguishing "stalled" via `error_message` rather than a new status avoids fragmenting `failed`-state handling across the codebase (cancellation, dashboards, etc. already only care about "did it fail," not why).

**Alternatives considered:**
- A fully separate sub-state machine / dedicated `colab_status` column — rejected as more machinery than the one new waiting-state actually requires.

### Decision 4: Scoped per-job credential, modeled on `widget_api_keys` but distinct

**Choice:** New table `training_job_colab_tokens` (or similar): `id`, `training_job_id` (FK), `key_hash` (sha256), `key_prefix`, `expires_at`, `created_at`, `revoked_at`. On notebook generation, mint `raw_token = f"ner_colab_{uuid4().hex}"`, return it once (embedded in the notebook — see Decision 5), store only the hash. The callback endpoint authenticates by hashing the presented token and looking up a matching, non-expired, non-revoked row, which resolves unambiguously to one `training_job_id` (and transitively, one tenant).

**Rationale:** This mirrors the existing, already-reviewed `widget_api_keys` pattern (hash-at-rest, show-once, revocable) rather than inventing a new credential scheme, but scopes it to a single job with an expiry — a standing tenant-wide key would be unnecessarily broad blast-radius for a credential embedded in a downloadable file that leaves the platform's control entirely.

**Alternatives considered:**
- Reuse `widget_api_keys` directly — rejected: those are tenant-wide and don't expire, wrong shape for a credential that's going into a file a user downloads and might forget about; a leaked widget key has different (already-accepted) risk properties than a leaked training credential that could be used to inject fake "completed" callbacks with attacker-controlled artifacts.
- Short-lived JWT (matching the existing internal service-to-service pattern) — rejected: that pattern assumes both parties can mint tokens using the shared internal secret; a Colab notebook has no way to safely hold that secret, and JWTs aren't independently revocable the way a hashed opaque token backed by a DB row is.

### Decision 5: Notebook embeds the credential directly

**Choice:** The generated `.ipynb` embeds the raw token directly in a config cell, rather than requiring the Tenant Admin to paste it in separately.

**Rationale:** The proposal flagged this as an open trade-off; embedding wins on usability (no separate secret-management step for a persona who is, by definition, already trusted with `tenant_admin` access to this tenant's training data) and the blast radius is already bounded by Decision 4 (single-job scope, expiry, revocable, and the notebook only ever grants access to that one job's dataset export and callback — not general tenant data).

**Alternatives considered:**
- Separate copy-paste secret — rejected: adds friction for a credential whose worst-case misuse (someone else running your training notebook) is low-severity and already mitigated by expiry + revocation; the Tenant Admin can revoke and regenerate if the notebook file is shared unintentionally.

### Decision 6: Callback endpoint is proxied through the gateway, not exposed directly

**Choice:** Add a new gateway route (the gateway currently proxies `document_service`, `extraction_service`, `model_serving`, `chat_api`, `analytics_service`, but not `training_service` at all) forwarding `POST /api/v1/training-jobs/{id}/colab-callback` to `training_service`. `training_service` itself remains internal-only, reached only through this one new gateway-proxied route for colab callbacks (existing portal→training_service direct calls for the authenticated UI paths are unaffected, since those already work today over the platform's existing network boundary and this change doesn't need to alter them).

**Rationale:** The gateway is the platform's one existing, already-hardened internet-facing entry point (TLS termination, rate limiting, etc. presumably already live there for other proxied services). Adding a single new proxied route is a much smaller change in public attack surface than making `training_service` itself directly internet-reachable, which would expose every other `training_service` endpoint (job listing, cancel, approve) to the public network unless a separate ingress/firewall rule is layered on top.

**Alternatives considered:**
- Expose `training_service` directly on a public ingress — rejected: would newly expose all of `training_service`'s endpoints publicly (approve/reject/cancel/list), not just the callback, requiring careful new network policy just for this one endpoint's sake.

### Decision 7: Callback relays artifacts server-side; MinIO/MLflow stay internal

**Choice:** The notebook POSTs metrics and model artifact bytes (or a reference to them, e.g. base64-encoded checkpoint or a chunked upload) to the callback endpoint. `training_service` itself performs the MinIO `put` and MLflow `log_model`/registration calls, using its existing internal credentials — identical to what `worker.py` already does for the platform path, just triggered by an inbound HTTP call instead of a Celery task body.

**Rationale:** Confirmed by the earlier discussion — keeps MinIO/MLflow's reachability unchanged (internal-only, consistent with every other path in the system) and reuses the exact artifact-path convention ADR-003 requires (`s3://ner-platform/tenant-<uuid>/models/v<version>/`), so Model Serving needs no Colab-awareness at all.

**Alternatives considered:**
- Presigned MinIO upload URLs handed to the notebook — reconsidered and rejected in favor of full relay: presigned URLs would still require MinIO's endpoint to be reachable from the public internet (even if only for the duration of the presigned URL), which is the exposure this decision is trying to avoid; a full relay through an already-public endpoint has no such requirement.

### Decision 8: Heartbeat + timeout-to-failed

**Choice:** The notebook is instructed (in its generated training cell) to call the same callback endpoint periodically (e.g. every N minutes, and at minimum at start/each epoch/completion) with a lightweight heartbeat payload. A new periodic check (Celery beat task, reusing the existing Celery infra already present for `training_service`) scans jobs in `awaiting_notebook_launch` or `running` status with `compute_backend=colab`; any whose `last_heartbeat_at` (or `created_at`, if no heartbeat ever arrived) exceeds a configurable timeout (new `NER_COLAB_HEARTBEAT_TIMEOUT_MINUTES` setting, following the existing `NER_`-prefixed settings convention) transitions to `failed` with `error_message` explaining the stall.

**Rationale:** This is the only way to bound a job stuck behind a closed browser tab or an expired Colab session, given nothing else in the platform can observe the notebook's liveness.

**Alternatives considered:**
- No automatic detection (manual cancel only) — rejected per the explicit product decision; would leave jobs silently stuck indefinitely with no signal to the Tenant Admin.

## Risks / Trade-offs

- [A leaked/shared notebook file lets someone else inject fake callback data for that one job] → Mitigated by Decision 4's scope (single job, expiry, revocable) and by validating that the credential's `training_job_id` matches the path parameter on every callback; Tenant Admin can revoke and regenerate if a notebook is shared unintentionally.
- [Reconstructing the training cell to mirror `worker.py` risks drift if the platform's training logic changes later and the notebook template isn't updated in lockstep] → Generate the notebook from a single shared template/module rather than hand-copied code, so future changes to hyperparameter handling or model class are made once.
- [The new gateway route is the platform's first internet-facing endpoint into `training_service`, and a hashed-token auth scheme is new to this service] → Mitigated by reusing the already-reviewed `widget_api_keys` hash-at-rest pattern rather than inventing new crypto, and by scoping the route to exactly one endpoint rather than proxying all of `training_service`.
- [Heartbeat timeout requires a new periodic task; if misconfigured (too short) it could fail jobs still legitimately mid-training on a slow Colab GPU] → Default the timeout generously (e.g. well above one epoch's expected wall-clock time) and make it configurable per deployment via the new env var.
- [Artifact relay through a single HTTP call may hit size/timeout limits for larger fine-tuned models] → If needed, chunk the upload across multiple callback calls keyed by job id + sequence number; flagged as an implementation detail for tasks.md rather than a blocking design question.

## Migration Plan

1. Add a migration: `compute_backend` (default `'platform'`) and `last_heartbeat_at` columns on `training_jobs`; new `training_job_colab_tokens` table — applied to `tenant_template` and all existing `tenant_*` schemas, following the same multi-schema loop pattern used in migration 012.
2. Add the new gateway route for the colab-callback endpoint only; add the new endpoints to `training_service` (create-with-backend branch, notebook generation, callback/heartbeat handler, stall-detection Celery beat task).
3. Add the notebook-generation template/module (shared with `worker.py`'s existing training logic where possible, per the risk above).
4. Add frontend: compute-backend choice in `submit-job-slideover.tsx`, notebook download UI, and status treatment for `awaiting_notebook_launch` and stalled-`failed`.
5. Rollback: the new column defaults to `'platform'` and every existing code path is additive, so rollback is simply removing the new endpoints/route/frontend option; no existing `platform` job is affected since `compute_backend` defaults to the unchanged value for all pre-existing rows.

## Open Questions

- Exact heartbeat interval and timeout defaults — to be set conservatively at first and tuned once real Colab session durations are observed; tracked as a risk above, not a blocker.
- Whether artifact relay needs chunked upload for larger models — implementation detail, deferred to tasks.md.
- Whether the stall-detection Celery beat task needs its own dedicated worker/queue (mirroring `celery_worker_extraction`'s isolation) or can run on the existing `training_service` Celery app — leaning toward the existing app since the check itself is lightweight (a DB scan), but left open for tasks.md to confirm during implementation.
