from __future__ import annotations

import argparse
import json
from pathlib import Path

from .datasets import load_beir
from .run_benchmarks import _limit_benchmark_queries
from .system_augmentation import build_query_only_system_augmentation


def generate_system_augmentations(
    data_dir: str | Path,
    output_file: str | Path,
    *,
    audit_file: str | Path | None = None,
    split: str = "test",
    name: str | None = None,
    max_queries: int | None = None,
) -> dict:
    benchmark = load_beir(data_dir, split=split, name=name)
    benchmark = _limit_benchmark_queries(benchmark, max_queries)
    augmentations = {}
    audit = {
        "benchmark_name": benchmark.name,
        "split": split,
        "query_count": len(benchmark.queries),
        "generation_mode": "query_only_system_context",
        "records": {},
    }
    for index, query in enumerate(benchmark.queries.values(), start=1):
        augmentation, record_audit = build_query_only_system_augmentation(query.text, project_id=index)
        augmentations[query.id] = augmentation
        audit["records"][query.id] = record_audit

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(augmentations, indent=2), encoding="utf-8")
    if audit_file:
        audit_path = Path(audit_file)
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    return {
        "benchmark_name": benchmark.name,
        "query_count": len(benchmark.queries),
        "augmentation_file": str(output_path),
        "audit_file": str(audit_file or ""),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate query-only system augmentations for a BEIR benchmark.")
    parser.add_argument("--data-dir", required=True, help="BEIR dataset directory.")
    parser.add_argument("--output-file", required=True, help="JSON augmentation file to write.")
    parser.add_argument("--audit-file", default=None, help="Optional JSON audit file with generated objectives and tacit context.")
    parser.add_argument("--split", default="test", help="Qrels split name.")
    parser.add_argument("--name", default=None, help="Benchmark name for reports.")
    parser.add_argument("--max-queries", type=int, default=None, help="Optional query cap aligned to scored qrels.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = generate_system_augmentations(
        args.data_dir,
        args.output_file,
        audit_file=args.audit_file,
        split=args.split,
        name=args.name,
        max_queries=args.max_queries,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
