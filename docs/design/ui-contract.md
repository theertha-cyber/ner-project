# UI Design Contract — Tenant Self-Service Data Sources

## Source
Generated mockups refreshed after the approved CAP-2 tenant-scoped connection-control-plane API design update. The human reconfirmed the existing generated direction: **Clean structural foundation with existing portal override**. No new assets or external reference source is in scope.

## Codebase Discovery Findings

- Tenant-admin entry point is new: the sidebar renders only role-derived links from `navFor` (`src/portal/src/lib/nav-config.ts:27-60`; `src/portal/src/components/app-shell/Sidebar.tsx:35,117-124`), and the `tenant_admin` set (`src/portal/src/lib/nav-config.ts:36-47`) exposes document upload but no `/settings/data-sources` route. The list/detail bindings therefore add navigation without altering current routes.
- List binding (`GET /api/v1/data-sources` with allowlisted `q/provider/status/sort/order/page/page_size`) has no existing portal caller: current intake is browser-file multipart upload to `POST /api/v1/documents` normalized as human-originated `platform_upload` (`src/portal/src/hooks/use-upload.ts:16-70`; `src/document_service/api/v1/documents.py:64-109`). The new collection controls (20 per page, `last_activity` desc with ascending `id` tie-breaker, page-1 reset, out-of-range empty page, unknown-field rejection) do not replace that workflow.
- Detail safe-shape binding reflects the existing control-plane boundary: integration profiles are tenant-bound records but the current service explicitly prohibits tenant-admin create, edit, activate, and retire actions (`src/shared/integration_profile/store.py:21-65`; `src/shared/integration_profile/service.py:1-5`). The contract therefore binds only safe `Connection` display (provider/status/field names/finite outcome classes/schedule links/timestamps) and never values, secrets, endpoint details, connection strings, diagnostics, SQL, prompts, answers, or tenant content.
- Provider closed-schema and prerequisite bindings match declared-but-not-executable shapes: Azure Blob is a declared configuration shape while only platform-default adapters are executable and activation rejects non-executable selections (`src/shared/integration_profile/adapters.py:11-28,38-44`; `src/shared/integration_profile/service.py:161-175`). The Blob/PostgreSQL field sets, write-only values, `sslmode: verify-full`, secure-test plus `network_approved`/`governance_approved` attestations, `Idempotency-Key` mutations, and finite error codes are additions, not current behaviour. No tenant-facing source-management UI was found.
- Safe-outcome display binding matches existing SQL/chat containment: chat SQL is tenant-schema scoped, read-only, relation/column-whitelisted, and time-limited (`src/chat_api/services/sql_generator.py:1107-1144,1146-1219`; `src/chat_api/api/v1/chat.py:183-194`). Test/activation/sync outcomes therefore bind to finite classes with reason codes and request ID only. Theme wiring for these screens is valid: `src/portal/src/app/globals.css:1` imports `src/portal/design-system/ner-portal/tokens.css` as its first rule.

## Design System
- Style: Clean — existing portal override
- Platform: web
- Tokens: src/portal/design-system/ner-portal/tokens.css
- Theme Entry Point: src/portal/src/app/globals.css

Clean remains the structural base for compact enterprise administration: 8px-radius surfaces, restrained borders, and a clear table/form rhythm. It remains preferable to Bento (larger card-led density), Bold (marketing-led emphasis), and Editorial (serif content hierarchy). Existing portal colour, typography, light/dark, and logo treatments override the package defaults. Theme wiring is valid: `globals.css` imports the token file as its first rule.

## API-to-UI Contract
- The list view uses `GET /api/v1/data-sources` only with `q` (1–100 chars), `provider`, `status`, `sort` (`last_activity|created_at|provider|status`), `order` (`asc|desc`), `page` (>=1), and `page_size` (1–100). It defaults to `last_activity` descending with ascending `id` tie-breaker, page 1, and 20 items; search or filters reset to page 1; an out-of-range valid page is an empty list. Unknown query fields are rejected.
- The detail view represents only the safe `Connection` response shape: provider, status (`draft|validated|active|paused|error|retired`), configured field names, secret-reference field names, finite test/activation/sync outcome classes with reason codes, schedule (Blob only; PostgreSQL schedule disabled with `last_sync` omitted), replacement links, and timestamps. It never presents configuration values, secret-reference values, endpoint details, connection strings, provider diagnostics, SQL, prompts, answers, or tenant content.
- Create, update, test, activate, pause, replace, and retire are distinct actions. All mutation actions require an `Idempotency-Key` (1–128 printable ASCII, scoped to tenant/method/path/body digest, 24-hour replay); the UI treats an idempotent replay (`Idempotent-Replay: true`) as the returned safe result, surfaces `409 IDEMPOTENCY_KEY_REUSED` on key/body mismatch and `400 IDEMPOTENCY_KEY_REQUIRED` when missing, and renders finite safe error codes (`UNAUTHENTICATED`, `FORBIDDEN`, `CONNECTION_NOT_FOUND`, `INVALID_REQUEST`, `INVALID_LIFECYCLE_TRANSITION`, `TEST_REQUIRED`, `TEST_FAILED`, `ACTIVATION_PREREQUISITE_MISSING`, `ACTIVE_PROVIDER_EXISTS`, `RETIRED_CONNECTION`, `RETIRE_CONFIRMATION_REQUIRED`, `CONNECTION_TEST_UNAVAILABLE`, `INTERNAL_ERROR`) with the supplied request ID.
- The configuration form is provider-specific and closed-schema. Azure Blob requires account and container, permits prefix, and names `connection_string_ref`; Azure PostgreSQL requires host, database, username, port, `sslmode: verify-full`, and names `password_ref`. Values are write-only and absent after save.
- Activation is available only after a passed secure test and both finite attestations: `network_approved` and `governance_approved`. A same-provider incumbent produces a safe active-provider-exists block. Retirement requires explicit confirmation and an active connection must be paused first.

## Assets
None supplied.

## Craft Bindings
- `anti-ai-slop` — prevents generic dashboard patterns, filler copy, default-indigo styling, emoji icons, and invented metrics.
- `accessibility-baseline` — establishes semantic labels, contrast, visible focus, keyboard access, and focus order.
- `state-coverage` — requires loading, empty, filtered-empty, error, partial, and blocked states for control-plane data.
- `animation-discipline` — limits motion and requires reduced-motion support.
- `form-validation` — provider configuration, activation evidence, and schema-contract upload require inline validation and safe recovery.
- `typography` and `typography-hierarchy` — retain the existing portal information hierarchy across administration screens.
- `laws-of-ux` — governs the security-sensitive lifecycle and destructive confirmations.

## Implementation Notes
This is a responsive, desktop-primary authenticated tenant-admin flow using the existing portal app shell and light/dark mode. Browser history, deep links, and Back apply. No RTL locale is named, so `rtl-and-bidi` is not bound. Schema-contract management remains the approved PostgreSQL companion flow; CAP-2 itself does not add its API routes.

## Revision History

- 2026-09-10 (redo after wind-back): Re-saved with approved CAP-2 API-to-UI bindings retained; Clean structural foundation with existing portal override unchanged. Re-saved so the Design-gate artifact postdates the 2026-09-10 wind-back.
- 2026-09-10 (re-save after rewritten CAP-2 contract): Rewritten TDD `docs/design/tenant-self-service-data-sources.md` re-verified (normative authority: CAP-2 OpenSpec delta). Platform `web` (Next.js/React in `src/portal`), tokens `src/portal/design-system/ner-portal/tokens.css`, and Theme Entry Point wiring (`globals.css` imports the token file as its first rule) confirmed intact. API-to-UI bindings tightened to the rewritten contract only: list bounds/tie-breaker/out-of-range rule, safe-shape status enum and PostgreSQL schedule omission, idempotency scope with replay/reuse codes, and the finite error-code set. Clean existing-portal override, no-asset scope, and craft bindings unchanged. No functionality implemented.
