# Retrieval Eval Report — retrieval_eval/golden_set.jsonl

Run: 2026-08-13T09:38:32.598539+00:00 · Queries: 32
Corpus: `synthetic-fixture` · Scoring rule: `zero-degraded`

| Configuration | recall@k | precision@k | MRR@k | nDCG@k | degraded | failed |
|---|---|---|---|---|---|---|
| dense_only | 0.900 | 0.360 | 1.000 | 0.920 | 0 | 0 |
| hybrid | 0.900 | 0.360 | 1.000 | 0.920 | 0 | 0 |

**Best nDCG@k**: `dense_only` (0.920)

## Latency by query class

| Configuration | Query class | n | mean ms | max ms |
|---|---|---|---|---|
| dense_only | document_content | 32 | 2 | 33 |
| hybrid | document_content | 32 | 2 | 34 |