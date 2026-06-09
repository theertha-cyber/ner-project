# Reference DSL — Full Example

A complete reference implementation showing the DSL shape the skill produces.
The `styles` block is **mandatory**. This example uses Azure, most patterns
applied, and observability opted in. Use it as a structural reference — not
a copy/paste.

```dsl
workspace "SystemName" "Short description" {

    model {
        # ── People / Actors ──────────────────────────────────────────
        user  = person "User"  "Description"
        admin = person "Admin" "Description"

        # ── External Systems ─────────────────────────────────────────
        # REQUIRED: use flat third-parameter tag syntax — the Mermaid exporter
        # rejects { tags } block form on softwareSystem with "Too many tokens"
        extSystem = softwareSystem "External System" "Description" "External System"

        # ── Software System ──────────────────────────────────────────
        mySystem = softwareSystem "System Name" "What it does" {

            # L2 Containers — use platform-specific managed service names
            webapp = container "Web Application" "SPA frontend" "React" {
                tags "Web Browser"
            }

            apiGateway = container "API Gateway" "Single entry point — auth, routing, rate limiting, WAF" "Azure API Management" {
                tags "Service"
            }

            webBff = container "Web BFF" "Client-optimised API for web — aggregates Booking + Profile services" "Node.js/Express" {
                tags "Service"
            }

            bookingService = container "Booking Service" "Handles flight search and booking workflows. Implements Saga (choreography) for multi-service transactions. Bounded Context: Booking." "Java/Spring Boot on AKS" {
                tags "Service" "Bounded Context" "Saga Participant"

                # L3 Components — DDD + pattern annotations
                bookingAggregate  = component "Booking Aggregate Root"   "Enforces booking invariants and state transitions"              "Java"
                bookingRepo       = component "Booking Repository"        "Persistence abstraction for the Booking aggregate"             "Spring Data JPA"
                commandHandler    = component "Command Handler"           "Processes CreateBooking / CancelBooking commands (CQRS write)"  "Spring MVC"
                queryHandler      = component "Query Handler"             "Handles booking search and status reads (CQRS read)"           "Spring MVC"
                sagaCoordinator   = component "Saga Coordinator"          "Publishes domain events; triggers compensating transactions on failure" "Spring Events"
                outboxPublisher   = component "Outbox Publisher"          "Writes domain events to outbox table within same DB transaction (Outbox pattern)" "Spring Scheduler"
                inventoryClient   = component "Inventory Client"          "Calls external Amadeus API — Circuit Breaker + Retry (exponential backoff)" "Feign/Resilience4j"
                domainEvents      = component "Domain Events"             "BookingCreated, BookingCancelled, PaymentRequested"            "Spring ApplicationEvent"
            }

            eventBus = container "Event Bus" "Async event backbone for cross-service communication" "Azure Service Bus" {
                tags "Queue"
            }

            dlq = container "Dead Letter Queue" "Captures unprocessable messages after N retries" "Azure Service Bus (DLQ)" {
                tags "Queue"
            }

            bookingDb = container "Booking DB" "Transactional store for bookings and outbox table" "Azure SQL Database" {
                tags "Database"
            }

            bookingReadDb = container "Booking Read Model" "Denormalized read store for booking queries" "Azure Cosmos DB" {
                tags "Database"
            }

            otelCollector = container "OTEL Collector" "Receives and routes telemetry from all services" "Azure Monitor OTEL Exporter" {
                tags "Observability"
            }
            logStore      = container "Log Store"      "Centralised structured log storage and querying" "Azure Log Analytics" {
                tags "Observability"
            }
            metricsStore  = container "Metrics Store"  "Time-series metrics, SLO dashboards"             "Azure Monitor Metrics" {
                tags "Observability"
            }
            traceBackend  = container "Trace Backend"  "Distributed traces and service maps"             "Azure Application Insights" {
                tags "Observability"
            }
        }

        # ── Relationships ─────────────────────────────────────────────
        user  -> webapp     "Uses" "HTTPS"
        webapp -> apiGateway "Calls" "JSON/HTTPS"
        apiGateway -> webBff "Routes to" "JSON/HTTPS (Zero Trust, mTLS)"

        webBff -> bookingService "Calls" "REST/HTTPS (mTLS)"

        # Internal L3 relationships
        commandHandler   -> bookingAggregate  "Invokes"                  "Internal"
        commandHandler   -> bookingRepo       "Persists via"             "Internal"
        commandHandler   -> outboxPublisher   "Writes event to outbox"   "Internal (same transaction)"
        queryHandler     -> bookingReadDb     "Reads from"               "SQL"
        sagaCoordinator  -> domainEvents      "Publishes"                "Spring Events"
        outboxPublisher  -> eventBus          "Publishes via Outbox"     "AMQP"
        inventoryClient  -> extSystem         "Calls"                    "REST/HTTPS (Circuit Breaker)"

        eventBus -> dlq "Moves failed messages to" "After 3 retries"

        bookingService -> bookingDb     "Reads/Writes (command)" "SQL"

        # Observability
        bookingService -> otelCollector "Sends telemetry" "OTLP/gRPC"
        otelCollector  -> logStore      "Routes logs"     "HTTPS"
        otelCollector  -> metricsStore  "Routes metrics"  "HTTPS"
        otelCollector  -> traceBackend  "Routes traces"   "HTTPS"
    }

    views {
        # L1 — System Context
        systemContext mySystem "SystemContext" "L1 - System Context" {
            include *
            autoLayout lr
        }

        # L2 — Container View
        container mySystem "Containers" "L2 - Container View" {
            include *
            autoLayout lr
        }

        # L3 — Component View (one per container being broken down)
        component bookingService "BookingComponents" "L3 - Booking Service Components" {
            include *
            autoLayout lr
        }

        styles {
            element "Person" {
                background #08427B
                color #ffffff
                shape Person
                fontSize 22
            }
            element "Software System" {
                background #1168BD
                color #ffffff
                shape RoundedBox
            }
            element "External System" {
                background #6B6B6B
                color #ffffff
                shape RoundedBox
            }
            element "Container" {
                background #438DD5
                color #ffffff
                shape RoundedBox
            }
            element "Web Browser" {
                background #438DD5
                color #ffffff
                shape WebBrowser
            }
            element "Database" {
                background #2E6DA4
                color #ffffff
                shape Cylinder
            }
            element "Queue" {
                background #2E6DA4
                color #ffffff
                shape Pipe
            }
            element "Component" {
                background #85BBF0
                color #1A1A1A
                shape Component
            }
            element "Observability" {
                background #7B5EA7
                color #ffffff
                shape RoundedBox
            }
            element "Bounded Context" {
                border dashed
            }
            relationship "Relationship" {
                color #5A5A5A
                style dashed
                fontSize 14
                thickness 2
            }
        }
    }
}
```

## L3 rules

- Components are declared **inside** their parent container block.
- Each component needs: name, description, technology.
- Add a `component` view for each container being broken down.
- Component relationships can cross container boundaries (e.g., a component
  calling an external system).
- Keep L3 views under 15 elements.
- Use DDD naming when DDD is confirmed (Aggregate Root, Repository, Domain
  Events).

## Color reference

> The Mermaid exporter applies its own palette regardless of the DSL
> `styles` block. PlantUML and Structurizr Lite honour `styles`. For
> brand-consistent colors across all three formats, post-process the
> `.mmd` files manually.

| Element | Color | Shape |
|---|---|---|
| Person | `#08427B` dark blue | Person |
| Internal system | `#1168BD` blue | RoundedBox |
| External system | `#6B6B6B` grey | RoundedBox |
| Container (service) | `#438DD5` light blue | RoundedBox |
| Container (frontend) | `#438DD5` light blue | WebBrowser |
| Container (database) | `#2E6DA4` steel blue | Cylinder |
| Container (queue) | `#2E6DA4` steel blue | Pipe |
| Component | `#85BBF0` pale blue | Component |
| Observability | `#7B5EA7` purple | RoundedBox |
