## 1. Router: Fix Prefix and Route Parameters

- [x] 1.1 In `src/gateway/api/v1/entity_types.py`, change router prefix from `/api/v1/entity-types` to `/api/v1/tenants/{tenant_slug}/entity-types` — add `tenant_slug: str` as a path parameter on the router (or per route if FastAPI requires it at route level)
- [x] 1.2 Rename path parameter `entity_id: str` → `name: str` on the `GET /{entity_id}`, `PUT /{entity_id}`, and `DELETE /{entity_id}` route handlers; update all `service.*` calls to pass `name` instead of `entity_id`
- [x] 1.3 Add `PATCH /{name}` route handler that accepts `payload: dict` and calls `service.toggle_entity_type(tenant_id, name, payload["is_active"])` — return the result with status 200

## 2. Service: Add toggle_entity_type and _get_by_name

- [x] 2.1 In `src/gateway/services/entity_service.py`, add `_get_by_name(self, tenant_id: str, name: str) -> dict | None` that queries `WHERE name = :name AND tenant_id = :tid` and returns the flat `_row_to_dict` result (or `None` if not found)
- [x] 2.2 Add `toggle_entity_type(self, tenant_id: str, name: str, is_active: bool) -> dict` that: looks up by name, raises `NotFoundError` if missing, executes `UPDATE ... SET is_active = :active WHERE name = :name AND tenant_id = :tid`, commits, and returns the updated flat entity via `_get_by_name`
- [x] 2.3 Update `create_entity_type` to return `await self._get_by_name(tenant_id, payload["name"])` (flat dict) instead of the `{"entity_type": ...}` wrapped result from `_get_by_id`
- [x] 2.4 Update `update_entity_type` to accept `name: str` (not `entity_id`), look up via `_get_by_name`, update WHERE `name = :name AND tenant_id = :tid`, and return the flat result from `_get_by_name`
- [x] 2.5 Update `get_entity_type` and `soft_delete_entity_type` to accept `name: str`, look up via `_get_by_name`, and operate by name — remove all `entity_id`/UUID usage from the public service API
- [x] 2.6 Remove `_get_by_id` (UUID lookup) since it is no longer used after the above changes — or keep it private with a clear comment if any internal usage remains

## 3. Service: Fix JSON Deserialization in _row_to_dict

- [x] 3.1 In `_row_to_dict`, add `json.loads()` for the `examples` field with a guard: `json.loads(r.examples) if isinstance(r.examples, str) else (r.examples or [])` — covers None and already-parsed values
- [x] 3.2 In `_row_to_dict`, add `json.loads()` for the `base_label_mapping` field with the same guard pattern: `json.loads(r.base_label_mapping) if isinstance(r.base_label_mapping, str) else (r.base_label_mapping or {})` — covers None and already-parsed values

## 4. Verification

- [ ] 4.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 4.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 4.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 4.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 4.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [ ] 4.6 Run `openspec validate fix-entity-types-api-alignment --type change --strict` and confirm it exits clean before archive.
