# NER Platform — Identity & Tenant Entity Configuration (SM-01)

## Database Schemas

### `public` Schema — Global tables (shared across all tenants)

| Table | Columns | Description |
|-------|---------|-------------|
| `tenants` | `id` (UUID), `name`, `slug` (unique), `status` (active/inactive), `max_users`, `max_documents`, `max_storage_gb`, `max_model_versions`, `created_at`, `updated_at` | Tenant organizations. Each tenant gets an isolated schema on creation. |
| `tenant_users` | `id` (UUID), `tenant_id` (FK→tenants), `email` (unique per tenant), `password_hash`, `role` (system_admin/tenant_admin/business_user/annotator), `status` (active/inactive), `created_at` | User accounts scoped to a tenant. Email uniqueness enforced per-tenant. |
| `entity_definitions` | `id` (UUID), `tenant_id` (FK→tenants), `name`, `description`, `examples` (JSON), `validation_rule`, `target_table`, `base_label_mapping` (JSON), `version`, `required_flag`, `is_active`, `created_at`, `updated_at` | Custom entity types defined per tenant. Version increments on update. `base_label_mapping` maps CoNLL labels (PER/ORG/LOC/MISC) to tenant-specific types. |

### `tenant_template` Schema — Blueprint for tenant-isolated schemas

Created by migration `002`. When a tenant is provisioned, `CREATE SCHEMA tenant_{id}` copies this structure:

| Table | Purpose |
|-------|---------|
| `documents` | Uploaded files per tenant |
| `document_text_spans` | OCR/extracted text spans per document |
| `annotation_tasks` | Human annotation task assignments |
| `annotation_labels` | Labels applied during annotation |
| `training_jobs` | Fine-tuning job records |
| `model_versions` | Trained model artifacts |
| `extraction_runs` | Model inference runs |
| `extracted_entities` | Entities found by extraction |
| `audit_log` | Tenant-scoped audit trail |

*(Tables above the dashed line are for SM-02 onwards; schema exists but querying them returns empty until downstream sub-modules are built.)*

## Prerequisites

```bash
docker compose up -d postgres-test    # Start PostgreSQL 16 on port 5432
pip install -r requirements.txt       # or poetry install
alembic upgrade head                  # Run migrations
python -m src.gateway.seed            # Create bootstrap admin
```

## Starting the Server

```bash
uvicorn src.gateway.main:app --reload
```

Swagger UI: `http://localhost:8000/docs`

---

## API Endpoints

### Auth (`/api/v1/auth`)

#### POST `/api/v1/auth/login`
Authenticate a user and receive JWT tokens.

**Request body:**
```json
{
  "email": "admin@nerplatform.io",
  "password": "Admin123!"
}
```

**Response `200`:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "admin@nerplatform.io",
    "role": "system_admin",
    "tenant_id": "system",
    "tenant_slug": null
  }
}
```

**Response `401`:**
```json
{
  "error": { "code": "AUTH_ERROR", "message": "Invalid email or password" }
}
```

**JWT claims:** `sub` (tenant_id:user_id), `tenant_id`, `user_id`, `role`, `type` (access), `iat`, `exp`

**Storage:** Reads from `public.tenant_users` + `public.tenants`.

---

#### POST `/api/v1/auth/refresh`
Exchange a refresh token for a new access + refresh token pair.

**Request body:**
```json
{ "refresh_token": "eyJ..." }
```

**Response `200`:** Same token structure as login.

**Storage:** No DB write — token is decoded and re-issued.

---

#### POST `/api/v1/auth/logout`
Stub — does nothing currently. Intended to add the access token to a Redis blacklist.

**Request body:**
```json
{ "access_token": "eyJ..." }
```

**Response `200`:**
```json
{ "message": "Logged out successfully" }
```

---

### Admin - Tenants (`/api/v1/admin/tenants`)

All endpoints require `Authorization: Bearer <token>` with `role: system_admin`.

#### POST `/api/v1/admin/tenants` (201)
Create a new tenant with isolated PostgreSQL schema.

**Request body:**
```json
{
  "name": "Acme Corp",
  "slug": "acme-corp",
  "max_users": 10,
  "max_documents": 1000,
  "max_storage_gb": 5,
  "max_model_versions": 10
}
```
All fields except `name` are optional (slug auto-generated, quotas get defaults).

**Response `201`:**
```json
{
  "tenant": {
    "id": "uuid",
    "name": "Acme Corp",
    "slug": "acme-corp",
    "status": "active",
    "max_users": 10,
    ...
    "created_at": "2026-06-08 ...",
    "updated_at": "2026-06-08 ..."
  }
}
```

**Response `409`:** Duplicate slug.
```json
{
  "error": { "code": "CONFLICT", "message": "Tenant with slug 'acme-corp' already exists" }
}
```

**Storage:** `INSERT INTO public.tenants` + `CREATE SCHEMA tenant_{id}`.

---

#### GET `/api/v1/admin/tenants`
List tenants with pagination and optional status filter.

**Query params:** `?status=active&page=1&per_page=10`

**Response `200`:**
```json
{
  "tenants": [{ "id": "...", "name": "...", "slug": "...", "status": "active", ... }],
  "total": 25,
  "page": 1,
  "per_page": 10
}
```

**Storage:** `SELECT FROM public.tenants` with LIMIT/OFFSET.

---

#### GET `/api/v1/admin/tenants/{id}`
Get tenant detail with current user count.

**Response `200`:**
```json
{
  "tenant": {
    "id": "uuid",
    "name": "Acme Corp",
    "slug": "acme-corp",
    "status": "active",
    "user_count": 3,
    ...
  }
}
```

**Response `404`:**
```json
{
  "error": { "code": "NOT_FOUND", "message": "Tenant 'uuid' not found" }
}
```

**Storage:** `SELECT FROM public.tenants` + `COUNT FROM public.tenant_users`.

---

#### PUT `/api/v1/admin/tenants/{id}`
Update tenant metadata or quotas. Only `name`, `max_users`, `max_documents`, `max_storage_gb`, `max_model_versions` are updatable.

**Request body:** (partial update — send only changed fields)
```json
{ "max_users": 25, "name": "Acme Corp Updated" }
```

**Response `200`:** Same tenant object with updated fields.

---

#### POST `/api/v1/admin/tenants/{id}/deactivate`
Deactivate a tenant. Sets `status: inactive`. Subsequent tenant-scoped requests return 403.

**Response `200`:**
```json
{
  "tenant": { "id": "...", "status": "inactive", ... }
}
```

---

### Users (`/api/v1/tenants/{slug}/users`)

Requires `role: tenant_admin`. The slug in the URL is resolved to a tenant ID and validated against the JWT.

#### POST `/api/v1/tenants/{slug}/users` (201)
Create a user within the tenant. Checks `max_users` quota.

**Request body:**
```json
{
  "email": "user@acme.com",
  "password": "StrongPass1",
  "role": "annotator"
}
```
Password rules: min 8 chars, 1 uppercase, 1 lowercase, 1 digit. Role must be one of: `tenant_admin`, `business_user`, `annotator`.

**Response `201`:**
```json
{
  "user": {
    "id": "uuid",
    "email": "user@acme.com",
    "role": "annotator",
    "status": "active"
  }
}
```

**Response `429`:** Quota exceeded.
```json
{
  "error": { "code": "QUOTA_EXCEEDED", "message": "Users quota exceeded (limit: 5)" }
}
```

---

#### GET `/api/v1/tenants/{slug}/users`
List users for the tenant. Optional `?role=annotator` filter.

**Response `200`:**
```json
{
  "users": [{ "id": "...", "email": "...", "role": "annotator", "status": "active", "created_at": "..." }]
}
```

---

#### GET `/api/v1/tenants/{slug}/users/{uid}`
Get user detail.

**Response `200`:**
```json
{
  "user": {
    "id": "uuid",
    "email": "user@acme.com",
    "role": "annotator",
    "status": "active",
    "created_at": "2026-06-08T10:00:00Z"
  }
}
```

**Response `404`:**
```json
{
  "error": { "code": "NOT_FOUND", "message": "User 'uuid' not found" }
}
```

---

#### PUT `/api/v1/tenants/{slug}/users/{uid}`
Update user role or status. Allowed fields: `role`, `status`.

**Request body:** (partial update — send only changed fields)
```json
{ "role": "business_user" }
```

**Response `200`:**
```json
{
  "user": {
    "id": "uuid",
    "email": "user@acme.com",
    "role": "business_user",
    "status": "active"
  }
}
```

---

#### DELETE `/api/v1/tenants/{slug}/users/{uid}`
Soft-delete — sets `status: inactive`.

**Response `200`:**
```json
{
  "user": {
    "id": "uuid",
    "email": "user@acme.com",
    "role": "annotator",
    "status": "inactive"
  }
}
```

---

### Entity Types (`/api/v1/tenants/{slug}/entity-types`)

Requires `Authorization: Bearer <token>` with any valid tenant-scoped role. The slug in the URL is resolved to a tenant ID and validated against the JWT.

#### POST `/api/v1/tenants/{slug}/entity-types` (201)
Create an entity type with optional `base_label_mapping`.

**Request body:**
```json
{
  "name": "vendor_name",
  "description": "Name of a vendor/supplier",
  "examples": ["Acme Supplies", "Global Tech Ltd"],
  "validation_rule": null,
  "target_table": "vendors",
  "base_label_mapping": { "ORG": ["vendor_name"] },
  "required_flag": true
}
```

**`base_label_mapping` keys must be one of:** `PER`, `ORG`, `LOC`, `MISC`. Anything else returns 422.

**Response `201`:**
```json
{
  "entity_type": {
    "id": "uuid",
    "name": "vendor_name",
    "version": 1,
    "is_active": true,
    "base_label_mapping": { "ORG": ["vendor_name"] },
    ...
  }
}
```

**Response `422`:** Invalid label key.
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid base model label 'INVALID_LABEL'. Must be one of: LOC, MISC, ORG, PER"
  }
}
```

**Storage:** `INSERT INTO public.entity_definitions`.

---

#### GET `/api/v1/tenants/{slug}/entity-types`
List entity types. Optional `?is_active=true` filter.

**Response `200`:**
```json
{
  "entity_types": [
    { "id": "...", "name": "vendor_name", "version": 1, "is_active": true, ... },
    { "id": "...", "name": "customer_name", "version": 3, "is_active": false, ... }
  ]
}
```

---

#### GET `/api/v1/tenants/{slug}/entity-types/{id}`
Get entity type by ID.

---

#### PUT `/api/v1/tenants/{slug}/entity-types/{id}`
Update entity type. Increments `version`. `name` and `base_label_mapping` can be updated; mapping re-validated.

**Response `200`:**
```json
{
  "entity_type": { "id": "...", "name": "vendor_name", "version": 2, ... }
}
```

---

#### DELETE `/api/v1/tenants/{slug}/entity-types/{id}`
Soft-delete — sets `is_active: false`.

**Response `200`:** Entity type with `is_active: false`.

---

### Document Ingestion (`/api/v1/documents`)

Requires `Authorization: Bearer <token>` with any valid tenant-scoped role. The tenant is resolved from the JWT — no slug needed in the URL.

The document service runs as a standalone microservice on port 8001:
```bash
uvicorn src.document_service.main:app --port 8001 --reload
```

Swagger UI: `http://localhost:8001/docs`

#### POST `/api/v1/documents` (201)
Upload a document for OCR processing. Accepted types: `.pdf`, `.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff`. Max file size: 50MB.

**Request:** `multipart/form-data`
```
file: <binary>
```

**Response `201`:**
```json
{
  "id": "uuid",
  "filename": "invoice.pdf",
  "content_type": "application/pdf",
  "file_size": 245760,
  "status": "pending",
  "created_at": "2026-06-09T10:00:00Z",
  "updated_at": "2026-06-09T10:00:00Z"
}
```

**Response `413`:** File too large.
```json
{
  "error": { "code": "FILE_TOO_LARGE", "message": "File size exceeds maximum allowed size of 52428800 bytes" }
}
```

**Response `422`:** Unsupported file type.
```json
{
  "error": { "code": "UNSUPPORTED_FILE_TYPE", "message": "Unsupported file type: .exe. Allowed: .pdf, .jpg, .jpeg, .png, .tif, .tiff" }
}
```

**Storage:** Streams file to MinIO at `tenants/{tid}/documents/{docId}.{ext}`, inserts record in `tenant_{tid}.documents` with `status: "pending"`.

---

#### GET `/api/v1/documents`
List documents for the tenant with optional status filter and pagination.

**Query params:** `?status=processed&page=1&per_page=10`

**Response `200`:**
```json
{
  "documents": [
    {
      "id": "uuid",
      "filename": "invoice.pdf",
      "content_type": "application/pdf",
      "file_size": 245760,
      "status": "processed",
      "error_message": null,
      "blob_path": "tenants/{tid}/documents/{docId}.pdf",
      "created_at": "2026-06-09T10:00:00Z",
      "updated_at": "2026-06-09T10:05:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 10
}
```

**Storage:** `SELECT FROM tenant_{tid}.documents` with `WHERE status = ?` and LIMIT/OFFSET.

---

#### GET `/api/v1/documents/{doc_id}`
Get a single document's metadata and processing status.

**Response `200`:**
```json
{
  "id": "uuid",
  "filename": "invoice.pdf",
  "content_type": "application/pdf",
  "file_size": 245760,
  "status": "processed",
  "error_message": null,
  "blob_path": "tenants/{tid}/documents/{docId}.pdf",
  "created_at": "2026-06-09T10:00:00Z",
  "updated_at": "2026-06-09T10:05:00Z"
}
```

**Response `404`:**
```json
{
  "error": { "code": "NOT_FOUND", "message": "Document 'uuid' not found" }
}
```

#### DELETE `/api/v1/documents/{doc_id}`
Soft-delete a document. Sets `status: "deleted"`. The blob remains in MinIO.

**Response `200`:**
```json
{
  "id": "uuid",
  "filename": "invoice.pdf",
  "status": "deleted",
  ...
}
```

---

## Error Response Format

All errors follow this structure:
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable description",
    "request_id": "uuid"
  }
}
```

| HTTP Code | Error Code | When |
|-----------|-----------|------|
| 401 | `AUTH_ERROR` | Missing/invalid/expired JWT, wrong credentials |
| 403 | `TENANT_INACTIVE` | Tenant is deactivated |
| 403 | `TENANT_MISMATCH` | JWT tenant_id ≠ URL tenant_id |
| 403 | `FORBIDDEN` | Role insufficient — requires `system_admin` (admin routes) or `tenant_admin` (tenant-scoped user mgmt) |
| 404 | `TENANT_NOT_FOUND` | Tenant slug does not resolve |
| 404 | `NOT_FOUND` | Resource (user, entity type) not found |
| 409 | `CONFLICT` | Duplicate slug or email |
| 413 | `FILE_TOO_LARGE` | Upload exceeds 50MB limit |
| 422 | `UNSUPPORTED_FILE_TYPE` | File extension not in allowed list |
| 422 | `VALIDATION_ERROR` | Invalid input (password rules, label mapping) |
| 429 | `QUOTA_EXCEEDED` | Resource limit reached |

---

## Auth Flow Summary

```
Client                    Gateway (FastAPI)
  |                            |
  |-- POST /auth/login ------->|  Validates credentials
  |<-- { access_token,         |  Returns JWT (15-min TTL)
  |      refresh_token } ------|  + refresh token (7-day TTL)
  |                            |
  |-- GET /tenants/{slug}/...  |
  |   Authorization: Bearer .. |  Middleware decodes JWT
  |                            |  Dependency resolves slug→tenant_id
  |                            |  Compares JWT tenant_id vs URL
  |<-- 200 / 403 / 404 --------|  Forwards or rejects
  |                            |
  |-- POST /auth/refresh ----->|  Validates refresh token
  |<-- { new tokens } ---------|  Issues new pair
```

**In Swagger UI:** Click "Authorize" → enter `Bearer <access_token>` → all subsequent requests include it automatically.
