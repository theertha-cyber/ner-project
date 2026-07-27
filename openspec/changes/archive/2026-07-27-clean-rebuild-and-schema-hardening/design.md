## Context

The local `ner_dev` database no longer matches the Alembic migration chain. Three distinct failures were confirmed against the running stack:

| Symptom | Live error | Cause |
|---|---|---|
| Entity type create/list 500 | `UndefinedColumnError: column "validation_rule" does not exist` | `public.entity_definitions` has the 7-column shape from `scripts/setup_test_db.py`, not the 13-column shape from migration `001` |
| Upload / list documents 500 for new tenants | `UndefinedTableError: relation "tenant_<id>.documents" does not exist` | `tenant_template.documents` was dropped out of band; `TenantService.create_tenant` clones the template, so tenants created after the drop have no `documents` table |
| `system_admin` dashboard logs stack traces | `relation "tenant_system.documents" does not exist` | `_all_tenant_schemas` derives a schema name from every `public.tenants` row, including the virtual `system` tenant and four test-fixture tenants that have no schema |

Supporting evidence: `public.model_versions` exists (only `setup_test_db.py` creates it) and the fixture tenants `test-tenant`, `tenant-b`, `no-model`, `no-model-tenant` are present in `ner_dev` with two-table schemas matching that script exactly. Separately, the running containers were built from an image whose `alembic/versions/` stops at `020`, lacks `src/shared/retrieval/`, and still contains the deleted `chat_api/services/chunking_service.py` — so migration `022` never ran and `alembic_version` sits at `021`.

The database holds only disposable dev data. The decision to rebuild rather than repair is settled and is an input to this design, not a question it reopens.

## Goals / Non-Goals

**Goals:**

- Return the local environment to a state provably derived from the migration chain.
- Detect schema drift at `db-init` time rather than at first user request.
- Stop treating `public.tenants` rows as proof that a schema exists.
- Make per-tenant migration loops survive incomplete tenant schemas.
- Bring already-provisioned tenant schemas up to the current template shape.
- Stop `scripts/setup_test_db.py` from being able to write to a non-test database.

**Non-Goals:**

- Recovering the Acme Corp tenant's deleted users, or any other data in the current volume. It is gone and this change does not attempt otherwise.
- Explaining the out-of-band event that dropped `tenant_template.documents` and deleted those users. No code path in the repo does either; the mechanism was not identified.
- Changing the tenant-per-schema isolation model.
- Any production or shared-environment migration tooling. This is local dev only.
- Reworking the document-purpose-scoping feature itself. That work is already staged; this change only makes it applicable.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001: Tenant Data Isolation via Separate Database Schemas | Each tenant gets a dedicated Postgres schema `tenant_<id>`, cloned from `tenant_template` | Schema-per-tenant is fixed. Verification and reconciliation must work per schema; the fix for `tenant_system` cannot be "collapse to one schema" |
| ADR-003: Per-Tenant Model Serving Topology | Model serving is scoped per tenant | Nothing in this change may assume a single global model table; `public.model_versions` created by the fixture script is an artifact to remove, not a shape to adopt |
| ADR-004: OpenSpec Spec-Driven Development Governance | Behaviour changes are specified before implementation | Dashboard enumeration and migration robustness changes are specified as delta specs in this change, not written directly |
| ADR-005: OpenCode Agent Permissions and Boundaries | Agents operate within declared boundaries | Destructive volume removal is an operator step in the documented procedure, not something automation performs unprompted |
| ADR-006: Training Infrastructure with Asynchronous GPU Workers | Training runs asynchronously via Celery workers | Workers depend on `db-init` completing; making `db-init` fail on drift must not deadlock the worker services, only prevent them starting |
| ADR-007: Chatbot Architecture with Full RAG and Guardrails | RAG pipeline over per-tenant `document_chunks` | The rebuild must leave `document_chunks` with the `021` page-metadata and `022` purpose columns so the staged retrieval work is exercisable |
| ADR-008: Base Model as Default Inference Model | Base model serves when no tenant model is promoted | A rebuilt empty database has no promoted models; dashboards and extraction must still function, which the base-model default already guarantees |

ADR-002 is superseded in part by ADR-008 and is treated as historical context only.

## Decisions

### Decision 1: Rebuild from empty rather than repair in place

**Choice:** Remove the `postgres-data` volume and apply the full migration chain to an empty database, after rebuilding images.

**Rationale:** The drift has at least three independent sources and one unexplained one. Patching the known differences leaves the unknown drift in place, and the database contains nothing worth preserving. A rebuild also produces a database whose provenance is a single command sequence, which is what verification can then assert against.

**Alternatives considered:**
- Hand-patch `entity_definitions`, recreate `tenant_template.documents`, backfill tenant schemas — ruled out: slower, preserves nothing of value, and leaves unidentified drift.
- `alembic downgrade base` then `upgrade head` — ruled out: downgrades run against the drifted shape and several `downgrade()` functions (`002` drops `tenant_template` CASCADE) would fail or destroy more than intended on a database the chain did not build.

### Decision 2: Verify schema by comparing the live database against a freshly migrated reference

**Choice:** The verification step introspects the live database and compares it against what the chain declares, checking `public` table columns, the `tenant_template` table set, and each `tenant_<id>` schema's table set against `tenant_template`.

**Rationale:** Every confirmed failure in this investigation was a missing column or missing table — exactly what introspection catches. Using `tenant_template` as the reference for tenant schemas means the check stays correct as the chain grows, without maintaining a hand-written expected-schema manifest that would itself drift.

**Alternatives considered:**
- Alembic autogenerate diff against ORM metadata — ruled out: most tenant-scoped tables are raw SQL in migrations, not declarative models, so autogenerate has nothing to compare against.
- A checked-in expected-schema JSON snapshot — ruled out: becomes a second source of truth that must be regenerated on every migration, and going stale reintroduces the class of bug being fixed.

### Decision 3: Drift hard-fails `db-init`

**Choice:** Verification exits non-zero on drift, so `db-init` fails and dependent services do not start.

**Rationale:** The failure mode this change exists to prevent is a drifted database starting successfully and surfacing as scattered 500s hours later. A loud startup failure that names the drifted object is strictly more useful than five services running against a broken schema. The compose file already wires `depends_on: service_completed_successfully`, so the blocking behaviour needs no new mechanism.

**Alternatives considered:**
- Log and continue — ruled out: reproduces the current situation, where the drift was visible in logs and still cost an investigation.
- Auto-repair on detection — ruled out: silently mutating a schema at startup is how drift gets introduced, not how it gets fixed.

### Decision 4: Fix enumeration by intersecting tenants with `pg_namespace`

**Choice:** `_all_tenant_schemas` queries the schemas that exist and returns only those that correspond to a tenant row, rather than mapping every tenant row to a derived schema name.

**Rationale:** Existence in `pg_namespace` is the actual precondition for the queries that follow. The virtual `system` tenant is legitimate — `seed.py` creates it deliberately to own the system admin, and `resolve_tenant_from_jwt` already special-cases `tenant_id == "system"` — so the tenant row is not the bug; treating it as schema-backed is.

**Alternatives considered:**
- Hardcode a `system` exclusion — ruled out: fixes one row and leaves the four fixture tenants, and any future schema-less tenant, still failing.
- Give the system tenant a real empty schema — ruled out: creates a schema that exists only to be counted as zero, and adds a tenant schema that no tenant owns.

### Decision 5: Distinguish partial aggregates from complete ones

**Choice:** When a schema that does exist fails its query, the affected `sources` entry becomes `false`.

**Rationale:** Today `sources["documents"]` is set `true` whenever the loop completes, even if every iteration inside it failed and the total is a meaningless zero. Once schema-less tenants are filtered out, a remaining failure is a real problem and the caller should be told the number is partial. This preserves the existing per-schema rollback-and-continue behaviour required by `dashboard-summary-endpoint`; it only changes how the result is labelled.

**Alternatives considered:**
- Return `null` on any failure — ruled out: contradicts the in-force requirement that one tenant's failure must not blank out the others' data.

### Decision 6: Reconcile tenant schemas from `tenant_template` in one migration

**Choice:** A single new reconciliation migration walks every `tenant_<id>` schema, creates tables present in `tenant_template` but missing there, and adds columns present in the template's copy but missing from the tenant's.

**Rationale:** Migrations `003`, and parts of `002`, only ever touched `tenant_template`, so any tenant provisioned before them silently lags. Rather than retrofitting per-tenant loops into old revisions — which would not re-run on databases already past them — one forward reconciliation brings everything level and can be re-run safely.

**Alternatives considered:**
- Edit migrations `003` and earlier to add per-tenant loops — ruled out: already-applied revisions do not re-run, so this fixes only databases built from scratch, which are the ones that never had the problem.
- Reconcile at tenant-provisioning time only — ruled out: does nothing for tenants that already exist.

### Decision 7: Guard the fixture script on database name, with an explicit opt-in override

**Choice:** `scripts/setup_test_db.py` resolves the database name from the URL it will actually connect with and refuses anything not ending in `_test`, unless an opt-in environment variable is set.

**Rationale:** The script's default URL is already correct; the damage came from `NER_DATABASE_URL` overriding it. Checking the resolved name closes exactly that gap. The override keeps CI free to use a non-standard scratch database without weakening the default.

**Alternatives considered:**
- Remove the environment-variable override entirely — ruled out: CI and non-default ports legitimately need it.
- Interactive confirmation prompt — ruled out: the script runs unattended in CI.

## Risks / Trade-offs

- [Verification is too strict and blocks startup on benign differences, e.g. a developer's ad-hoc scratch table] → Compare only for presence of what the chain declares; do not fail on extra objects the chain does not know about.
- [Comparing tenant schemas against `tenant_template` is wrong if the template itself is drifted] → The template is checked against the chain first; a bad template fails verification before it can be used as a reference.
- [Hard-failing `db-init` makes the stack unstartable for someone mid-investigation on a deliberately odd database] → The failure message names the drifted objects and points at the documented clean-rebuild procedure, which is a one-command remedy for a disposable database.
- [The reconciliation migration walks every tenant schema and could be slow on a large tenant count] → Local dev has single-digit tenant counts; the loop is DDL-only with no table rewrites, and reconciliation is idempotent so a slow first run is not repeated.
- [Cloning a missing table from `tenant_template` via `LIKE` copies defaults, constraints, and indexes but not foreign keys] → Matches what `TenantService.create_tenant` and `seed.py` already do, so reconciliation produces the same shape provisioning does; no new inconsistency is introduced.
- [`src/shared/retrieval/` is untracked while the `chunking_service.py` deletion is staged, so a clean clone cannot build] → Tracking it is a task in this change and must land before the image rebuild.
- [The rebuild destroys the four fixture tenants that some manual dev workflow may quietly rely on] → Flagged in Open Questions; they are recreatable by running `setup_test_db.py` against `ner_test` where they belong.

## Migration Plan

1. Commit `src/shared/retrieval/` so the tree is self-consistent, and land the code fixes: dashboard enumeration, the `022` guard, the reconciliation migration, and the `setup_test_db.py` guard.
2. Add the verification step and wire it into `db-init` after `alembic upgrade head`.
3. `docker compose down -v` — this is the destructive step. It removes the `postgres-data` volume and every tenant, user, document, annotation, model version, and training run in it. Take a `pg_dump` first if anything in the current database is wanted for reference, since nothing is recoverable afterwards.
4. `docker compose build` to produce images carrying the full migration chain and `src/shared/retrieval`.
5. `docker compose up`. `db-init` applies the chain to an empty database, seeds, and runs verification.
6. Confirm `alembic_version` is at head, `tenant_template.documents` exists, `public.entity_definitions` has all declared columns, and `public.model_versions` is absent.
7. Exercise the three broken paths: create an entity type, create a tenant and upload a document to it, and load the `system_admin` dashboard with a clean log.

Rollback: there is no data to roll back to. If the rebuilt stack fails, the fallback is to revert the code changes and rebuild again — the database is reproducible from the chain by construction, which is the point of the change.

## Open Questions

- Should the reconciliation migration also run at tenant-provisioning time as a safety net, or is atomic template cloning sufficient? Leaning sufficient, given Decision 6 and the provisioning atomicity requirement.
- Do the four fixture tenants need to exist in `ner_dev` for any current manual workflow? Assumption: no, they belong in `ner_test`.
- Should verification also assert column *types*, not just presence? Every confirmed failure was presence-only. Starting with presence keeps false positives low; type checking can be added if a type-drift incident ever occurs.
- No in-force ADR appears to need revisiting for this change.
