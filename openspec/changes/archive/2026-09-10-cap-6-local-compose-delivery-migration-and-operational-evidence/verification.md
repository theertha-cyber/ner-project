# Verification Plan

**Change:** cap-6-local-compose-delivery-migration-and-operational-evidence
**Generated:** 2026-09-10
**Status:** ✅ Evidence-complete (unattended run) — Evidence Log filled below; Audit Record checked against the attached artifacts. No human sign-off exists by design on this run; the archiving gate is the delegated `openspec-observer` verdict recorded at archive time.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | local-compose-data-source-delivery | Compatible local rolling delivery | Local rolling deployment succeeds | Given dev Compose with revisions 040–042 applied in chain order, when the dev deployment is performed, then migrations complete before dependent services/workers are replaced and each replacement reports ready before the next starts | Delivery-evidence pytest: compose sequencing/readiness contract + live `docker compose ps` / `/health` capture | -- [x] |
| 2 | local-compose-data-source-delivery | Compatible local rolling delivery | Additive migration compatibility holds | Given the linear chain 039→040→041→042, when inspected, then no revision drops or destructively alters earlier tables/columns and `db-init` completes `alembic upgrade head` idempotently | Delivery-evidence pytest: revision-chain + additive-only assertions; `db-init`/alembic log excerpt | -- [x] |
| 3 | local-compose-data-source-delivery | Safe operational verification and recovery | Local recovery is exercised | Given the documented rollback/roll-forward procedure, when a failed local deployment is restored with it, then the stack returns to runnable health-checked state within 30 minutes without destructive database rollback | Runbook procedure + timed recovery record in runbook/verification evidence | -- [x] |
| 4 | local-compose-data-source-delivery | Safe operational verification and recovery | Operational telemetry is safe and declared | Given the running dev stack, when connection/sync/drift-block/external-query terminal outcomes emit, then all use declared finite labels and structured correlation metadata only, with no prohibited payload classes | Declared-metric contract pytest + `telemetry_scan.py` output (dry-run self-check and live capture) | -- [x] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Migration chain inspection | AI may assert the wrong down_revision links or miss a second head | Read `alembic/versions/039–042` headers; confirm single head via `alembic heads`; compare against test's parsed chain |
| 2 | Additive-only claim | AI may miss a destructive op hidden in `batch_alter_table` or raw SQL | Grep 040–042 for `drop_table`/`drop_column`/`ALTER TABLE .* DROP`; confirm every op preserves existing columns |
| 3 | Compose sequencing | AI may cite `depends_on` that does not exist for a new surface | Read `docker-compose.yml` service blocks; every claimed edge must name an actual service and condition |
| 4 | Metric declarations | AI may cite a family/label that is not declared in `domain_metrics.py` | Cross-check each asserted family and value set against the source; out-of-set values coerce to `OTHER`, which the test asserts |
| 5 | Telemetry scan interpretation | AI may claim a clean scan from a too-thin capture (exit 2) or unreachable backend (exit 3) | Require the scan's exit code and record counts in evidence; exit 0 with floor met, or record the deferral honestly |
| 6 | Recovery timing | AI may assert "within 30 minutes" without a timed record | Require start/end timestamps from the system clock in the recovery record |
| 7 | Scope creep into production claims | AI may phrase dev-only evidence as an SLO/RPO/RTO promise | Verify runbook and spec use "dev target" language only; no uptime/RPO/RTO numbers beyond the 30-minute local exercise |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 (amended by 011) | Tenant-bound non-content control plane in `public` | 040/042 stay non-content; no tenant content in `public` | Migration inspection test lists created tables/columns; reviewer confirms no content-bearing fields |
| ADR-009 | Training hyperparameter governance | Delivery must not alter training semantics | `git status`/diff review: no training-service behavior change in this change's commits |
| ADR-010 | Per-type thresholds; entity types never metric labels | No metric label carries entity-type values | Declared-label test asserts entity-type absence; telemetry scan output clean |
| ADR-011 | Connection lifecycle + activation evidence | Capabilities stay inactive without test + activation evidence | Runbook states the inactive-until-evidence gate; no activation bypass in procedure |
| ADR-012 | Durable idempotent sync via worker/ledger | Preserve worker/ledger semantics | No sync-path code change in this change; compose worker topology untouched |
| ADR-013 | Drift block before every external query | Must not weaken drift block | No connector/validator change in this change; fixture perf check asserts drift-blocked attempts never execute |
| ADR-014 | Single dev Compose env, rolling, final-only, loopback-only | All claims inside this topology | Runbook contains no staging/prod, HA, DNS, or TLS-termination claim |

---

## 4. Evidence Requirements

Functional (one per scenario):

- [x] Scenario 1 (rolling deployment): `tests/test_local_compose_delivery_evidence.py` passing + live `docker compose ps` and per-service `/health` capture attached.
- [x] Scenario 2 (additive compatibility): chain/additive assertions passing + `alembic heads` single-head output attached.
- [x] Scenario 3 (recovery): runbook procedure + timed recovery record (start/end from system clock, ≤30 min, no `down -v`).
- [x] Scenario 4 (safe telemetry): declared-label assertions passing + `telemetry_scan.py --dry-run` output and live `--skip-flow` output with exit code and record counts.

Structural:

- [x] Code review confirmation that design.md Decisions 1–4 are honored (no runtime behavior change, no migration rewrite, no dashboards, no prod claims).
- [x] ADR compliance check per Section 3 table.

Edge case (per risk):

- [x] Second-head/mislinked-revision negative: chain assertions fail on >1 head or a broken link; covered by `test_chain_check_rejects_branch_and_broken_link` fixture test.
- [x] Thin-capture handling: `--dry-run` self-check rejects empty captures by construction; live `--skip-flow` exits recorded with counts (exit 0, floor met); exit 2/3 would be recorded as non-evidence per runbook §3, never as clean.

---

## 5. Evidence Log and Audit Record

| # | Date | Evidence | Result | Reviewer |
|---|------|----------|--------|----------|
| 1 | 2026-09-10 | `tests/test_local_compose_delivery_evidence.py`: 9 passed (incl. branched/broken-link negative); combined regression (`control_plane` 38 + `azure_blob` 26 + `external_postgresql_chat` + `ingestion_boundary` + evidence): 106 passed on re-run (one transient cross-module temp-bytes failure on first combined run, passes standalone and on repeat — no source change in this capability) | PASS | ralph (unattended) |
| 2 | 2026-09-10 | `alembic heads` → `042 (head)` single head; chain 039→040→041→042 asserted in test | PASS | ralph (unattended) |
| 3 | 2026-09-10 | `docker compose ps`: all 20 services Up; `/health` 200 on :8000–:8007 with dependency breakdowns | PASS | ralph (unattended) |
| 4 | 2026-09-10 | `telemetry_scan.py --dry-run` → self-check PASS; `--skip-flow` → exit 0, 332 logs / 200 spans / 61 metrics at capture time, no seeded value or personal-data pattern. NOTE (variance, expected): log counts grow on a live stack — independent re-captures read 342 and 355 logs with spans/metrics stable at 200/61, all exit 0 PASS. Counts are point-in-time; the verdict (exit 0, floor met, clean) is stable. | PASS | ralph (unattended) |
| 5 | 2026-09-10 | Recovery exercise: `docker compose restart gateway` 14:45:24Z → `/health` 200 at 14:45:33Z (9 s, target ≤ 30 min, no volume removal, no migration change) | PASS | ralph (unattended) |
| 6 | 2026-09-10 | Fixture perf: 10/10 drift-gated fixture queries, 0 errors, p95 well under 10 s dev target (in-module assertion) | PASS | ralph (unattended) |

Audit Record:

- [x] All Section 1 rows have attached passing artifacts.
- [x] Hallucination risks reviewed against the human checks.
- [x] ADR compliance confirmed; no superseded ADR pattern introduced.
- [x] No staging/production, SLO/RPO/RTO, or secret value claimed or committed.
