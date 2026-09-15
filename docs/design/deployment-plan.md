# Deployment Plan — Tenant Self-Service Data Sources

## Environment Ladder

| Environment | Priority | Target | Production environment |
|---|---:|---|---|
| dev | 1 (lowest and final) | Docker Compose on developer machine | No |

`dev` is the entire recorded ladder and deploys last. Staging and production are explicitly deferred/out of scope and are not implied by this plan.

## Approval Policy

Recorded value: `final-only`. The single final `dev` environment is gated before deployment.

## Rollout Strategy

Recorded strategy: `rolling`. Docker Compose deploys changed application services and workers sequentially after additive/backward-compatible migrations and health/readiness verification; each compatible prior component stays in place until its replacement is healthy. Single-replica local services may still experience interruption, so this strategy makes no zero-downtime claim. There is no router or traffic split. Rollback restores prior compatible images/configuration, or roll-forward applies a compatible corrective migration; destructive database rollback is not assumed.

## Per-Environment Configuration

### dev

| Item | Recorded design |
|---|---|
| Entry point | `localhost` via the Compose-published portal/application port; the build's user guide declares the concrete port. No custom domain or provider hostname. |
| Scale/replica intent | One local instance of each required service/worker and one local instance of each dependency; no availability target. |
| Configuration and secret names | `DATABASE_URL`, `RABBITMQ_URL`, `REDIS_URL`, `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `JWT_SECRET`, `TELEMETRY_PEPPER`, local Azure Blob/Azure PostgreSQL secret-reference environment variable names, and existing model/LLM configuration names. |
| Sources | Ignored developer `.env` supplied to Compose; local `env://` only. Never commit secret values. |

## Access Handoff

At deploy time collect the actual localhost URL, Compose service status, and health/readiness URLs. If the build creates a seeded/demo account, collect its non-secret definition path and access instructions; none is assumed by this design. Collect local administration/dashboard surfaces and the user-facing local setup guide path produced by the build. No public URL, DNS, cloud console, or hosted admin handoff exists.

## Preconditions

- Docker Engine and Docker Compose are installed and running on the developer machine.
- Required local ports are free.
- The developer provides required values in an ignored local `.env`; this pipeline never handles credentials itself.
- Azure capability testing requires customer-approved resources, customer network approval/allowlisting as applicable, least-privilege credentials, TLS validation, and passing connection-test evidence. The capability remains inactive otherwise.
- Staging/production subscriptions, clusters, registries, DNS zones, and cloud CLI authentication are out of scope. A later deployment design must record them; this plan does not choose them.

## Revision History

- 2026-09-09: Approved — single `dev` (docker-compose, localhost, rolling, final-only); staging/production explicitly deferred.
- 2026-09-10 (redo after wind-back): Re-saved unchanged; content remains valid and preserves the approved dev-only docker-compose ladder. Re-saved so the Design-gate artifact postdates the 2026-09-10 wind-back.
