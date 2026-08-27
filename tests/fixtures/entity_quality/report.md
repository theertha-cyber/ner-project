# Entity Quality Eval Report

Run: 2026-08-14T08:16:06.830286+00:00 · Cases: 18 · Fixture: `tests/fixtures/entity_quality/fixture.jsonl`

| Configuration | precision | recall | F1 | exact value | entity type | hallucination |
|---|---|---|---|---|---|---|
| bert_only | 0.667 | 0.769 | 0.714 | 0.792 | 0.750 | 0.000 |
| bert_repairs | 0.731 | 0.792 | 0.760 | 0.833 | 0.792 | 0.000 |
| bert_repairs_postprocess | 0.731 | 0.792 | 0.760 | 0.833 | 0.792 | 0.000 |

## Attributed deltas

Adjacent pairs only. A first-versus-last comparison would credit the deterministic repairs to the post-processor.

| From | To | d F1 | d precision | d recall | d exact value | d entity type |
|---|---|---|---|---|---|---|
| bert_only | bert_repairs | +0.046 | +0.064 | +0.022 | +0.042 | +0.042 |
| bert_repairs | bert_repairs_postprocess | +0.000 | +0.000 | +0.000 | +0.000 | +0.000 |

## Release gate

- **Result**: PASS
- Model: `gpt-4o-mini` · Prompt: `v1`
