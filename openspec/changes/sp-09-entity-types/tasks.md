## 1. Types

- [ ] 1.1 Create `src/portal/src/types/entity-types.ts` — export `EntityType` interface with fields: `id: string`, `name: string`, `description: string`, `examples: string[]`, `base_label_mapping: Record<string, string[]>`, `target_table: string | null`, `required_flag: boolean`, `is_active: boolean`, `version: number`
- [ ] 1.2 Export `EntityTypeListResponse` interface: `{ entity_types: EntityType[] }`

## 2. API Hooks

- [ ] 2.1 Create `src/portal/src/hooks/use-entity-types.ts` — `useEntityTypes()` using `useQuery`, queryKey `["entity-types", tenantSlug]`, fetching `GET /api/v1/tenants/{slug}/entity-types` via `authFetch`; tenantSlug obtained from `useAuth()` (verification: unit test confirming URL and query key — covers scenarios 18, 19)
- [ ] 2.2 Create `src/portal/src/hooks/use-create-entity-type.ts` — `useCreateEntityType()` using `useMutation`, POSTing to `/api/v1/tenants/{slug}/entity-types`, invalidating `["entity-types", tenantSlug]` on success (covers scenario 11)
- [ ] 2.3 Create `src/portal/src/hooks/use-update-entity-type.ts` — `useUpdateEntityType()` using `useMutation`, PUTting to `/api/v1/tenants/{slug}/entity-types/{name}`, invalidating `["entity-types", tenantSlug]` on success (covers scenario 12)
- [ ] 2.4 Create `src/portal/src/hooks/use-toggle-entity-type.ts` — `useToggleEntityType()` using `useMutation`, PATCHing to `/api/v1/tenants/{slug}/entity-types/{name}` with `{ is_active: boolean }`, invalidating `["entity-types", tenantSlug]` on success; on error, call `queryClient.invalidateQueries` to refetch (covers scenarios 15, 16, 17)
- [ ] 2.5 Export all four hooks from `src/portal/src/hooks/index.ts`

## 3. EntityTypeCard Component

- [ ] 3.1 Create `src/portal/src/components/entity-types/EntityTypeCard.tsx` — props: `entityType: EntityType`, `index: number`, `onEdit: () => void`, `onToggle: () => void`; derive hue from `[25, 330, 235, 285, 155, 200, 60][index % 7]`; render colored dot (34×34 outer, 12×12 inner in OKLCH), name in JetBrains Mono weight-600 14.5 px, `v{version}` label, description, required/active pills, BASE LABEL MAPPING monospace box, EXAMPLES text, Edit and Deactivate/Reactivate buttons (covers scenarios 4, 5, 6)
- [ ] 3.2 Apply hover lift styles: `transition: transform 150ms, border-color 150ms` with `:hover { transform: translateY(-2px); border-color: var(--primary-line) }` (covers scenario 7)
- [ ] 3.3 Write `src/portal/src/components/entity-types/EntityTypeCard.test.tsx` — render tests for all card fields, pill labels, and button text for active vs inactive entity types

## 4. DefineEntityTypeSlideOver Component

- [ ] 4.1 Create `src/portal/src/components/entity-types/DefineEntityTypeSlideOver.tsx` — props: `open: boolean`, `onClose: () => void`, `editTarget: EntityType | null` (null = create mode); compose with existing `<SlideOver width={460}>`
- [ ] 4.2 Render header: title "Create entity type" / "Edit entity type", path moniker `POST /api/v1/entity-types` in JetBrains Mono, ✕ close button
- [ ] 4.3 Render NAME input (JetBrains Mono, `placeholder="vendor_name"`, disabled when `editTarget !== null`) — covers scenario 9
- [ ] 4.4 Render DESCRIPTION input (`placeholder="Name of a vendor / supplier"`) pre-filled from `editTarget?.description`
- [ ] 4.5 Render EXAMPLES input (`placeholder="Acme Supplies, Global Tech Ltd"`, comma-separated) — on save, split on `", "` to produce `string[]`; pre-fill from `editTarget?.examples.join(", ")`
- [ ] 4.6 Render BASE MODEL LABEL chip row — hard-coded array `["PER", "ORG", "LOC", "MISC"]`, single-select enforced (clicking a chip deselects others), default to first key of `editTarget?.base_label_mapping` in edit mode (covers scenarios 10, 9)
- [ ] 4.7 Render Required flag toggle row: label "Required flag", sub-label "enforce presence at extraction", boolean toggle pre-filled from `editTarget?.required_flag`
- [ ] 4.8 Render save button labeled "Create entity type" / "Save changes"; on click call `useCreateEntityType` or `useUpdateEntityType` as appropriate, show success toast via `useToast`, close slide-over on success; show error toast on API error and keep slide-over open (covers scenarios 11, 12, 14)
- [ ] 4.9 Write `src/portal/src/components/entity-types/DefineEntityTypeSlideOver.test.tsx` — tests for: create mode field state, edit mode pre-fill + NAME disabled, chip single-select, Escape closes (inherited from SlideOver), submit calls correct mutation, error toast on failure (covers scenarios 8, 9, 10, 13, 14)

## 5. EntityTypesPage

- [ ] 5.1 Create `src/portal/src/components/entity-types/EntityTypesPage.tsx` — call `useEntityTypes()`; manage slide-over state (`open: boolean`, `editTarget: EntityType | null`); render page header (path moniker, active-count / total, h1, "+ Define entity type" button), 2-column card grid with `EntityTypeCard` per entity type, and `DefineEntityTypeSlideOver`
- [ ] 5.2 Render 6 skeleton placeholder cards while `isLoading` is true — use `PlaceholderScreen`-compatible pattern or a simple grid of `<div>` skeletons with `animate-pulse` (covers scenario 2)
- [ ] 5.3 Render empty-state message when `data?.entity_types.length === 0` — "Define your first entity type to get started" or equivalent; ensure "+ Define entity type" button is still shown (covers scenario 3)
- [ ] 5.4 Wire toggle button on each card to `useToggleEntityType` with the entity type name and inverse of current `is_active`; show success/error toasts
- [ ] 5.5 Replace `PlaceholderScreen` in `src/portal/src/app/(auth)/entity-types/page.tsx` with `<EntityTypesPage />` (covers scenario 1)
- [ ] 5.6 Write `src/portal/src/components/entity-types/EntityTypesPage.test.tsx` — tests for: header renders, skeleton during loading, empty state, card grid with data, toggle mutation called on Deactivate/Reactivate click

## 6. Verification & Evidence

- [ ] 6.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 6.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 6.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 6.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 6.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [ ] 6.6 Run `openspec validate sp-09-entity-types --type change --strict` and confirm it exits clean before archive.
