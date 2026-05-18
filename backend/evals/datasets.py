from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional


@dataclass(frozen=True)
class Document:
    id: str
    title: str
    text: str


@dataclass(frozen=True)
class Query:
    id: str
    text: str


@dataclass(frozen=True)
class RetrievalBenchmark:
    name: str
    corpus: Dict[str, Document]
    queries: Dict[str, Query]
    qrels: Dict[str, Dict[str, int]]


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


def load_beir(data_dir: str | Path, split: str = "test", name: Optional[str] = None) -> RetrievalBenchmark:
    root = Path(data_dir)
    corpus_path = root / "corpus.jsonl"
    queries_path = root / "queries.jsonl"
    qrels_candidates = [
        root / "qrels" / f"{split}.tsv",
        root / "qrels" / f"{split}.txt",
        root / f"qrels.{split}.tsv",
        root / "qrels.tsv",
        root / "qrels.txt",
    ]
    qrels_path = next((path for path in qrels_candidates if path.exists()), None)
    missing = [str(path) for path in [corpus_path, queries_path] if not path.exists()]
    if missing or not qrels_path:
        expected = ", ".join(["corpus.jsonl", "queries.jsonl", "qrels/test.tsv or qrels.tsv"])
        raise FileNotFoundError(f"Missing BEIR files in {root}. Expected {expected}. Missing: {missing}")

    corpus: Dict[str, Document] = {}
    for item in _read_jsonl(corpus_path):
        doc_id = str(item.get("_id") or item.get("id") or "").strip()
        if not doc_id:
            continue
        corpus[doc_id] = Document(
            id=doc_id,
            title=str(item.get("title") or ""),
            text=str(item.get("text") or item.get("abstract") or ""),
        )

    queries: Dict[str, Query] = {}
    for item in _read_jsonl(queries_path):
        query_id = str(item.get("_id") or item.get("id") or "").strip()
        text = str(item.get("text") or item.get("query") or "").strip()
        if query_id and text:
            queries[query_id] = Query(id=query_id, text=text)

    return RetrievalBenchmark(
        name=name or root.name,
        corpus=corpus,
        queries=queries,
        qrels=load_qrels(qrels_path),
    )


def load_qrels(path: str | Path) -> Dict[str, Dict[str, int]]:
    qrels_path = Path(path)
    qrels: Dict[str, Dict[str, int]] = {}
    with qrels_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            parts = stripped.split("\t") if "\t" in stripped else stripped.split()
            if line_number == 1 and any(part.lower() in {"query-id", "query_id", "corpus-id", "doc_id", "score"} for part in parts):
                continue
            if len(parts) == 4:
                query_id, _, doc_id, score_text = parts
            elif len(parts) >= 3:
                query_id, doc_id, score_text = parts[:3]
            else:
                raise ValueError(f"Invalid qrels line in {qrels_path}:{line_number}: {line.rstrip()}")
            try:
                score = int(float(score_text))
            except ValueError as exc:
                raise ValueError(f"Invalid qrels score in {qrels_path}:{line_number}: {score_text}") from exc
            qrels.setdefault(str(query_id), {})[str(doc_id)] = score
    return qrels


def load_augmentation_file(path: str | Path | None) -> Dict[str, dict]:
    if not path:
        return {}
    augmentation_path = Path(path)
    if not augmentation_path.exists():
        raise FileNotFoundError(f"Ontology augmentation file not found: {augmentation_path}")
    payload = json.loads(augmentation_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Ontology augmentation file must be a JSON object keyed by query id.")
    return {str(key): value if isinstance(value, dict) else {"expanded_terms": value} for key, value in payload.items()}

