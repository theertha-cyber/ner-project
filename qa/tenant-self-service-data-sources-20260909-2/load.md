# Load -- tenant-self-service-data-sources-20260909-2

Scope: protocol-level load against the deployed dev system http://localhost:8000 (single-environment ladder: dev is both lowest and highest non-production rung, so this run carries `load: yes`). Tooling: k6 v0.57.0 native binary (workspace-local for the run, removed afterwards; recorded in `.qa/state.json`). Load contract: base URL from the deployment record only; allowed host `localhost:8000` only. Auth via bearer token loaded from the process environment inside the script (`__ENV.K6_TOKEN`) — no literal in the script or command line. SLO source: design NFR-PERF-001 dev target (p95 ≤ 10 s, error rate < 1% applied as k6 thresholds `p(95)<10000`, `rate<0.01`).

## Stages

- smoke: 1 VU / 30 s — `GET /health` + authenticated `GET /api/v1/data-sources` with safe-shape check
- average: 5 VU / 60 s — same mix
- stress / soak: **not run** — small local dev box sized nothing like production; an SLO measured here would fail for reasons unrelated to the code

## Results

| Metric | SLO | Observed | Status |
|---|---|---|---|
| checks | all pass | **8154/8154 (100%)** | pass |
| `http_req_failed` | < 1% | **0.00% (0/5436)** | pass |
| `http_req_duration` p95 | < 10 000 ms | **avg 33.0 ms, med 28.9 ms, p90 53.8 ms, p95 57.5 ms, max 731.8 ms** | pass |
| throughput | no target | 5436 reqs at 60.3/s | no target |

Raw export: `../evidences/tenant-self-service-data-sources-20260909-2/load/k6-summary.json`; script: `../evidences/tenant-self-service-data-sources-20260909-2/load/k6-smoke-avg.js`.

## Decision

Load SLO **met** at smoke and average stages. Stress/soak not run on this dev box — named condition on the release gate.
