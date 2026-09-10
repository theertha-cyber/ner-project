## Why

CAP-2 through CAP-5 delivered tenant self-service data sources (connection control plane, durable Blob sync, contract-governed external PostgreSQL chat, administration portal) but the integrated feature has no verified local delivery path: no ordered migration evidence, no deployment sequencing record, and no operational evidence that the approved single `dev` Docker Compose environment runs the new capabilities safely. ADR-014 records the dev-only Compose topology; this change makes it real and evidenced.

## What Changes

- Adds a `local-compose-data-source-delivery` capability recording the local rolling delivery sequence (additive migrations first, then sequential service/worker replacement gated on readiness) for the CAP-2–CAP-5 increments.
- Adds a safe operational verification and recovery record: local health/readiness evidence, declared finite aggregate telemetry for connection, sync, drift-block, and external-query terminal outcomes, and a documented compatible rollback/roll-forward procedure that restores a runnable health-checked stack within 30 minutes without destructive database rollback.
- Adds a local deployment runbook (`docs/runbooks/tenant-data-sources-local-delivery.md`) and executable delivery evidence (a pytest module asserting migration ordering/compatibility, compose sequencing/readiness contract, and declared-metric finite-label contract, plus telemetry-scan and fixture performance evidence).
- No staging, production, Kubernetes, cloud secret-manager, HA, remote DNS, or TLS-termination claim is introduced.

## Capabilities

### New Capabilities

- `local-compose-data-source-delivery`: local Compose rolling delivery, additive migration sequencing, service/worker readiness, safe operational telemetry, and compatible recovery for the tenant data-source feature.

### Modified Capabilities

- None. Existing `local-dev-stack` and `service-readiness` requirements are referenced, not changed; this capability constrains only the data-source delivery sequence and its evidence.

## Impact

- Affected: `docker-compose.yml` (verified, extended only if a sequencing/readiness gap is found), `alembic/versions/040_*`, `041_*`, `042_*` (ordering/compatibility evidence, no rewrite), `src/shared/observability/domain_metrics.py` (verified declarations only), `scripts/telemetry_scan.py` (executed as evidence), new runbook and new delivery-evidence tests.
- Downstream: portal and gateway/chat/document services gain no new runtime behavior; the change is delivery procedure plus verification.
- Azure live verification stays deferred per `run.provisioning` (`skip`: fixtures/fakes only); capabilities remain inactive until approved resources and activation evidence exist.

## Open Questions

- None. Topology (ADR-014), ladder/strategy/approvals (deployment-plan), and the deferred production targets are all recorded; this change operates strictly inside them.
