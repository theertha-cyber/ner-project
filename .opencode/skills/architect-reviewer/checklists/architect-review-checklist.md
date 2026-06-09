---
# Architect Review Checklist
# Version: 1.0
#
# HOW THIS FILE IS USED
# The architect-reviewer skill loads this file at the start of every review
# session. Each item is evaluated against the change folder artifacts, ADRs,
# openspec/project.md, and the existing source-of-truth specs.
#
# SEVERITY
#   BLOCKER → FAIL on this item forces overall verdict to FAIL
#   WARNING → FAIL on this item forces PASS WITH WARNINGS at most
#   INFO    → recorded but does not affect the verdict
#
# SECTIONS
# AR-ADR  — ADR Conformance
# AR-PSL  — Pattern Selection Log
# AR-DOM  — Domain Boundary Integrity
# AR-RES  — Resilience Design
# AR-TXN  — Transaction & Consistency
# AR-CAC  — Caching Design
# AR-CTR  — Inter-Service Contracts
# AR-OBS  — Observability
# AR-SEC  — Security
# AR-CON  — Consistency With Existing Architecture
---

# Architect Review Checklist

## Section AR-ADR — ADR Conformance

> Verify that the design complies with every applicable Architecture
> Decision Record. An ADR is applicable if it governs the service,
> data store, messaging infrastructure, pattern, API style, auth
> approach, or observability standard used in this change.

| ID | Severity | Checklist Item |
|---|---|---|
| AR-ADR-01 | BLOCKER | Every ADR in `PROJECT.md`'s ADR table whose `governs-patterns` or domain intersects with this change has been reviewed for compliance. |
| AR-ADR-02 | BLOCKER | No ADR-mandated pattern is absent from the design without a documented exception or a superseding ADR. |
| AR-ADR-03 | BLOCKER | No pattern applied in the design violates an Accepted ADR (e.g., using shared DB when ADR requires Database-per-service). |
| AR-ADR-04 | BLOCKER | Any deviation from an ADR is explicitly documented in `proposal.md` as an exception, with a justification and a reference to the ADR being deviated from. |
| AR-ADR-05 | WARNING | Patterns that require a governing ADR before use (CQRS, Saga Orchestration, Bulkheads, new caching infrastructure) have their governing ADR referenced in `design.md`'s Pattern Selection Log. |
| AR-ADR-06 | WARNING | ADRs marked "Deprecated" in `PROJECT.md` are not used as justification for design decisions in this change. |
| AR-ADR-07 | INFO | Where no ADR covers a significant design decision in this change, an open question in `proposal.md` notes that a new ADR may be warranted. |

## Section AR-PSL — Pattern Selection Log

> Independently re-evaluate the Pattern Selection Log in `design.md`.
> Do not assume the spec-generator's selection is correct — verify
> each decision against the requirements, architecture context, and ADRs.

| ID | Severity | Checklist Item |
|---|---|---|
| AR-PSL-01 | BLOCKER | The Pattern Selection Log is present as the first section of `design.md`. |
| AR-PSL-02 | BLOCKER | Every pattern marked **Applied** has a corresponding design section in `design.md` with concrete configuration values (not placeholders). |
| AR-PSL-03 | BLOCKER | Every pattern marked **Applied** has at least one SHALL requirement and one GIVEN/WHEN/THEN scenario in the delta spec. |
| AR-PSL-04 | BLOCKER | No pattern is marked **Already in place** unless the existing infrastructure genuinely covers it with no new configuration or code required for this change. |
| AR-PSL-05 | WARNING | The rationale for each pattern decision is sound — "Not applicable" entries have a credible reason, not a blank or "N/A". |
| AR-PSL-06 | WARNING | Patterns that are standard for the change's characteristics are not silently omitted: any synchronous outbound call has Timeouts; any idempotent-capable repeated operation has Retries; any DB-write + event-publish has Outbox. |
| AR-PSL-07 | WARNING | The Bulkheads pattern is considered for any change that introduces a new downstream dependency or a new class of heavy consumers. |
| AR-PSL-08 | INFO | The Pattern Selection Log's "Architectural assumptions" field is populated where context was missing, rather than left blank. |

## Section AR-DOM — Domain Boundary Integrity

> Verify that the design respects service ownership boundaries and
> does not introduce hidden coupling between services.

| ID | Severity | Checklist Item |
|---|---|---|
| AR-DOM-01 | BLOCKER | This service does not read from another service's database directly (no cross-schema queries, no shared connection strings). |
| AR-DOM-02 | BLOCKER | This service does not write to another service's database directly. |
| AR-DOM-03 | BLOCKER | Cross-service reads are performed via an API endpoint or a read model (event-sourced projection) — not via a direct DB join or shared table. |
| AR-DOM-04 | BLOCKER | Cross-service writes are performed via domain events, saga steps, or async commands — not via synchronous chained API calls that would fail together. |
| AR-DOM-05 | BLOCKER | The sub-module does not expose another service's internal data model (entities, IDs, field names) through its own public API or events. |
| AR-DOM-06 | WARNING | The public API and event contracts defined in `design.md` are versioned (version field in event payloads, version path prefix or header in APIs). |
| AR-DOM-07 | WARNING | Shared domain concepts (e.g., a "user" entity referenced by multiple services) are referenced by ID only — not by embedding the full object from another service's domain. |
| AR-DOM-08 | WARNING | The service does not implement domain logic that belongs to another service's bounded context (e.g., the Order service does not implement payment validation logic). |
| AR-DOM-09 | INFO | If a new shared type or contract is introduced, it is added to `openspec/CONTRACTS.md`. |

## Section AR-RES — Resilience Design

> Verify that resilience patterns are applied correctly and configured
> consistently with `PROJECT.md` defaults and existing services.

| ID | Severity | Checklist Item |
|---|---|---|
| AR-RES-01 | BLOCKER | Every synchronous outbound call in the design (HTTP, gRPC, external DB) has an explicit timeout value specified — no call is unbounded. |
| AR-RES-02 | BLOCKER | Retry logic is only applied to operations that are idempotent or have an idempotency guard — non-idempotent operations without a guard are not retried. |
| AR-RES-03 | BLOCKER | Circuit Breaker is applied to every synchronous call to an external service that could exhibit slow failure (latency degradation, not just hard errors). |
| AR-RES-04 | BLOCKER | Every Circuit Breaker has a defined fallback behaviour that is safe — not just propagating the error or returning an empty response silently. |
| AR-RES-05 | WARNING | Timeout values are within the ranges specified in `PROJECT.md` Section 7 (Resilience Defaults), or the deviation is documented in `design.md` with a reason. |
| AR-RES-06 | WARNING | Retry backoff uses exponential backoff with jitter — fixed-interval retries without jitter are flagged as a thundering herd risk. |
| AR-RES-07 | WARNING | Retry count is bounded by a deadline (total elapsed time), not only by a count — count-only retries can exceed the caller's own timeout. |
| AR-RES-08 | WARNING | Non-retryable error codes (4xx class, permanent failures) are explicitly listed in `design.md` so the retry logic does not retry them. |
| AR-RES-09 | WARNING | Circuit Breaker thresholds and recovery windows are consistent with existing services in `PROJECT.md`, or the difference is explained. |
| AR-RES-10 | INFO | Bulkheads are considered when this change introduces a new downstream dependency that could monopolise a shared thread pool or connection pool. |

## Section AR-TXN — Transaction & Consistency

> Verify that distributed transaction and consistency patterns are
> applied correctly for the change's data and event flows.

| ID | Severity | Checklist Item |
|---|---|---|
| AR-TXN-01 | BLOCKER | Any operation that writes to a DB and publishes a domain event uses the Outbox pattern (or a documented equivalent from an ADR) — no fire-and-forget publish after DB commit. |
| AR-TXN-02 | BLOCKER | Any business transaction spanning more than one service uses a Saga (choreography or orchestration) — no distributed synchronous chains used as a substitute. |
| AR-TXN-03 | BLOCKER | Every Saga step has a defined compensating transaction that is idempotent and genuinely reverses the step's effect. |
| AR-TXN-04 | BLOCKER | Any endpoint or consumer that may receive duplicate requests (at-least-once delivery, client retries) has an idempotency guard — not just a comment that "callers should deduplicate". |
| AR-TXN-05 | WARNING | The Saga variant (choreography vs. orchestration) is consistent with the project's messaging architecture as documented in `PROJECT.md`. |
| AR-TXN-06 | WARNING | Saga state is persisted before each step begins — application restart mid-saga does not lose progress. |
| AR-TXN-07 | WARNING | The Outbox relay mechanism referenced in the design matches the existing relay infrastructure in `PROJECT.md` — a new relay is not introduced without an ADR. |
| AR-TXN-08 | WARNING | Idempotency TTL is at least as long as the maximum retry window of any caller that could send duplicate requests. |
| AR-TXN-09 | WARNING | Compensation failure scenarios ("what if the compensating transaction itself fails?") have a defined dead-letter or manual-intervention path. |
| AR-TXN-10 | INFO | The eventual consistency window introduced by async processing (Outbox relay lag, Saga step delay) is documented and acceptable per the feature's stated requirements. |

## Section AR-CAC — Caching Design

> Verify that caching patterns are applied correctly, use existing
> infrastructure, and handle unavailability gracefully.

| ID | Severity | Checklist Item |
|---|---|---|
| AR-CAC-01 | BLOCKER | The caching infrastructure used (Redis cluster, Memcached, CDN) matches what is documented in `PROJECT.md` — no new caching infrastructure is introduced without an ADR. |
| AR-CAC-02 | BLOCKER | Cache unavailability is handled gracefully — the application degrades to DB reads, not crashes or returns errors, when the cache is unreachable. |
| AR-CAC-03 | BLOCKER | All write paths that can change cached data are listed as invalidation triggers in the Caching Design section — no write path is silently missing. |
| AR-CAC-04 | WARNING | Cache key schema follows the project's naming convention from `PROJECT.md` (e.g., `<service>:<entity>:<id>`) and is stable across deployments. |
| AR-CAC-05 | WARNING | TTL values are appropriate for the data's change frequency — data that changes frequently does not have a long TTL that would serve stale results. |
| AR-CAC-06 | WARNING | Write-through or read-through caching is only used if the caching middleware supports it — cache-aside is the default if unspecified. |
| AR-CAC-07 | WARNING | Cold-start cache stampede risk is addressed (probabilistic early expiry, distributed lock, or staggered population) when many instances may simultaneously encounter a cache miss. |
| AR-CAC-08 | INFO | If a cache is shared across services, the key namespace ensures no key collision between services. |

## Section AR-CTR — Inter-Service Contracts

> Verify that all contracts exposed or consumed by this change are
> well-defined, versioned, and registered.

| ID | Severity | Checklist Item |
|---|---|---|
| AR-CTR-01 | BLOCKER | Every API endpoint defined in `design.md` has a complete schema: method, path, request body, response body (success and error cases), and status codes. |
| AR-CTR-02 | BLOCKER | Every domain event defined in `design.md` has a complete schema: event type, version, aggregate type, aggregate ID, and payload fields with types. |
| AR-CTR-03 | BLOCKER | No existing event schema or API response shape is changed in a backwards-incompatible way without a version increment and a migration plan for existing consumers. |
| AR-CTR-04 | WARNING | New contracts (API endpoints, events) are registered or planned for registration in `openspec/CONTRACTS.md`. |
| AR-CTR-05 | WARNING | Event schemas use an explicit version field (e.g., `"version": "1"`) so consumers can handle schema evolution. |
| AR-CTR-06 | WARNING | API contracts include an error response schema that is consistent with the project's standard error format from `PROJECT.md`. |
| AR-CTR-07 | INFO | Contract tests are identified as required in `tasks.md` for any new API contract or event schema. |

## Section AR-OBS — Observability

> Verify that the design emits the signals required to operate this
> change in production — particularly for applied patterns.

| ID | Severity | Checklist Item |
|---|---|---|
| AR-OBS-01 | BLOCKER | The Observability section of `design.md` is present and lists specific metrics, log events, and trace spans — not a generic statement. |
| AR-OBS-02 | BLOCKER | Every applied resilience pattern emits its required signal: retry count for Retries, circuit state for Circuit Breaker. |
| AR-OBS-03 | BLOCKER | Every applied caching pattern emits cache hit and cache miss counters. |
| AR-OBS-04 | BLOCKER | Every applied Outbox emits outbox pending count and relay lag. |
| AR-OBS-05 | BLOCKER | Every applied Saga emits step-level events (step name, status, duration, correlation/saga ID). |
| AR-OBS-06 | WARNING | Metric names and label conventions are consistent with the project's observability standards in `PROJECT.md` Section 8. |
| AR-OBS-07 | WARNING | All log entries for significant events include the correlation/request ID so events can be traced across services. |
| AR-OBS-08 | WARNING | Error log entries include structured fields: operation name, error code, error message, and relevant entity IDs — not just a stack trace. |
| AR-OBS-09 | INFO | Alerting thresholds for new metrics are identified in `design.md` or noted as a follow-up task. |

## Section AR-SEC — Security

> Verify that security controls are consistent with the project's
> standards and appropriate for the data handled.

| ID | Severity | Checklist Item |
|---|---|---|
| AR-SEC-01 | BLOCKER | Authentication is enforced on every new endpoint that is not explicitly designated as public — no endpoint is unauthenticated by accident. |
| AR-SEC-02 | BLOCKER | Authorisation is specified: which roles or permissions are required for each operation, and what the system returns for unauthorised access. |
| AR-SEC-03 | BLOCKER | Secrets (API keys, credentials, connection strings) are managed via the project's secret management tool (`PROJECT.md` Section 6) — none are hardcoded or in config files committed to the repository. |
| AR-SEC-04 | BLOCKER | Any personally identifiable information (PII) or sensitive data handled by this change is identified in `design.md`, and the data handling approach (encryption, masking, retention) is documented. |
| AR-SEC-05 | WARNING | Input validation is specified for every API endpoint — required fields, types, formats, length limits, and allowed value sets. |
| AR-SEC-06 | WARNING | The auth mechanism (JWT, API key, session) is consistent with the project's standard from `PROJECT.md`. |
| AR-SEC-07 | WARNING | Data transmitted between services is encrypted in transit — no plaintext sensitive data over internal network calls. |
| AR-SEC-08 | INFO | SQL queries and DB interactions use parameterised queries or an ORM — no string concatenation for query construction. |

## Section AR-CON — Consistency With Existing Architecture

> Verify that the design is coherent with the existing system and
> does not introduce unjustified divergence.

| ID | Severity | Checklist Item |
|---|---|---|
| AR-CON-01 | WARNING | The technology choices in the design (libraries, frameworks, data stores) are consistent with `PROJECT.md`'s tech stack — no new technology is introduced without an ADR. |
| AR-CON-02 | WARNING | The architectural style of the change (layering, naming of layers, DI approach) is consistent with existing services in the codebase. |
| AR-CON-03 | WARNING | The change does not re-implement functionality that already exists as a shared library or platform service — it reuses existing solutions. |
| AR-CON-04 | WARNING | If a new cross-cutting pattern or library is introduced (not in `PROJECT.md`), it is documented in `proposal.md` as an open question or assumption, and flagged for ADR creation. |
| AR-CON-05 | INFO | The design would serve as a reasonable precedent for future similar changes — it does not make bespoke choices that would be confusing to follow in another sub-module. |

---

## Verdict Calculation

| Condition | Verdict |
|---|---|
| Any BLOCKER item status is FAIL | **FAIL** |
| One or more WARNING items status is FAIL, no BLOCKER failures | **PASS WITH WARNINGS** |
| All BLOCKER and WARNING items status is PASS | **PASS** |

INFO items are recorded in the report but do not affect the verdict.

---

## Customisation Notes

- Add project-specific ADR conformance checks under AR-ADR with sequential IDs.
- Add service-specific domain boundary rules under AR-DOM.
- Adjust resilience thresholds in AR-RES to match your `PROJECT.md` defaults.
- Disable items not applicable to your stack (e.g., AR-CAC items if no cache
  exists) by adding a `disabled: true` annotation or deleting the row.
