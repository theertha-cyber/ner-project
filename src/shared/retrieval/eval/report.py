import datetime
import json
from dataclasses import asdict

from src.shared.retrieval.eval.runner import MatrixResult


def build_json_report(golden_set_name: str, query_count: int, matrix: MatrixResult) -> dict:
    configurations = []
    per_query: dict[str, dict] = {}

    for config_result in matrix.configurations:
        configurations.append({
            "name": config_result.name,
            "retrieval_config": asdict(config_result.retrieval_config),
            "degraded_query_count": config_result.degraded_query_count,
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
                "error": run.error,
            }

    return {
        "run_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "golden_set": golden_set_name,
        "query_count": query_count,
        "configurations": configurations,
        "per_query": per_query,
        "aggregate": {c["name"]: c["aggregate"] for c in configurations},
    }


def build_markdown_summary(report: dict) -> str:
    lines = [
        f"# Retrieval Eval Report — {report['golden_set']}",
        "",
        f"Run: {report['run_timestamp']} · Queries: {report['query_count']}",
        "",
        "| Configuration | recall@k | precision@k | MRR@k | nDCG@k | degraded queries |",
        "|---|---|---|---|---|---|",
    ]

    best_name, best_ndcg = None, -1.0
    for config in report["configurations"]:
        agg = config["aggregate"]
        if agg is None:
            continue
        degraded_note = f"{config['degraded_query_count']}" + (" (excluded from baseline)" if config["degraded_query_count"] else "")
        lines.append(
            f"| {config['name']} | {agg['recall_at_k']:.3f} | {agg['precision_at_k']:.3f} | "
            f"{agg['mrr_at_k']:.3f} | {agg['ndcg_at_k']:.3f} | {degraded_note} |"
        )
        if agg["ndcg_at_k"] > best_ndcg:
            best_ndcg = agg["ndcg_at_k"]
            best_name = config["name"]

    lines.append("")
    if best_name is not None:
        lines.append(f"**Best nDCG@k**: `{best_name}` ({best_ndcg:.3f})")

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
