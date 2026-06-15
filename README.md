# NER Platform — Identity, Tenant Entity Configuration, Annotation Workspace & Training Pipeline (SM-01→SM-04)

## Database Schemas

### `public` Schema — Global tables (shared across all tenants)

| Table | Columns | Description |
|-------|---------|-------------|
| `tenants` | `id` (UUID), `name`, `slug` (unique), `status` (active/inactive), `max_users`, `max_documents`, `max_storage_gb`, `max_model_versions`, `created_at`, `updated_at` | Tenant organizations. Each tenant gets an isolated schema on creation. |
| `tenant_users` | `id` (UUID), `tenant_id` (FK→tenants), `email` (unique per tenant), `password_hash`, `role` (system_admin/tenant_admin/business_user/annotator), `status` (active/inactive), `created_at` | User accounts scoped to a tenant. Email uniqueness enforced per-tenant. |
| `entity_definitions` | `id` (UUID), `tenant_id` (FK→tenants), `name`, `description`, `examples` (JSON), `validation_rule`, `target_table`, `base_label_mapping` (JSON), `version`, `required_flag`, `is_active`, `created_at`, `updated_at` | Custom entity types defined per tenant. Version increments on update. `base_label_mapping` maps CoNLL labels (PER/ORG/LOC/MISC) to tenant-specific types. |

### `tenant_template` Schema — Blueprint for tenant-isolated schemas

Created by migration `002`, extended by `003` and `004`. When a tenant is provisioned, `CREATE SCHEMA tenant_{id}` copies this structure:

| Table | Purpose | Added In |
|-------|---------|----------|
| `documents` | Uploaded files per tenant | SM-02 (migration 002) |
| `document_text_spans` | OCR/extracted text spans per document | SM-02 (migration 002) |
| `annotation_tasks` | Human annotation task assignments | SM-01 (migration 002), altered in SM-03 (migration 004) |
| `spans` | Confirmed entity span annotations (char_start, char_end, entity_type, text_content, confidence) | SM-03 (migration 004) |
| `suggested_spans` | Pre-labeling suggestions with confidence score | SM-03 (migration 004) |
| `annotation_labels` | Labels applied during annotation | SM-01 (migration 002, future use) |
| `training_jobs` | Fine-tuning job records (status, hyperparams, metrics, error_message, celery_task_id, mlflow_run_id, mlflow_run_url) | SM-04 (migration 005 + 006) |
| `model_versions` | Trained model artifacts (version_number, training_job_id, status, metrics, artifact_path, mlflow_run_id) | SM-04 (migration 005 + 006) |
| `extraction_runs` | Model inference runs | SM-01 (migration 002, future use) |
| `extracted_entities` | Entities found by extraction | SM-01 (migration 002, future use) |
| `audit_log` | Tenant-scoped audit trail | SM-01 (migration 002, future use) |

**SM-03 additions to `annotation_tasks`:** columns `annotator_user_id` (VARCHAR), `updated_at` (TIMESTAMPTZ), default status changed to `unannotated`. Unique partial index `idx_task_active_document` prevents two annotators from working on the same document simultaneously.

**SM-04 additions (migration 006):** `training_jobs` gained `mlflow_run_id` (VARCHAR) and `mlflow_run_url` (TEXT). `model_versions` gained `mlflow_run_id` (VARCHAR) to link each trained model to its MLflow run. `mlflow_run_url` for model versions is computed at response time from the tracking URI.

## Prerequisites

```bash
docker compose up -d postgres-test minio redis    # Start PostgreSQL 16, MinIO S3, Redis
docker compose up -d mlflow                       # Start MLflow Tracking Server (PostgreSQL backend + MinIO artifact store)
pip install -r requirements.txt                   # or poetry install
alembic upgrade head                              # Run migrations
python -m src.gateway.seed                        # Create bootstrap admin
```

## Starting the Servers

The platform runs three services that can be started independently:

### Gateway (Auth, Tenants, Users, Entity Types)

```bash
uvicorn src.gateway.main:app --reload    # http://localhost:8000/docs
```

### Document Ingestion Service

```bash
uvicorn src.document_service.main:app --port 8001 --reload   # http://localhost:8001/docs
```

### Annotation Service

```bash
uvicorn src.annotation_service.main:app --port 8002 --reload   # http://localhost:8002/docs
```

### Training Service

```bash
uvicorn src.training_service.main:app --port 8003 --reload    # http://localhost:8003/docs
```

**Celery worker** (processes training jobs in the background):
```bash
celery -A src.training_service.celery_app worker --loglevel=info --concurrency=1
```

### Model-Serving Service

```bash
uvicorn src.model_serving.main:app --port 8004 --reload   # http://localhost:8004/docs
```

### Extraction Service

```bash
uvicorn src.extraction_service.main:app --port 8005 --reload   # http://localhost:8005/docs
```

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

### Entity Types (`/api/v1/entity-types`)

**Service:** `src.gateway.main:app` — port 8000
**Swagger UI:** `http://localhost:8000/docs`

Requires `Authorization: Bearer <token>` with any valid tenant-scoped role. The tenant is resolved from the JWT automatically — no slug needed in the URL.

#### POST `/api/v1/entity-types` (201)
Create an entity type with optional `base_label_mapping`. Only `name` is required.

**Request body:** (minimum)
```json
{ "name": "per_name" }
```

**Request body:** (full)
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

**Response `422`:** Invalid label key or missing `name`.
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid base model label 'INVALID_LABEL'. Must be one of: LOC, MISC, ORG, PER"
  }
}
```

**Response `404`:** JWT tenant not found or deactivated.

**Storage:** `INSERT INTO public.entity_definitions`.

---

#### GET `/api/v1/entity-types`
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

#### GET `/api/v1/entity-types/{id}`
Get entity type by ID.

**Response `404`:** Entity type not found.

---

#### PUT `/api/v1/entity-types/{id}`
Update entity type. Increments `version`. `name` and `base_label_mapping` can be updated; mapping re-validated.

**Response `200`:**
```json
{
  "entity_type": { "id": "...", "name": "vendor_name", "version": 2, ... }
}
```

---

#### DELETE `/api/v1/entity-types/{id}`
Soft-delete — sets `is_active: false`.

**Response `200`:** Entity type with `is_active: false`.

---

### Document Ingestion (`/api/v1/documents`)

**Service:** `src.document_service.main:app` — port 8001
**Swagger UI:** `http://localhost:8001/docs`

Requires `Authorization: Bearer <token>` with any valid tenant-scoped role. The tenant is resolved from the JWT — no slug needed in the URL.

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

### Annotation Workspace (`/api/v1/documents/{doc_id}/spans`, `/api/v1/annotation-tasks`, `/api/v1/annotation-export`)

**Service:** `src.annotation_service.main:app` — port 8002
**Swagger UI:** `http://localhost:8002/docs`

Requires `Authorization: Bearer <token>` with any valid tenant-scoped role. The tenant is resolved from the JWT — no slug in the URL.

Annotation tasks follow a three-status lifecycle:
```
unannotated → in-progress → completed
```
A document can have only one active task at a time (enforced by DB unique partial index `idx_task_active_document` on `status IN ('unannotated', 'in-progress')`).

Entity types must be pre-configured via the Gateway's entity-types endpoint. The annotation service validates spans against `public.entity_definitions` for the JWT's tenant.

---

#### Span CRUD

##### POST `/api/v1/documents/{doc_id}/spans` (201)
Create a confirmed entity span on a processed document.

**Request body:**
```json
{
  "entity_type": "ORG",
  "char_start": 0,
  "char_end": 4,
  "text": "Acme",
  "confidence": 1.0
}
```

**Response `201`:**
```json
{
  "id": "uuid",
  "entity_type": "ORG",
  "char_start": 0,
  "char_end": 4,
  "text": "Acme",
  "confidence": 1.0
}
```

**Response `422`:** Invalid entity type (not in `public.entity_definitions` for this tenant).
```json
{
  "detail": { "code": "VALIDATION_ERROR", "message": "Entity type 'INVALID' is not configured for this tenant" }
}
```

**Response `404`:** Document not found or not in `processed` status.

**Storage:** `INSERT INTO tenant_{tid}.spans`.

---

##### GET `/api/v1/documents/{doc_id}/spans`
List confirmed spans for a document.

**Query params:** `?type=suggested` — returns suggested (pre-labeled) spans instead of confirmed spans.

**Response `200`:**
```json
[
  {
    "id": "uuid",
    "entity_type": "ORG",
    "char_start": 0,
    "char_end": 4,
    "text": "Acme",
    "confidence": 1.0,
    "created_at": "2026-06-09T10:00:00Z"
  }
]
```

**Storage:** `SELECT FROM tenant_{tid}.spans` (or `suggested_spans` when `?type=suggested`).

---

##### PATCH `/api/v1/documents/{doc_id}/spans/{span_id}`
Update a span's fields. Allowed fields: `entity_type`, `char_start`, `char_end`, `text`, `confidence`.

**Request body:** (partial)
```json
{ "entity_type": "PER", "confidence": 0.95 }
```

**Response `200`:**
```json
{
  "id": "uuid",
  "entity_type": "PER",
  "char_start": 0,
  "char_end": 4,
  "text": "Acme",
  "confidence": 0.95
}
```

**Response `404`:** Span not found.

**Storage:** `UPDATE tenant_{tid}.spans SET ... WHERE id = :id`.

---

##### DELETE `/api/v1/documents/{doc_id}/spans/{span_id}` (204)
Delete a span. No response body.

**Response `204`:** No content.

**Response `404`:** Span not found.

**Storage:** `DELETE FROM tenant_{tid}.spans WHERE id = :id`.

---

#### Pre-labeling

##### POST `/api/v1/documents/{doc_id}/prelabel`
Generate suggested spans from the tenant's `base_label_mapping`. Uses keyword matching against the document's extracted text. Replaces all existing suggestions for the document.

**Response `200`:**
```json
[
  {
    "id": "uuid",
    "entity_type": "ORG",
    "char_start": 0,
    "char_end": 4,
    "text": "Acme",
    "confidence": 0.85
  }
]
```
Confidence is set to `0.85` for all mock pre-labeling results.

**Response `422`:** Document has no extracted text.

**Storage:** `DELETE FROM tenant_{tid}.suggested_spans WHERE document_id = :doc_id` → `INSERT INTO tenant_{tid}.suggested_spans` — all in a single transaction.

---

##### POST `/api/v1/documents/{doc_id}/spans/promote/{suggest_id}` (201)
Promote a suggested span to a confirmed span. The suggested span is deleted on success.

**Response `201`:**
```json
{
  "id": "uuid",
  "entity_type": "ORG",
  "char_start": 0,
  "char_end": 4,
  "text": "Acme",
  "confidence": 0.85
}
```

**Response `404`:** Suggested span not found.

**Storage:** `INSERT INTO tenant_{tid}.spans` → `DELETE FROM tenant_{tid}.suggested_spans WHERE id = :id` — single transaction.

---

#### Annotation Task Management

##### POST `/api/v1/annotation-tasks` (201)
Create an annotation task linking an annotator to a document. Status starts as `unannotated`.

**Request body:**
```json
{
  "document_id": "uuid",
  "annotator_user_id": "uuid"
}
```

**Response `201`:**
```json
{
  "id": "uuid",
  "document_id": "uuid",
  "annotator_user_id": "uuid",
  "status": "unannotated"
}
```

**Response `409`:** Document already has an active task.
```json
{
  "error": { "code": "CONFLICT", "message": "AnnotationTask with document_id 'uuid' already exists" }
}
```

**Response `422`:** Missing `document_id` or `annotator_user_id`.

**Storage:** `INSERT INTO tenant_{tid}.annotation_tasks`. Lock enforced by unique partial index `idx_task_active_document`.

---

##### GET `/api/v1/annotation-tasks`
List annotation tasks for the tenant.

**Query params:** `?status=unannotated` — filter by status (`unannotated`, `in-progress`, `completed`).

**Response `200`:**
```json
[
  {
    "id": "uuid",
    "document_id": "uuid",
    "annotator_user_id": "uuid",
    "status": "unannotated",
    "created_at": "2026-06-09T10:00:00Z",
    "updated_at": null
  }
]
```

**Storage:** `SELECT FROM tenant_{tid}.annotation_tasks` with optional `WHERE status = :status`.

---

##### PATCH `/api/v1/annotation-tasks/{task_id}`
Update annotation task status. Valid transitions: `unannotated` → `in-progress` → `completed`.

**Request body:**
```json
{ "status": "in-progress" }
```

**Response `200`:**
```json
{
  "id": "uuid",
  "status": "in-progress"
}
```

**Response `422`:** Invalid transition (e.g., `unannotated` → `completed`).
```json
{
  "detail": { "code": "INVALID_TRANSITION", "message": "Cannot transition from 'unannotated' to 'completed'" }
}
```

**Response `422`:** Completing a task with no confirmed spans.
```json
{
  "detail": { "code": "NO_SPANS", "message": "Document must have at least one confirmed span before task can be completed" }
}
```

**Response `404`:** Task not found.

**Storage:** `UPDATE tenant_{tid}.annotation_tasks SET status = :status WHERE id = :id`.

---

#### Annotation Export

##### GET `/api/v1/annotation-export`
Export annotated documents in HuggingFace Dataset JSONL format (one JSON object per line, with `tokens` and `tags` arrays in BIO2 format).

**Query params:** `?entity_types=ORG,PER&document_ids=uuid1,uuid2`

| Param | Type | Description |
|-------|------|-------------|
| `entity_types` | string (optional) | Comma-separated list of entity types to include. Types not in the list get `O` tags. |
| `document_ids` | string (optional) | Comma-separated list of document UUIDs to export. If omitted, exports all documents. |

**Response `200`:** `application/jsonl`
```jsonl
{"tokens": ["Acme", "Corp", "sells", "Widgets", "."], "tags": ["B-ORG", "I-ORG", "O", "O", "O"]}
{"tokens": ["John", "likes", "Widgets", "."], "tags": ["B-PER", "O", "O", "O"]}
```

**Storage:** `SELECT FROM tenant_{tid}.documents` → `SELECT FROM tenant_{tid}.spans` → tokenization via `str.split()` → BIO2 tag encoding.

---

### Training Jobs API (`/api/v1/training-jobs`)

**Service:** `src.training_service.main:app` — port 8003
**Swagger UI:** `http://localhost:8003/docs`

Requires `Authorization: Bearer <token>`. POST and cancel endpoints require `role: tenant_admin`. Approve and reject endpoints require `role: system_admin`. GET and list endpoints are accessible by any role.

The training job lifecycle:
```
pending_approval → queued → running → completed
                               → failed
pending_approval → rejected
pending_approval → cancelled (by tenant admin before approval)
queued → cancelled
running → cancelled
```

---

#### POST `/api/v1/training-jobs` (201)
Submit a new training job for system admin approval. Validates 500+ confirmed spans exist and hyperparameters are in range, then creates the job in `pending_approval` status. A Celery task is NOT enqueued until a system admin approves the job.

**Request body:**
```json
{
  "learning_rate": 2e-5,
  "num_epochs": 3,
  "batch_size": 8,
  "max_seq_length": 128
}
```

| Field | Type | Constraints |
|-------|------|-------------|
| `learning_rate` | float | `> 0` |
| `num_epochs` | int | `1–50` |
| `batch_size` | int | `>= 1` |
| `max_seq_length` | int | `32–512` |

**Response `201`:**
```json
{
  "id": "uuid",
  "status": "pending_approval",
  "hyperparams": { "learning_rate": 2e-5, "num_epochs": 3, "batch_size": 8, "max_seq_length": 128 },
  "current_epoch": null,
  "current_loss": null,
  "metrics": null,
  "error_message": null,
  "model_version_id": null,
  "mlflow_run_id": null,
  "mlflow_run_url": null,
  "created_at": "2026-06-10T12:00:00Z",
  "started_at": null,
  "completed_at": null,
  "failed_at": null
}
```

**Response `422`:** Insufficient entities.
```json
{
  "detail": "Insufficient annotated entities: 42. Minimum 500 required."
}
```

**Response `422`:** Invalid hyperparams (handled by Pydantic — returns field-level validation errors).

**Response `403`:** Non-admin user.

**Storage:** `INSERT INTO tenant_{tid}.training_jobs` with `status = 'pending_approval'` and `celery_task_id = NULL`. No Celery task is enqueued at this point.

---

#### GET `/api/v1/training-jobs`
List training jobs with optional status filter and pagination.

**Query params:** `?status=running&page=1&per_page=20`

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | string | — | Filter by status: `pending_approval`, `queued`, `running`, `completed`, `failed`, `cancelled`, `rejected` |
| `page` | int | 1 | Page number (≥ 1) |
| `per_page` | int | 20 | Items per page (1–100) |

**Response `200`:**
```json
{
  "items": [
    {
      "id": "uuid",
      "status": "running",
      "hyperparams": { "learning_rate": 2e-5, "num_epochs": 3, "batch_size": 8, "max_seq_length": 128 },
      "current_epoch": 2,
      "current_loss": 0.032,
      "metrics": null,
      "error_message": null,
      "model_version_id": null,
      "mlflow_run_id": "a1b2c3d4e5f6...",
      "mlflow_run_url": "http://localhost:5000/#/experiments/1/runs/a1b2c3d4e5f6...",
      "created_at": "2026-06-10T12:00:00Z",
      "started_at": null,
      "completed_at": null,
      "failed_at": null
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 20
}
```

**Storage:** `SELECT FROM tenant_{tid}.training_jobs` with optional `WHERE status = :status` and LIMIT/OFFSET.

---

#### GET `/api/v1/training-jobs/{job_id}`
Get a single training job's status and all status-specific fields.

**Response `200` (queued):**
```json
{
  "id": "uuid",
  "status": "queued",
  "hyperparams": { ... },
  "current_epoch": null,
  "current_loss": null,
  "metrics": null,
  "error_message": null,
  "model_version_id": null,
  "mlflow_run_id": null,
  "mlflow_run_url": null,
  "created_at": "...",
  "started_at": null,
  "completed_at": null,
  "failed_at": null
}
```

**Response `200` (running):** Includes `current_epoch`, `current_loss`, `mlflow_run_id`, and `mlflow_run_url`.

**Response `200` (completed):** Includes `metrics` (`eval_loss`, `eval_precision`, `eval_recall`, `eval_f1`) and `model_version_id`.

**Response `200` (failed):** Includes `error_message`.

**Response `404`:**
```json
{
  "detail": "Training job not found"
}
```

**Storage:** `SELECT FROM tenant_{tid}.training_jobs WHERE id = :id`.

---

#### POST `/api/v1/training-jobs/{job_id}/cancel`
Cancel a training job that is in `pending_approval`, `queued`, or `running` status. Revokes the Celery task with `terminate=True` if one exists (no-op for `pending_approval` jobs that haven't been enqueued yet).

**Response `200`:**
```json
{
  "id": "uuid",
  "status": "cancelled",
  ...
}
```

**Response `422`:** Job is already in a terminal state (`completed`, `failed`, `cancelled`).
```json
{
  "detail": "Cannot cancel job in 'completed' status"
}
```

**Response `404`:** Job not found.

**Storage:** `celery_app.control.revoke(task_id, terminate=True)` + `UPDATE tenant_{tid}.training_jobs SET status = 'cancelled'`.

---

#### POST `/api/v1/training-jobs/{job_id}/approve`
Approve a training job. Requires `role: system_admin`. Accepts a `tenant_id` query parameter to specify which tenant owns the job. Enqueues the Celery task and transitions the job from `pending_approval` to `queued`.

**Query params:** `?tenant_id=<uuid>` (required)

**Response `200`:**
```json
{
  "id": "uuid",
  "status": "queued",
  ...
}
```

**Response `422`:**
```json
{
  "detail": "Cannot approve job in 'completed' status"
}
```

**Response `403`:** Non-system-admin.

**Storage:** `celery_app.send_task("fine_tune_model", args=[tenant_id, job_id, hyperparams])` + `UPDATE tenant_{tid}.training_jobs SET status = 'queued', celery_task_id = :task_id`.

---

#### POST `/api/v1/training-jobs/{job_id}/reject`
Reject a training job. Requires `role: system_admin`. Accepts a `tenant_id` query parameter to specify which tenant owns the job and an optional reason. Transitions the job from `pending_approval` to `rejected`.

**Query params:** `?tenant_id=<uuid>` (required)

**Request body:**
```json
{
  "reason": "GPU cluster at capacity"
}
```

**Response `200`:**
```json
{
  "id": "uuid",
  "status": "rejected",
  "error_message": "GPU cluster at capacity",
  ...
}
```

**Response `422`:**
```json
{
  "detail": "Cannot reject job in 'completed' status"
}
```

**Response `403`:** Non-system-admin.

**Storage:** `UPDATE tenant_{tid}.training_jobs SET status = 'rejected', error_message = :reason`.

---

### Model Registry API (`/api/v1/models`)

**Service:** `src.training_service.main:app` — port 8003
**Swagger UI:** `http://localhost:8003/docs`

Requires `Authorization: Bearer <token>`. GET endpoints are accessible by any role. POST (promote/demote) requires `role: tenant_admin`.

Model version status lifecycle:
```
training → completed → promoted → archived
```

---

#### GET `/api/v1/models`
List all model versions for the tenant, ordered by `version_number` descending.

**Response `200`:**
```json
{
  "items": [
    {
      "id": "uuid",
      "version_number": 3,
      "training_job_id": "uuid",
      "status": "promoted",
      "metrics": { "eval_loss": 0.021, "eval_precision": 0.92, "eval_recall": 0.89, "eval_f1": 0.90 },
      "artifact_path": "tenants/{tid}/models/v1/{version_id}/",
      "mlflow_run_id": "a1b2c3d4e5f6...",
      "mlflow_run_url": "http://localhost:5000/#/experiments/1/runs/a1b2c3d4e5f6...",
      "created_at": "2026-06-10T12:00:00Z",
      "promoted_at": "2026-06-10T12:30:00Z",
      "archived_at": null
    }
  ]
}
```

**Storage:** `SELECT FROM tenant_{tid}.model_versions ORDER BY version_number DESC`.

---

#### GET `/api/v1/models/active`
Get the currently promoted model version.

**Response `200`:**
```json
{
  "id": "uuid",
  "version_number": 3,
  "status": "promoted",
  "artifact_path": "tenants/{tid}/models/v1/{version_id}/",
  "mlflow_run_id": "a1b2c3d4e5f6...",
  "mlflow_run_url": "http://localhost:5000/#/experiments/1/runs/a1b2c3d4e5f6...",
  "metrics": { "eval_f1": 0.90 },
  ...
}
```

**Response `404`:**
```json
{
  "detail": "No active model found"
}
```

**Storage:** `SELECT FROM tenant_{tid}.model_versions WHERE status = 'promoted' LIMIT 1`.

---

### Model Warmup

**Service:** `src.model_serving.main:app` — port 8004
**Swagger UI:** `http://localhost:8004/docs`

Requires `Authorization: Bearer <token>` with any valid tenant-scoped role.

#### POST `/internal/v1/tenants/{tid}/warmup`
Pre-load a model into the inference cache for a tenant. If `version_number` is provided, that specific version is loaded. Otherwise, the currently promoted (active) version is resolved.

**Request body:** (optional — omit to load active version)
```json
{
  "version_number": 2
}
```

**Response `200`:** Model loaded into cache.
```json
{
  "status": "ok",
  "version_number": 2
}
```

**Response `404`:** No active version found, or specified version does not exist / cannot be loaded.
```json
{
  "detail": "No active model version found for this tenant"
}
```

**Storage:** Calls `download_model_artifacts(tenant_id, version_number)` to fetch ONNX model from MinIO at `tenants/{tid}/models/v{version}/`, then loads it via ONNX Runtime and stores it in the in-memory `model_cache`. On subsequent inference requests, the cached model is reused without re-loading.

---

#### POST `/api/v1/models/{version_id}/promote`
Promote a completed model to production. Auto-archives any previously promoted version. After promoting, the system calls the model-serving warmup endpoint to pre-load the model into the inference cache. If warmup fails (model-serving unavailable), the promote still succeeds — the model is loaded on-demand during the first extraction request.

**Response `200`:**
```json
{
  "id": "uuid",
  "version_number": 3,
  "status": "promoted",
  "mlflow_run_id": "a1b2c3d4e5f6...",
  "mlflow_run_url": "http://localhost:5000/#/experiments/1/runs/a1b2c3d4e5f6...",
  "promoted_at": "2026-06-10T12:30:00Z",
  ...
}
```

**Response `422`:** Model is not in `completed` status.
```json
{
  "detail": "Only completed models can be promoted"
}
```

**Response `403`:** Non-admin user.

**Response `404`:** Version not found.

**Storage:** `UPDATE tenant_{tid}.model_versions SET status = 'archived' WHERE status = 'promoted'` → `UPDATE tenant_{tid}.model_versions SET status = 'promoted', promoted_at = NOW() WHERE id = :id`. Then HTTP POST to model-serving warmup endpoint at `/internal/v1/tenants/{tid}/warmup`.

---

#### POST `/api/v1/models/{version_id}/warmup`
Standalone warmup endpoint — pre-loads a model into the model-serving inference cache without changing its promotion status. Useful for CI/CD pipelines and operators.

**Response `200`:**
```json
{
  "status": "ok",
  "version_number": 1
}
```

**Response `404`:** Version not found.

**Storage:** HTTP POST to model-serving internal warmup endpoint.

---

#### POST `/api/v1/models/{version_id}/demote`
Demote a promoted model back to completed.

**Response `200`:**
```json
{
  "id": "uuid",
  "version_number": 3,
  "status": "completed",
  "promoted_at": null,
  ...
}
```

**Response `422`:** Model is not in `promoted` status.
```json
{
  "detail": "Only promoted models can be demoted"
}
```

**Response `403`:** Non-admin user.

**Response `404`:** Version not found.

**Storage:** `UPDATE tenant_{tid}.model_versions SET status = 'completed' WHERE id = :id`.

---

### MLflow Integration

The training service logs every fine-tuning run to MLflow for experiment tracking, model comparison, and artifact management.

**How it works:**
1. A Celery worker starts a training job → creates an MLflow experiment (per tenant, lazy) and a run
2. The run ID (`mlflow_run_id`) is persisted on the `training_jobs` row when training begins
3. A Hugging Face `MLflowCallback` logs per-epoch metrics (loss, precision, recall, F1) to the run
4. On success, the run ID is propagated to the `model_versions` table so every version links back to its MLflow run
5. The run URL (`mlflow_run_url`) is computed as `{tracking_uri}/#/experiments/{exp_id}/runs/{run_id}` — returned in all API responses

**Environment variable:** `NER_MLFLOW_TRACKING_URI=http://localhost:5000` (`.env.example` line 27).

**Docker Compose:** The MLflow Tracking Server is defined in `docker-compose.yml` with a PostgreSQL backend (`mlflow-db`) and MinIO artifact store — run `docker compose up -d mlflow` to start it.

**Verification:** Navigate to `http://localhost:5000` in a browser. After a successful training run, models appear under the tenant-specific experiment in the MLflow UI.

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
| 404 | `NOT_FOUND` | Resource (user, entity type, document, span, task) not found |
| 409 | `CONFLICT` | Duplicate slug or email; annotation task already exists for document |
| 413 | `FILE_TOO_LARGE` | Upload exceeds 50MB limit |
| 422 | `UNSUPPORTED_FILE_TYPE` | File extension not in allowed list |
| 422 | `VALIDATION_ERROR` | Invalid input (password rules, label mapping, entity type, missing fields, invalid hyperparams) |
| 422 | `INVALID_TRANSITION` | Task status transition not allowed (e.g., unannotated → completed) |
| 422 | `NO_SPANS` | Task cannot be completed because document has no confirmed spans |
| 422 | `NO_TEXT` | Document has no extracted text (pre-labeling) |
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
