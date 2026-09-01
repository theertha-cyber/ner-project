# Enterprise Chatbot Porting — Consolidated Findings & Integration Plan

**Status:** Draft for review
**Date:** 2026-08-20
**Sources:** (1) `InApp_Enterprise_Chatbot_Portting_Findings.docx` — structured writeup; (2) raw meeting notes (per-engagement, unstructured). Both are notes from the *same* meeting, taken by two people.
**Purpose:** Consolidate what was discussed about InApp's existing enterprise chatbot engagements, and define which of those capabilities we fold into the NER Platform chat assistant, in what order, and how.

---

## 0. How to read this document

The two note sets are complementary rather than redundant:

- The **raw notes** preserve *which engagement* each behaviour came from (Gordian, DCF, FinFrock, Axiom, Intuitive). The formal writeup drops the engagement names and merges everything into a single narrative.
- The **formal writeup** preserves the *flow-level detail* (step-by-step query flows, validation criteria, the challenge table) that the raw notes only gesture at.

Section 1 re-attaches the engagement names to the behaviours. Section 2 onward is the merged view. Where the two sources disagree, it is called out explicitly in **§3 Open questions** — those are not resolved here.

---

## 1. Engagement-by-engagement findings

### 1.1 Gordian — proposals, RBAC, Pandas + graphs

| Aspect | Finding |
|---|---|
| Domain | A set of **proposals**, originally delivered as PDFs. |
| Hierarchy | **Owner → Contractor → Proposal**. This hierarchy is enforced *inside the chatbot* via RBAC — a user only ever reasons over the slice of data their role permits. |
| Ingestion | PDF readers were evaluated; **PyMuPDF** was chosen but **could not reliably extract table data**. This was the blocker that forced the change of data source. |
| Data source pivot | PDF → **Parquet** → converted to **CSV**, loaded as a Pandas DataFrame. The chatbot ultimately queries tabular data, not documents. |
| Framework | **LangChain**. |
| Agent | A **custom agent**, not an off-the-shelf LangChain agent — single-agent architecture calling multiple tools. |
| Tools | Pandas-query tool, graph tool, execution tool. |
| LLM data exposure | The **full CSV/Excel was never sent to the LLM**. Only a **subset of columns, plus column descriptions** (and distribution/metadata) were provided. The model generates a query; the query runs against the real data locally. |
| Memory | **No conversation memory** was implemented. |
| Delivery | Shipped as a **PWA (Progressive Web App)**. |
| Headline capability | **Graph generation** — treated as the main selling point of the product. |

**Follow-up / clarification behaviour.** Graph requests are under-specified by nature, so the bot must interrogate the user before it can render anything: what time period, what data, what goes on the X axis, what goes on the Y axis, what chart type. Time-period clarification was singled out as the most important — without it a chart is scoped wrong and quietly misleading.

### 1.2 DCF — GraphRAG trial

GraphRAG was attempted here. The formal writeup's GraphRAG section describes a **skills/experience knowledge-graph** use case: professional-level Python experience, frameworks known, years of experience, project experience, skills such as Python and SQL — with **question answering and scoring against stated criteria**. Flow: question → identify required skills/criteria → retrieve relevant knowledge → evaluate against criteria → produce a score or structured answer. A defined schema backed the knowledge representation so questions map onto structured fields and relationships.

### 1.3 FinFrock — deterministic text-to-SQL

| Aspect | Finding |
|---|---|
| Data | A SQL database with **multiple related tables**. |
| Approach | Fully **deterministic**: the LLM writes a SQL query, the query produces the answer. |
| LLM context | The **schema** is supplied as context, plus **few-shot examples**. |
| The hard part | Teaching the model *how to filter* and *how to join across tables* correctly. |

### 1.4 Axiom — multi-tenant schema-aware SQL at scale

| Aspect | Finding |
|---|---|
| Framework | **LangGraph** (not plain LangChain). |
| Data | Vendor-specific tables for electronic goods. **Same schema shape for every tenant.** |
| Context supplied | Schema design information, **column descriptions**, relations, and cross-table mappings. |
| Schema retrieval | **Azure AI Search** — full-text search across the schema documents, **indexed per tenant**, so the relevant schema slice is cheap to fetch at query time. *(The formal writeup instead records Elasticsearch as the schema/search layer, with Spark explored for full-text search and performance — see §3.)* |
| Safety | Generated SQL is **sanitised** before execution. |
| Trust | A **confidence score** is attached to each generated query. |

**The schema-aware query flow** (from the writeup):

1. User asks a question.
2. Relevant entities / terms are identified.
3. Schema and metadata are searched.
4. Relevant tables, columns and relationships are retrieved.
5. The required schema context is assembled.
6. A database query is generated.
7. The query is **validated against the schema** — table existence and naming, column availability, schema consistency, relationships/joining patterns, query-to-schema alignment.
8. The validated query executes against the real database.
9. The result is returned.

### 1.5 Intuitive — multimodal medical retrieval

| Aspect | Finding |
|---|---|
| Domain | Medical — **surgical equipment with training modules**. Users ask questions about the equipment. |
| Retrieval behaviour | A single question returns **every relevant artefact**: documents, notes, and **video with a timestamp** pointing at the answer. |
| Technology | **FastGraphRAG**. |
| Limitation | **No conversational memory.** |

---

## 2. Merged view — the cross-cutting takeaways

### 2.1 The privacy boundary is the single most reusable idea

Every structured-data engagement independently converged on the same architecture: **the LLM sees the shape of the data, never the data**.

```
user question
  → reasoning layer receives schema / column descriptions / metadata only
  → an operation is generated (SQL, or a Pandas expression)
  → the operation is validated
  → the operation executes against the real data, outside the model
  → the result is returned
```

This was valuable **commercially as much as technically** — Gordian's team could tell the client, truthfully and simply, "your dataset is not passed to the LLM." That is a sentence worth being able to say to every tenant.

### 2.2 Generate-then-execute, not generate-the-answer

Gordian (Pandas), FinFrock (SQL) and Axiom (SQL) are the same pattern in different syntax: the model's job is to emit a *program*, and a deterministic runtime produces the number. This eliminates arithmetic hallucination outright and makes every answer reproducible and auditable.

### 2.3 Schema quality is the actual bottleneck

The writeup's challenge table is unambiguous about where these systems fail — and none of the failures are model failures:

| Challenge | Observation |
|---|---|
| Schema consistency | Different databases use different table/column naming conventions; mapping is hard. |
| Metadata quality | Query generation is only as good as the table/column descriptions. |
| Conditional constraints | Business rules, fixed date ranges, and similar constraints must be **explicitly represented as metadata** — the model cannot infer them. |
| Scoring accuracy | Confidence scores do not reliably indicate whether a query is actually correct. |

Axiom's answer — treat schema + descriptions + relationships as a **searchable, per-tenant indexed artefact** rather than a static prompt blob — is the one that scales past a handful of tables.

### 2.4 Two independent teams flagged the same gap: no conversation memory

Gordian and Intuitive both shipped without it. Our platform already has conversation context, and it should be treated as a differentiator rather than a checkbox.

### 2.5 Retrieval should return *addresses*, not just prose

Intuitive's video-with-timestamp result is the strongest UX idea in the set: an answer that points precisely at its evidence, in whatever medium the evidence lives in.

### 2.6 Agreed direction for our platform (from the raw notes)

Four things were named as what we should build:

1. **Ingestion of all document types** — not a single format.
2. **Graph / knowledge-graph retrieval.**
3. **Faceted search dashboard** — entity-wise filtering.
4. **Data export.**

Plus two technologies to evaluate: **FastGraphRAG** and **RAG-Anything** (multimodal / heterogeneous content).

---

## 3. Open questions — where the two note sets disagree

These need to be confirmed with the people who ran the engagements before they land in any plan.

| # | Point | Formal writeup says | Raw notes say | Why it matters |
|---|---|---|---|---|
| 1 | Gordian's agent | A **LangChain DataFrame Agent** generates the Pandas query | **No built-in agent** was used — a **custom agent** was written | Determines whether there is code we can lift directly, or only a pattern to re-implement. |
| 2 | Axiom's schema search layer | **Elasticsearch**, with **Spark** explored for full-text search/performance | **Azure AI Search**, indexed per tenant | Decides what we stand up. We already run Postgres + pgvector; a third search dependency is a real cost. |
| 3 | GraphRAG ownership | Presented as one merged "GraphRAG-based knowledge retrieval" section | Splits across **DCF** (GraphRAG trial) and **Intuitive** (FastGraphRAG, production) | Determines which one is a proven pattern and which was an experiment. |

---

## 4. Where the NER Platform stands today

Assessed against the current codebase, so the gap list below is real rather than assumed.

**Already built and shipping:**

| Capability | Where |
|---|---|
| LangGraph orchestration with **deterministic, non-model-decided routing** | `src/chat_api/graph/builder.py` |
| Guardrail → orchestrator → retrieval → prompt assembly → source assembly → generation | `src/chat_api/graph/nodes.py` |
| Text-to-SQL with a **table/column whitelist**, length cap, default LIMIT | `src/chat_api/services/sql_generator.py` |
| Query repair loop with a **closed set of attempt outcomes** and defect classification | `src/chat_api/services/sql_generator.py` |
| Least-privilege SQL execution role | `src/chat_api/services/sql_execution_role.py` |
| Pluggable retrieval tool registry — `semantic_retrieval`, `structured_retrieval` | `src/shared/retrieval/tools/` |
| Orchestration budget, per-entry status, partial-failure reporting, degraded-mode traces | `src/shared/retrieval/orchestrator.py` |
| Citations derived from **the evidence the prompt actually admitted** | `src/chat_api/services/context_assembler.py` |
| **Conversation memory / context** | `ChatState.conversation_context` |
| **Entity resolution + clarification turn** (behind a flag) | `src/chat_api/services/entity_resolver.py` |
| Multi-tenant schema isolation, JWT, rate limiting, widget keys | `src/chat_api/middleware/`, `api/v1/widget_keys.py` |
| PDF + image ingestion with OCR fallback, chunking, embeddings | `src/document_service/services/ocr_worker.py` |
| Annotation export | `src/annotation_service/api/v1/export.py` |

**We are already ahead of the reference engagements on:** deterministic routing (Axiom used LangGraph but model-led), conversation memory (Gordian and Intuitive both lacked it), citation fidelity, partial-failure handling, and multi-tenancy as a platform primitive rather than a per-project concern.

**Genuine gaps, mapped to findings:**

| Gap | Source | Notes |
|---|---|---|
| **Chart / graph generation** | Gordian | Nothing in the chat path renders a visualisation. This was Gordian's headline selling point. |
| **Clarification for under-specified requests** | Gordian | Entity-resolution clarification exists but is flag-gated and entity-scoped; there is no axis/time-range/chart-type clarification. |
| **Schema metadata catalogue + retrieval** | Axiom | `WHITELISTED_TABLES` is a hardcoded Python dict of bare column names — no descriptions, no relationships, no per-tenant indexing, no search. This is the single biggest structural gap. |
| **Confidence scoring on generated queries** | Axiom | We classify outcomes but do not score query-to-question alignment. |
| **External / tenant-owned database querying** | FinFrock, Axiom | We only query our own platform schema. |
| **Pandas / tabular file querying** | Gordian | No CSV / Parquet / XLSX ingestion path at all — `ALLOWED_EXTENSIONS` is `{pdf, jpg, jpeg, png, tif, tiff}`. |
| **Graph / GraphRAG retrieval** | DCF, Intuitive | No knowledge-graph tool in the registry. |
| **Multimodal retrieval with timestamps** | Intuitive | No video/audio ingestion; no timestamp-addressable evidence. |
| **Faceted search dashboard** | Agreed direction | No entity-wise structured filtering UI. |
| **Export from chat** | Agreed direction | Export exists for annotations, not for chat/extraction results. |
| **Hierarchical, record-level RBAC** | Gordian | We have tenant + role isolation; we do not have an owner→contractor→proposal-style *record-level* hierarchy filter. |

---

## 5. Integration plan

Ordered by (value × fit with what we already have) ÷ effort. Each item names the existing seam it plugs into, so nothing here requires re-architecting the chat graph.

### Phase 1 — high value, low structural risk

**1.1 Schema metadata catalogue** *(unblocks 1.2, 2.1, 3.3 — do this first)*

Replace the hardcoded `WHITELISTED_TABLES` dict with a first-class, per-tenant metadata store: table descriptions, column descriptions, value distributions / sample values, relationships and join paths, and **business constraints as explicit metadata** (the writeup is emphatic that these must be stated, not inferred). Retrieve the relevant slice per question instead of pasting the whole schema into every prompt.

*Start with Postgres full-text plus our existing pgvector index over the metadata documents — we already run both.* Only introduce a dedicated search service if that measurably fails at tenant scale. This sidesteps open question #2 rather than needing it answered.

**1.2 Query validation + confidence score**

Between generation and execution, validate against the catalogue on Axiom's five criteria — table existence, column availability, schema consistency, relationship/join validity, query-to-schema alignment — and emit a confidence score. Surface low confidence in the UI as a hedge or a clarification prompt rather than a silent answer. Heed the writeup's own warning: **the score is a signal, not a verdict**, so it must never gate execution on its own.

**1.3 Chart generation tool**

Register a `chart_generation` tool in the existing `ToolRegistry` (`src/shared/retrieval/tools/`), so it inherits budget, timeout, degraded-mode and trace handling for free. It consumes the rows `structured_retrieval` already returns and emits a chart spec — **a declarative spec (e.g. Vega-Lite / Chart.js config) rendered client-side, not model-authored plotting code**. That reproduces Gordian's headline capability without introducing arbitrary code execution into the request path.

**1.4 Chart clarification turn**

Reuse the `pending_clarification` mechanism already built for entity resolution to ask Gordian's five questions when a visualisation request is under-specified — time period first. This is an extension of an existing state field, not a new subsystem.

**1.5 Export from chat**

Let a business user take any chat result set to CSV / XLSX. Small, and it closes one of the four named directions.

### Phase 2 — new surface area, well-understood

**2.1 Tabular file ingestion (CSV / XLSX / Parquet)**

Add to `ALLOWED_EXTENSIONS` and route to a tabular handler instead of OCR. **Learn Gordian's lesson directly: do not try to extract tables out of PDFs.** PyMuPDF failed at exactly this, and the fix was to accept the tabular format upstream. Land the data in Postgres as a queryable per-tenant table so it flows into the existing SQL path — strictly better than Gordian's in-memory Pandas approach, and it gets validation, RBAC and the audit trail for free.

**2.2 Faceted search dashboard**

Entity-wise structured filtering over `document_entities`, driven by the tenant's configured entity types. This complements semantic and SQL retrieval rather than replacing either, and is the most directly useful thing for a business user staring at a large extraction result set.

**2.3 Record-level RBAC hierarchy**

Generalise Gordian's owner→contractor→proposal pattern into a configurable record-scope filter applied at retrieval time — enforced in the **tool layer**, below the LLM, so no prompt can talk its way around it.

### Phase 3 — evaluate before committing

**3.1 Graph retrieval** — Register a graph tool alongside the existing two and A/B it against semantic retrieval on relationship-heavy questions. Evaluate **FastGraphRAG** (Intuitive's production choice) ahead of vanilla GraphRAG. Gate on a measured win: graph construction cost is real and recurring.

**3.2 Multimodal / heterogeneous content (RAG-Anything)** — Evaluate for video, audio and mixed documents, with Intuitive's **timestamp-addressable evidence** as the acceptance bar. Anything less is not worth the ingestion complexity.

**3.3 External tenant database connector** — Generalise the SQL path into a connector that points at a tenant's own database rather than only our schema. Highest ceiling in the set, and the largest security surface — it should not start until 1.1 and 1.2 are proven in production on our own schema.

### Explicitly not adopted

| Rejected | Reason |
|---|---|
| PDF table extraction | Failed for Gordian; superseded by 2.1. |
| Model-authored Python/Pandas execution in the request path | Arbitrary code execution against tenant data. The generate-then-execute *principle* is adopted; the executor is SQL, which we already validate, whitelist and run under a least-privilege role. |
| Shipping as a separate PWA | We already have a portal and an embeddable widget. |
| A separate Elasticsearch/Spark deployment | See 1.1 — start with what we run. Revisit only on measured need. |

---

## 6. Deployment items raised

Two logistics items were noted and are currently unowned:

- **Request a VM** for the deployment.
- **Ask ITS to add the domain.**

---

## 7. Key takeaway

The existing InApp chatbots are **not one product to port** — they are a set of independently-proven enterprise AI behaviours, and the platform's job is to absorb the behaviours without inheriting the per-project implementations.

The NER Platform already has the harder half: deterministic orchestration, multi-tenancy, conversation memory, citation fidelity, and a validated SQL path with a least-privilege executor — all things the reference engagements either lacked or rebuilt per client. What we are missing is mostly **surface**: a real schema metadata layer, charts, faceted filtering, export, and tabular ingestion.

The single highest-leverage item is the **schema metadata catalogue (1.1)**. It is the thing standing between our hardcoded five-table whitelist and a genuinely schema-aware assistant, and it unblocks confidence scoring, tabular ingestion and the external-database connector behind it.

---

## 8. Immediate next steps

1. Resolve the three discrepancies in **§3** with the engagement teams.
2. Confirm whether any Gordian or Axiom code is available to lift, or whether these are patterns to re-implement.
3. Size Phase 1 and put dates against it; fold into `docs/production-plan.md`.
4. Assign owners to the two deployment items in **§6**.
