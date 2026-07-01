## 1. Implementation

- [x] 1.1 In `src/portal/src/app/(auth)/training-jobs/page.tsx`, read the authenticated user's role via `useAuth` (already imported) and add a `const isTenantAdmin = user?.role === "tenant_admin"` constant
- [x] 1.2 Wrap the `+ Submit Job` button (lines ~65–71) in a conditional render: `{isTenantAdmin && <button ...>+ Submit Job</button>}`
- [x] 1.3 Wrap the `<SubmitJobSlideover>` render (line ~115) in the same guard: `{isTenantAdmin && <SubmitJobSlideover open={submitOpen} onClose={() => setSubmitOpen(false)} />}`
- [x] 1.4 Verify the `submitOpen` state and `setSubmitOpen` are still correctly scoped — they are harmless when not rendered but confirm no stale state issues

## 2. Verification — Scenario Tests

- [ ] 2.1 Manual check (tenant_admin): Log in as a tenant_admin user, navigate to `/training-jobs`, and confirm the `+ Submit Job` button is visible in the header (covers Spec Alignment row 1)
- [ ] 2.2 Manual check (system_admin): Log in as a system_admin user, navigate to `/training-jobs`, and confirm the `+ Submit Job` button is absent from the DOM (covers Spec Alignment row 2)
- [ ] 2.3 Manual check (slideover absent): While logged in as system_admin, inspect the DOM and confirm no `SubmitJobSlideover` component is mounted (covers Spec Alignment row 3)
- [ ] 2.4 Smoke check — approve/reject: Confirm the `JobActions` approve/reject buttons still render for system_admin on a selected job (regression check — Hallucination Risk 3)

## 3. Verification & Evidence

- [ ] 3.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 3.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 3.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 3.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 3.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [ ] 3.6 Run `openspec validate remove-submit-training-job-button --type change --strict` and confirm it exits clean before archive.
