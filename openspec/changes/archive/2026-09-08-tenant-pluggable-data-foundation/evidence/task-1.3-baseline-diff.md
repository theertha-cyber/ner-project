# Task 1.3 — Hygiene group leaves the pass/fail set unchanged

No test file was modified for group 1.

| Run | Command | Result |
|---|---|---|
| Baseline (`main`, commit `ea95bb5`) | `pytest -q --continue-on-collection-errors` | 94 failed, 2185 passed, 33 skipped, 33 errors |
| After group 1 (`schema_for_tenant` + engine resolver) | same | 84 failed, 2194 passed, 33 skipped, 34 errors |

The whole-suite id sets differ by 13 entries (`baseline_ids.txt` vs `after_group1_ids.txt`), all in
`test_entity_query.py`, `test_extraction_worker_normalization.py`, `test_dashboard_summary.py`,
`test_dashboard_summary_roles.py`, and `test_training_jobs.py`. These are order- and shared-database
dependent, not caused by this change. Isolating exactly those five files gives an identical result on
both trees:

```
clean tree  : 10 failed, 94 passed, 3 warnings in 165.97s
group-1 tree: 10 failed, 94 passed, 3 warnings in 139.47s
```

The suite is red on `main` before this change (see the baseline row); that pre-existing condition is
out of scope here. What task 1.3 asserts — that group 1 adds no failure — holds.
