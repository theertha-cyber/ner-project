## 1. Chat API Routes — Remove `{tid}`

- [x] 1.1 In `src/chat_api/api/v1/chat.py`, change router prefix from `/api/v1/tenants/{tid}/chat` to `/api/v1/chat`
- [x] 1.2 In all 4 chat handlers (`chat`, `list_conversations`, `get_conversation`, `delete_conversation`), remove the `tid: str` function parameter from each signature
- [x] 1.3 In `chat()` handler, remove the `if tenant_id != tid` mismatch check (keep the `if not tenant_id` guard)
- [x] 1.4 In `list_conversations`, `get_conversation`, `delete_conversation`, remove any remaining `tid` parameter usage (none exist beyond the signature and mismatch check — confirm by inspection)
- [x] 1.5 In `src/chat_api/api/v1/widget_keys.py`, change router prefix from `/api/v1/tenants/{tid}/widget-keys` to `/api/v1/widget-keys`
- [x] 1.6 In all 3 widget-key handlers (`create_widget_key`, `list_widget_keys`, `revoke_widget_key`), remove the `tid: str` parameter from each signature
- [x] 1.7 In `create_widget_key`, remove the `if tenant_id != tid` mismatch check (keep `if not tenant_id` guard)

## 2. Gateway Proxy — Update Routes

- [x] 2.1 In `src/gateway/api/v1/chat_proxy.py`, update all 7 proxy route paths to remove `{tid}`:
  - `POST /tenants/{tid}/chat` → `POST /chat`
  - `GET /tenants/{tid}/chat/conversations` → `GET /chat/conversations`
  - `GET /tenants/{tid}/chat/conversations/{conv_id}` → `GET /chat/conversations/{conv_id}`
  - `DELETE /tenants/{tid}/chat/conversations/{conv_id}` → `DELETE /chat/conversations/{conv_id}`
  - `POST /tenants/{tid}/widget-keys` → `POST /widget-keys`
  - `GET /tenants/{tid}/widget-keys` → `GET /widget-keys`
  - `DELETE /tenants/{tid}/widget-keys/{key_id}` → `DELETE /widget-keys/{key_id}`
- [x] 2.2 Remove `tid: str` parameter from each proxy handler signature
- [x] 2.3 Update the internal forwarded URLs in `_proxy()` calls to match new chat service paths (remove `tenants/{tid}` segment)

## 3. Spec Sync

- [x] 3.1 Sync delta spec to main spec: update `openspec/specs/chat-api/spec.md` to reflect the new URL paths (remove `{tid}` from all scenario URL references)
- [x] *(Additional)* Update `openspec/specs/embeddable-widget/spec.md` — `{tid}` references in widget-keys scenarios
- [x] *(Additional)* Update `src/portal/src/app/(auth)/chat/page.tsx` — hardcoded `CHAT_API_BASE` URL constant

## 4. Verification & Evidence

- [ ] 4.1 Run acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass
- [ ] 4.2 Collect functional evidence (test output / log) for each scenario — one entry per row in verification.md § Evidence Log
- [ ] 4.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register
- [ ] 4.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance
- [ ] 4.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required)
- [ ] 4.6 Run `openspec validate tenant-from-jwt-in-chat-api --type change --strict` and confirm it exits clean before archive
