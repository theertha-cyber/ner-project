---
name: technical-design-document
description: >-
  Create a Technical Design Document (TDD) for a new project or existing project
  integration. Covers scope, requirements, architecture, services, CI/CD,
  observability, and success criteria following enterprise architecture standards.
---

# Technical Design Document

## Setup

1. **Project type** — ask whether this is a new project or an integration into an existing one.
2. **Requirements** — look for a `requirement_docs/` folder in the project root and read all files. If absent, ask the user to describe the requirements.
3. **Existing project scan** (skip for new projects):
   - Read `design-docs/`, `docs/`, `adr/`, `.adr/`, or `decisions/` for prior ADRs and decisions.
   - Identify current tech stack, key modules, frontend framework (if any), and integration boundaries.
   - Scan for existing CI/CD config: `.github/workflows/`, `azure-pipelines.yml`, `Jenkinsfile`, `.gitlab-ci.yml`, `bitbucket-pipelines.yml`. Understand existing pipeline stages, environments, and deployment strategy before designing CI/CD.
   - Look for existing DB schemas: `migrations/`, `schema/`, `prisma/`, `flyway/`, `liquibase/`, or ORM model files.
   - Note existing patterns and constraints that must be respected.
4. **Clarify gaps** — ask targeted questions for anything that cannot be filled with confidence.

---

## Document Structure

### 1. Scope

| | Items |
|---|---|
| **In Scope** | What this effort explicitly covers |
| **Out of Scope** | What a reader might assume is included but is not |

---

### 2. Assumptions & Constraints

| Type | Detail |
|------|--------|
| **Assumption** | Things believed true but not yet verified (team skills, third-party APIs, data availability) |
| **Constraint** | Hard limits — budget, timeline, mandated tech stack, compliance, legacy boundaries |

---

### 3. Requirements

#### Functional Requirements

List each requirement with its API contract or schema where applicable:

- For **API-facing features**: include the OpenAPI contract (endpoint, method, request/response shape, status codes). Example:
  ```yaml
  POST /api/v1/orders
  Request:  { customerId, items: [{ productId, qty }] }
  Response: { orderId, status, estimatedDelivery }
  Errors:   400 (invalid payload), 404 (product not found), 409 (insufficient stock)
  ```
- For **database-related features**: include entity/table design and relationships. Example:
  ```
  orders        { id, customer_id FK, status, created_at }
  order_items   { id, order_id FK, product_id FK, qty, unit_price }
  ```
- For **frontend features**: scan the frontend codebase (components, routing, state management) and explicitly list:
  - New pages / routes to be added
  - Components to be created or modified
  - State changes (store, context, hooks)
  - API calls the frontend will make
  - UX flows and validations

#### Non-Functional Requirements (NFRs)

| Attribute | Target | Notes |
|-----------|--------|-------|
| Latency | e.g., p95 < 300 ms | API response time |
| Availability | e.g., 99.9% monthly | Uptime SLA |
| Throughput | e.g., 1,000 req/s | Peak load |
| Security | e.g., OAuth 2.0, OWASP Top 10 | Auth model |
| Recovery | RPO 15 min / RTO 60 min | DR targets |

---

### 4. Architecture

- Prose description of the proposed design.
- For **existing project integrations**: explicitly map how the new design connects to or modifies existing components — reference them by name.
- Cover: data flow, key integration points, technology choices with rationale, scalability approach, and notable failure modes.
- Include a Mermaid or ASCII diagram showing the high-level component/flow view.

---

### 5. Services & Modules

| Name | Responsibility | Technology | Interfaces (in / out) |
|------|---------------|------------|----------------------|
| | | | |

---

### 6. CI/CD

- If an existing pipeline was found in Setup step 3, describe the **current pipeline** first, then explain what changes or additions are needed.
- If no pipeline exists, design one from scratch appropriate to the stack.

| Stage | Tool / Action | Environment | Notes |
|-------|--------------|-------------|-------|
| Build | e.g., `npm run build` | All | |
| Test | Unit + integration | All | |
| Static Analysis | Lint, SAST | All | |
| Deploy | e.g., Docker push + Helm upgrade | Dev / Staging / Prod | |
| Smoke Test | Health check endpoint | Post-deploy | |

Also cover:
- **Branch strategy** — e.g., feature → dev → staging → main with promotion gates
- **Secrets management** — how credentials are injected (Key Vault, GitHub Secrets, etc.)
- **Rollback approach** — how a bad deploy is reversed

---

### 7. Observability

| Pillar | Detail |
|--------|--------|
| **Logging** | Events logged, log levels, structured format, retention policy |
| **Metrics** | Key indicators (request rate, error rate, queue depth) with alerting thresholds |
| **Tracing** | Distributed tracing tool (e.g., OpenTelemetry), trace propagation across services |
| **Dashboards & Alerts** | Dashboards to create, on-call alert conditions and owners |
| **Health Checks** | Liveness / readiness endpoints, SLA breach detection |

---

### 8. Success Criteria

| Deliverable | Success Criteria | Verification Method |
|-------------|-----------------|---------------------|
| | | |

---

## C4 Diagrams

After presenting the draft, ask:

> Would you like C4 architecture diagrams (Context, Container, Component levels) generated for this design? I can invoke the `c4-diagram` skill.

If the user agrees, invoke the `c4-diagram` skill.

---

## Output

1. Present the full document in chat for review. Revise on request.
2. Once approved, produce the `.md` file with:
   - Cover page with document title, project name, date, and version
   - Table of contents
   - Each section using Heading 1/2 styles
   - All tables rendered as formatted DOCX tables (not plain text)
   - Code blocks / contracts in monospace styled paragraphs
   - Page numbers in the footer
3. Save to `design-docs/NN-<short-name>.md` (e.g., `01-payment-service-integration.md`). If `design-docs/` does not exist, ask the user where to save.

---

## Quality Gate

Before presenting, verify:

- [ ] NFRs are quantified — no "fast", "scalable", or "secure" without numbers
- [ ] API-facing requirements include OpenAPI contract shapes
- [ ] DB-related requirements include schema / entity design
- [ ] Frontend tasks are listed explicitly with routes, components, and state changes
- [ ] CI/CD section builds on the existing pipeline if one was found
- [ ] Architecture section references existing components for integration work
- [ ] Every service in §5 maps to at least one requirement in §3
- [ ] Observability names concrete metrics, alert conditions, and owners
- [ ] Success criteria are measurable and verifiable
- [ ] Assumptions are distinguished from constraints
