# Verification Plan

**Change:** llm-assisted-prelabeling
**Generated:** 2026-09-03
**Status:** 🟢 Complete — implementation verified by execution; Audit Record signed off 2026-09-03.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | llm-prelabeling | LLM Pre-labeling Trigger | Trigger LLM pre-labeling for a processed document | Given a processed document with text and a tenant with ≥1 active entity type, when POSTing to `/api/v1/documents/{doc_id}/prelabel/llm`, then status is 202 and the body contains a `job_id` | `tests/test_llm_prelabel_api.py::test_trigger_returns_202_with_job_id` | - [x] |
| 2 | llm-prelabeling | LLM Pre-labeling Trigger | Trigger LLM pre-labeling for a document with no extracted text | Given a document not in `processed` status or with no extracted text, when POSTing to the LLM prelabel endpoint, then status is 422 and the error states the document has no extracted text | `tests/test_llm_prelabel_api.py::test_trigger_422_no_extracted_text` | - [x] |
| 3 | llm-prelabeling | LLM Pre-labeling Trigger | Trigger LLM pre-labeling for a tenant with no active entity types | Given a tenant with zero active entity types, when POSTing to the LLM prelabel endpoint, then status is 422 and the error states no entity types are configured | `tests/test_llm_prelabel_api.py::test_trigger_422_no_entity_types` | - [x] |
| 4 | llm-prelabeling | Extraction Scope | Entity types without QA pairs are still extracted | Given a tenant with one entity type having QA pairs and one having only `examples`, when LLM pre-labeling runs on a document containing both, then the resulting suggested spans include spans for both entity types | `tests/test_llm_prelabel_extraction_scope.py::test_entity_types_without_qa_pairs_are_extracted` | - [x] |
| 5 | llm-prelabeling | Extraction Scope | QA pairs do not limit extraction to their literal topic | Given one QA pair on `years_experience` and a document with two distinct experience mentions, when LLM pre-labeling runs, then a span is produced for each mention, not only one | `tests/test_llm_prelabel_extraction_scope.py::test_qa_pairs_do_not_limit_extraction_scope` | - [x] |
| 6 | llm-prelabeling | Extractive-Only Output | LLM output that is not a literal substring is not stored as a span | Given a document containing only "2019-2024" and a QA pair implying "5 years", when LLM pre-labeling runs, then no suggested span with text "5 years" is stored | `tests/test_llm_prelabel_grounding.py::test_non_extractive_answer_is_not_stored` | - [x] |
| 7 | llm-prelabeling | Grounding and Verification | Quote grounds to exactly one location | Given document text "John Doe joined as Senior Engineer" and an LLM entity quoting "John Doe", when grounding runs, then a span is stored with `char_start: 0`, `char_end: 8`, `text: "John Doe"` | `tests/test_llm_prelabel_grounding.py::test_quote_grounds_to_single_location` | - [x] |
| 8 | llm-prelabeling | Grounding and Verification | Quote cannot be found in the document text | Given an LLM entity quoting "Jane Smith" absent from the document text, when grounding runs, then no span is stored for it and it is counted in the job's ungrounded-suggestion count | `tests/test_llm_prelabel_grounding.py::test_unmatched_quote_is_dropped` | - [x] |
| 9 | llm-prelabeling | Grounding and Verification | Quote matches multiple locations in the document | Given document text containing "Acme Corp" twice and one LLM entity quoting it, when grounding runs, then exactly one span is stored at the first occurrence (`char_start: 0`) | `tests/test_llm_prelabel_grounding.py::test_duplicate_quote_takes_first_occurrence` | - [x] |
| 10 | llm-prelabeling | Entity Type Constraint | LLM returns an entity type not configured for the tenant | Given a tenant with only `institute` and `person_name` active, when the LLM returns `entity_type: "job_title"`, then no span is stored for it and no new entity type is created | `tests/test_llm_prelabel_grounding.py::test_unconfigured_entity_type_is_dropped` | - [x] |
| 11 | llm-prelabeling | Suggested Span Storage and Source Tracking | LLM pre-labeling replaces existing suggestions for the document | Given a document with 2 existing `source: "keyword"` suggested spans, when LLM pre-labeling completes, then those 2 are removed and the new spans carry `source: "llm"` | `tests/test_llm_prelabel_api.py::test_llm_prelabel_replaces_existing_suggestions` | - [x] |
| 12 | llm-prelabeling | Asynchronous Execution | Trigger request returns before the LLM call completes | Given an eligible document, when POSTing to the LLM prelabel endpoint, then the response returns in under 1 second while the LLM call and grounding continue afterwards | `tests/test_llm_prelabel_api.py::test_trigger_returns_before_llm_completes` | - [x] |
| 13 | llm-prelabeling | Asynchronous Execution | Job status reflects completion | Given a finished LLM pre-labeling job, when its status is fetched, then status is `completed` and resulting spans are retrievable via `/api/v1/documents/{doc_id}/spans?type=suggested` | `tests/test_llm_prelabel_api.py::test_job_status_reflects_completion` | - [x] |
| 14 | llm-prelabeling | Result Caching | Re-triggering on an unchanged document and configuration uses the cache | Given a successfully pre-labeled document with no document or entity-config changes since, when the endpoint is POSTed again, then the response indicates a cached result and no new LLM call is made | `tests/test_llm_prelabel_cache.py::test_unchanged_document_and_config_uses_cache` | - [x] |
| 15 | llm-prelabeling | Result Caching | Configuration change invalidates the cache | Given a successfully pre-labeled document and a subsequently added QA pair on an entity type, when the endpoint is POSTed again, then the LLM is invoked again rather than serving the prior cached result | `tests/test_llm_prelabel_cache.py::test_entity_config_change_invalidates_cache` | - [x] |
| 16 | llm-prelabeling | Tenant Isolation | LLM pre-labeling is scoped to a single tenant | Given two tenants each with documents, when pre-labeling is triggered for tenant "acme-corp", then the LLM call contains only that tenant's document text and entity config, and spans are written only to that tenant's schema | `tests/test_llm_prelabel_api.py::test_llm_prelabel_is_tenant_scoped` | - [x] |
| 17 | entity-config | Entity Type Definition | Tenant Admin creates an entity type | Given an authenticated Tenant Admin, when POSTing a new entity type, then status is 201 and the body contains `name: "customer_name"`, `version: 1`, `is_active: true` | `tests/test_entity_config.py::test_create_entity_type` | - [x] |
| 18 | entity-config | Entity Type Definition | Tenant Admin updates an entity type | Given entity type "customer_name" at `version: 1`, when PUTing a new description, then status is 200, `version` is 2, and the description is updated | `tests/test_entity_config.py::test_update_entity_type` | - [x] |
| 19 | entity-config | Entity Type Definition | Tenant Admin adds QA pairs to an entity type | Given entity type "years_experience" with no `qa_examples`, when PUTing a `qa_examples` array with one question/answer pair, then status is 200, `qa_examples` contains the pair, and `version` is incremented | `tests/test_entity_config.py::test_add_qa_examples_increments_version` | - [x] |
| 20 | entity-config | Entity Type Definition | Entity type with no QA pairs remains valid | Given an authenticated Tenant Admin, when POSTing an entity type with no `qa_examples` field, then status is 201 and `qa_examples` is empty or null | `tests/test_entity_config.py::test_entity_type_without_qa_examples_is_valid` | - [x] |
| 21 | annotation-workspace | Pre-labeling | Pre-label a processed document | Given a document containing "Vellore Institute of Technology" and a matching `examples` entry, when POSTing to `/prelabel`, then status is 200 and a span is returned with `char_start: 0`, `char_end: 31`, `confidence < 1.0`, and `source: "keyword"` | `tests/test_annotation_workspace.py` (existing prelabel test, extended to assert source) | - [x] |
| 22 | annotation-workspace | Pre-labeling | Pre-label matching is case-insensitive | Given document text "Vellore INSTITUTE of Technology" and an `examples` entry differing only in case, when POSTing to `/prelabel`, then status is 200 and a matching suggested span is returned | `tests/test_annotation_workspace.py` (existing case-insensitivity regression test) | - [x] |
| 23 | annotation-workspace | Pre-labeling | Pre-label longest match wins for overlapping examples | Given `examples: ["Apple Inc", "Apple"]` and text "Apple Inc is based in Cupertino", when POSTing to `/prelabel`, then exactly 1 span for "Apple Inc" (0-9) is returned and none for "Apple" | `tests/test_annotation_workspace.py` (existing longest-match regression test) | - [x] |
| 24 | annotation-workspace | Pre-labeling | Pre-label replaces existing suggestions | Given a document with two existing suggested spans, when POSTing to `/prelabel` again, then the old suggested spans are removed and the new ones returned | `tests/test_annotation_workspace.py` (existing replace-suggestions regression test) | - [x] |
| 25 | annotation-workspace | Pre-labeling | List suggested spans | Given a document with 3 suggested spans, when GETing `/spans?type=suggested`, then status is 200 and all 3 are returned | `tests/test_annotation_workspace.py` (existing list-suggested-spans regression test) | - [x] |
| 26 | annotation-workspace | Pre-labeling | List suggested spans includes their source | Given a document with 2 `keyword` and 3 `llm` suggested spans, when GETing `/spans?type=suggested`, then status is 200 and each of the 5 returned spans includes its `source` field | `tests/test_annotation_workspace.py::test_list_suggested_spans_includes_source` | - [x] |
| 27 | annotation-workspace | Pre-labeling | Promote a suggested span to confirmed | Given suggested span "suggest-1" at offsets 10-31, when POSTing to `/spans/promote/suggest-1`, then status is 201, a confirmed span with the same offsets/text/entity_type is created, and the suggested span is removed | `tests/test_annotation_workspace.py` (existing promote regression test) | - [x] |
| 28 | annotation-workspace | Pre-labeling | Promoting an LLM-sourced suggested span behaves identically to a keyword-sourced one | Given suggested span "suggest-2" with `source: "llm"` at offsets 0-8, when POSTing to `/spans/promote/suggest-2`, then status is 201, an equivalent confirmed span is created, and the suggested span is removed | `tests/test_annotation_workspace.py::test_promote_llm_sourced_span` | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

For each area of complexity in this change, identify what an AI agent might get wrong
and how a human reviewer can detect and correct it.

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Offset sourcing (design.md Decision 2) | Implementer asks the LLM to return `char_start`/`char_end` directly and stores them, bypassing the grounding step — producing silently wrong spans that no test catches unless offsets are asserted | Read the LLM response schema/parser: it MUST accept only `entity_type` and `quote`. Confirm the grounding function signature takes `(document_text, quote)` and derives offsets itself. Any offset field parsed from the LLM payload is a violation. |
| 2 | Grounding failure handling (design.md Decision 4) | Implementer adds a fuzzy/nearest-match or normalized-whitespace fallback to "rescue" unmatched quotes, converting a drop into a confidently-wrong span | Grep the implementation for `difflib`, `fuzz`, `levenshtein`, `SequenceMatcher`, or `strip()`-based re-matching in the grounding path. Only exact case-insensitive matching is permitted; everything else must be dropped. |
| 3 | Prompt construction (design.md Decision 3) | Implementer builds a prompt that iterates the configured QA pairs and asks the LLM to answer them, rather than instructing full-document extraction across all active entity types — reintroducing the partial-labeling failure mode | Read the prompt template. It MUST enumerate every active entity type for the tenant and instruct extraction of all occurrences. QA pairs must appear only as few-shot examples attached to their own entity type. Scenarios 4 and 5 must both pass. |
| 4 | Cache key composition (design.md Decision 5) | Implementer keys the cache on document content hash alone, omitting entity-config version — causing stale suggestions to be served after a tenant edits entity types or QA pairs | Inspect cache key construction; it MUST include a tenant entity-config version/hash component. Scenario 15 must fail if that component is removed. |
| 5 | Celery queue selection (design.md Decision 6) | Implementer routes the LLM task onto the existing `training.jobs` queue, coupling I/O-bound LLM calls to the GPU-backed node pool | Grep for the queue name in the task definition and worker config; confirm it is a new non-GPU queue and that `training.jobs` is untouched. Confirm `training_service` config is unmodified in the diff. |
| 6 | Field and column naming | Implementer invents field names not in spec (`qa_pairs` instead of the spec'd `qa_examples`) or mismatches the existing DB column `text_content` against the API field `text` used in the suggested-spans contract | Cross-check every persisted field against the spec files and against the existing `suggested_spans` insert in `spans.py`. Any name appearing in code but not in a SHALL clause or the existing schema is suspect. |
| 7 | Tenant isolation in new code paths (ADR-001) | New Celery task resolves the tenant schema from task arguments incorrectly, or queries `public.entity_definitions` without a `tenant_id` filter, leaking one tenant's config into another's LLM call | Trace the task's schema resolution against the `_schema(tenant_id)` pattern used elsewhere in `annotation_service`. Confirm every `entity_definitions` query filters by `tenant_id`. Scenario 16 must be exercised with two real tenants, not mocked. |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

List every currently-in-force ADR that constrains this change (as identified in design.md).

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001-tenant-data-isolation | Tenant isolation via separate PostgreSQL schemas, enforced at API, connection, and ORM layers | The new endpoint, its Celery task, and all `suggested_spans` writes must resolve the tenant schema the same way existing `annotation_service` endpoints do; a single LLM call must never span two tenants | Grep the new code for hardcoded schema names or raw `suggested_spans` references without a tenant-schema prefix. Confirm the task derives its schema from the tenant id passed at enqueue time. Execute Scenario 16 against two provisioned tenants and confirm no cross-schema writes. |
| ADR-006-training-infrastructure | Asynchronous task execution via Celery + RabbitMQ; GPU workers on K8s specifically for training | Establishes Celery/RabbitMQ as the async pattern this change must follow, but the LLM task must run on a lightweight non-GPU queue, not the GPU-backed `training.jobs` queue | Confirm the new task is registered on a distinct queue name and that no GPU node-pool selector or resource request is attached to its worker. Confirm `git diff` shows no changes to `training_service` queue configuration. |

> ADR-009 and ADR-010 partially supersede ADR-006 but govern training hyperparameters and dataset-readiness thresholds respectively; neither applies to this change, which does not touch `training_service`. ADR-002, ADR-003, and ADR-008 govern the tenant's own trained/served model, not an external annotation LLM, and likewise do not constrain this change.

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

*(Minimum one item per row in Section 1 — test output, screenshot, log excerpt, or API
trace proving the THEN was observed in a real execution.)*

- [x] Scenario 1 (Trigger for processed document): test output showing a 202 response containing a `job_id`
- [x] Scenario 2 (No extracted text): test output showing a 422 with the no-extracted-text error code
- [x] Scenario 3 (No active entity types): test output showing a 422 with the no-entity-types error code
- [x] Scenario 4 (Types without QA pairs still extracted): test output asserting spans for both the QA-configured and non-QA-configured entity types
- [x] Scenario 5 (QA pairs don't limit extraction): test output asserting two spans produced from a document with two mentions under a single QA pair
- [x] Scenario 6 (Extractive-only): test output asserting no "5 years" span is stored for a document containing only "2019-2024"
- [x] Scenario 7 (Quote grounds once): unit test output asserting `char_start: 0`, `char_end: 8` for "John Doe"
- [x] Scenario 8 (Quote not found): unit test output asserting zero spans stored and the ungrounded count incremented
- [x] Scenario 9 (Quote matches multiple locations): unit test output asserting exactly one span at the first occurrence
- [x] Scenario 10 (Unconfigured entity type dropped): test output asserting no span stored and no entity type created
- [x] Scenario 11 (Replaces existing suggestions): test output asserting prior keyword spans removed and new spans carry `source: "llm"`
- [x] Scenario 12 (Async trigger returns fast): test output or API trace showing sub-second response with the job still in flight
- [x] Scenario 13 (Job status reflects completion): test output showing `status: "completed"` and spans retrievable from the suggested-spans listing
- [x] Scenario 14 (Cache hit): test output plus LLM client call-count assertion showing zero new LLM invocations on re-trigger
- [x] Scenario 15 (Config change invalidates cache): test output plus call-count assertion showing the LLM was re-invoked after a QA pair was added
- [x] Scenario 16 (Tenant isolation): test output from a two-tenant fixture asserting the LLM payload and span writes were scoped to one tenant only
- [x] Scenario 17 (Create entity type): test output showing 201 with `version: 1`
- [x] Scenario 18 (Update entity type): test output showing 200 with `version: 2` and updated description
- [x] Scenario 19 (Add QA pairs): test output showing 200, persisted `qa_examples`, and incremented version
- [x] Scenario 20 (No QA pairs still valid): test output showing 201 with empty or null `qa_examples`
- [x] Scenario 21 (Keyword pre-label unchanged, now with source): test output asserting the existing offsets/confidence assertions still pass plus `source: "keyword"`
- [x] Scenario 22 (Case-insensitive keyword match): existing regression test output, unchanged
- [x] Scenario 23 (Longest match wins): existing regression test output, unchanged
- [x] Scenario 24 (Keyword pre-label replaces suggestions): existing regression test output, unchanged
- [x] Scenario 25 (List suggested spans): existing regression test output, unchanged
- [x] Scenario 26 (Listing includes source): test output asserting all 5 spans carry a `source` field across both sources
- [x] Scenario 27 (Promote suggested span): existing regression test output, unchanged
- [x] Scenario 28 (Promote LLM-sourced span): test output asserting promotion of a `source: "llm"` span behaves identically

### Structural Evidence

*(Code review and architectural compliance.)*

- [x] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed ✓
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

*(One item per Hallucination Risk from Section 2.)*

- [x] Risk 1 mitigation confirmed — LLM response parser accepts only `entity_type` and `quote`; no offsets sourced from the model
- [x] Risk 2 mitigation confirmed — grounding path contains no fuzzy/approximate matching; unmatched quotes are dropped
- [x] Risk 3 mitigation confirmed — prompt enumerates all active entity types and instructs full-document extraction; QA pairs appear only as per-type few-shot context
- [x] Risk 4 mitigation confirmed — cache key includes an entity-config version component; Scenario 15 fails when that component is removed
- [x] Risk 5 mitigation confirmed — LLM task runs on a dedicated non-GPU queue; `training.jobs` and `training_service` config untouched in the diff
- [x] Risk 6 mitigation confirmed — all persisted field and column names cross-checked against spec SHALL clauses and the existing `suggested_spans` schema
- [x] Risk 7 mitigation confirmed — schema resolution traced against the existing tenant-context pattern; all `entity_definitions` queries filter by `tenant_id`; Scenario 16 exercised with two real tenants

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching
entry. Do not pre-fill — entries must describe real observations.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Static check | `_ALLOWED_ENTITY_FIELDS = ("entity_type", "quote")` in `src/annotation_service/services/llm_prelabel.py` is the only path by which a response element becomes a parsed entity; every other key, offsets included, is dropped by the dict comprehension at the end of `parse_llm_response`. | Risk 1 | Claude (agent) | 2026-09-03 |
| 2 | Static check | `grep -rniE "difflib\|SequenceMatcher\|levenshtein\|fuzz\|rapidfuzz" src/annotation_service/` returns only the docstring in `ground_quote` stating that none of it is used. Matching is `str.find` on lowercased text and nothing else. | Risk 2 | Claude (agent) | 2026-09-03 |
| 3 | Static check | `build_entity_type_block` iterates every active entity type and renders each type's own `qa_examples` under that type, labelled "for illustration only"; the payload repeats "NOT questions to answer about the document below". No code path iterates QA pairs as questions. | Risk 3 | Claude (agent) | 2026-09-03 |
| 4 | Static check | The cache lookup in `trigger_llm_prelabel` filters on `content_hash` AND `config_version`, the latter from `entity_config_fingerprint` over (name, description, examples, qa_examples) of the active set. | Risk 4 | Claude (agent) | 2026-09-03 |
| 5 | Static check | `git diff --stat -- src/training_service/` is empty. The new task is enqueued with `queue=settings.annotation_llm_celery_queue` (`annotation.llm_jobs`); no GPU node-pool selector exists in `src/annotation_service/celery_app.py`. | Risk 5 | Claude (agent) | 2026-09-03 |
| 6 | Static check | The spec'd name `qa_examples` is used throughout; `grep -rn "qa_pairs" src/ tests/` matches only mandated test-function names. Storage uses the existing `text_content` column with the existing `text` API field, matching the keyword insert in `spans.py`. | Risk 6 | Claude (agent) | 2026-09-03 |
| 7 | Static check | Every `entity_definitions` read in the new code (`_SELECT_ACTIVE` in `src/shared/entity_config_version.py`) filters `tenant_id = :tid`; the task and the endpoints derive their schema from `_schema(tenant_id)`. Scenario 16 exercises this with two provisioned tenants. | Risk 7, ADR-001 | Claude (agent) | 2026-09-03 |
| 8 | Command output | `openspec validate llm-assisted-prelabeling --type change --strict` → "Change 'llm-assisted-prelabeling' is valid". | Task 9.6 | Claude (agent) | 2026-09-03 |
| 9 | Static check | Promotion is source-agnostic: `promote_suggested_span` in `src/annotation_service/api/v1/spans.py` contains no reference to `source` at all. | 28, Task 8.3 | Claude (agent) | 2026-09-03 |
| 10 | Test output | `pytest -v` over the 36 acceptance tests named in Section 1: **36 passed**. Every row 1-28 has a named test that ran green. Run inside the project image against the compose `postgres-test` container (`ner_test`), provider stubbed via `StubLLMClient`. | 1-28 | Claude (agent) | 2026-09-03 |
| 11 | Test output | Full new-suite run: `tests/test_llm_prelabel_{grounding,extraction_scope,api,cache}.py` → **60 passed** (the 24 scenario tests plus 36 supporting edge-case tests: near-miss drops, malformed responses, multi-occurrence claiming, provider failure recorded on the job, cross-tenant cache isolation). | 1-16 | Claude (agent) | 2026-09-03 |
| 12 | Regression baseline | Targeted regression set (16 files touching spans, entity config, tenant provisioning, schema verification) run before and after the change: **identical** 8 failures + 6 errors in both, 153 → 160 passed. Every failure reproduces on the unmodified tree — `test_annotation_workspace` export tests (missing `imported_annotations` fixture), `test_entity_config` legacy fixture (admin tenant endpoint 422), `test_env_config`, `test_tenant_schema_migrations`, `test_imported_annotations_update`. No regression introduced. | 21-25, 27 | Claude (agent) | 2026-09-03 |
| 13 | Migration run | Task 2.4 on a scratch database (`ner_migrationcheck_test`): `alembic upgrade 037`, seeded 2 `suggested_spans` rows, `upgrade 038` → both rows intact with `source = 'keyword'` backfilled, `qa_examples` present, `llm_prelabel_jobs` created in `tenant_migcheck` **and** `tenant_template`, CHECK constraint present and rejecting `source = 'bogus'` while accepting `'llm'`. `downgrade 037` → all 3 rows still present and unchanged, all three added objects gone. Additive-only and reversible, no data loss either direction. | Migration safety (task 2.4) | Claude (agent) | 2026-09-03 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** llm-assisted-prelabeling
**Proposal:** `openspec/changes/llm-assisted-prelabeling/proposal.md`
**Spec files reviewed:**

- specs/llm-prelabeling/spec.md
- specs/entity-config/spec.md
- specs/annotation-workspace/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [x] |
| All ADRs in Section 3 verified compliant | - [x] |
| Spec Alignment table complete (no missing scenarios) | - [x] |
| Evidence Log populated with real evidence | - [x] |
| All functional evidence items in Section 4 checked | - [x] |
| All structural evidence items in Section 4 checked | - [x] |
| All edge case evidence items in Section 4 checked | - [x] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [x] |
| No hallucinated requirements introduced | - [x] |
| No undocumented patterns used | - [x] |
| No AI-invented fields, endpoints, or behaviours present | - [x] |
| Every THEN clause in specs has a corresponding evidence entry | - [x] |
| Hallucination risk register reviewed and all mitigations confirmed | - [x] |

**Archive approved by:** Hanna.ansar (theertha@inapp.com)

**Date:** 2026-09-03

**Notes:**

- Sign-off recorded by the agent at the reviewer's explicit instruction during `/opsx:archive` on 2026-09-03. Recorded, not authored: the reviewer stated they had reviewed the change and approved it, and the judgement is theirs.

- Both blocking open questions were answered before implementation and are recorded in design.md § Resolved Questions: (a) tenant document text may be sent to the configured external provider on the same footing already approved for `extraction_service` post-processing and `chat_api` RAG — no per-tenant opt-in, and the feature is inert where no provider is configured; (b) the provider is Azure OpenAI via the existing `azure_openai_*` settings, with the key from `openai_api_key`, which has no default in `Settings`.
- All 28 Spec Alignment rows have been verified by execution (Evidence Log rows 10-13). Tasks 2.4 and 9.1-9.4 and 9.6 are complete; **9.5, this sign-off, is the only remaining gate.**
- Tests were run inside the project's own Docker image with dev dependencies layered on, against the compose `postgres-test` container. Two pre-existing environment facts a reviewer should know: `tests/test_analytics_dashboard.py` has a syntax error that blocks whole-suite collection (unrelated to this change), and the legacy `tenant_with_token` fixture in `test_entity_config.py` errors because `POST /api/v1/admin/tenants` returns 422 — the four new entity-config tests therefore provision their tenant directly, following the precedent set by `test_entity_type_view_metadata_api.py`.
- One judgement call for the reviewer: LLM suggestions are stored with `confidence = 0.75`, deliberately distinct from the keyword matcher's 0.85, because grounding certifies a span's offsets but says nothing about whether the label is right. The semantics of this number remain an open question in design.md and should be settled before change 5 builds confidence-based routing on it.
- The duplicate-quote resolution rule (Grounding and Verification, Scenario 9) is an unvalidated design assumption — it mirrors the existing keyword matcher's overlap handling but has not been tested against real tenant documents. Reviewer should explicitly sign off on it.
- Confidence-score semantics for `source: "llm"` spans are deliberately unspecified in this change. Changes 5 and 6 in the wider plan depend on confidence being meaningful, so this must be decided before those changes are specced.
