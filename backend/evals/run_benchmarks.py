from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Mapping, Sequence

from .datasets import RetrievalBenchmark, load_augmentation_file, load_beir
from .metrics import summarize_rankings
from .retrieval import BM25Index, augmented_query, augmentation_terms


def _safe_float(value: float) -> float:
    return round(float(value), 6)


def _limit_benchmark_queries(benchmark: RetrievalBenchmark, max_queries: int | None) -> RetrievalBenchmark:
    if not max_queries or max_queries <= 0 or len(benchmark.queries) <= max_queries:
        return benchmark
    scored_query_ids = [query_id for query_id in benchmark.qrels if query_id in benchmark.queries]
    selected_query_ids = scored_query_ids[:max_queries]
    if not selected_query_ids:
        selected_query_ids = list(benchmark.queries)[:max_queries]
    limited_queries = {query_id: benchmark.queries[query_id] for query_id in selected_query_ids}
    limited_qrels = {
        query_id: benchmark.qrels[query_id]
        for query_id in limited_queries
        if query_id in benchmark.qrels
    }
    return RetrievalBenchmark(
        name=f"{benchmark.name}_sample{len(limited_queries)}",
        corpus=benchmark.corpus,
        queries=limited_queries,
        qrels=limited_qrels,
    )


def _summary_delta(baseline: Mapping[str, float | int], candidate: Mapping[str, float | int]) -> Dict[str, float]:
    keys = ["precision_at_k", "recall_at_k", "ndcg_at_k", "map", "mrr"]
    return {key: _safe_float(float(candidate.get(key, 0.0)) - float(baseline.get(key, 0.0))) for key in keys}


def _run_retrieval_modes(
    benchmark: RetrievalBenchmark,
    modes: Sequence[str],
    top_k: int,
    metric_k: int,
    augmentation_by_query: Mapping[str, dict],
) -> Dict[str, object]:
    index = BM25Index.from_documents(benchmark.corpus)
    mode_reports: Dict[str, object] = {}
    per_query_audit: Dict[str, dict] = {}

    for mode in modes:
        rankings = {}
        for query_id, query in benchmark.queries.items():
            augmentation = augmentation_by_query.get(query_id, {}) if mode == "ontology" else {}
            search_text = augmented_query(query.text, augmentation)
            rankings[query_id] = index.search(search_text, top_k=top_k)
            if mode == "ontology":
                per_query_audit[query_id] = {
                    "raw_query": query.text,
                    "ontology_terms": augmentation_terms(augmentation),
                    "search_routing": augmentation.get("search_routing", []) if isinstance(augmentation, dict) else [],
                    "top_docs": [doc_id for doc_id, _ in rankings[query_id][: min(10, top_k)]],
                }
        summary = summarize_rankings(rankings, benchmark.qrels, metric_k)
        mode_reports[mode] = {
            "metrics": {key: _safe_float(value) if isinstance(value, float) else value for key, value in summary.as_dict().items()},
            "rankings": {
                query_id: [{"doc_id": doc_id, "score": _safe_float(score)} for doc_id, score in ranked[: min(20, top_k)]]
                for query_id, ranked in rankings.items()
            },
        }

    if "baseline" in mode_reports and "ontology" in mode_reports:
        mode_reports["ontology"]["delta_vs_baseline"] = _summary_delta(
            mode_reports["baseline"]["metrics"],
            mode_reports["ontology"]["metrics"],
        )

    return {"modes": mode_reports, "ontology_audit": per_query_audit}


def _write_markdown_report(report: Mapping[str, object], path: Path) -> None:
    modes = report.get("modes", {})
    lines = [
        f"# Benchmark Report: {report.get('benchmark_name')}",
        "",
        f"- Generated: {report.get('generated_at')}",
        f"- Corpus documents: {report.get('document_count')}",
        f"- Queries: {report.get('query_count')}",
        f"- Metric cutoff: @{report.get('metric_k')}",
        "",
        "## Retrieval Metrics",
        "",
        "| Mode | Precision | Recall | nDCG | MAP | MRR | Queries |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    if isinstance(modes, dict):
        for mode, mode_report in modes.items():
            if not isinstance(mode_report, dict) or "metrics" not in mode_report:
                continue
            metrics = mode_report.get("metrics", {})
            if not isinstance(metrics, dict):
                continue
            lines.append(
                "| {mode} | {precision:.4f} | {recall:.4f} | {ndcg:.4f} | {map_score:.4f} | {mrr:.4f} | {queries} |".format(
                    mode=mode,
                    precision=float(metrics.get("precision_at_k", 0.0)),
                    recall=float(metrics.get("recall_at_k", 0.0)),
                    ndcg=float(metrics.get("ndcg_at_k", 0.0)),
                    map_score=float(metrics.get("map", 0.0)),
                    mrr=float(metrics.get("mrr", 0.0)),
                    queries=int(metrics.get("query_count", 0)),
                )
            )
    ontology = modes.get("ontology") if isinstance(modes, dict) else None
    if isinstance(ontology, dict) and ontology.get("delta_vs_baseline"):
        delta = ontology["delta_vs_baseline"]
        lines.extend(
            [
                "",
                "## Ontology Lift",
                "",
                "| Metric | Delta |",
                "| --- | ---: |",
            ]
        )
        if isinstance(delta, dict):
            for key, value in delta.items():
                lines.append(f"| {key} | {float(value):+.4f} |")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- `baseline` uses the benchmark query text only.",
            "- `ontology` appends query-specific ontology expansion terms, reasoning lenses, and tacit context from the augmentation file.",
            "- The JSON report includes per-query ontology audit records for stakeholder inspection.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> Dict[str, object]:
    if args.benchmark != "beir":
        raise ValueError("Only BEIR-style retrieval benchmarks are supported by this runner today.")
    benchmark = load_beir(args.data_dir, split=args.split, name=args.name)
    max_queries = getattr(args, "max_queries", None)
    benchmark = _limit_benchmark_queries(benchmark, max_queries)
    augmentation_by_query = load_augmentation_file(args.augmentation_file)
    modes = [mode.strip() for mode in args.modes.split(",") if mode.strip()]
    if not modes:
        modes = ["baseline"]

    report = {
        "benchmark_name": benchmark.name,
        "benchmark_type": args.benchmark,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "document_count": len(benchmark.corpus),
        "query_count": len(benchmark.queries),
        "max_queries": max_queries,
        "top_k": args.top_k,
        "metric_k": args.metric_k,
        "augmentation_file": str(args.augmentation_file or ""),
    }
    report.update(_run_retrieval_modes(benchmark, modes, args.top_k, args.metric_k, augmentation_by_query))

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{benchmark.name}_retrieval_report.json"
    markdown_path = output_dir / f"{benchmark.name}_retrieval_report.md"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_markdown_report(report, markdown_path)
    return {"json_report": str(report_path), "markdown_report": str(markdown_path), **report}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run standardized biomedical retrieval benchmarks.")
    parser.add_argument("--benchmark", default="beir", choices=["beir"], help="Benchmark loader to use.")
    parser.add_argument("--data-dir", required=True, help="Directory containing BEIR corpus.jsonl, queries.jsonl, and qrels.")
    parser.add_argument("--split", default="test", help="Qrels split name for BEIR-style qrels/test.tsv.")
    parser.add_argument("--name", default=None, help="Name to use in output reports.")
    parser.add_argument("--augmentation-file", default=None, help="JSON file keyed by query id with ontology augmentation payloads.")
    parser.add_argument("--modes", default="baseline,ontology", help="Comma-separated modes: baseline,ontology.")
    parser.add_argument("--top-k", type=int, default=100, help="Number of documents to retrieve per query.")
    parser.add_argument("--metric-k", type=int, default=10, help="Cutoff for metrics such as nDCG@K and Precision@K.")
    parser.add_argument("--max-queries", type=int, default=None, help="Optional deterministic query cap for smoke/sample runs.")
    parser.add_argument("--output-dir", default="data/eval_runs/latest", help="Directory for JSON and Markdown reports.")
    return parser


def main() -> None:
    result = run(build_parser().parse_args())
    print(json.dumps({"json_report": result["json_report"], "markdown_report": result["markdown_report"]}, indent=2))


if __name__ == "__main__":
    main()
