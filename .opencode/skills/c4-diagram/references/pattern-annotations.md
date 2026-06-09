# Architectural Pattern Annotation Rules

When a pattern is confirmed in Phase 1 Q5, apply these rules to the DSL.
Patterns appear in **container/component descriptions** and **relationship
labels** — not as separate boxes (unless the pattern IS a separate
infrastructure element like a DLQ or OTEL Collector). Load only the
sections for the confirmed patterns.

## Saga (Choreography)

- Annotate the orchestrating service container:
  `"...Implements Saga (choreography) for multi-service workflows"`
- Each participating service:
  `"...Saga participant — listens for [EventName], publishes [CompensationEvent] on failure"`
- Compensating transaction relationships:
  label with `"Compensates via" "[CompensationEventName]"`
- Add tag `"Saga Participant"` to involved containers.

## Saga (Orchestration)

- Add a dedicated `Saga Orchestrator` component inside the coordinating
  service.
- The orchestrator component calls each participant service explicitly.
- Label outgoing calls: `"Step 1: Reserve inventory"`,
  `"Step 2: Charge payment"`, etc.
- Label compensation calls: `"Compensate: Release inventory"` etc.

## CQRS

- L3: Add two distinct components inside the service — `Command Handler`
  and `Query Handler`.
- If separate read model: add a `Read Model Store` ContainerDb alongside
  the write DB.
- Relationship from Command Handler to write DB, Query Handler to read DB.
- Label: `"Writes (command)"` and `"Reads (query)"`.

## Outbox Pattern

- L3: Add `Outbox Publisher` component inside the service that writes to DB.
- Relationship: `Outbox Publisher -> [Queue/Event Bus]` labeled
  `"Publishes via Outbox (same transaction)"`.
- Relationship: `[Command Handler / Service] -> Outbox Publisher` labeled
  `"Writes event to outbox table"`.

## Circuit Breaker + Retry

- L3: Add `[ExternalSystem] Client` component (e.g., `Amadeus Client`).
- Annotate component description:
  `"Calls [External] via REST — Circuit Breaker + Retry (exponential backoff)"`.
- Relationship to external system:
  label `"REST/HTTPS (Circuit Breaker)"`.

## BFF (Backend for Frontend)

- L2: Add separate containers per client type: `"Web BFF"` and `"Mobile BFF"`.
- Each BFF calls the same downstream services.
- BFF descriptions:
  `"Client-optimised API for [Web/Mobile] — aggregates [ServiceA] + [ServiceB]"`.
- Tag `"Service"` on BFF containers.

## API Gateway

- L2: Explicit `API Gateway` container at the system entry point.
- Description:
  `"Single entry point — handles auth, routing, rate limiting, WAF"`.
- All external actors route through the API Gateway before reaching
  backend containers.
- Tag `"Service"`; use platform-specific technology string from
  `cloud-platforms.md`.

## Hub-Spoke Networking

- L2: Add a `Network Hub` container tagged `"Infrastructure"`.
- Description:
  `"Centralised shared services — firewall, NAT, DNS, centralized egress"`.
- Spoke workload containers reference the hub:
  `[ServiceA] -> networkHub "Routes egress via" "Private endpoint"`.
- Add note in container descriptions:
  `"Deployed in spoke VNet — routes via hub"`.

## Zero Trust

- Annotate all service-to-service relationships: add `"mTLS"` to the
  protocol field.
- Example: `serviceA -> serviceB "Calls" "REST/HTTPS (mTLS, Zero Trust)"`.
- API Gateway description:
  `"Zero Trust entry — validates identity token on every request"`.
- Add tag `"Zero Trust"` to service containers.

## Dead Letter Queue (DLQ)

- L2: Add explicit `Dead Letter Queue` Container tagged `"Queue"`.
- Technology: platform-specific (e.g., `"Amazon SQS (DLQ)"`).
- Relationship from main queue/event bus:
  `[Queue] -> dlq "Moves unprocessable messages to" "After N retries"`.

## DDD (Domain-Driven Design)

- L3: Name components using DDD vocabulary:
  - `[Domain] Aggregate Root` — owns the domain state and invariants.
  - `[Domain] Repository` — persistence abstraction.
  - `[Domain] Domain Events` — events published after state changes.
  - `[Domain] Application Service` — orchestrates use cases.
- Tag the service container `"Bounded Context"`.
- Component descriptions include the DDD role (e.g.,
  `"Aggregate Root — enforces booking invariants"`).

## Observability (OTEL Pipeline)

When the user opts in to observability infrastructure, add these containers
to the L2 diagram:

```dsl
otelCollector = container "OTEL Collector" "Receives and routes telemetry from all services" "[Platform OTEL Collector]" {
    tags "Observability"
}
logStore = container "Log Store" "Centralised structured log storage" "[Platform Log Store]" {
    tags "Observability"
}
metricsStore = container "Metrics Store" "Time-series metrics and SLO dashboards" "[Platform Metrics Store]" {
    tags "Observability"
}
traceBackend = container "Trace Backend" "Distributed trace storage and service maps" "[Platform Trace Backend]" {
    tags "Observability"
}

# Relationships — all services instrument via OTEL
[serviceA] -> otelCollector "Sends traces/metrics/logs" "OTLP/gRPC"
[serviceB] -> otelCollector "Sends traces/metrics/logs" "OTLP/gRPC"
otelCollector -> logStore    "Routes logs to"    "HTTPS"
otelCollector -> metricsStore "Routes metrics to" "HTTPS"
otelCollector -> traceBackend "Routes traces to"  "HTTPS"
```

Add to the `styles` block:

```dsl
element "Observability" {
    background #7B5EA7
    color #ffffff
    shape RoundedBox
}
```

## Quick reference

| Pattern | Where in diagram | DSL signal |
|---|---|---|
| Saga (Choreography) | Container description + relationship labels | `tags "Saga Participant"`, compensation relationship labels |
| Saga (Orchestration) | Explicit Saga Orchestrator component in L3 | Component named "Saga Orchestrator" |
| CQRS | L3 Command Handler + Query Handler + Read Model DB | Separate `ContainerDb` for read model |
| Outbox | L3 component: Outbox Publisher | Relationship label "Publishes via Outbox (same transaction)" |
| Circuit Breaker | L3 component: [External] Client | Resilience4j / Polly / Hystrix in description |
| BFF | L2 separate containers per client type | Containers named "Web BFF", "Mobile BFF" |
| API Gateway | L2 entry-point container | Container named "API Gateway" with WAF/auth in description |
| Hub-Spoke | L2 Network Hub container | Spoke services route via it |
| Zero Trust | Relationship protocol labels | `"REST/HTTPS (mTLS, Zero Trust)"` on all service-to-service edges |
| DLQ | L2 separate Queue container | `ContainerQueue` named "Dead Letter Queue" |
| DDD | L3 component names | Aggregate Root, Repository, Domain Events, Application Service |
| Observability | L2 Observability containers (purple) | OTEL Collector + Log Store + Metrics Store + Trace Backend |
