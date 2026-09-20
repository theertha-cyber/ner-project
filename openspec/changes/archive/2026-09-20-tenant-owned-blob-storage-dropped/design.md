## Context

The platform stores a document's bytes through one application-owned boundary, `ContentStore`, with exactly three operations and no configuration in any signature (`original-document-storage`). One adapter implements it today — `MinioContentStore`, declaring `kind = "platform_minio"` — and two instances of it are cached process-wide: a durable one on `settings.minio_bucket` and a working one on `settings.minio_working_bucket` with an expiry rule. Retention mode selects between them: `platform_blob` writes durable, `ephemeral` writes working, `source_only` writes nothing.

The selection seam for a different backend already exists and is deliberately inert. `CONTENT_STORE_ADAPTERS` admits `tenant_azure_blob`; `AZURE_EXECUTABLE_SELECTIONS` already maps `("content_store_adapter", "tenant_azure_blob")` to an Azure provider, so `is_selection_executable` returns true for a tenant holding an active Azure Blob connection. Only the execution side is missing, and it says so: `DocumentIngestionService._write_content` carries a docstring recording that the profile's `content_store_adapter` is not consulted, because "only the platform defaults are executable in this change."

ADR-017 made the gap concrete. A `tenant_owned` tenant keeps rows and vectors in its own PostgreSQL, but had nowhere tenant-side to retain an original — so `platform_blob` retention is rejected for it outright (`RetentionModeNotPermittedForDataPlane`), and those tenants must accept `ephemeral` or `source_only`. They trade durable originals for residency.

Chat attachments are in scope without special handling: they are ingested as document rows through the same `DocumentIngestionService` (ADR-011, conversation-scoped chat attachments), so routing the store routes them too.

## Goals / Non-Goals

**Goals:**

- Every byte the platform stores on a tenant's behalf — uploaded documents, chat attachments, and the working copies of both — is written to a container that tenant owns, when that tenant has configured one.
- The `ContentStore` contract does not change. No caller learns which backend is in use, and no container, account, credential, or key rule crosses the boundary.
- Documents written before activation stay readable, by recording which store produced each reference rather than inferring it from the tenant's current profile.
- `platform_blob` retention becomes available to a `tenant_owned` tenant, removing the residency-versus-durability trade ADR-017 imposed.
- Failure is closed. An unreachable tenant container rejects uploads and fails reads; it never falls back to platform MinIO.

**Non-Goals:**

- Migrating bytes already in MinIO. Existing objects stay where they are, readable through their recorded backend kind.
- Moving fine-tuned model artifacts (`tenants/{id}/models/v{n}/`) or MLflow run artifacts (`s3://ner-platform/mlflow/`) out of platform MinIO, for any tenant.
- Making the `ContentStore` protocol asynchronous.
- Any S3-compatible tenant store. `tenant_s3` stays recordable-but-inert; only `tenant_azure_blob` becomes executable here.
- Latency or recovery targets for tenant-owned storage, consistent with DEC-004.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001-tenant-data-isolation | Schema-per-tenant isolation; content, artifacts, and indexes never cross a tenant boundary. Topology clause partially superseded by ADR-017. | Every key this design writes stays under a tenant-scoped prefix, and a resolved store is bound to the tenant whose request produced it. One tenant's connection may never serve another's bytes. |
| ADR-011-tenant-scoped-azure-connection-control-plane | Tenant-bound lifecycle records in `public` for a finite Azure catalog; secret *references* only, Vault outside local Compose; activation requires a passing connection test, network approval evidence, and TLS validation; one active connection per provider per tenant. | The new provider reuses this lifecycle wholesale — draft/test/activate/pause/retire, `<scheme>://<path>` secret references, the one-active partial unique index, and the evidence requirements. No parallel mechanism. |
| ADR-011-conversation-scoped-chat-attachments (Proposed) | Chat attachments are document rows with a `conversation_id`; deleting a conversation hard-deletes the rows, derived spans and chunks, and the underlying blob objects. | The hard-delete path must resolve the store from each document's recorded backend kind, not from a process-wide instance, or a `tenant_owned` conversation's objects would be orphaned in the tenant's container. |
| ADR-012-durable-azure-blob-source-synchronization | Celery source-sync jobs against a tenant's read-only Blob source; temporary Blob bytes deleted on every terminal path; `source_only` retention for synced originals. | The read-only source connection keeps its meaning and its privileges. A synced document's *destination* store is resolved by this design; its *source* remains ADR-012's. The retention restriction on sync is re-derived, not silently kept. |
| ADR-017-tenant-owned-postgresql-data-plane (Proposed) | Per-tenant data plane; a separate write-capable `azure_postgresql_data_plane` provider distinct from the read-only one; fail closed with no platform fallback; `platform_blob` rejected for `tenant_owned`. | Sets the pattern this design follows for a write-capable provider and for fail-closed behaviour. Its `platform_blob` rejection is the clause this change conditionally lifts — which is a supersession the ADR step must record, not an edit to ADR-017. |
| ADR-006-training-infrastructure (Proposed, partially superseded by 009/010) | Dedicated training infrastructure producing model artifacts. | Model artifacts stay in platform MinIO. This design states that as an explicit residency exclusion rather than leaving it unaddressed. |

## Decisions

### Decision 1: A separate write-capable provider, `azure_blob_content_store`

**Choice:** Add a fourth approved provider rather than reusing `azure_blob` or adding a `purpose` column to it. Its configuration is `account`, `container`, and an optional `prefix`; its secret field is `connection_string_ref`. Its connection test asserts *write* capability — a round-trip put, open, and delete under a scratch key — plus the presence of a lifecycle rule on the working prefix.

**Rationale:** `azure_blob` is a read-only source connection. ADR-011 states its credential is least-privilege for reading a business source; a tenant administrator who configured it did not consent to the platform writing into that container, and the container being synced *from* is exactly the wrong place to write platform content *to* — synced writes would be re-enumerated as source objects on the next sync pass. Separating the provider also makes "one content store per tenant" fall out of the existing one-active-per-provider partial unique index with no new constraint, and lets the two connections carry genuinely different credentials and test suites. This is the same reasoning ADR-017 used to split `azure_postgresql_data_plane` from `azure_postgresql`.

**Alternatives considered:**
- Reuse `azure_blob` — ruled out: conflates read-only source privileges with write privileges, breaks the one-active index's meaning, and risks the platform writing into a container it also enumerates as a source.
- A `purpose` discriminator column on one provider — ruled out: every uniqueness, validation, and resolution path would need to learn about `purpose`, and the partial unique index would have to be rebuilt to include it. A provider string already carries that meaning.

### Decision 2: The backend is recorded per document, never re-derived

**Choice:** Persist the producing store's `kind` on the document alongside its storage reference (a `content_store_kind` column on `documents`, backfilled to `platform_minio`). `open` and `delete` resolve their store from that recorded value. The tenant's current profile selection is consulted at **write** time only.

**Rationale:** `StorageReference` is an opaque string with no backend identity, and the profile is mutable. If `open` resolved the store from the profile, then the moment a tenant activated a content-store connection every pre-existing document would resolve to the tenant's container, where its bytes are not — silently returning "gone" for content that exists. The same failure runs in reverse on retire. This mirrors the discipline `original-document-storage` already applies to retention itself: the recorded value governs, "never a re-derivation." It is also what makes Decision 6's no-migration position tenable at all.

**Alternatives considered:**
- Encode the backend into the reference string — ruled out: the contract states the reference is opaque and that deriving anything from it is prohibited. Every consumer would need parsing rules, which is the coupling the boundary exists to prevent.
- Resolve from the profile on read — ruled out: makes activation retroactively destroy access to existing content.
- Try MinIO, then the tenant container — ruled out: a fallback read is a cross-tenant-boundary guess, and it turns a misconfiguration into silent success.

### Decision 3: One container, two prefixes, with a prefix-scoped lifecycle rule

**Choice:** The tenant provisions one container. Durable bytes and working copies separate by key prefix within it. The bounded lifetime of `ephemeral` working copies is enforced by an Azure lifecycle management rule scoped to the working prefix, asserted present by the connection test and refused without it.

**Rationale:** MinIO uses two buckets specifically so the expiry rule applies to working copies and nothing else, and that property is preserved here by a prefix-scoped rule. What changes is the number of artifacts a tenant must provision and the number of credentials to rotate — one instead of two. Critically, the expiry stays enforced by the object store rather than by the application reaching a terminal state, which is what makes `ephemeral` retention a guarantee rather than an intention; that property is unchanged, it simply moves to the tenant's account.

**Alternatives considered:**
- Two containers, mirroring MinIO exactly — ruled out: doubles tenant-side provisioning and connection configuration for a blast-radius improvement on a rule the activation test already verifies.
- Application-enforced expiry — ruled out: it is precisely the weaker guarantee the current design rejected.

### Decision 4: Tenant-scoped store resolution, bounded cache, fail closed

**Choice:** `get_durable_store()` and `get_working_store()` become tenant-scoped. Resolution asks the profile for `content_store_adapter` and the resolver whether that selection is executable for this tenant; an executable `tenant_azure_blob` yields an Azure adapter built from the active connection, anything else yields the platform MinIO instance. Resolved adapters are cached per tenant with a bounded size, as `EngineResolver` does for engines. When the tenant's container is unreachable, uploads are rejected before bytes are accepted and reads raise a typed unavailable error. There is no fallback to MinIO, ever.

**Rationale:** The fallback is the whole danger. A tenant configures its own container precisely so its content does not sit on platform infrastructure; a fallback write on a transient outage would put it there permanently and silently, and no later reconciliation could tell that it had happened. Failing closed makes the outage visible and bounded, which is ADR-017's position for the relational plane and should not differ here. Rejecting uploads *before* accepting bytes matters for the same reason: buffering them platform-side to retry is a residency violation with extra steps.

**Alternatives considered:**
- Fall back to MinIO on error, reconcile later — ruled out above.
- Buffer platform-side and retry — ruled out: the buffer is platform-side storage of tenant content.
- Resolve a fresh client per request — ruled out: connection-string parsing and client construction per upload, with no reuse across a sync batch.

### Decision 5: Lift ADR-017's `platform_blob` rejection, conditionally

**Choice:** `RetentionModeNotPermittedForDataPlane` fires for a `tenant_owned` tenant **without** an active content-store connection. With one, `platform_blob` retention is permitted, and `SYNC_ALLOWED_RETENTION` widens to admit it when the durable store is tenant-owned.

**Rationale:** The rejection was never about `platform_blob` as a retention semantic — it was about the absence of anywhere tenant-side to honour it. ADR-017's own words: that tenant's data plane "has no platform-side blob store to retain an original in." Once it has one, the objection is gone, and continuing to reject would force `tenant_owned` tenants to keep choosing between durable originals and residency for no remaining reason. The same reasoning applies to the sync constraint, whose comment records the objection as durable *platform-side* storage of synced content.

**Alternatives considered:**
- Keep the rejection, require `source_only` — ruled out: preserves the trade-off this change exists to remove.
- Lift unconditionally for `tenant_owned` — ruled out: a `tenant_owned` tenant with no content-store connection still has no tenant-side durable store, so the original objection stands exactly as written.

### Decision 6: No migration of existing bytes

**Choice:** Objects written before activation stay in MinIO and remain readable through their recorded backend kind. Activation has no precondition on tenant emptiness. A future bulk migration is possible but is not part of this change.

**Rationale:** Decision 2 already makes split-backend content correct, so migration buys a tidier residency story rather than a working one. Against that: a resumable bulk copy across a tenant network boundary, per-object verification, reference rewriting inside the tenant store, and a partial-migration state that every read path would have to reason about. Deferring keeps this change's failure modes to "wrote somewhere" or "refused to write," rather than adding "half moved."

**Alternatives considered:**
- Migrate during activation — ruled out: turns activation into a long-running, partially-failable operation.
- Block activation unless the tenant has no stored originals — ruled out: limits the feature to new tenants, and makes the attribution column unnecessary at the cost of the capability itself.

### Decision 7: The content-store slot is independent of the data plane

**Choice:** No cross-slot constraint. A `platform` data-plane tenant may activate a content-store connection; the only condition on `tenant_azure_blob` is an active `azure_blob_content_store` connection.

**Rationale:** The profile's slots are independent by construction, and document bytes are the largest and most obviously sensitive artifact a tenant submits — wanting them in one's own account without relocating an entire relational plane is a coherent and much cheaper posture. Coupling the slots would add a constraint the profile model does not otherwise have, in exchange for a tidier contractual statement that can be made in the contract instead.

**Alternatives considered:**
- Require `data_plane = tenant_owned` — ruled out: introduces cross-slot coupling for a documentation benefit, and denies the cheaper residency posture to tenants who want only it.

### Decision 8: A synchronous Azure client, behind the unchanged contract

**Choice:** The adapter uses the synchronous `azure.storage.blob.BlobServiceClient`. The `ContentStore` protocol stays synchronous.

**Rationale:** `put`, `open`, and `delete` are synchronous today and are called from synchronous worker code (OCR, ingestion). `blob_sync` uses the `.aio` client because it enumerates and fetches inside async Celery paths, which is a different call context. Making the boundary async to match `blob_sync` would force every existing caller and the MinIO adapter to change for no benefit to this change; the package supports both clients.

**Alternatives considered:**
- Async contract — ruled out: a contract-wide breaking change driven by an implementation detail of one adapter.
- Reuse `AzureBlobLiveProvider` — ruled out: it implements the `BlobProvider` source interface (enumerate/acquire), not the content-store interface (put/open/delete), and is bound to read-only source semantics.

## Risks / Trade-offs

- [A tenant removes or edits the working-prefix lifecycle rule after activation, so `ephemeral` retention silently stops being bounded] → The connection test asserts the rule at activation and refuses without it. Ongoing drift is not detected; carried as an open question for periodic re-assertion.
- [Every content read for an active tenant becomes a cross-network call, affecting the interactive chat-attachment path most] → Bounded per-tenant client cache and connection reuse. Targets remain deferred per DEC-004; flagged as an open question specifically for the chat path.
- [A tenant's container outage blocks uploads and content reads entirely for that tenant] → Intended, per Decision 4. Mitigated by a typed error distinguishing it from a platform fault, per-tenant isolation so no other tenant is affected, and service readiness continuing to reflect only platform dependencies.
- [Content permanently split across two backends for tenants who activate late] → Decision 2 makes this correct rather than merely tolerable; a later migration change remains possible on top of the attribution column.
- [A connection string grants broader access than the platform needs, and a misconfigured container is shared with the tenant's own data] → The activation test writes only under the platform prefix; documentation requires a dedicated container; ADR-011's evidence requirements apply unchanged.
- [ADR-017 is still `Proposed` and its implementation is in flight on this branch] → This change depends on its data-plane record and retention rule. Sequence after it; the ADR step records the conditional supersession of its `platform_blob` clause rather than editing it.
- [Retiring a connection makes tenant content inaccessible to the platform while objects remain in the tenant's account] → Consistent with ADR-017's offboarding position; deleting objects is a customer action. Carried as an open question for contracts.

## Migration Plan

1. Ship the attribution column first: add `content_store_kind` to the `documents` table in the tenant-store baseline and as a tenant-store revision, backfilled to `platform_minio` and defaulted for new rows. This is inert on its own and safe to deploy alone.
2. Convert `open` and `delete` call sites to resolve their store from the recorded kind. With only one adapter registered, behaviour is unchanged — this is the step that proves attribution routing before any second backend exists.
3. Add the `azure_blob_content_store` provider, its validation, its write-capable connection test, and the portal surface. No tenant can activate one until the adapter exists, so this is also inert.
4. Add the Azure content-store adapter and tenant-scoped resolution, still returning MinIO for every tenant because no connection can yet be executable.
5. Make `tenant_azure_blob` executable and relax the two retention rules. This is the only step with tenant-visible behaviour change, and it is per-tenant: a tenant is affected exactly when it activates a connection.
6. Add Azurite to local Compose as a stand-in tenant container, and verify the full path end to end.

**Rollback:** Steps 1–4 are additive and roll back by not activating anything. After step 5, rollback for a given tenant is retiring its content-store connection: new writes return to MinIO, and objects already in the tenant container remain correctly addressed by their recorded kind, so nothing becomes unreadable. No data movement is required in either direction — which is the practical payoff of Decision 2.

## Open Questions

- Should the working-prefix lifecycle rule be re-asserted periodically, or is activation-time verification sufficient? Affects whether a background health check is in scope.
- Does the deferral of latency targets (DEC-004) still hold for the interactive chat-attachment read path, which is now a cross-network call?
- Confirm the offboarding statement for contracts: retiring a connection leaves objects in the tenant's account, and deleting them is a customer action.
- **ADR to record:** this design conditionally lifts ADR-017's "`platform_blob` is rejected for a `tenant_owned` tenant" clause. ADR-017 is not to be edited; the adr step should record a superseding ADR covering that clause only, alongside the write-capable-provider and content-store-residency decisions.
