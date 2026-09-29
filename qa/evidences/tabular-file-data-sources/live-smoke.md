# Live smoke: uploaded tabular file answers in chat (task 8.2)

Status: **passed on 2026-09-23 after three defect fixes** (see "Defects found"). Screenshot
files are still to be attached (see "Screenshots").

Covers verification.md row 56, "Live stack answers from an uploaded file".

## Environment

- Stack: local `docker compose`. `db-init`, `gateway`, `chat_api`, `portal` and
  `celery_worker_tabular` rebuilt from the working tree at 13:46 UTC (the running
  images dated from 2026-09-21 and did not contain the tabular code). `chat_api` was
  rebuilt again at 14:05 and 14:09 and `portal` at 14:11 for the fixes below.
- Platform DB `ner_dev` at alembic revision `057` after `db-init`.
- `celery_worker_tabular` consuming `tabular_ingest`; `tabular_cache` volume mounted on `chat_api`.
- Real LLM: Azure OpenAI `gpt-4o-mini`.
- Portal driven in the Claude desktop browser pane, signed in as `arjun@gmail.com`
  (tenant admin, tenant `arjunj` / `a3e06d2f-a028-4bcf-a7a6-7c4ef836e3ce`, `tenant_owned`
  with an Azure PostgreSQL data plane).
- Input: `sales_q3.csv` in this folder (same rows as `tests/tabular_support.py::SALES_Q3_CSV`).
  The file went to the portal's own file input through a `DataTransfer` change event,
  because the pane cannot drive the native file picker.

## Timeline (UTC)

| Step | Time | Evidence |
|---|---|---|
| Upload accepted, version row created (`profiling`) | 13:47:38.107 | `tabular_file_versions.created_at` |
| `tabular_profile_version` received | 13:47:38.928 | worker log |
| Profiling done, `needs_review` | 13:47:42.545 (3.6 s task, 4.4 s from upload; limit 60 s) | worker log `{'outcome': 'needs_review'}` |
| Review screen: 4 columns, types `text/text/bigint/text`, load report "4 rows read · 4 to load · 0 rejected" | 13:48 | pane screenshot (viewed in session) |
| Publish clicked | 13:49:10 | portal list shows `Publishing` |
| `tabular_publish_version` done, `ready` | 13:49:11.151 (0.16 s) | worker log `{'outcome': 'ready', 'previous_version': None}`; `published_at` 13:49:11.141 |
| Question asked: "total closed revenue in EMEA?" (third attempt, after fixes) | 14:09:27.8 | pane clock |
| guardrail admitted, 2.2 s | 14:09:30.471 | chat_api `graph node=guardrail` |
| orchestrator planned, 1.6 s | 14:09:32.059 | chat_api `graph node=orchestrator` |
| entity_resolution skipped (tabular-only plan), 0.08 s | 14:09:32.139 | chat_api `graph node=entity_resolution` |
| statement validated, 1 relation | 14:09:34.730 | `external_pg_statement_validated {'relations': 1}` |
| retrieval_execution done, 4.6 s | 14:09:36.726 | chat_api |
| source_assembly, 1 source | 14:09:36.731 | chat_api `output_count=1` |
| generation done, 2.2 s | 14:09:38.931 | chat_api |

DB row after publish: file `aefa4ffc-5262-4fe6-b621-e8de86aeb582`, `sales_q3.csv`, v1, `ready`,
relation `sales_q3`.

## Result

- Answer: "The total closed revenue in EMEA is 1,650." (expected `1650`)
- Citation after reopening the conversation: chip `sales_q3.csv`. Expanded card:
  `sales_q3.csv` / `Version 1` / `Columns: amount, region, status`. It shows no `EMEA`,
  no `closed` and no row value, which matches the "Citation names file and columns only" scenario.

## Defects found and fixed during the run

1. **Domain guardrail declined the question.** "I can only answer questions about your
   tenant's documents…" (14:00:14). `DOMAIN_CLASSIFIER_SYSTEM_PROMPT` describes only
   documents and entities, and nothing told it the tenant has ready files.
   Fix: `guardrail_node` resolves the tenant's ready tabular files (display name,
   description and column names from the served contract, no row values) and
   `GuardrailService.classify_domain(..., tabular_sources=...)` appends them to the prompt.
   Files: `src/chat_api/graph/nodes.py`, `src/chat_api/services/guardrails.py`.
   Tests: `tests/test_chat_api_guardrails.py::TestDomainClassification::test_tabular_sources_reach_the_classifier_prompt`,
   `test_no_tabular_sources_leaves_prompt_unchanged`.
2. **Entity resolution hijacked the turn.** "I found multiple candidates named "in"…"
   (14:05:55). The resolver treats every 1–3 word n-gram as a person mention, and "in"
   matched words in stored resume values. Its result only rescopes
   `semantic_retrieval`/`structured_retrieval` entries, so a plan without them gains nothing from it.
   Fix: `entity_resolution_node` returns early when the plan has no non-rejected
   document-scoped entry (after pending-clarification handling).
   Test: `tests/test_entity_resolution_graph.py::TestPlanWithoutDocumentScopedEntries::test_tabular_only_plan_skips_resolution`.
   Still open, and outside this change: a stopword like "in" can still be read as a
   person mention whenever the plan does include document retrieval.
3. **Portal rendered the citation as "Unknown document".** `CitationCard`/`CitationChips`
   ignored the `file_name`, `file_version`, `sheet` and `columns` fields.
   Fix: label from `file_name`; a `tabular_file` card shows version, sheet and columns.
   Files: `src/portal/src/components/chat/CitationCard.tsx`, `CitationChips.tsx`.
   Test: `CitationCard.test.tsx` "renders a tabular_file citation by file name, version and columns".

The automated end-to-end test (row 55) stubs the LLMs and asserts on the envelope, not on
the rendered portal, so it could not catch 1–3.

## Environment issues (not defects in this change)

- The tenant's Azure store (`ner-tenant-managed-db.postgres.database.azure.com`) was
  unreachable (firewall), and `db-init` marked the data plane `migration_required` /
  `unreachable`. After the user added the host IP, `docker compose run --rm db-init`
  returned `outcome=up_to_date` and the status went back to `ready`.
- The circuit breaker then still refused content routes with 503, because
  `health_outcome=timeout` was stale: no beat runs `probe_tenant_data_plane_health`
  in this compose stack. Running the probe once by hand set it to `healthy`.
- Value hints persisted as `[[], ["closed"], [], []]`. The pane's scripted checkbox
  toggles did not reach React state. This is a harness limit, and hints are optional.

## Screenshots

The browser pane cannot write screenshots to disk. Each step above was checked on a live
pane screenshot during the session. To finish the evidence, capture and save these here:
`review.png` (review screen), `ready.png` (file list showing Ready), `chat-answer.png`
(answer with the expanded citation card).
