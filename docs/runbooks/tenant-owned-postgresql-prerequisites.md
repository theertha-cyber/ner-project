# Tenant-Owned PostgreSQL Data Plane — Customer Prerequisites Runbook

Scope: what a customer (or the operator configuring on their behalf) must have
ready on their own Azure Database for PostgreSQL — Flexible Server before a
`tenant_owned` tenant's data-plane connection can be tested, activated, and
provisioned (ADR-017). Nothing here is optional unless explicitly marked.

## 1. Server

- **PostgreSQL 16 or newer.** The secure tester checks `server_version_num`
  before anything else and fails closed with `server_version_unsupported`
  below 16.0 — this is not negotiable at activation time, only correctable by
  upgrading the server.
- **Azure Database for PostgreSQL — Flexible Server.** Single Server is not
  supported (no path to the extensions or private networking this requires).

## 2. The `vector` extension

The tenant's data lives in a schema with pgvector-backed chunk embeddings —
`CREATE EXTENSION vector` runs during provisioning, but the extension must be
**allow-listed** on the server first:

- Azure Portal → the Flexible Server resource → **Server Parameters** →
  `azure.extensions` → add `VECTOR` → Save (this restarts the server).
- Confirm: `SHOW azure.extensions;` includes `VECTOR`, or
  `SELECT * FROM pg_available_extensions WHERE name = 'vector';` returns a row.

The secure tester checks both `azure.extensions` and
`pg_available_extensions` (self-hosted servers have no `azure.extensions`
setting) and fails closed with `vector_extension_unavailable` if neither shows
it. This is the most common activation blocker in practice — verify it before
anything else.

## 3. A dedicated database

Provision (or designate) one database on the server for this tenant alone.
Do not point a `tenant_owned` connection at a database any other system
writes to:

- Provisioning refuses to touch a schema that already contains tables it
  didn't create (`target_schema_not_empty`) — this protects against
  collision, but a dedicated database avoids the question entirely.
- The platform's own generated schema is named `tenant_<tenant id>` inside
  whatever database the connection points at; nothing outside that schema is
  touched or read.

## 4. A login role for the platform's connection

Create a role the platform's own workers and API processes will connect as:

```sql
CREATE ROLE ner_platform WITH LOGIN PASSWORD '<generated, not this literal>';
GRANT CREATE, CONNECT ON DATABASE <the dedicated database> TO ner_platform;
```

This is the role whose password becomes the connection's `password_ref`
secret — provide it as a resolvable reference (`env://...` in this
deployment's resolver), never as a literal value in configuration.

**Required privilege: `CREATE` on the database**, so the platform can create
its `tenant_<id>` schema and the tables inside it at provisioning time. The
secure tester checks `has_database_privilege(current_user, current_database(),
'CREATE')` and fails closed with `insufficient_privilege` if it's missing.

**Also required on Azure Flexible Server: `azure_pg_admin` membership.**
Allow-listing `vector` in `azure.extensions` (step 2) is not sufficient by
itself — Azure treats `vector` as an "untrusted" extension, and `CREATE
EXTENSION vector` fails with `InsufficientPrivilege` for any role that isn't a
member of `azure_pg_admin`, even with `CREATE` on the database. Grant it
alongside the role creation in step 4:
```sql
GRANT azure_pg_admin TO ner_platform;
```
This is a real gap the secure tester does not currently catch ahead of
provisioning (`_schema_create_privilege`/`_vector_extension_available` check
allow-listing and `CREATE`, not `azure_pg_admin` membership) — provisioning
itself fails with `store_unreachable` if it's missing, discovered only at the
`CREATE EXTENSION` step.

## 5. The query role — two supported paths

The platform provisions a `NOLOGIN` role (`ner_chat_sql` by default) that chat
SQL generation runs under via `SET LOCAL ROLE`, scoped read-only to the
tenant's own generated tables. Pick one:

- **Preferred — grant `CREATEROLE`** to the login role from step 4, so
  provisioning creates the query role itself:
  ```sql
  ALTER ROLE ner_platform CREATEROLE;
  ```
- **Fallback — pre-create the role yourself**, if your policy refuses
  `CREATEROLE` to an external connection:
  ```sql
  CREATE ROLE ner_chat_sql NOLOGIN NOINHERIT;
  ```
  Provisioning detects an existing role by this name and grants against it
  without trying to create it.

The secure tester checks for either `rolcreaterole`/`rolsuper` on the login
role or a pre-existing role matching the configured name, and fails closed
with `query_role_unavailable` if neither is true.

## 6. Network reachability

The platform's workers and API processes must reach the server on its
PostgreSQL port from wherever this deployment runs them. Two supported
shapes, in order of preference:

- **Private networking** — Azure Private Endpoint (Flexible Server's private
  access networking mode) into the platform's VNet, or VNet peering. No
  traffic crosses the public internet.
- **Public access with an egress allowlist** — Flexible Server's firewall
  rules restricted to the platform's known egress IP ranges. TLS is required
  either way (the connection validates as `sslmode=verify-full`); this shape
  is acceptable but strictly weaker than private networking, and should be a
  documented exception, not the default.

A connection test that cannot open a TCP/TLS session to the configured host
and port fails closed with `connection_failed` (or `tls_validation_failed` for
a certificate problem) — that failure alone does not distinguish "wrong
network path" from "wrong host/port typo"; check both.

## 7. What happens if a prerequisite is missing later, not at setup

None of these checks are one-time. A server downgraded below 16, an extension
removed from the allow-list, a login role losing its `CREATE` grant, or a
network path closing after the tenant is already `ready` all surface the same
way: the next resolver call or periodic health probe records `unreachable`,
`auth_failed`, or `timeout` (never a driver message or the credential itself),
content routes for that tenant alone return 503
`TENANT_DATA_PLANE_UNAVAILABLE`, and every other tenant — platform-hosted or
otherwise — is unaffected. Restoring the prerequisite is sufficient; no
platform-side action reprovisions anything.
