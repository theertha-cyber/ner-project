## ADDED Requirements

### Requirement: Portal Multi-Stage Docker Build

The system SHALL provide `src/portal/Dockerfile` with separate `deps`, `build`, and `runner` stages. The `runner` stage SHALL be based on a minimal Node.js runtime image and SHALL contain only the Next.js `standalone` build output (`.next/standalone`, `.next/static`, `public`) — not the full `node_modules` tree or dev dependencies.

#### Scenario: Portal image builds successfully

- **GIVEN** `src/portal/Dockerfile` and `src/portal/next.config.js` with `output: "standalone"`
- **WHEN** `docker compose build portal` is run
- **THEN** the build SHALL complete successfully producing a runnable image

#### Scenario: Runtime image excludes dev dependencies

- **GIVEN** the built `portal` image
- **WHEN** the final `runner` stage layer is inspected
- **THEN** dev-only dependencies (e.g. build tooling, TypeScript compiler, test frameworks) SHALL NOT be present
- **AND** the image SHALL still serve the app via `node server.js`

### Requirement: Portal Compose Service

`docker-compose.yml` SHALL define a `portal` service built from `src/portal/Dockerfile`, mapping host port `3000` to the container's port `3000`, with any environment variables required to reach the `gateway` service.

#### Scenario: Portal starts as part of the compose stack

- **GIVEN** `docker compose up` is run from the project root
- **WHEN** the `portal` service container starts
- **THEN** it SHALL bind to port `3000` and be reachable at `http://localhost:3000`

#### Scenario: Portal can reach the gateway API

- **GIVEN** the `portal` service has an environment variable pointing at the gateway (e.g. a public API base URL)
- **WHEN** the portal makes a browser-side or server-side request to the gateway
- **THEN** the request SHALL resolve successfully to the `gateway` service
