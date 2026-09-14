# AGENTS.md — Baseline Agent Instructions

> **Read this file first, every session.** It is intentionally short.
> Detailed policy lives in `docs/` and must be loaded on demand — do not
> preload it.

---

## 1. First steps every session

1. Read `PROJECT.md` in the project root. It holds the project-specific
   context (tech stack, service topology, ADRs, conventions) that
   overrides the defaults referenced below. **If `PROJECT.md` does not
   exist, stop and tell the user.**
2. For the task at hand, load only the `docs/` files relevant to it
   (see the router below).

---

## 2. The invariants

This project uses **Spec-Driven Development (SDD)** via OpenSpec. Four
invariants govern everything else:

1. **No code is written before a spec exists and has been reviewed.**
   See `docs/workflow/sdd-pipeline.md` for exceptions and the full
   pipeline. If in doubt, treat it as spec-required.
2. **Every Acceptance Criterion in any `spec.md` must have at least one
   executable verification artifact that fails when the AC's `THEN`
   clause is violated.** See `docs/workflow/acceptance-criteria.md` for
   the full policy (allowed artifact types, what counts as satisfied,
   enforcement points).
3. **No secret may be hardcoded in source code, configuration files, or
   committed `.env` files.** All secrets (API keys, signing keys,
   passwords, access tokens, hashing peppers) MUST be loaded exclusively
   from environment variables sourced from a developer's local `.env`
   file that is excluded from version control via `.gitignore`. Default
   values for secret-class settings in `Settings` (e.g. `jwt_secret`,
   `minio_access_key`, `minio_secret_key`, `telemetry_pepper`) MUST NOT
   be present — the application SHALL fail at startup if they are absent
   from the environment. A pepper with a default is a committed secret:
   an HMAC under a publicly-known key is reversible by enumeration over
   a tenant's user list, which puts raw identity back into telemetry
   while the field still looks hashed.
4. **Log the shape of data, never the data.** No log record and no span
   attribute may contain generated SQL, prompt text, model answer text,
   document content, extracted entity values, credentials, bearer
   tokens, widget keys or connection strings. An event describing such
   an operation records its shape instead — counts, durations, outcomes,
   enumerated failure reasons, entity *type* names. Anything touching a
   sensitive value MUST be logged with structured fields
   (`logger.info("event_name", extra={...})`) rather than interpolated
   into the message, because the redaction filter in
   `src/shared/observability` contains structured fields reliably and
   arbitrary message strings only partially. Never log an exception
   object from a database or model call directly — a driver error quotes
   the offending literal back; log `type(exc).__name__` instead. Never
   use `print` or `traceback.print_exc()` in a service or worker: stdout
   is the one path no filter, formatter or level can reach, and the
   extraction worker printed 80 characters of document text that way for
   months. Never raise the level of `sqlalchemy.engine` — at INFO it
   echoes every statement with its bound parameters. Every process
   configures logging through
   `src.shared.observability.init_observability(service_name)` and
   nothing else calls `logging.basicConfig`.

   Metrics are declared, never created at a call site. Every metric
   family lives in `src/shared/observability/domain_metrics.py` with its
   exact label keys and a written-out, finite set of values for each
   one; call sites import a named recorder and pass typed arguments.
   A label value MUST be a module constant from the code being measured
   or a category function that strips payload — `_defect_class(defect)`,
   never `defect`; `type(exc).__name__`, never `str(exc)`. Prometheus has
   no redaction filter on any path, retention is long and dashboard
   access is broad, so a label is a worse place for tenant content than
   a log line, not a better one. An entity *type* name is safe in a log
   record and on a span, and is NOT safe as a metric label: entity types
   are tenant-configured, so the value set is neither enumerable at
   declaration nor free of the tenant's own vocabulary. Adding a
   `tenant_id` label requires amending `TENANT_LABEL_ALLOWLIST` in the
   same file, which is a reviewed diff and fails the build until it is
   made. Span attributes follow every rule above: they reach the same
   collector as the logs, and the release-gate scan
   (`scripts/telemetry_scan.py`) reads spans and metric labels as well as
   log records.

---

## 3. Router — where the rules live

Load each file only when the current task matches its "when to read"
column. Do not read them all upfront.

| Topic | File | When to read |
|---|---|---|
| SDD pipeline & exceptions | `docs/workflow/sdd-pipeline.md` | Starting any feature/fix/refactor; deciding if a spec is required. |
| Skills catalog | `docs/workflow/skills-catalog.md` | Choosing which skill to invoke. |
| OpenSpec artifacts & delta-spec rules | `docs/workflow/openspec-artifacts.md` | Creating, validating, or archiving a change. |
| AC verification policy | `docs/workflow/acceptance-criteria.md` | Writing or reviewing ACs; pairing tasks with tests; deciding if an AC is satisfied. |
| Microservice patterns & pattern defaults | `docs/architecture/microservice-patterns.md` | Writing or reviewing any spec that touches service boundaries, resilience, or data ownership. |
| ADR discipline | `docs/architecture/adr-discipline.md` | Proposing, superseding, or enforcing an ADR. |
| Coding standards & commits | `docs/standards/coding-standards.md` | Implementing tasks, writing tests, preparing commits. |
| Telemetry & observability | `src/shared/observability/` module docstrings | Adding a log call, a span or a metric; anything that touches invariant 4. |
| Context hygiene | `docs/agents/context-hygiene.md` | Running the reviewer council or any multi-step skill chain. |
| Guardrails (NOT-to-do + escalation) | `docs/agents/guardrails.md` | Before any irreversible action, or when uncertain whether to proceed. |
| Project ADRs | `docs/adr/` | When a spec or design references a specific ADR. |
| Feature decompositions | `docs/decomposition/` | Reviewing an existing feature breakdown before spec-generation or implementation planning. |

`docs/README.md` has the same index in a browsable form.

---

## 4. Conflict resolution

When instructions disagree, apply this precedence (highest wins):

```
ADR  >  PROJECT.md  >  AGENTS.md (this file)  >  docs/
```

## 5. When in doubt

Ask the user. Do not assume. Escalation triggers are listed in
`docs/agents/guardrails.md`.

---

## 6. Feature decomposition documents

When the `feature-decomposer` skill is used, it writes a structured
Markdown document to `docs/decomposition/<feature-name>.md`. Each file
contains:

- A one-paragraph feature summary.
- A numbered list of sub-modules (`[SM-01]`, `[SM-02]`, …), each with
  its OpenSpec domain, scope, key requirements, contracts/interfaces,
  prerequisites, and implementation notes.
- A dependency wave table (Wave 1, Wave 2, …) showing the suggested
  implementation sequence.
- A cross-cutting concerns section covering NFRs and shared utilities.

Load the relevant file from `docs/decomposition/` whenever you are
planning spec-generation or implementation for an already-decomposed
feature.
