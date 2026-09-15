# Security -- tenant-self-service-data-sources-20260909-2

Scope: change set `60db8d0^..4dd49e5` (74 files audited) plus the live dev surface http://localhost:8000 + http://localhost:3000. Adversarial pass by `security-auditor` (mandatory, unconditional) folded in below verbatim in substance; severities unchanged. Environment dev: observe-only, no exploitation. No `.env` or secret material opened; no credential values appear in this file.

## Findings

| Finding | Severity | Entry Point | Evidence | Exploitability | Remediation |
|---|---|---|---|---|---|
| SEC-001 — pre-activation connection test dials arbitrary host:port (SSRF oracle: passed vs connection_failed vs tls_validation_failed) | medium | `POST /api/v1/data-sources` (`azure_postgresql` host/port) then `POST …/{id}/test` via `service.py:test_connection` → `testing.py:75 socket.create_connection` | `src/shared/data_sources/testing.py:66-88`; route live in `/openapi.json`; requires tenant-admin JWT; no data/credentials returned | reachable by design, bounded to authenticated tenant admins | gate `test` on `network_approved` evidence; constrain host to Azure/public names or egress proxy; per-tenant rate limit; unify failure signals |
| SEC-002 — validator accepts `SELECT *` / `alias.*` / unresolvable columns, defeating contract column allowlist | medium | future `statement` input to `execute_external_query` (today only `external_chat_answer`, which has **no callers** — dead code as deployed) | `src/shared/external_postgres/validator.py:285-316` | not reachable as deployed; blast radius when wired is the tenant's own external DB (server-side per-tenant resolution holds) | default-deny bare `*`; expand `alias.*` against contract columns; reject unresolvable qualifiers; add negative tests |
| SEC-003 — validator gaps: `FOR UPDATE/SHARE` not rejected; dollar-quoted literals bypass literal scan; unbounded `OFFSET` | low | same future entry as SEC-002 | same file, lines 139-142 + `clamp_limit` | not reachable as deployed | reject locking clauses; normalize/reject dollar-quoting; cap `OFFSET` |
| SEC-004 — contract upload parses unbounded JSON body before validation (transient worker memory/CPU) | low | `POST …/{id}/contracts` via `external_pg_contracts.py:98-104` (`await request.body()` + `json.loads`, no cap); requires tenant-admin JWT | code inspection; route live | reachable by inspection, transient availability only | route/global body-size limit (e.g. 64–256 KB) returning 413 before parsing |

## What passed

- Baseline `auth-check-required`: every new route declares `require_tenant_admin` + `resolve_tenant_from_jwt`; single-record access constrains `(id, tenant_id)` → cross-tenant ids yield 404 with no metadata. Live: unauthenticated list → 401; malformed JWT → 401.
- Baseline `parameterized-queries-only`: all new SQL binds values; sort uses `SORT_COLUMNS` allowlist; LIMIT/OFFSET are bound params; schema interpolations are constants or alnum-gated.
- Baseline `no-hardcoded-secrets` / `secrets-redacted-in-logs-and-traces`: diff-wide pattern scan found credential-shaped content nowhere (field names only); secret grammar restricts schemes so inline credentials are rejected as references; responses carry field names only; new logs/metrics carry finite classes and ids — no SQL, prompts, rows, endpoints, or values. Live list body confirms: names/outcomes only.
- Live safe-shape probe: `page_size=200` → 422, unknown param → 422, bad UUID → 404, unauth → 401 — all finite codes with request ids, no stacks.
- Threat models: ADR-011 and ADR-013 carry STRIDE tables (baseline `threat-model-required-for-new-external-boundaries` satisfied; ADR-012/014 reasonably carry none).

## Gaps (honest, non-blocking)

- Dependency CVE reachability **undetermined**: no `pip-audit`/`osv-scanner`/`gitleaks`/`semgrep` in this environment and no portal lockfile for `npm audit`. Not assumed clean.
- Live cross-tenant 404 and contract-publish index isolation confirmed by tests, not re-proven live (needs two tenant JWTs / active connection).
- Pre-existing surface (outside change set, noted not counted): unauthenticated `/docs`, `/openapi.json`, `/metrics`; no security headers (consistent with declared dev-loopback posture, must change before any shared environment); no gateway rate limiting; `minio/minio:latest` mutable tag.

## Decision

**0 critical, 0 high — non-blocking.** No finding meets the `fail` bar. SEC-001/SEC-002 are medium follow-ups with exact remediations; SEC-003/SEC-004 are low.
