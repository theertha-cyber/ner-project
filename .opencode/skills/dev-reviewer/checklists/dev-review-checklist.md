---
# Developer Review Checklist
# Version: 1.0
#
# HOW THIS FILE IS USED
# The dev-reviewer skill loads this file at the start of every review session.
# Each item is evaluated against the change folder artifacts and the relevant
# codebase files provided as context.
#
# SEVERITY
#   BLOCKER → FAIL on this item forces overall verdict to FAIL
#   WARNING → FAIL on this item forces PASS WITH WARNINGS at most
#   INFO    → recorded but does not affect the verdict
#
# SECTIONS
# DR-FE  — Technical Feasibility
# DR-TC  — Task Completeness
# DR-TO  — Task Ordering
# DR-CB  — Codebase Consistency
# DR-PI  — Pattern Implementation Correctness
# DR-AV  — AC Verification Feasibility
#         (policy: docs/workflow/acceptance-criteria.md)
# DR-AF  — Agent-Friendliness
# DR-CX  — Complexity Assessment
# DR-DX  — Developer Experience & Maintainability
---

# Developer Review Checklist

## Section DR-FE — Technical Feasibility

> Verify that every element of the design can be implemented with the
> project's current tech stack, libraries, and infrastructure without
> introducing new dependencies that have not been approved.

| ID | Severity | Checklist Item |
|---|---|---|
| DR-FE-01 | BLOCKER | Every library or framework referenced in `design.md` is already a project dependency (in `package.json`, `requirements.txt`, `pom.xml`, etc.) or is explicitly listed as a new dependency to be added in `tasks.md`. |
| DR-FE-02 | BLOCKER | Every infrastructure component referenced in `design.md` (message broker, cache, DB feature, secret store) is listed as available in `PROJECT.md` Section 6. |
| DR-FE-03 | BLOCKER | Every environment variable or configuration value referenced in `design.md` either already exists or has a corresponding task to add it to the environment configuration. |
| DR-FE-04 | BLOCKER | The runtime language version, framework version, and ORM version assumed by the design are consistent with `PROJECT.md` Section 2 — the design does not use APIs introduced in a newer version. |
| DR-FE-05 | WARNING | New dependencies introduced by this change (libraries, frameworks) have been evaluated for licence compatibility and are not known to have critical security vulnerabilities at the time of this review. |
| DR-FE-06 | WARNING | Any design decision that requires a specific version of an existing dependency (e.g., a feature introduced in Redis 7.0) is noted in `design.md` and the project's current version satisfies it. |
| DR-FE-07 | INFO | Platform-specific constraints (OS, container base image, cloud provider SDK) that affect implementation are documented in `design.md` or `proposal.md`. |

## Section DR-TC — Task Completeness

> Verify that every implementation action implied by the design has a
> corresponding task in `tasks.md`. Check all common categories of
> missing tasks systematically.

| ID | Severity | Checklist Item |
|---|---|---|
| DR-TC-01 | BLOCKER | A task exists for every DB schema change (new table, new column, new index, renamed column, dropped column) implied by `design.md`'s Data Model section. |
| DR-TC-02 | BLOCKER | A task exists for every new environment variable or configuration key referenced in `design.md`. |
| DR-TC-03 | BLOCKER | A task exists for wiring every new service, repository, handler, or middleware into the DI container or application bootstrap. |
| DR-TC-04 | BLOCKER | A task exists for every new infrastructure resource implied by the design (new Kafka topic, new Redis key namespace, new S3 bucket, new secret) — not just the application code that uses it. |
| DR-TC-05 | BLOCKER | If the Outbox pattern is applied: a task exists for the outbox table migration AND a separate task exists for wiring the relay in the service bootstrap. |
| DR-TC-06 | BLOCKER | If the Saga pattern is applied: a task exists for implementing the saga state persistence mechanism (not just the saga step logic). |
| DR-TC-07 | BLOCKER | If the Circuit Breaker pattern is applied: a task exists for configuring the circuit breaker as a shared singleton (not per-request). |
| DR-TC-08 | BLOCKER | If the Cache pattern is applied: a task exists for the cache unavailability fallback implementation, not just the happy-path cache read/write. |
| DR-TC-09 | BLOCKER | Every AC in every functional task has a named executable verification artifact (test file path + test case name) and a "Must fail if" note per the AC Verification Policy (`docs/workflow/acceptance-criteria.md`). An implementation task without paired verification artifacts = FAIL. |
| DR-TC-10 | WARNING | A task exists for updating the OpenAPI specification, event schema registry, or API documentation if the change modifies a public interface. |
| DR-TC-11 | WARNING | A task exists for adding observability instrumentation (metrics, structured log events, trace spans) identified in `design.md`'s Observability section. |
| DR-TC-12 | WARNING | A task exists for adding or updating feature flags if the project uses feature flagging for new features. |
| DR-TC-13 | WARNING | A task exists for updating `openspec/CONTRACTS.md` if a new inter-service contract is introduced. |
| DR-TC-14 | INFO | A task exists for updating developer documentation (README, runbook, architecture diagram) if the change introduces a significant new component or behaviour. |

## Section DR-TO — Task Ordering

> Verify that tasks are sequenced so each task can be completed
> without depending on something created by a later task.

| ID | Severity | Checklist Item |
|---|---|---|
| DR-TO-01 | BLOCKER | Migration tasks (DB schema changes, new tables) appear before any application code task that references the new schema. |
| DR-TO-02 | BLOCKER | Type definition or interface tasks (new domain types, shared interfaces, event schemas) appear before any task that implements or consumes those types. |
| DR-TO-03 | BLOCKER | Infrastructure provisioning tasks (new Kafka topic, new Redis namespace, new secret) appear before any application code task that depends on that infrastructure. |
| DR-TO-04 | BLOCKER | DI wiring / bootstrap tasks appear after all the components being registered are implemented. |
| DR-TO-05 | BLOCKER | Integration test tasks appear after all implementation tasks that the integration test exercises. |
| DR-TO-06 | BLOCKER | Contract test tasks appear after the contract (API endpoint or event schema) is implemented. |
| DR-TO-07 | WARNING | Unit test tasks for a module appear immediately after the implementation task for that module — not batched at the end of all implementation tasks. |
| DR-TO-08 | WARNING | The observability instrumentation task appears after the implementation tasks it instruments, but before the integration test tasks that verify metric emission. |
| DR-TO-09 | INFO | Tasks are grouped in a logical development sequence (domain model → repository → application service → API → tests) consistent with how the codebase is structured. |

## Section DR-CB — Codebase Consistency

> Verify that the design's conventions, naming, and patterns match
> the existing codebase — the implementation should feel native.

| ID | Severity | Checklist Item |
|---|---|---|
| DR-CB-01 | BLOCKER | File and directory names specified in `tasks.md` follow the project's naming convention (`PROJECT.md` Section 9 or inferred from the codebase). |
| DR-CB-02 | BLOCKER | Class, function, and method names referenced in `tasks.md` follow the project's naming convention (PascalCase for classes, camelCase for methods, etc.). |
| DR-CB-03 | BLOCKER | The error handling pattern (error types, exception hierarchy, HTTP error response shape) matches the existing project pattern — no new ad-hoc error handling is introduced. |
| DR-CB-04 | BLOCKER | The test file structure (co-located vs. separate directory, file naming convention, describe/it nesting style) is consistent with the existing test suite. |
| DR-CB-05 | WARNING | DB table names, column names, and index names follow the project's schema naming convention (e.g., `snake_case` plural for tables). |
| DR-CB-06 | WARNING | Domain event names and Kafka topic names follow the project's naming convention from `PROJECT.md`. |
| DR-CB-07 | WARNING | If the project already implements a similar pattern (Circuit Breaker, Cache, Retry) in another service, this change uses the same library and configuration approach — not a different one. |
| DR-CB-08 | WARNING | Log statement structure (log level usage, field names in structured logs, correlation ID inclusion) is consistent with the existing codebase. |
| DR-CB-09 | WARNING | Dependency injection registration (constructor injection vs. property injection, registration in the correct container module) is consistent with the existing DI approach. |
| DR-CB-10 | INFO | Code comments and documentation style is consistent with the existing codebase (JSDoc, docstrings, inline comments for non-obvious logic only). |

## Section DR-PI — Pattern Implementation Correctness

> Verify that each applied pattern is implemented in a way that is
> technically correct — not just present. Only check patterns marked
> Applied in the Pattern Selection Log.

### Outbox Pattern

| ID | Severity | Checklist Item |
|---|---|---|
| DR-PI-OB-01 | BLOCKER | The outbox record is written in the same DB transaction as the domain write — they are not in separate transactions. |
| DR-PI-OB-02 | BLOCKER | The relay marks a record as published only after receiving a broker ACK — not optimistically before the publish attempt. |
| DR-PI-OB-03 | BLOCKER | The mark-published operation is protected against TOCTOU races (e.g., uses a conditional update: `UPDATE outbox SET published_at = NOW() WHERE id = ? AND published_at IS NULL`). |
| DR-PI-OB-04 | BLOCKER | Consumers of outbox-published events have a deduplication mechanism — the Outbox pattern guarantees at-least-once, not exactly-once. |
| DR-PI-OB-05 | WARNING | The outbox table has an index on unpublished records (e.g., `WHERE published_at IS NULL`) — no full table scan on the relay query. |
| DR-PI-OB-06 | WARNING | The outbox retention policy (cleanup of old published records) is implemented or referenced as a follow-up task. |

### Idempotency Guard

| ID | Severity | Checklist Item |
|---|---|---|
| DR-PI-ID-01 | BLOCKER | The deduplication store write is atomic with the operation result — they are stored in the same transaction or using a compare-and-set atomic operation. |
| DR-PI-ID-02 | BLOCKER | Two simultaneous first-time requests with the same idempotency key cannot both succeed (double-insert protection — unique constraint, atomic CAS, or distributed lock). |
| DR-PI-ID-03 | BLOCKER | The TTL is enforced by the store (e.g., Redis `EXPIRE`, DB cleanup job) — not by application-level logic that could be bypassed. |
| DR-PI-ID-04 | WARNING | The idempotency key source is specified: client-supplied header, content hash, or request-derived value — not ambiguous. |
| DR-PI-ID-05 | WARNING | The stored response includes enough information to reconstruct the original response on a cache hit — not just a success/failure flag. |

### Circuit Breaker

| ID | Severity | Checklist Item |
|---|---|---|
| DR-PI-CB-01 | BLOCKER | The circuit breaker instance is a shared singleton per downstream dependency — not instantiated per request, which would defeat the purpose. |
| DR-PI-CB-02 | BLOCKER | The fallback behaviour is implemented and does not simply re-throw the exception — it returns a safe alternative response. |
| DR-PI-CB-03 | WARNING | Circuit breaker state is in-memory (acceptable for most cases, but noted) — if state must survive service restarts, a persistence mechanism is specified. |
| DR-PI-CB-04 | WARNING | The circuit breaker wraps only the downstream call — not the entire request handler, which would prevent the caller from receiving partial results from other dependencies. |
| DR-PI-CB-05 | INFO | The circuit breaker library used is the same one already in use in the project (consistent with DR-CB-07). |

### Saga

| ID | Severity | Checklist Item |
|---|---|---|
| DR-PI-SA-01 | BLOCKER | Saga state (current step, correlation ID, each step's status) is persisted to a durable store before each step begins — not held only in memory. |
| DR-PI-SA-02 | BLOCKER | Every compensating transaction is idempotent — it can be called multiple times without side effects beyond the first successful execution. |
| DR-PI-SA-03 | BLOCKER | The saga can resume from the correct step after an application restart — it does not re-execute steps that already completed. |
| DR-PI-SA-04 | BLOCKER | A dead-letter or manual-intervention path is defined for the case where a compensating transaction fails after exhausting retries. |
| DR-PI-SA-05 | WARNING | For choreography sagas: each service subscribes to exactly the events it needs to trigger its step — no service subscribes to events it does not act on. |
| DR-PI-SA-06 | WARNING | For orchestration sagas: the orchestrator persists its position before sending each command — it does not re-send commands it already sent on restart. |

### Retries

| ID | Severity | Checklist Item |
|---|---|---|
| DR-PI-RT-01 | BLOCKER | Retry logic is only applied to idempotent operations or operations protected by an idempotency guard — retrying a non-idempotent operation without a guard is a correctness bug. |
| DR-PI-RT-02 | BLOCKER | Exponential backoff includes jitter — fixed-interval retries from multiple instances simultaneously create a thundering herd against the downstream. |
| DR-PI-RT-03 | BLOCKER | Non-retryable errors (4xx responses, permanent failures) are not retried — the retry logic has an explicit non-retryable error list. |
| DR-PI-RT-04 | WARNING | Retries are bounded by a total deadline (elapsed time), not only by a count — count-only retries can exceed the caller's own timeout if each attempt takes the full individual timeout. |
| DR-PI-RT-05 | WARNING | The retry implementation reuses the same connection or client correctly — it does not accumulate open connections on each retry attempt. |

### Caching

| ID | Severity | Checklist Item |
|---|---|---|
| DR-PI-CA-01 | BLOCKER | Cache keys are deterministic and stable across application restarts and deployments — no process-local IDs, random values, or timestamp components in the key. |
| DR-PI-CA-02 | BLOCKER | Cache unavailability is caught and handled — the application falls through to the DB without propagating a cache connection error to the caller. |
| DR-PI-CA-03 | BLOCKER | For write-through: if the DB write fails, the cache is not updated. If the cache write fails, the DB write is not rolled back — the failure mode is documented and acceptable. |
| DR-PI-CA-04 | WARNING | Cache stampede risk on cold start is addressed: when many instances simultaneously encounter a cache miss for the same key, only one DB read is triggered (probabilistic expiry, distributed lock, or background warming). |
| DR-PI-CA-05 | WARNING | Cache key namespacing prevents collision between different entities or between environments (e.g., `prod:order:123` vs `staging:order:123`). |
| DR-PI-CA-06 | INFO | The cache serialisation format (JSON, MessagePack, binary) is specified and consistent with the project's existing approach. |

## Section DR-AV — AC Verification Feasibility

> Enforces the AC Verification Policy
> (`docs/workflow/acceptance-criteria.md`) at the implementation layer.
> DR-TC-09 ensures verification artifacts are named; DR-AV ensures
> they can actually be written and run in this codebase.

| ID | Severity | Checklist Item |
|---|---|---|
| DR-AV-01 | BLOCKER | Every named verification artifact's test file path matches the project's test-file convention (co-located vs. separate tree, naming pattern) so the test harness will discover and execute it. |
| DR-AV-02 | BLOCKER | Every named verification artifact can be written with the test frameworks and fixtures already in the project, OR a prerequisite task exists to add the required harness (contract-test framework, test container, mock server). A verification artifact with no viable harness = FAIL. |
| DR-AV-03 | BLOCKER | Every AC's "Must fail if" note is technically plausible — a developer can trace, given the design, how mutating the `THEN` clause would cause the artifact to fail. Vague notes ("the test would fail") = FAIL. |
| DR-AV-04 | BLOCKER | The chosen verification layer can actually observe the AC's `THEN` clause. Example FAIL: AC's THEN asserts a DB row is written, but the verification artifact is a unit test that mocks the repository. |
| DR-AV-05 | BLOCKER | Verification artifacts that depend on infrastructure (DB, cache, broker) either use the project's existing integration-test strategy (test containers, shared test DB) or have a prerequisite task adding it — they do not assume infra not yet in the project. |
| DR-AV-06 | WARNING | Verification artifact file paths and test case names follow the project's existing conventions (e.g., `*.spec.ts` vs. `*.test.ts`; `describe/it` vs. `test()` structure). |
| DR-AV-07 | WARNING | If an AC's THEN involves timing, ordering, or concurrency, the verification artifact uses the project's existing deterministic test helpers (fake clock, controlled scheduler) rather than real sleeps or wall-clock assertions. |
| DR-AV-08 | INFO | For ACs verified by integration or contract tests, the task lists the expected test-run time budget so the CI impact is visible. |

## Section DR-AF — Agent-Friendliness

> Verify that task descriptions are specific enough for an AI coding
> agent to implement correctly without needing follow-up questions.
> This section is particularly important in this SDD workflow.

| ID | Severity | Checklist Item |
|---|---|---|
| DR-AF-01 | BLOCKER | Every task has a "Files affected" field listing the exact file paths to create or modify — not a vague description of where the code should go. |
| DR-AF-02 | BLOCKER | Every task description names the specific class, function, method, or interface to create or modify — not "add the necessary handler" or "implement the required logic". |
| DR-AF-03 | BLOCKER | No task description defers detail to another document with "see design.md for details" — the task must be self-contained or quote the relevant design detail inline. |
| DR-AF-04 | BLOCKER | Every task's acceptance criteria uses concrete, observable conditions — not "ensure correctness" or "verify it works". |
| DR-AF-05 | WARNING | Tasks that require creating a new file specify the full file path, not just the directory. |
| DR-AF-06 | WARNING | Tasks that require modifying an existing file name the specific method or section to modify, not just the file. |
| DR-AF-07 | WARNING | Tasks that introduce a new dependency specify the exact package name and version to install. |
| DR-AF-08 | WARNING | Tasks that reference a configuration key or environment variable name the exact key name as it will appear in the config file. |
| DR-AF-09 | INFO | Tasks are written in the imperative mood ("Implement...", "Create...", "Add...") consistent with how a developer would describe work to a colleague. |

## Section DR-CX — Complexity Assessment

> Assess whether the design's complexity is proportionate to the
> requirement — flag over-engineering and under-engineering equally.

| ID | Severity | Checklist Item |
|---|---|---|
| DR-CX-01 | WARNING | The design does not introduce an abstraction layer (interface, factory, strategy pattern) that serves only one implementation with no foreseeable extension — premature abstraction is flagged. |
| DR-CX-02 | WARNING | The design does not implement a pattern (e.g., CQRS, Saga) for a use case where a simpler approach (direct DB write, synchronous call) would satisfy the requirements — over-engineering is flagged. |
| DR-CX-03 | WARNING | The design does not under-engineer — it does not omit required patterns (e.g., no Outbox when event delivery must be reliable) in the name of simplicity. |
| DR-CX-04 | INFO | If the design is more complex than the reviewer would recommend, a simpler alternative is noted in the Complexity Assessment section of the report as a suggestion (non-blocking). |

## Section DR-DX — Developer Experience & Maintainability

> Verify that the implementation, as designed, will be understandable
> and maintainable by future developers.

| ID | Severity | Checklist Item |
|---|---|---|
| DR-DX-01 | WARNING | Task descriptions do not require deep knowledge of the entire system to understand — a developer unfamiliar with this sub-module could execute the task from the description alone. |
| DR-DX-02 | WARNING | The design does not introduce a "magic" mechanism (e.g., reflection-based auto-registration, macro-generated code) without a clear explanation in `design.md` of how it works. |
| DR-DX-03 | WARNING | Configuration values (timeouts, TTLs, thresholds, batch sizes) are not hardcoded in application logic — they are read from environment variables or a config object. |
| DR-DX-04 | INFO | Non-obvious implementation choices in `design.md` include a brief rationale so future developers understand why the approach was taken, not just what it is. |
| DR-DX-05 | INFO | The implementation is structured so that a future change to a single pattern (e.g., swapping the Circuit Breaker library) requires changes in only one place. |

---

## Verdict Calculation

| Condition | Verdict |
|---|---|
| Any BLOCKER item status is FAIL | **FAIL** |
| One or more WARNING items status is FAIL, no BLOCKER failures | **PASS WITH WARNINGS** |
| All BLOCKER and WARNING items status is PASS | **PASS** |

Pattern-specific sections under DR-PI only apply when the corresponding
pattern is marked Applied in the Pattern Selection Log. Skip sub-sections
for patterns that are Not applicable or Already in place.

---

## Customisation Notes

- Add project-specific feasibility checks under DR-FE (e.g., specific
  cloud provider constraints, corporate proxy requirements).
- Add codebase-specific consistency checks under DR-CB (e.g., your project's
  specific DI container registration pattern).
- Adjust DR-AF items to reflect how your agents are prompted — if your
  agents are given broader context, some AF items may be relaxed.
- Add DR-PI sub-sections for any additional patterns your project uses
  beyond the standard set.
