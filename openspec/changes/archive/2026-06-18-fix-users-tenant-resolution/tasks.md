## 1. Router Update

- [x] 1.1 In `src/gateway/api/v1/users.py`, change the router prefix from `/api/v1/tenants/{tenant_id}/users` to `/api/v1/users`
- [x] 1.2 Update the import line — add `resolve_tenant_from_jwt` and remove `resolve_tenant` from the import of `src.gateway.dependencies`
- [x] 1.3 Replace `Depends(resolve_tenant)` with `Depends(resolve_tenant_from_jwt)` in all five endpoint function signatures (`create_user`, `list_users`, `get_user`, `update_user`, `delete_user`)
- [x] 1.4 Rename the injected parameter from `resolved_tenant_id` to `tenant_id` (or keep the name — ensure it is passed correctly to the service call)

## 2. Smoke Test

- [x] 2.1 Restart the gateway service and confirm Swagger UI at `/docs` shows the users endpoints under `/api/v1/users` with no `{tenant_id}` path parameter
- [x] 2.2 In Swagger UI, authenticate with a tenant admin Bearer token and POST `/api/v1/users` — confirm 201 response (verifies Scenario 1 — update verification.md row 1 Verification Artifact: "Swagger UI manual test")
- [x] 2.3 GET `/api/v1/users` — confirm 200 with user list (Scenario 2 — verification.md row 2)
- [x] 2.4 GET `/api/v1/users/{user_id}` — confirm 200 with user fields (Scenario 3 — verification.md row 3)
- [x] 2.5 PUT `/api/v1/users/{user_id}` with role change — confirm 200 with updated role (Scenario 4 — verification.md row 4)
- [x] 2.6 DELETE `/api/v1/users/{user_id}` — confirm 200 and status "inactive" (Scenario 5 — verification.md row 5)
- [x] 2.7 Repeat POST `/api/v1/users` with an annotator token — confirm 403 (Scenario 6 — verification.md row 6)
- [x] 2.8 Repeat POST `/api/v1/users` with no Authorization header — confirm 401 (Scenario 7 — verification.md row 7)

## 3. Spec Update

- [x] 3.1 Update `openspec/specs/tenant-user-mgmt/spec.md` to replace the old URL pattern (`/api/v1/tenants/{slug}/users`) with the new one (`/api/v1/users`) — sync from the delta spec in this change

## 4. Verification & Evidence

- [x] 4.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 4.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 4.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 4.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [x] 4.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 4.6 Run `openspec validate fix-users-tenant-resolution --type change --strict` and confirm it exits clean before archive.
