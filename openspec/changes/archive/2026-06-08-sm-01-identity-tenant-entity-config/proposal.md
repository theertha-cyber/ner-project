## Why

The platform needs a foundation layer before any tenant can use it. Currently there is no tenant provisioning, no user authentication, and no entity type configuration. Without this change, no tenant can onboard, no user can log in, and no NER labels can be defined. This is the base block that all seven sub-modules (SM-02 through SM-07) depend on.

## What Changes

- New **tenant provisioning** flow: System Admin creates tenants, which allocates an isolated PostgreSQL schema, a URL, and storage prefixes.
- New **user management** with tenant-scoped directories: each tenant manages its own users and roles (Tenant Admin, Business User, Annotator) independently.
- New **JWT authentication** with tenant context embedded in the token; all subsequent requests carry `{tenant_id, user_id, role}`.
- New **entity type configuration** API and UI: tenants define custom entity labels, descriptions, validation rules, and a `base_label_mapping` from the base model's CoNLL classes (PER, ORG, LOC, MISC) to their custom types.
- New **System Admin console**: a separate SPA for tenant CRUD, quota management, and infrastructure monitoring.
- New **tenant context middleware** in the API gateway that extracts tenant identity from URL path or subdomain and injects it into every request scope.

## Capabilities

### New Capabilities

- `tenant-provisioning`: System Admin CRUD for tenants — creates isolated PostgreSQL schema, allocates tenant-specific URL, provisions blob storage prefix, sets resource quotas.
- `user-auth`: Tenant-scoped user directories with role-based access control (Tenant Admin, Business User, Annotator) and JWT authentication carrying `{tenant_id, user_id, role}` in every request.
- `entity-config`: Entity type CRUD with fields, descriptions, examples, validation rules, target table mapping, versioning, and `base_label_mapping` from base model CoNLL classes to custom types.
- `admin-console`: System Admin single-page application for tenant lifecycle management, quota monitoring, user oversight, and GPU job visibility.

### Modified Capabilities

None — this is the first change in a greenfield project.

## Impact

- **New database objects**: `public.tenants`, `public.tenant_users`, `public.entity_definitions` tables in the `public` schema; per-tenant schema creation at provisioning time.
- **New API endpoints**: `/api/v1/admin/tenants/*`, `/api/v1/admin/tenants/{tid}/users/*`, `/api/v1/tenants/{tid}/entity-types/*`, `/api/v1/auth/login`.
- **New middleware**: Tenant context resolver in the API gateway.
- **New frontend routes**: System Admin SPA (`/admin/*`), Tenant Admin SPA (`/app/*`).
- **Downstream consumers**: SM-02 through SM-07 all depend on tenant context, user auth, and entity type definitions from this change.

## Open Questions

- Should tenant provisioning be synchronous (block until schema is created) or async (tenant status = `provisioning` → `active`)?
Answer: Async.
- What is the exact URL format for tenant-specific login URLs? (e.g., `https://{tenant-slug}.app.example.com/login` or `https://app.example.com/{tenant-slug}/login`)
Answer: `https://{tenant-slug}.app.example.com/login`
- Maximum tenant count before sharding consideration — ADR-001 mentions 500, but is this a hard limit for the initial release?
Answer: 500
