# 014. Local Docker Compose Deployment Topology

## Status
Accepted

## Context

The human deployment decision for this build is `dev` only, using Docker Compose on a developer machine with a localhost entry point; staging and production are explicitly deferred and out of scope. Baseline policy requires an ADR for deployment topology. A developer-machine Compose deployment cannot provide production high availability or traffic splitting.

## Decision

Use one lowest-and-final environment named `dev`, targeted to Docker Compose on the developer machine. Use the recorded `rolling` strategy: deploy changed services/workers sequentially only after compatible additive migrations and readiness checks, preserving the prior compatible component until its replacement is healthy. This local target may use a single replica and therefore does not promise no interruption. Roll back by restoring the prior image/configuration or roll forward with a compatible corrective migration; destructive database rollback is not assumed. Apply `final-only` approval policy, which gates the single dev environment. Access is loopback-only through the Compose-published application port; no provider hostname, custom domain, DNS, or TLS termination is part of this build.

## Alternatives Considered

| Option | Why not chosen |
|---|---|
| dev > staging > production | Explicitly deferred and would invent cloud/deployment facts. |
| Kubernetes/ECS | Not selected by the human and disproportionate for local-only delivery. |
| Recreate, blue-green, or canary | Recreate was not selected; blue-green/canary require traffic routing unavailable in this local topology. |

## Consequences

Local development receives reproducible containerized dependencies and an explicit compatible roll-forward/rollback path, but has no production SLO, remote entry point, or cloud secret-manager claim. Later non-local deployment requires a new approved topology ADR and deployment plan revision.

## Related
- Requirement(s): Delivery and Deployment Requirements; NFR-AVAIL-001; NFR-DR-001
- Supersedes / Superseded by: None.

## Revision History

- 2026-09-10 (redo after wind-back): Re-saved unchanged; dev-only Compose topology (rolling, final-only, localhost) remains valid. Re-saved so the Design-gate artifact postdates the 2026-09-10 wind-back.
