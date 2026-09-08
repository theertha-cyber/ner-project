## ADDED Requirements

### Requirement: Dependency Connection Retry with Bounded Exponential Backoff

Each backend service (`chat_api`, `extraction_service`, `gateway`, `document_service`, `training_service`) SHALL retry initial connections to its required infrastructure dependencies (PostgreSQL for all services; MinIO for `document_service`; Redis/Celery broker for services that use it) using bounded exponential backoff instead of failing immediately on the first connection attempt.

#### Scenario: Postgres not yet ready at service startup

- **GIVEN** a service starts before its PostgreSQL dependency has finished accepting connections
- **WHEN** the service attempts its first database connection
- **THEN** it SHALL retry with exponential backoff (starting delay ≥ 0.5s, multiplier ≥ 2, capped max delay ≤ 10s) instead of raising an unhandled exception on the first failed attempt

#### Scenario: MinIO not yet ready at document_service startup

- **GIVEN** `document_service` starts before MinIO is accepting connections
- **WHEN** `document_service` initializes its storage client and attempts bucket verification/creation
- **THEN** it SHALL retry with bounded exponential backoff rather than crashing the process on the first `ClientError`

#### Scenario: Dependency never becomes available within the retry bound

- **GIVEN** a required dependency remains unreachable for longer than the configured maximum retry duration
- **WHEN** the retry bound is exhausted
- **THEN** the service SHALL surface a clear startup failure (non-zero exit or logged fatal error identifying which dependency failed) rather than retrying indefinitely

#### Scenario: Dependency recovers after service process is already running

- **GIVEN** a service process is running and a previously-unreachable dependency becomes available
- **WHEN** the next readiness check or query is attempted
- **THEN** the service SHALL successfully reconnect and resume normal operation without requiring a manual restart

### Requirement: Retry Parameters Are Externally Configurable

Retry/backoff parameters (initial delay, backoff multiplier, max delay, max total retry duration) SHALL be configurable via environment variables, with defaults that reproduce current Docker Compose startup behavior unchanged.

#### Scenario: No environment override present

- **GIVEN** no retry-related environment variables are set
- **WHEN** a service starts under the existing local Docker Compose configuration
- **THEN** retry defaults SHALL be applied and startup behavior SHALL be equivalent to pre-change behavior when dependencies are already available (i.e., no added delay when nothing needs retrying)

#### Scenario: Environment override present

- **GIVEN** an operator sets a retry-tuning environment variable (e.g. max retry duration) to a non-default value
- **WHEN** the service starts
- **THEN** the service SHALL use the overridden value instead of the built-in default

### Requirement: Readiness Endpoint Reflects Actual Dependency State

Each service SHALL expose a `/health` endpoint that reports readiness based on the real-time reachability of its declared critical dependencies, returning HTTP 200 with a per-dependency status breakdown when all critical dependencies are reachable, and HTTP 503 with the same breakdown identifying which dependency failed when any are not.

#### Scenario: All dependencies reachable

- **GIVEN** a service's PostgreSQL (and MinIO/Redis/model dependency, where applicable) are all reachable
- **WHEN** a client requests `/health`
- **THEN** the response SHALL be HTTP 200 with a JSON body listing each checked dependency and its individual status as healthy

#### Scenario: A critical dependency is unreachable

- **GIVEN** a service's PostgreSQL connection is currently failing
- **WHEN** a client requests `/health`
- **THEN** the response SHALL be HTTP 503 with a JSON body identifying PostgreSQL as unhealthy, while still reporting the status of other checked dependencies

#### Scenario: chat_api and extraction_service check base model availability

- **GIVEN** `chat_api` or `extraction_service` is running
- **WHEN** a client requests `/health`
- **THEN** the readiness check SHALL confirm the default base model is available (consistent with the always-available base-model guarantee) and SHALL NOT report not-ready solely due to the absence of a tenant-specific model

### Requirement: Liveness Endpoint Independent of Dependency State

Each service SHALL expose a `/health/live` endpoint that returns HTTP 200 whenever the service process is running and able to handle HTTP requests, regardless of the reachability of its infrastructure dependencies.

#### Scenario: Dependencies are down but the process is running

- **GIVEN** a service's PostgreSQL dependency is unreachable
- **WHEN** a client requests `/health/live`
- **THEN** the response SHALL be HTTP 200, distinct from the `/health` readiness response for the same moment

### Requirement: Externally Configurable Deployment Assumptions

CORS origins, CORS origin regex, PostgreSQL SSL mode, and inter-service base URLs SHALL be settable via environment variables, with defaults that preserve current local Docker Compose behavior.

#### Scenario: Default configuration under Docker Compose

- **GIVEN** no relevant environment variables are overridden
- **WHEN** a service starts under the existing `docker-compose.yml`
- **THEN** CORS origins, CORS regex, database SSL mode, and inter-service URLs SHALL resolve to the same effective values as before this change

#### Scenario: SSL mode overridden via environment variable

- **GIVEN** an operator sets a PostgreSQL SSL mode environment variable to a non-default value
- **WHEN** the service constructs its database connection
- **THEN** the resulting connection SHALL use the overridden SSL mode without requiring the entire `DATABASE_URL` to be reconstructed
