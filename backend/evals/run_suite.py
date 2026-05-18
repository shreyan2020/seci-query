from __future__ import annotations

import argparse
import json
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

from . import run_benchmarks
from .extraction_metrics import _write_markdown as _write_extraction_markdown
from .extraction_metrics import evaluate_extraction


def _safe_name(value: object, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    return "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in text)


def _resolve_path(value: str | None, config_path: Path, must_exist: bool = False) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if path.is_absolute():
        resolved = path
    else:
        cwd_path = Path.cwd() / path
        config_relative_path = config_path.parent / path
        resolved = cwd_path if cwd_path.exists() or not config_relative_path.exists() else config_relative_path
    if must_exist and not resolved.exists():
        raise FileNotFoundError(f"Required benchmark path does not exist: {resolved}")
    return resolved


def _format_metric(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    if isinstance(value, int):
        return str(value)
    return str(value)


def _compact_metrics(metrics: Mapping[str, object], keys: Iterable[str]) -> str:
    parts = []
    for key in keys:
        if key in metrics:
            parts.append(f"{key}={_format_metric(metrics[key])}")
    return ", ".join(parts) if parts else "-"


def _run_retrieval_task(task: Mapping[str, Any], config_path: Path, suite_output_dir: Path) -> Dict[str, Any]:
    task_id = _safe_name(task.get("id"), "retrieval")
    task_output_dir = suite_output_dir / task_id
    data_dir = _resolve_path(str(task.get("data_dir", "")), config_path, must_exist=True)
    augmentation_file = _resolve_path(task.get("augmentation_file"), config_path, must_exist=False)
    args = Namespace(
        benchmark=task.get("benchmark", "beir"),
        data_dir=str(data_dir),
        split=task.get("split", "test"),
        name=task.get("name"),
        augmentation_file=str(augmentation_file) if augmentation_file else None,
        modes=task.get("modes", "baseline,ontology"),
        top_k=int(task.get("top_k", 100)),
        metric_k=int(task.get("metric_k", 10)),
        max_queries=task.get("max_queries"),
        output_dir=str(task_output_dir),
    )
    report = run_benchmarks.run(args)
    modes = report.get("modes", {})
    baseline = modes.get("baseline", {}) if isinstance(modes, dict) else {}
    ontology = modes.get("ontology", {}) if isinstance(modes, dict) else {}
    primary_metrics = {}
    if isinstance(baseline, dict) and isinstance(baseline.get("metrics"), dict):
        primary_metrics["baseline_ndcg_at_k"] = baseline["metrics"].get("ndcg_at_k", 0.0)
        primary_metrics["baseline_recall_at_k"] = baseline["metrics"].get("recall_at_k", 0.0)
    if isinstance(ontology, dict) and isinstance(ontology.get("metrics"), dict):
        primary_metrics["ontology_ndcg_at_k"] = ontology["metrics"].get("ndcg_at_k", 0.0)
        primary_metrics["ontology_recall_at_k"] = ontology["metrics"].get("recall_at_k", 0.0)
    if isinstance(ontology, dict) and isinstance(ontology.get("delta_vs_baseline"), dict):
        primary_metrics["ontology_ndcg_delta"] = ontology["delta_vs_baseline"].get("ndcg_at_k", 0.0)
        primary_metrics["ontology_recall_delta"] = ontology["delta_vs_baseline"].get("recall_at_k", 0.0)
    return {
        "id": task_id,
        "type": "retrieval_beir",
        "status": "passed",
        "benchmark_name": report.get("benchmark_name"),
        "report_json": report.get("json_report"),
        "report_markdown": report.get("markdown_report"),
        "primary_metrics": primary_metrics,
        "document_count": report.get("document_count"),
        "query_count": report.get("query_count"),
    }


def _run_extraction_task(task: Mapping[str, Any], config_path: Path, suite_output_dir: Path) -> Dict[str, Any]:
    task_id = _safe_name(task.get("id"), "extraction")
    task_output_dir = suite_output_dir / task_id
    task_output_dir.mkdir(parents=True, exist_ok=True)
    gold_path = _resolve_path(str(task.get("gold", "")), config_path, must_exist=True)
    prediction_path = _resolve_path(str(task.get("predictions", "")), config_path, must_exist=True)
    report_name = _safe_name(task.get("name"), task_id)
    report = evaluate_extraction(gold_path, prediction_path)
    json_path = task_output_dir / f"{report_name}_report.json"
    markdown_path = task_output_dir / f"{report_name}_report.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_extraction_markdown(report, markdown_path)
    entity_metrics = report.get("entity_metrics", {})
    relation_metrics = report.get("relation_metrics", {})
    primary_metrics = {}
    if isinstance(entity_metrics, dict):
        primary_metrics["entity_f1"] = entity_metrics.get("f1", 0.0)
        primary_metrics["entity_recall"] = entity_metrics.get("recall", 0.0)
    if isinstance(relation_metrics, dict):
        primary_metrics["relation_f1"] = relation_metrics.get("f1", 0.0)
        primary_metrics["relation_recall"] = relation_metrics.get("recall", 0.0)
    return {
        "id": task_id,
        "type": "extraction_jsonl",
        "status": "passed",
        "benchmark_name": task.get("name", task_id),
        "report_json": str(json_path),
        "report_markdown": str(markdown_path),
        "primary_metrics": primary_metrics,
        "paper_count": report.get("paper_count"),
    }


def _run_task(task: Mapping[str, Any], config_path: Path, suite_output_dir: Path) -> Dict[str, Any]:
    task_type = str(task.get("type", "")).strip()
    if task_type == "retrieval_beir":
        return _run_retrieval_task(task, config_path, suite_output_dir)
    if task_type == "extraction_jsonl":
        return _run_extraction_task(task, config_path, suite_output_dir)
    raise ValueError(f"Unsupported benchmark task type: {task_type}")


def _write_suite_markdown(summary: Mapping[str, Any], path: Path) -> None:
    lines = [
        f"# Benchmark Suite: {summary.get('suite_name')}",
        "",
        f"- Generated: {summary.get('generated_at')}",
        f"- Description: {summary.get('description', '')}",
        f"- Tasks: {summary.get('task_count')} total, {summary.get('passed_count')} passed, {summary.get('failed_count')} failed, {summary.get('skipped_count')} skipped",
        "",
        "| Task | Type | Benchmark | Status | Primary Metrics | Report |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for task in summary.get("tasks", []):
        if not isinstance(task, dict):
            continue
        metrics = task.get("primary_metrics", {})
        metrics_text = _compact_metrics(metrics, metrics.keys()) if isinstance(metrics, dict) else "-"
        report = task.get("report_markdown") or task.get("report_json") or ""
        report_text = str(report) if report else "-"
        lines.append(
            "| {task_id} | {task_type} | {benchmark} | {status} | {metrics} | {report} |".format(
                task_id=task.get("id", ""),
                task_type=task.get("type", ""),
                benchmark=task.get("benchmark_name", ""),
                status=task.get("status", ""),
                metrics=metrics_text,
                report=report_text,
            )
        )
        if task.get("error"):
            lines.append(f"| {task.get('id', '')} error | | | | {task.get('error')} | |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def run_suite(config_path: str | Path, output_dir: str | Path, include_disabled: bool = False, fail_fast: bool = False) -> Dict[str, Any]:
    config_file = Path(config_path)
    config = json.loads(config_file.read_text(encoding="utf-8"))
    suite_output_dir = Path(output_dir)
    suite_output_dir.mkdir(parents=True, exist_ok=True)
    task_summaries = []

    for task in config.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task_id = _safe_name(task.get("id"), "task")
        if task.get("enabled", True) is False and not include_disabled:
            task_summaries.append(
                {
                    "id": task_id,
                    "type": task.get("type", ""),
                    "status": "skipped",
                    "benchmark_name": task.get("name") or task.get("standard_benchmark") or task_id,
                    "skip_reason": "disabled in suite config",
                }
            )
            continue
        try:
            task_summaries.append(_run_task(task, config_file, suite_output_dir))
        except Exception as exc:  # pragma: no cover - exercised by CLI usage and failed external data paths.
            task_summaries.append(
                {
                    "id": task_id,
                    "type": task.get("type", ""),
                    "status": "failed",
                    "benchmark_name": task.get("name") or task.get("standard_benchmark") or task_id,
                    "error": str(exc),
                }
            )
            if fail_fast:
                break

    summary = {
        "suite_name": config.get("suite_name", config_file.stem),
        "description": config.get("description", ""),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": str(config_file),
        "output_dir": str(suite_output_dir),
        "task_count": len(task_summaries),
        "passed_count": sum(1 for task in task_summaries if task.get("status") == "passed"),
        "failed_count": sum(1 for task in task_summaries if task.get("status") == "failed"),
        "skipped_count": sum(1 for task in task_summaries if task.get("status") == "skipped"),
        "tasks": task_summaries,
    }
    json_path = suite_output_dir / "suite_summary.json"
    markdown_path = suite_output_dir / "suite_summary.md"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _write_suite_markdown(summary, markdown_path)
    summary["json_report"] = str(json_path)
    summary["markdown_report"] = str(markdown_path)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a configured backend benchmark suite.")
    parser.add_argument("--config", required=True, help="Suite JSON file.")
    parser.add_argument("--output-dir", default="data/eval_runs/suite", help="Directory for aggregate and per-task reports.")
    parser.add_argument("--include-disabled", action="store_true", help="Run disabled tasks from the suite file.")
    parser.add_argument("--fail-fast", action="store_true", help="Stop after the first failed task.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = run_suite(args.config, args.output_dir, include_disabled=args.include_disabled, fail_fast=args.fail_fast)
    print(json.dumps({"json_report": summary["json_report"], "markdown_report": summary["markdown_report"]}, indent=2))
    if summary["failed_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
