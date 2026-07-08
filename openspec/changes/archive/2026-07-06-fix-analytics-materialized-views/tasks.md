## 1. Alembic Migration

- [x] 1.1 Create migration `015` (revises `014`) with a PL/pgSQL block that iterates all `tenant_*` schemas (excluding `tenant_template`) and creates the four materialized views using `CREATE MATERIALIZED VIEW IF NOT EXISTS` and their unique indexes using the same SQL definitions from migration `011`
- [x] 1.2 Add a post-creation `REFRESH MATERIALIZED VIEW CONCURRENTLY` for each view in the migration so existing data is populated immediately
- [x] 1.3 Run `alembic upgrade head` and confirm it completes without error and creates MVs in `tenant_demo_tenant` (or any other existing tenant schema)
- [x] 1.4 Run `alembic upgrade head` a second time and confirm it is idempotent (no error, no duplicate data)

## 2. Seed Script Update

- [x] 2.1 Add the four `CREATE MATERIALIZED VIEW IF NOT EXISTS` statements to `src/gateway/seed.py` after the tenant schema tables are created, using the same SQL definitions as migration `011`
- [x] 2.2 Add unique index creation and `REFRESH MATERIALIZED VIEW CONCURRENTLY` after each MV is created in seed.py
- [x] 2.3 Re-run the seed (via `db-init` or directly) and confirm MVs exist in `tenant_demo_tenant` with populated data
- [x] 2.4 Re-run the seed a second time and confirm idempotency

## 3. Verification & Evidence

- [ ] 3.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 3.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 3.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 3.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 3.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [ ] 3.6 Run `openspec validate fix-analytics-materialized-views --type change --strict` and confirm it exits clean before archive.
