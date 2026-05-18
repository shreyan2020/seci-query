from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Set, Tuple


EntityKey = Tuple[str, str]
RelationKey = Tuple[str, str, str]


@dataclass(frozen=True)
class F1Summary:
    precision: float
    recall: float
    f1: float
    true_positive: int
    predicted: int
    gold: int

    def as_dict(self) -> Dict[str, float | int]:
        return {
            "precision": round(self.precision, 6),
            "recall": round(self.recall, 6),
            "f1": round(self.f1, 6),
            "true_positive": self.true_positive,
            "predicted": self.predicted,
            "gold": self.gold,
        }


def _read_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL in {path} at line {line_number}: {exc}") from exc


def _norm(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _entity_key(item: Mapping[str, object]) -> EntityKey:
    label = _norm(item.get("label") or item.get("text") or item.get("name"))
    entity_type = _norm(item.get("type") or item.get("entity_type") or "entity")
    return label, entity_type


def _relation_key(item: Mapping[str, object], entity_lookup: Mapping[str, EntityKey]) -> RelationKey:
    source = _norm(item.get("source") or item.get("head") or item.get("arg1"))
    target = _norm(item.get("target") or item.get("tail") or item.get("arg2"))
    relation = _norm(item.get("relation") or item.get("type") or item.get("predicate") or "related_to")
    source_label = entity_lookup.get(source, (source, ""))[0]
    target_label = entity_lookup.get(target, (target, ""))[0]
    return source_label, relation, target_label


def _load_records(path: str | Path) -> Dict[str, dict]:
    records: Dict[str, dict] = {}
    for item in _read_jsonl(Path(path)):
        paper_id = str(item.get("paper_id") or item.get("id") or item.get("pmid") or "").strip()
        if not paper_id:
            raise ValueError(f"Record in {path} is missing paper_id/id/pmid.")
        records[paper_id] = item
    return records


def _sets_for_record(record: Mapping[str, object]) -> Tuple[Set[EntityKey], Set[RelationKey]]:
    raw_entities = record.get("entities") or record.get("nodes") or []
    raw_relations = record.get("relations") or record.get("edges") or []
    entities = [_entity_key(item) for item in raw_entities if isinstance(item, dict)]
    entity_lookup = {}
    for item, key in zip([item for item in raw_entities if isinstance(item, dict)], entities):
        for candidate in [item.get("id"), item.get("label"), item.get("text"), item.get("name")]:
            if candidate:
                entity_lookup[_norm(candidate)] = key
    relations = {
        _relation_key(item, entity_lookup)
        for item in raw_relations
        if isinstance(item, dict)
    }
    return set(entities), relations


def _score(predicted: Set[tuple], gold: Set[tuple]) -> F1Summary:
    true_positive = len(predicted & gold)
    precision = true_positive / len(predicted) if predicted else 0.0
    recall = true_positive / len(gold) if gold else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    return F1Summary(precision, recall, f1, true_positive, len(predicted), len(gold))


def evaluate_extraction(gold_path: str | Path, prediction_path: str | Path) -> Dict[str, object]:
    gold_records = _load_records(gold_path)
    prediction_records = _load_records(prediction_path)
    all_gold_entities: Set[EntityKey] = set()
    all_pred_entities: Set[EntityKey] = set()
    all_gold_relations: Set[RelationKey] = set()
    all_pred_relations: Set[RelationKey] = set()
    per_paper = {}

    for paper_id, gold_record in gold_records.items():
        pred_record = prediction_records.get(paper_id, {"entities": [], "relations": []})
        gold_entities, gold_relations = _sets_for_record(gold_record)
        pred_entities, pred_relations = _sets_for_record(pred_record)
        all_gold_entities.update((paper_id, *key) for key in gold_entities)
        all_pred_entities.update((paper_id, *key) for key in pred_entities)
        all_gold_relations.update((paper_id, *key) for key in gold_relations)
        all_pred_relations.update((paper_id, *key) for key in pred_relations)
        per_paper[paper_id] = {
            "entities": _score(pred_entities, gold_entities).as_dict(),
            "relations": _score(pred_relations, gold_relations).as_dict(),
        }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "paper_count": len(gold_records),
        "entity_metrics": _score(all_pred_entities, all_gold_entities).as_dict(),
        "relation_metrics": _score(all_pred_relations, all_gold_relations).as_dict(),
        "per_paper": per_paper,
    }


def _write_markdown(report: Mapping[str, object], path: Path) -> None:
    entities = report.get("entity_metrics", {})
    relations = report.get("relation_metrics", {})
    lines = [
        "# Ontology Extraction Benchmark",
        "",
        f"- Generated: {report.get('generated_at')}",
        f"- Papers: {report.get('paper_count')}",
        "",
        "| Target | Precision | Recall | F1 | TP | Predicted | Gold |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, metrics in [("Entities", entities), ("Relations", relations)]:
        if not isinstance(metrics, dict):
            continue
        lines.append(
            "| {label} | {precision:.4f} | {recall:.4f} | {f1:.4f} | {tp} | {predicted} | {gold} |".format(
                label=label,
                precision=float(metrics.get("precision", 0.0)),
                recall=float(metrics.get("recall", 0.0)),
                f1=float(metrics.get("f1", 0.0)),
                tp=int(metrics.get("true_positive", 0)),
                predicted=int(metrics.get("predicted", 0)),
                gold=int(metrics.get("gold", 0)),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate ontology extraction against normalized gold annotations.")
    parser.add_argument("--gold", required=True, help="JSONL gold file with paper_id, entities, and relations.")
    parser.add_argument("--predictions", required=True, help="JSONL predictions file with paper_id, entities, and relations.")
    parser.add_argument("--output-dir", default="data/eval_runs/extraction", help="Directory for JSON and Markdown reports.")
    parser.add_argument("--name", default="ontology_extraction", help="Report filename prefix.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    report = evaluate_extraction(args.gold, args.predictions)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{args.name}_report.json"
    markdown_path = output_dir / f"{args.name}_report.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_markdown(report, markdown_path)
    print(json.dumps({"json_report": str(json_path), "markdown_report": str(markdown_path)}, indent=2))


if __name__ == "__main__":
    main()

