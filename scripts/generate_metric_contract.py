"""Regenerate `docs/observability/metric-contract.md` from the live declarations.

    python scripts/generate_metric_contract.py

The contract is generated rather than written because a hand-maintained list of families
and label values drifts within one sprint, and a drifted contract is worse than none — a
dashboard built against it silently matches nothing. Run this after adding or changing a
family in `src/shared/observability/domain_metrics.py`.
"""

import pathlib
import sys

sys.path.insert(0, ".")

from src.shared.observability import domain_metrics as dm  # noqa: E402

GROUPS = [
    ("Tenant safety", ("ner_tenant_mismatch", "ner_search_path", "ner_auth_", "ner_rate_limit")),
    ("Chat — guardrails, resolution, retrieval", ("ner_guardrail", "ner_entity_resolution", "ner_retrieval", "ner_rerank")),
    ("Chat — SQL generation and execution", ("ner_sql_",)),
    ("Chat — LLM usage and answers", ("ner_llm_", "ner_answer", "ner_chat_")),
    ("Extraction and projection", ("ner_extraction", "ner_projection")),
    ("Celery queues", ("ner_celery",)),
    ("Model serving", ("ner_inference", "ner_model_")),
    ("Training", ("ner_training",)),
]

HEADER = """# Metric contract

Every metric family this platform emits, its labels, and the closed set of values each
label may carry. Generated from the declarations in
`src/shared/observability/domain_metrics.py`, which is the only place a family or a label
is defined — no call site anywhere constructs a metric or names a label.

This is the input story 5.1's dashboards and alert rules are built against. Two properties
make it usable as a contract rather than as documentation:

- **Every label's value set is finite and written out.** The number of series a family can
  produce is therefore the product of its enumerations and is computable here, before
  anything ships, rather than discovered when the endpoint gets slow. A value outside the
  set is coerced to `other` at record time; it never mints a new series.
- **`tenant_id` appears on exactly five families**, listed at the end. Adding a sixth is a
  reviewed diff against `TENANT_LABEL_ALLOWLIST` and fails the build until the list is
  amended.

Two things are deliberately absent from every family below, and both would look useful:

- **Model quality.** No family exposes F1, precision, recall or loss. MLflow versions those
  against the run, the params and the artifact; a Prometheus copy would be a second source
  of truth with worse fidelity and a shorter retention window. Dashboards link to MLflow.
- **Entity type.** Entity types are tenant-configured, so the value set is neither
  enumerable here nor free of the tenant's own vocabulary — a schema carrying
  `policy_holder` and `claim_number` identifies an insurer to everyone with dashboard
  access. Per-type counts live on the extraction run's span instead, where they are
  tenant-scoped and expire with the trace.

"""

FOOTER_TEMPLATE = """
## The tenant-label allowlist

These five families, and only these, may carry `tenant_id`:

{allowlist}

They are per-tenant consumption attribution. That is the one question trace sampling makes
impossible to answer accurately — a sampled trace gives a consumption figure that is wrong
by construction, and a billing number has to be exact. Everything else a tenant label could
answer is answerable by joining a trace, where `tenant_id` already lives and access is
narrower than dashboard access.

The list is a written-out `frozenset`, not a prefix or a pattern. `ner_llm_*` would admit
families nobody reviewed, which is the same mistake at one remove.

## Totals

- Families: {family_count}
- Series if every enumerated combination occurs: {series_count} (excluding the tenant
  dimension, which is bounded by the tenant table rather than by an enumeration)
"""


def render_family(name: str, family: dm.Family) -> str:
    lines = [f"#### `{name}`", "", f"*{family.kind}* — {family.description}", ""]
    if not family.labels:
        lines.append("No labels.")
        lines.append("")
        return "\n".join(lines)

    lines.append("| Label | Values |")
    lines.append("|---|---|")
    for label in family.labels:
        if isinstance(label, dm._TenantLabel):
            values = "_the tenant's identifier — allowlisted, see below_"
        else:
            values = ", ".join(f"`{v}`" for v in sorted(label.values))
        lines.append(f"| `{label.name}` | {values} |")
    lines.append("")
    if family.buckets:
        lines.append(f"Buckets: {', '.join(str(b) for b in family.buckets)}")
        lines.append("")
    lines.append(f"Series when every combination occurs: {family.series_count()}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    seen: set[str] = set()
    sections = []
    for title, prefixes in GROUPS:
        names = sorted(
            name
            for name in dm.FAMILIES
            if name.startswith(prefixes) and name not in seen
        )
        seen.update(names)
        if not names:
            continue
        body = "\n".join(render_family(name, dm.FAMILIES[name]) for name in names)
        sections.append(f"## {title}\n\n{body}")

    leftover = sorted(set(dm.FAMILIES) - seen)
    if leftover:
        body = "\n".join(render_family(name, dm.FAMILIES[name]) for name in leftover)
        sections.append(f"## Other\n\n{body}")

    allowlist = "\n".join(f"- `{name}`" for name in sorted(dm.TENANT_LABEL_ALLOWLIST))
    footer = FOOTER_TEMPLATE.format(
        allowlist=allowlist,
        family_count=len(dm.FAMILIES),
        series_count=sum(f.series_count() for f in dm.FAMILIES.values()),
    )

    out = pathlib.Path("docs/observability/metric-contract.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(HEADER + "\n".join(sections) + footer, encoding="utf-8")
    print(f"wrote {out} ({len(dm.FAMILIES)} families)")


if __name__ == "__main__":
    main()
