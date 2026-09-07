# Local Development: Clean Database Rebuild

Use this procedure when the local `ner_dev` database has drifted from what the
Alembic migration chain declares — for example, `docker compose up`'s
`db-init` service fails with a schema-verification error (see
`src/gateway/verify_schema.py`), or you're seeing errors like
`column "..." does not exist` or `relation "..." does not exist` for tables
the application expects.

## This procedure is destructive

**Running the steps below permanently deletes every tenant, user, document,
annotation, model version, and training run in your local `postgres-data`
Docker volume.** There is no undo. If anything in the current database is
worth keeping, take a backup first:

```bash
docker exec ner-project-postgres-test-1 pg_dump -U ner ner_dev > ner_dev_backup.sql
```

The local database is treated as disposable dev data — this is the intended
and supported remedy for a drifted database, not a last resort.

## Procedure

Run these in order. Do not skip the build step — the running containers may
predate migrations or code changes on disk, in which case reapplying
migrations against an old image reproduces the same drift you're trying to
fix.

```bash
docker compose down -v      # Removes the postgres-data volume and all its contents
docker compose build        # Rebuilds images from the current working tree
docker compose up           # Applies the full migration chain to an empty database, seeds, and verifies
```

`db-init` runs `alembic upgrade head`, `python -m src.gateway.seed`, and
`python -m src.gateway.verify_schema`, in that order, before any application
service starts. If verification finds drift, `db-init` exits non-zero and
none of the dependent services (`gateway`, `document_service`,
`extraction_service`, `annotation_service`, `training_service`,
`celery_worker`, `celery_worker_extraction`) will start — check the `db-init`
logs for the specific schema, table, or column named as missing.

## Confirming the rebuild worked

```bash
docker exec ner-project-postgres-test-1 psql -U ner -d ner_dev -c "SELECT version_num FROM alembic_version;"
docker exec ner-project-postgres-test-1 psql -U ner -d ner_dev -c "\d tenant_template.documents"
docker exec ner-project-postgres-test-1 psql -U ner -d ner_dev -c "\dt public.*"
```

- `alembic_version` should equal the highest revision number under
  `alembic/versions/`.
- `tenant_template.documents` should exist and include `purpose`,
  `content_type`, `file_size`, and `blob_path`.
- `public` should **not** contain `model_versions` — that table is a
  test-fixture artifact (`scripts/setup_test_db.py`) and should never appear
  in `ner_dev`.

Then exercise the paths that regress most visibly under drift: create an
entity type, create a tenant and upload a document to it, and load the
`system_admin` dashboard.

---

# Local Observability Stack

`docker compose up` also starts five observability containers. They exist so the
platform's telemetry is inspectable on a laptop, without the production cluster.

| Container | URL | What it holds |
|---|---|---|
| `grafana` | <http://localhost:3001> | The single pane. Prometheus, Loki and Tempo are provisioned as datasources; anonymous access is enabled because this is a laptop-scoped viewer, not a deployed service. |
| `otel-collector` | `localhost:4317` (gRPC), `localhost:4318` (HTTP) | Receives OTLP from all ten processes and fans traces to Tempo, metrics to Prometheus and logs to Loki. |
| `tempo` | <http://localhost:3200> | Traces. Retention is one hour — this is for diagnosis, not history. |
| `loki` | <http://localhost:3100> | Logs, from all ten processes over OTLP. Query them in Grafana's Explore with `{service_name="gateway"}`. |
| `prometheus` | <http://localhost:9090> | Metrics, scraped from each service's `/metrics` plus the collector's `:8889`. |

Grafana is on **3001**, not 3000: the portal already owns 3000.

## Configuration

Three settings govern telemetry, all in `.env`:

- `NER_TELEMETRY_PEPPER` — **required, no default.** Keys the HMAC that turns a
  user id into the `user_hash` on every record. Generate with
  `openssl rand -hex 32`. A service will not start without it. Rotating it
  breaks correlation of one user across the rotation, by design.
- `NER_OTLP_ENDPOINT` — where to export. `otel-collector:4317` inside compose,
  `localhost:4317` for a bare-metal run. **Empty disables export entirely**,
  which is the one-setting rollback if telemetry ever causes a problem.
- `NER_LOG_FORMAT` — `json` (default) or `console`. Set `console` locally if you
  read `docker logs` directly; the fields are the same, only the rendering
  differs.

## Reading the logs

Records are single-line JSON carrying `ts`, `level`, `service`, `event`,
`request_id`, `trace_id`, `tenant_id` and `user_hash`. To follow one request
across services:

```bash
docker compose logs --no-log-prefix | grep '"request_id": "abc-123"'
```

Or send the identifier yourself and grep for it:

```bash
curl -s -H "X-Request-ID: my-debug-id" http://localhost:8000/health -i
```

In Grafana, a record's `trace_id` links straight through to the trace in Tempo.

### Reading logs in Grafana

Every process writes each record twice: to stdout, where `docker logs` and the `grep`
above still work, and over OTLP to the collector, which forwards it to Loki. In Grafana's
Explore, pick the Loki datasource and start from the service:

```
{service_name="gateway"} |= "sql_attempt"
```

`service_name` and `service_instance_id` are the only stream labels; everything else the
record carries — `event`, `request_id`, `tenant_id`, `trace_id`, the JSON body itself — is
searchable but not indexed, which is what keeps a per-request identifier from becoming a
cardinality problem. Clicking `trace_id` on a record opens the trace in Tempo.

Export follows `NER_OTLP_ENDPOINT` like the other two signals: empty means stdout only,
which is the state of a bare-metal run and of the test suite. Records are batched onto a
background thread, and the exporter's own failures are never themselves exported, so a
stopped collector costs log delivery and nothing else.

## The release-gate telemetry scan

`scripts/telemetry_scan.py` drives one seeded flow against the running stack and then
reads back what Loki, Tempo and Prometheus actually hold, failing on any seeded value or
personal-data pattern in a log record, a span attribute or a metric label.

```bash
python scripts/telemetry_scan.py
```

It needs the stack up. Two flags are worth knowing:

```bash
python scripts/telemetry_scan.py --dry-run     # self-check only, no stack needed
python scripts/telemetry_scan.py --skip-flow   # scan telemetry already in the backends
```

`--dry-run` feeds the scan's own checkers records containing what they are meant to catch.
It takes under a second, needs nothing running, and is worth running before trusting a
clean result — a scan that has quietly stopped finding anything otherwise reports "PASS".

### Reading the output

The exit code says what happened, and the three failures need different responses:

| Code | Meaning | What to do |
|---|---|---|
| 0 | Clean, and the capture was big enough to mean it | Nothing |
| 1 | A seeded value or a personal-data pattern was found | Read the finding; it names the backend and prints the record |
| 2 | The capture was too thin to conclude anything | Check export, not the application — this is usually a stopped collector |
| 3 | A backend was unreachable | Bring the stack up; a gate that passes when it cannot read is not a gate |

Code 2 is the one to understand. A scan that queries three backends and reports clean
because nothing was exported is worse than no scan, because it produces evidence for a
gate that was never actually applied. So the record-count floor is checked *before* any
content check, and a capture below it fails on its own:

```
FAIL: the capture is too thin to conclude anything.
  logs: captured 0, expected at least 20
  spans: captured 0, expected at least 10
```

You can reproduce that state deliberately — it is how the rule was verified:

```bash
docker compose stop otel-collector
sleep 45
SCAN_WINDOW_SECONDS=30 python scripts/telemetry_scan.py --skip-flow   # exits 2
docker compose start otel-collector
```

A finding (code 1) prints the backend, what matched, and the record itself:

```
FAIL: 1 finding(s).
  [spans] seeded entity value: Priyadarshini Raghunathan
      in: span leak_probe candidate=Priyadarshini Raghunathan duration_ms=0.19
```

`SCAN_WINDOW_SECONDS` controls how far back it reads (default 600). Narrow it when you
have just planted something and do not want an earlier run's records in the window; widen
it when the flow is slow. `SCAN_LOKI_URL`, `SCAN_TEMPO_URL`, `SCAN_PROMETHEUS_URL` and
`SCAN_GATEWAY_URL` point it at a stack other than the local one.

The scan also runs in CI as its own job (`.github/workflows/telemetry-scan.yml`), separate
from the unit suite so that a slow, stack-dependent check never slows the fast feedback
loop — and so that disabling it would be a visible act rather than a quiet degradation.

## What is deliberately absent

No dashboards and no alert rules. Both belong to a later change; this one
supplies the signals they will be built from.

`tenant_id` is on records and spans, and on exactly **five metric families** — chat
requests, LLM tokens, LLM cost, extraction jobs and rate-limit rejections — named
explicitly in `TENANT_LABEL_ALLOWLIST` in `src/shared/observability/domain_metrics.py`.
Those five are per-tenant consumption attribution, which trace sampling makes impossible
to answer accurately any other way. Every other question a tenant label could answer is
answerable by joining a trace, where the identifier already lives and access is narrower.
Adding a sixth is a reviewed diff and fails the build until the list is amended.

Entity *type* names are on spans and log records and on **no metric label at all**. They
are tenant-configured, so a tenant that defines `policy_holder` and `claim_number` would
be identifiable from label values alone, in a store every dashboard user can read and with
a year of retention. The per-type breakdown ADR-010 needs lives on the extraction run's
span, which is tenant-scoped and expires with the trace.

## Running without the observability stack

Every service tolerates an unreachable collector: span export is batched onto a
background thread, so a stopped `otel-collector` costs telemetry and nothing
else. Requests are served normally and health checks keep passing.

```bash
docker compose stop otel-collector
curl -s http://localhost:8000/health    # still {"status": "ok"}
```
