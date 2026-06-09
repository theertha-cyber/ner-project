## Context

This is the foundation change for the multi-tenant custom NER platform. There is no existing code — the project is greenfield. The change covers tenant lifecycle management, user authentication with tenant-scoped directories, and entity type configuration. Downstream sub-modules (document ingestion, annotation, training, extraction, chatbot, analytics) all depend on the tenant context, user identity, and entity type definitions established here.

Key constraints from the existing architecture:
- ADR-001 mandates per-tenant PostgreSQL schemas with `search_path` enforcement.
- ADR-002 fixes the base model to dslim/bert-base-NER — entity type configuration must support mapping its CoNLL classes (PER, ORG, LOC, MISC) to custom types.
- ADR-004 requires all changes to follow OpenSpec artifact gates.
- The tech stack is FastAPI (Python), React/Next.js (TypeScript), PostgreSQL 16, MinIO/S3, with JWT-based auth.

## Goals / Non-Goals

**Goals:**
- System Admin can provision new tenants with isolated PostgreSQL schemas and storage prefixes.
- Tenant Admin can create and manage users within their tenant scope.
- Users can authenticate via JWT, with `{tenant_id, user_id, role}` embedded in the token.
- Tenant Admin can define entity types with descriptions, validation rules, and base_label_mapping.
- System Admin has a dedicated SPA for tenant lifecycle management.
- Tenant context middleware resolves tenant identity from URL prefix on every request.

**Non-Goals:**
- Document upload or processing (SM-02).
- Annotation workflows or pre-labeling (SM-03).
- Training infrastructure or GPU job orchestration (SM-04).
- Model serving or extraction (SM-05).
- Chatbot or analytics (SM-06, SM-07).

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 Tenant Data Isolation | Separate PostgreSQL schemas per tenant with `search_path`, prefix-based object storage isolation. | Tenant provisioning MUST create a new schema `tenant_{tid}`. All tenant-scoped tables go in this schema. Middleware MUST set `search_path` per request. |
| ADR-002 Base Model Strategy | Single curated base model dslim/bert-base-NER for all tenants; no BYOM. | Entity type configuration MUST support `base_label_mapping` field mapping CoNLL classes (PER, ORG, LOC, MISC) to tenant custom entity types. |
| ADR-004 OpenSpec Governance | Mandatory artifact gates: proposal → design → spec → tasks → evidence → archive. | This design follows the approved proposal. Specs and tasks will be created as separate artifacts. |
| ADR-005 OpenCode Agent Boundaries | Role-specific agents with bounded tool access and human approval gates. | Implementation tasks in this change are scoped to agent type boundaries defined by the project's agent configuration. |

## Decisions

### Decision 1: Tenant Identity Resolution via URL Path Prefix

**Choice:** Tenant is identified by a URL path prefix `/app/<tenant-slug>/...` rather than a subdomain.

**Rationale:** URL path prefix works identically in development (`localhost:3000/app/acme-corp/login`) and production without DNS configuration for each tenant. The API gateway pattern- matches `/app/{tenant_slug}/*` and injects the resolved tenant context. Tenant-specific login URLs take the form `https://app.example.com/app/<tenant-slug>/login`.

**Alternatives considered:**
- Subdomain per tenant (`acme-corp.app.example.com`) — cleaner isolation but requires wildcard DNS, TLS certificate management per tenant, and doesn't work in local dev without `/etc/hosts` entries.
- Custom domain per tenant — maximum flexibility but complex DNS + TLS provisioning unsuitable for MVP.

### Decision 2: Synchronous Tenant Provisioning

**Choice:** Tenant provisioning is synchronous — the API call blocks until the PostgreSQL schema is created, migrations are applied, and the storage prefix is initialized.

**Rationale:** Tenant provisioning is an infrequent, admin-only operation (< 1 per day at launch). Keeping it synchronous simplifies the API contract (no polling for status) and eliminates the need for async job infrastructure at this layer. The response returns the tenant record with `status: "active"`.

**Alternatives considered:**
- Async provisioning with `status: "provisioning"` → webhook to `active` — adds complexity (job queue, status polling) for no benefit given the low frequency and short execution time (< 5s for schema creation).

### Decision 3: JWT with Namespaced Custom Claims

**Choice:** JWT access tokens carry namespaced custom claims: `{"sub": "{tid}:{uid}", "tenant_id": "uuid", "role": "tenant_admin"}`. Tokens are signed with HS256 using a per-environment secret. Access token TTL: 15 minutes. Refresh token TTL: 7 days.

**Rationale:** Embedding `tenant_id` and `role` in the JWT avoids a database lookup on every request. The `sub` claim follows RFC 7519 conventions while encoding both tenant and user identity. Short-lived access tokens limit exposure from token leakage.

**Alternatives considered:**
- Database session lookup per request — more secure (immediate revocation) but adds latency and database load to every API call.
- OAuth2 with external IdP — over-engineered for MVP; can be layered on later.

### Decision 4: Entity Type Configuration with Label Mapping

**Choice:** Entity type definitions include a `base_label_mapping` field: a JSON object mapping base model CoNLL class names to arrays of tenant entity type names. E.g., `{"PER": ["customer_name", "vendor_name"], "ORG": ["company_name"]}`.

**Rationale:** This enables the annotation service (SM-03) to pre-label documents without understanding tenant semantics — it runs the base model, gets standard labels, and then maps them to tenant types via this configuration. The mapping is stored per entity type and versioned alongside the entity definition.

**Alternatives considered:**
- Pre-labeling at annotation time using a generic base model output without mapping — annotators would see PER/ORG/LOC/MISC labels instead of their domain-specific types and would need to manually re-tag everything, defeating the purpose of pre-labeling.

### Decision 5: Admin Console as a Separate SPA Route

**Choice:** The System Admin console is a separate route within the same Next.js frontend: `/admin/*`. It loads only when the authenticated user has the `system_admin` role. Tenant admin and user flows live under `/app/<tenant-slug>/*`.

**Rationale:** A single frontend deployment simplifies CI/CD and shared component usage (UI library, auth middleware). Role-based routing prevents unauthorized access to admin functions.

**Alternatives considered:**
- Separate admin SPA deployment — full isolation but duplicates build pipeline and deployment infrastructure.
- Admin functions embedded in the main app behind role gates — simpler but risks accidental exposure of admin UI elements.

## Risks / Trade-offs

- [Synchronous tenant provisioning blocks the API for several seconds during schema creation] → Acceptable for infrequent admin operations. Add a 60-second DB statement timeout as safety net.
- [URL path prefix tenant resolution: tenant-slug could conflict across tenants] → Slug uniqueness enforced at the database level with a unique constraint. Slugs are auto-generated from tenant name with UUID suffix on collision.
- [JWT token revocation requires waiting for token expiry (max 15 min)] → Implement a token blacklist checked by the tenant context middleware for immediate revocation of compromised tokens.
- [Entity type versioning adds complexity to the data model] → Versions are tracked via `version` integer incremented on each update. Specifying the requirements ensures training jobs reference a frozen entity config version.

## Migration Plan

1. Deploy the shared infrastructure: PostgreSQL database with `public` schema migrations (tenants, tenant_users, entity_definitions tables).
2. Deploy the API gateway with tenant context middleware and auth endpoints.
3. Deploy the frontend with admin and tenant SPA routes.
4. System Admin provisions a first tenant via the admin console to validate the full flow end-to-end.
5. No rollback needed for a greenfield deployment — if issues arise, the database is dropped and recreated.

## Open Questions

- Should tenant provisioning include a seed step that creates an initial System Admin user and the first Tenant Admin user? (Current design: System Admin is provisioned out-of-band via migration seed script.)
Answer: create an initial system admin user and first tenant admin user. If the current design specified in the adr files or tdd file mentioned is not this, update the respective files.