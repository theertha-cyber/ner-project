## 1. Fix Chat Page Authentication

- [x] 1.1 Add `import { authFetch } from "@/lib/auth-fetch"` to imports in `src/portal/src/app/(auth)/chat/page.tsx`
- [x] 1.2 Replace `fetch(CHAT_API_BASE + "/conversations", { credentials: "include" })` with `authFetch(CHAT_API_BASE + "/conversations")` in `loadConversations`
- [x] 1.3 Replace `fetch(CHAT_API_BASE + "/conversations/" + convId, { credentials: "include" })` with `authFetch(CHAT_API_BASE + "/conversations/" + convId)` in `loadMessages`
- [x] 1.4 Replace `fetch(CHAT_API_BASE + "/conversations/" + convId, { method: "DELETE", credentials: "include" })` with `authFetch(CHAT_API_BASE + "/conversations/" + convId, { method: "DELETE" })` in `handleDeleteConversation`
- [x] 1.5 Replace `fetch(CHAT_API_BASE, { method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include", body: ... })` with `authFetch(CHAT_API_BASE, { method: "POST", headers: { "Content-Type": "application/json" }, body: ... })` in `handleSendMessage`

## 2. Verification & Evidence

- [x] 2.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 2.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 2.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 2.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 2.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 2.6 Run `openspec validate fix-chat-page-auth --type change --strict` and confirm it exits clean before archive.
