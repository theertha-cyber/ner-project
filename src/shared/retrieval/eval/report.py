import datetime
import json
from dataclasses import asdict

from src.shared.retrieval.eval.metrics import SCORING_RULE
from src.shared.retrieval.eval.runner import MatrixResult


def build_json_report(golden_set_name: str, query_count: int, matrix: MatrixResult) -> dict:
    configurations = []
    per_query: dict[str, dict] = {}

    for config_result in matrix.configurations:
        configurations.append({
            "name": config_result.name,
            "retrieval_config": asdict(config_result.retrieval_config),
            "degraded_query_count": config_result.degraded_query_count,
            "failed_query_count": config_result.failed_query_count,
            # A score against the synthetic fixture is not evidence about tenant
            # behaviour, and a score under one rule is not comparable with another.
            # Both travel with every reported number.
            "corpus": config_result.corpus,
            "scoring_rule": config_result.scoring_rule,
            "latency_ms_by_query_class": {
                cls: {"count": len(v), "mean": sum(v) / len(v), "max": max(v)}
                for cls, v in config_result.latency_by_query_class().items() if v
            },
            "aggregate": asdict(config_result.aggregate) if config_result.aggregate else None,
        })
        for run in config_result.per_query:
            per_query.setdefault(run.query_id, {})[config_result.name] = {
                "recall_at_k": run.metrics.recall_at_k,
                "precision_at_k": run.metrics.precision_at_k,
                "mrr_at_k": run.metrics.mrr_at_k,
                "ndcg_at_k": run.metrics.ndcg_at_k,
                "skipped": run.metrics.skipped,
                "skip_reason": run.metrics.skip_reason,
                "degraded": run.degraded,
                "failed": run.metrics.failed,
                "query_class": run.query_class,
                "latency_ms": run.latency_ms,
                "error": run.error,
            }

    corpora = {c["corpus"] for c in configurations}
    return {
        "run_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "golden_set": golden_set_name,
        "query_count": query_count,
        "corpus": corpora.pop() if len(corpora) == 1 else sorted(corpora),
        "scoring_rule": SCORING_RULE,
        "configurations": configurations,
        "per_query": per_query,
        "aggregate": {c["name"]: c["aggregate"] for c in configurations},
    }


def build_markdown_summary(report: dict) -> str:
    lines = [
        f"# Retrieval Eval Report — {report['golden_set']}",
        "",
        f"Run: {report['run_timestamp']} · Queries: {report['query_count']}",
        f"Corpus: `{report.get('corpus')}` · Scoring rule: `{report.get('scoring_rule')}`",
        "",
        "| Configuration | recall@k | precision@k | MRR@k | nDCG@k | degraded | failed |",
        "|---|---|---|---|---|---|---|",
    ]

    best_name, best_ndcg = None, -1.0
    for config in report["configurations"]:
        agg = config["aggregate"]
        if agg is None:
            continue
        # Degraded and failed queries score zero and stay in the denominator, so the
        # counts explain the score rather than sitting beside an unaffected one.
        lines.append(
            f"| {config['name']} | {agg['recall_at_k']:.3f} | {agg['precision_at_k']:.3f} | "
            f"{agg['mrr_at_k']:.3f} | {agg['ndcg_at_k']:.3f} | "
            f"{config['degraded_query_count']} | {config.get('failed_query_count', 0)} |"
        )
        if agg["ndcg_at_k"] > best_ndcg:
            best_ndcg = agg["ndcg_at_k"]
            best_name = config["name"]

    lines.append("")
    if best_name is not None:
        lines.append(f"**Best nDCG@k**: `{best_name}` ({best_ndcg:.3f})")

    latency_rows = [
        (config["name"], cls, stats)
        for config in report["configurations"]
        for cls, stats in sorted(config.get("latency_ms_by_query_class", {}).items())
    ]
    if latency_rows:
        lines.extend([
            "",
            "## Latency by query class",
            "",
            "| Configuration | Query class | n | mean ms | max ms |",
            "|---|---|---|---|---|",
        ])
        for name, cls, stats in latency_rows:
            lines.append(f"| {name} | {cls} | {stats['count']} | {stats['mean']:.0f} | {stats['max']:.0f} |")

    failed = [
        (qid, cfg_name, data)
        for qid, by_config in report["per_query"].items()
        for cfg_name, data in by_config.items()
        if data.get("error")
    ]
    if failed:
        lines.append("")
        lines.append("## Failed queries")
        for qid, cfg_name, data in failed:
            lines.append(f"- `{qid}` ({cfg_name}): {data['error']}")

    return "\n".join(lines)


def write_report(report: dict, json_path: str, markdown_path: str) -> None:
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    with open(markdown_path, "w", encoding="utf-8") as f:
        f.write(build_markdown_summary(report))
