## 1. Types

- [x] 1.1 Create `src/portal/src/types/model-registry.ts` — export `ModelVersion` interface with fields: `version_number: number`, `status: "training" | "completed" | "promoted" | "archived"`, `training_job_id: string`, `created_at: string`, `metrics: ModelMetrics | null`, `mlflow_run_id: string | null`, `mlflow_run_url: string | null`, `artifact_path: string | null`
- [x] 1.2 Export `ModelMetrics` interface: `{ eval_f1: number, eval_precision: number, eval_recall: number, eval_loss: number }` with optional per-entity keys
- [x] 1.3 Export `ModelVersionListResponse` and `ActiveModelResponse` interfaces

## 2. API Hooks

- [x] 2.1 Create `src/portal/src/hooks/use-model-versions.ts` — `useModelVersions()` using `useQuery`, queryKey `["models", tenantSlug]`, fetching `GET /api/v1/models` via `authFetch`; also fetches `GET /api/v1/models/active` as a separate query with key `["models", "active", tenantSlug]`; tenantSlug obtained from `useAuth()` (verification: unit test confirming URLs and query keys — covers scenarios 20, 21)
- [x] 2.2 Create `src/portal/src/hooks/use-promote-model.ts` — `usePromoteModel()` using `useMutation`, POSTing to `/api/v1/models/{id}/promote`, invalidating `["models", tenantSlug]` and `["models", "active", tenantSlug]` on success (covers scenario 12)
- [x] 2.3 Create `src/portal/src/hooks/use-demote-model.ts` — `useDemoteModel()` using `useMutation`, POSTing to `/api/v1/models/{id}/demote`, invalidating `["models", tenantSlug]` and `["models", "active", tenantSlug]` on success (covers scenario 16)
- [x] 2.4 Create `src/portal/src/hooks/use-warmup-model.ts` — `useWarmupModel()` using `useMutation`, POSTing to `/api/v1/models/{id}/warmup`, invalidating `["models", tenantSlug]` on success (covers scenario 18)
- [x] 2.5 Export all four hooks from `src/portal/src/hooks/index.ts`

## 3. ModelVersionCard Component

- [x] 3.1 Create `src/portal/src/components/model-registry/ModelVersionCard.tsx` — props: `model: ModelVersion`, `isActive: boolean`, `isSelected: boolean`, `onSelect: () => void`; render version number label (e.g. "v3"), status badge with appropriate color (promoted=primary, completed=good, archived=neutral, training=warn), F1 score or "—" when null, formatted creation date; apply selected highlight state (covers scenarios 4, 5, 6)
- [x] 3.2 Write `src/portal/src/components/model-registry/ModelVersionCard.test.tsx` — render tests for all status badges, F1 display, promoted distinct styling, training pending indicator

## 4. ModelDetailPanel Component

- [x] 4.1 Create `src/portal/src/components/model-registry/ModelDetailPanel.tsx` — props: `model: ModelVersion | null`, `role: string`; render metrics grid (F1, Precision, Recall, Loss) with stat cards, MLflow run link with `target="_blank"`, artifact path in JetBrains Mono, training job lineage reference, per-entity metrics in collapsible `<details>`/`<summary>` accordion (covers scenarios 7, 8, 9, 10, 11)
- [x] 4.2 Render role-gated action buttons: "Promote" (visible when `role === "tenant_admin"` && `model.status === "completed"`), "Demote" (visible when `role === "tenant_admin"` && `model.status === "promoted"`), "Warmup" (visible when `role === "tenant_admin"`) — each wired to its mutation hook (covers scenarios 12, 13, 14, 15, 16, 17, 18)
- [x] 4.3 Show loading spinner on action button during mutation pending state; show error toast via `useToast` on mutation failure (covers scenarios 15, 19)
- [x] 4.4 Write `src/portal/src/components/model-registry/ModelDetailPanel.test.tsx` — tests for: metrics grid rendering, MLflow link, per-entity metrics accordion, empty state when no model selected, role-gated button visibility, status-gated button visibility, promote/demote/warmup mutation calls, error toast on failure

## 5. ModelRegistryPage

- [x] 5.1 Create `src/portal/src/components/model-registry/ModelRegistryPage.tsx` — call `useModelVersions()`; manage selected model state; render page header (path moniker, version count, h1), left-column card list with `ModelVersionCard`, right-column `ModelDetailPanel` (covers scenario 1)
- [x] 5.2 Render 3 skeleton placeholder cards while `isLoading` is true — use `animate-pulse` skeleton pattern (covers scenario 2)
- [x] 5.3 Render empty-state message when `data?.length === 0` — "No model versions yet — train your first model" (covers scenario 3)
- [x] 5.4 Replace `PlaceholderScreen` in `src/portal/src/app/(auth)/models/page.tsx` with `<ModelRegistryPage />` (covers scenario 1)
- [x] 5.5 Write `src/portal/src/components/model-registry/ModelRegistryPage.test.tsx` — tests for: header renders, skeleton during loading, empty state, card list with data, card selection updates detail panel

## 5b. Base Model (Version 0) Entry

- [x] 5b.1 In `ModelRegistryPage.tsx`: build a synthetic version-0 `ModelVersion` entry — use `activeModel` data when `activeModel.version_number === 0`, otherwise construct `{ id: "v0-base", version_number: 0, status: "archived", ... }`; append it after the sorted fine-tuned model list so version 0 is always last
- [x] 5b.2 In `ModelVersionCard.tsx`: when `model.version_number === 0`, render label "Base Model" instead of "v0"
- [x] 5b.3 In `ModelDetailPanel.tsx`: when `model.version_number === 0`, hide all action buttons and show model name `dslim/bert-base-NER` with supported labels PER / ORG / LOC / MISC
- [x] 5b.4 Remove the "No model versions yet" empty-state message (version 0 is always present so the list is never empty); update `ModelRegistryPage.test.tsx` and `ModelVersionCard.test.tsx` accordingly

## 6. Verification & Evidence

- [x] 6.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 6.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 6.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 6.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 6.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [ ] 6.6 Run `openspec validate sp-10-model-registry --type change --strict` and confirm it exits clean before archive. (Note: validator reports "no deltas found" for all changes in this project including archived ones — appears to be a known environment issue; spec format matches archived changes that were successfully applied.)
