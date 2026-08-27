"""Renders the entity-quality comparison as JSON and as a readable summary.

Run it with:

    python -m src.shared.entity_eval.report

Writing both forms keeps the numbers diffable and the conclusion legible, matching what
`src/shared/retrieval/eval/report.py` already does for retrieval."""

import argparse
import datetime
import json
from pathlib import Path

from src.shared.entity_eval.fixture import load_fixture
from src.shared.entity_eval.runner import CONFIGURATIONS, evaluate_gate, run_fixture

DEFAULT_FIXTURE = Path("tests/fixtures/entity_quality/fixture.jsonl")
DEFAULT_JSON = Path("tests/fixtures/entity_quality/report.json")
DEFAULT_MARKDOWN = Path("tests/fixtures/entity_quality/report.md")


def build_report(fixture_path: Path) -> dict:
    cases = load_fixture(fixture_path)
    result = run_fixture(cases)
    gate = evaluate_gate(result)
    return {
        "run_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "fixture": str(fixture_path).replace("\\", "/"),
        "case_count": len(cases),
        "class_counts": _class_counts(cases),
        **result.as_dict(),
        "gate": gate.as_dict(),
    }


def _class_counts(cases) -> dict:
    counts: dict[str, int] = {}
    for case in cases:
        counts[case.failure_class] = counts.get(case.failure_class, 0) + 1
    return dict(sorted(counts.items()))


def build_markdown(report: dict) -> str:
    lines = [
        "# Entity Quality Eval Report",
        "",
        f"Run: {report['run_timestamp']} · Cases: {report['case_count']} · "
        f"Fixture: `{report['fixture']}`",
        "",
        "| Configuration | precision | recall | F1 | exact value | entity type | hallucination |",
        "|---|---|---|---|---|---|---|",
    ]
    by_name = {c["configuration"]: c for c in report["configurations"]}
    for name in CONFIGURATIONS:
        config = by_name.get(name)
        if config is None:
            continue
        lines.append(
            f"| {name} | {config['precision']:.3f} | {config['recall']:.3f} | "
            f"{config['f1']:.3f} | {config['exact_value_accuracy']:.3f} | "
            f"{config['entity_type_accuracy']:.3f} | {config['hallucination_rate']:.3f} |"
        )

    lines.extend([
        "",
        "## Attributed deltas",
        "",
        "Adjacent pairs only. A first-versus-last comparison would credit the "
        "deterministic repairs to the post-processor.",
        "",
        "| From | To | d F1 | d precision | d recall | d exact value | d entity type |",
        "|---|---|---|---|---|---|---|",
    ])
    for delta in report["deltas"]:
        lines.append(
            f"| {delta['from']} | {delta['to']} | {delta['f1']:+.3f} | "
            f"{delta['precision']:+.3f} | {delta['recall']:+.3f} | "
            f"{delta['exact_value_accuracy']:+.3f} | {delta['entity_type_accuracy']:+.3f} |"
        )

    gate = report["gate"]
    lines.extend(["", "## Release gate", ""])
    lines.append(f"- **Result**: {'PASS' if gate['passed'] else 'FAIL'}")
    lines.append(f"- Model: `{gate['postprocess_model']}` · Prompt: `{gate['postprocess_prompt_version']}`")
    for reason in gate["reasons"]:
        lines.append(f"- Blocked: {reason}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Entity-quality evaluation report")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()

    report = build_report(args.fixture)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.markdown_out.write_text(build_markdown(report), encoding="utf-8")
    print(build_markdown(report))


if __name__ == "__main__":
    main()
