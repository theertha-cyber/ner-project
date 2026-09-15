# QA Report -- tenant-self-service-data-sources-20260909-2

## Deployment Under Test
- Base URL: http://localhost:8000 (portal http://localhost:3000/)
- Environment: dev (single-environment ladder — lowest and highest non-production rung; this run carries `load: yes`)
- Target: docker-compose (local)
- Deployment record: `docs/deploy/tenant-self-service-data-sources-20260909-2-dev.md`
- Deployment health at landing: healthy (migrations 038–042 applied, seed + schema verification passed, 20/20 services Up, `/health` ok)

## Authentication
- Mode: seeded account
- Account: Tenant Admin `admin@democorp.io`, defined by the build in `src/gateway/seed.py` and quoted in the deployment record's `## Access` → `Sign in` row (values never appear in any report, log, or command line; the bearer token lived in memory only)
- Authenticated surface covered: yes (API list/bounds/404 probes + full axe scan of `/settings/data-sources` as tenant admin)

## Scope
- Commit range: `60db8d0^..4dd49e5` (73 files), HEAD `74fe6d4`; branch `external-tenant-data-sources`
- Components: CAP-2 control plane, CAP-3 Blob sync, CAP-4 external-PG chat, CAP-5 admin portal, CAP-6 delivery/migrations
- C4 containers: gateway, document/extraction/chat services, portal, Celery/RabbitMQ sync worker, platform Postgres/pgvector
- NFR authority: **technical design document + ADRs** (`docs/design/tenant-self-service-data-sources.md` NFR table; ADRs 011–014). No requirement-document fall-through was needed. WCAG 2.1 AA is this suite's documented default (requirement leaves accessibility open).
- Profile: full (smoke → load). Deep review: no — not requested (`code-quality.md` omitted by choice). Sanity: not applicable to a full-application pass (file omitted by choice). No supplied case list was used. Spec rewrites checked: 2 (CAP-2 scenario-header restore; CAP-4 ADDED→MODIFIED re-type) — both archive-guard mechanics, no requirement substance changed; held.
- Degradations applied (unattended run, `question` denied): missing-SLO → design NFRs used; unclear-scope → widest safe scope audited; unrepresentative-env → dev-box caveats recorded; contract-conflict → none found. Telemetry scan false-positive class (UUID fragments matching card/phone regexes) judged by shape, not assumed clean.

## Results By Test Type
| Test Type | Status | Report |
|---|---|---|
| Smoke | pass | [smoke.md](./smoke.md) |
| Sanity | not applicable to this run's scope | — |
| Regression | pass (no run-attributable regression; 49 pre-existing portal failures named) | [regression.md](./regression.md) |
| Integration | pass (2 deliberate live gaps covered by suites) | [integration.md](./integration.md) |
| Unit | pass (1 hardening recommendation) | [unit.md](./unit.md) |
| Security | pass (0 critical, 0 high; 2 medium + 2 low follow-ups) | [security.md](./security.md) |
| Performance | pass (p95 22 ms vs 10 s dev target) | [performance.md](./performance.md) |
| Load | pass at smoke+average (p95 57.5 ms, 0 failures); stress/soak not run | [load.md](./load.md) |
| Accessibility | **fail (2 serious violations on the new primary screen)** | [accessibility.md](./accessibility.md) |
| Demo & Fixture Hygiene | pass (clean) | [demo-fixture-hygiene.md](./demo-fixture-hygiene.md) |
| Code Quality | not requested | — |

## Evidence
- Combined visual dashboard: not applicable (non-Playwright evidence tree; screenshots per type)
- All run evidence: `qa/evidences/tenant-self-service-data-sources-20260909-2/` (axe.json, login.png, data-sources.png, axe-scan.mjs, k6-summary.json, k6-smoke-avg.js)
- Cases run: [test-cases.csv](./test-cases.csv)

## UI Fidelity (ui-ux-governor, mode: verify, against `docs/design/ui-contract.md`)
P0 lint clean across all new data-sources scope; `globals.css` token-file import intact as first rule; safe-shape holds structurally (client types cannot hold secret values; errors render code + request id only); state coverage complete on list/detail with one minor gap (contract history shows its empty state while still loading); accessibility baseline statically passes (labelled controls, text-backed badges, alert/status roles, focus trap + restore, visible focus rings); animation audit **Approve** with findings (no `prefers-reduced-motion` guard anywhere; 350 ms entrance exceeds the 300 ms budget); token use clean except five `#fff` on-primary literals worth promoting into a token. Visual screenshot comparison by the agent was blocked (no browser tool in its context) — this run captured the screenshots itself (see evidence) and the rendered Data Sources page matches the contract: labelled filters, safe empty state, recovery action, sidebar entry.

## Release Gate
- Decision: **fail**
- Blocking issues (already live on dev, http://localhost:8000 + http://localhost:3000):
  - A11Y-01: serious color-contrast violation on the Data Sources screen — sidebar user-badge role caption at `color: var(--ink-3)` (`#94a3b8`, ~2.9:1) in 10 px text, below the 4.5:1 baseline minimum (`src/portal/src/components/app-shell/Sidebar.tsx` via `tokens.css:40`).
  - A11Y-02: serious missing document title — root layout exports no `<title>`/metadata (`src/portal/src/app/layout.tsx`), failing every page including `/settings/data-sources`.
- Conditional approvals: none (a `fail` carries no conditional approvals; gaps below are follow-up work)

## Follow-Up Work
| Item | Owner | Priority | Required Before |
|---|---|---|---|
| Fix A11Y-01: raise small-text caption to a ≥4.5:1 token (or add an on-primary/ink token) | Portal | blocking | re-gate |
| Fix A11Y-02: export `metadata.title` (and landmark/region naming) from root layout | Portal | blocking | re-gate |
| Add `prefers-reduced-motion` guard; bring entrance ≤300 ms; promote 5× `#fff` literals to a token | Portal | normal | next release |
| Contract-history loading skeleton (empty state flashes before data arrives) | Portal | low | next release |
| SEC-001 (medium): gate connection `test` on network evidence; constrain PG host; rate-limit; unify failure signals | Security/Backend | high | next release |
| SEC-002 (medium): validator default-deny on `*`/unresolvable columns + negative tests | Backend | high | before external-PG chat is wired to any caller |
| SEC-003/SEC-004 (low): locking-clause + literal + OFFSET hardening; body-size cap on contract upload | Backend | normal | next release |
| Fix 49 pre-existing portal test failures (stale counts/text, incl. `business_user` nav count) | Portal | normal | next release |
| Tune `telemetry_scan.py` UUID-fragment false positives; re-run `--skip-flow` to green | Security/Ops | normal | next release |
| Dependency CVE reachability undetermined here (no scanners/lockfile) — run pip-audit/npm audit in CI | Security | normal | next release |
| Stress/soak not measured (small dev box) — measure on a production-sized rung before any shared environment | QA/Ops | normal | staging gate |
| Live second-tenant isolation probe + write-path lifecycle exercise (deliberately skipped to avoid demo pollution) | QA | low | staging gate |
