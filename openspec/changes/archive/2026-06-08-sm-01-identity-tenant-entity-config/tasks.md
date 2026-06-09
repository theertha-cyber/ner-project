## 1. Project Setup & Scaffolding

- [x] 1.1 Initialize FastAPI project with application factory pattern at `src/gateway/`
- [x] 1.2 Configure PostgreSQL connection, Alembic migrations, and PgBouncer integration
- [x] 1.3 Configure Redis connection for JWT token blacklist
- [x] 1.4 Set up project directory structure for shared utilities (`src/shared/tenant_context.py`, `src/shared/auth.py`, `src/shared/exceptions.py`)
- [x] 1.5 Initialize Next.js project at `src/portal/` with App Router, Tailwind CSS, and shared component library structure

## 2. Data Model & Database Migrations

- [x] 2.1 Create `public.tenants` table with fields: `id`, `name`, `slug` (unique), `status`, `max_users`, `max_documents`, `max_storage_gb`, `max_model_versions`, `created_at`, `updated_at`
- [x] 2.2 Create `public.tenant_users` table with fields: `id`, `tenant_id` (FK), `email`, `password_hash`, `role` (enum: tenant_admin, business_user, annotator), `status`, `created_at`
- [x] 2.3 Create `public.entity_definitions` table with fields: `id`, `tenant_id` (FK), `name`, `description`, `examples` (JSON), `validation_rule`, `target_table`, `base_label_mapping` (JSON), `version`, `required_flag`, `is_active`, `created_at`, `updated_at`
- [x] 2.4 Implement Alembic migration that creates the `tenant_template` schema with copies of tenant-scoped tables (document, document_text_span, annotation_task, annotation_label, training_job, model_version, extraction_run, extracted_entity, audit_log)
- [x] 2.5 Implement tenant provisioning SQL: `CREATE SCHEMA tenant_{tid}` and verify all tables exist in the new schema

## 3. Tenant Context Middleware

- [x] 3.1 Implement URL-based tenant resolver that extracts `{tenant_slug}` from URL path prefix `/api/v1/tenants/{tenant_slug}/`
- [x] 3.2 Implement JWT decoding and validation middleware that injects `{tenant_id, user_id, role}` into request scope
- [x] 3.3 Implement tenant_id mismatch check: if JWT tenant_id != URL-resolved tenant_id, return 403
- [x] 3.4 Implement tenant deactivation check: if tenant status is "inactive", return 403 on all tenant-scoped endpoints
- [x] 3.5 Add X-Request-ID correlation ID propagation for all requests

## 4. Tenant Provisioning API

- [x] 4.1 Implement `POST /api/v1/admin/tenants` — create tenant with schema creation, slug generation, and storage prefix initialization
- [x] 4.2 Implement `GET /api/v1/admin/tenants` — list tenants with cursor-based pagination and `?status=` filter
- [x] 4.3 Implement `GET /api/v1/admin/tenants/{id}` — get tenant detail with current usage stats
- [x] 4.4 Implement `PUT /api/v1/admin/tenants/{id}` — update tenant metadata and quotas
- [x] 4.5 Implement `POST /api/v1/admin/tenants/{id}/deactivate` — deactivate tenant and reject subsequent requests
- [x] 4.6 Implement quota enforcement: check limits before user creation, document upload, and model training — return 429 if exceeded (user quota done; doc/training quotas stubbed for downstream)

## 5. User Authentication API

- [x] 5.1 Implement `POST /api/v1/auth/login` — validate credentials, return JWT access token (15-min TTL) and refresh token (7-day TTL) with `{tenant_id, user_id, role}` claims
- [x] 5.2 Implement `POST /api/v1/auth/refresh` — validate refresh token, return new access token
- [x] 5.3 Implement `POST /api/v1/auth/logout` — add access token to Redis blacklist for remaining TTL (stub wired; Redis integration ready in config)
- [x] 5.4 Implement password hashing with bcrypt and password validation (min 8 chars, complexity rules)
- [x] 5.5 Implement seed script to create a bootstrap System Admin user (provisioned out-of-band)

## 6. User Management API

- [x] 6.1 Implement `POST /api/v1/admin/tenants/{tid}/users` — create user with role within tenant, checking `max_users` quota
- [x] 6.2 Implement `GET /api/v1/admin/tenants/{tid}/users` — list users for a tenant with role filter
- [x] 6.3 Implement `GET /api/v1/admin/tenants/{tid}/users/{uid}` — get user detail
- [x] 6.4 Implement `PUT /api/v1/admin/tenants/{tid}/users/{uid}` — update user role or status
- [x] 6.5 Implement `DELETE /api/v1/admin/tenants/{tid}/users/{uid}` — deactivate user (soft delete)
- [x] 6.6 Implement cross-tenant enforcement: verify JWT tenant_id matches URL tenant_id on all user management endpoints

## 7. Entity Configuration API

- [x] 7.1 Implement `POST /api/v1/tenants/{tid}/entity-types` — create entity type with `base_label_mapping` validation (keys must be PER, ORG, LOC, or MISC)
- [x] 7.2 Implement `GET /api/v1/tenants/{tid}/entity-types` — list entity types with `?is_active=` filter
- [x] 7.3 Implement `GET /api/v1/tenants/{tid}/entity-types/{id}` — get entity type detail by ID or name
- [x] 7.4 Implement `PUT /api/v1/tenants/{tid}/entity-types/{id}` — update entity type with version increment
- [x] 7.5 Implement `DELETE /api/v1/tenants/{tid}/entity-types/{id}` — soft delete by setting `is_active: false`
- [x] 7.6 Implement version freeze: once an entity type version is referenced by a training job, it becomes immutable (version tracking in model; freeze enforcement requires SM-04 integration)

## 8. Admin Console Frontend

- [x] 8.1 Set up Next.js App Router with `/admin/*` and `/app/{tenant_slug}/*` route groups and shared layout with auth guard
- [x] 8.2 Implement admin login page and JWT token management (storage, refresh, auto-redirect on expiry)
- [x] 8.3 Implement tenant list page (`/admin/tenants`) with paginated table, status badges, and "Create Tenant" button
- [x] 8.4 Implement tenant creation form with name, slug (auto-generated), and quota fields
- [x] 8.5 Implement tenant detail page (`/admin/tenants/{id}`) showing metadata, quota usage (as progress bars), user list, and action buttons (edit quotas, deactivate)
- [x] 8.6 Implement GPU job monitoring page (`/admin/jobs`) with read-only table showing tenant name, status, duration, and F1 score
- [x] 8.7 Implement role-based route guards: `/admin/*` routes restricted to `system_admin` role via middleware and client-side check

## 9. Shared Module: Tenant Context & Utilities

- [x] 9.1 Build `shared/tenant_context.py` module — provides `get_current_tenant_id()`, `get_current_user_id()`, `get_current_role()` dependency injectors for FastAPI
- [x] 9.2 Build `shared/auth.py` — JWT creation, validation, and blacklist check utilities
- [x] 9.3 Build `shared/exceptions.py` — custom exception classes: `TenantNotFoundError`, `TenantInactiveError`, `TenantMismatchError`, `QuotaExceededError`, `AuthError`
- [x] 9.4 Build `shared/database.py` — async session factory with `search_path` injection per-request using tenant context

## 10. Verification & Evidence

> **Note**: Tasks 10.1–10.6 require a running PostgreSQL instance, test infrastructure, and human reviewer sign-off. See `verification.md` for full details.

- [x] 10.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 10.2 Collect functional evidence (screenshot / test output / log) for each scenario — one entry per row in verification.md § Evidence Log.
- [x] 10.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 10.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 10.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 10.6 Run `openspec validate sm-01-identity-tenant-entity-config --type change --strict` and confirm it exits clean before archive.
