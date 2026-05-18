from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple


@dataclass(frozen=True)
class MetricSummary:
    precision_at_k: float
    recall_at_k: float
    ndcg_at_k: float
    map: float
    mrr: float
    query_count: int

    def as_dict(self) -> Dict[str, float | int]:
        return {
            "precision_at_k": self.precision_at_k,
            "recall_at_k": self.recall_at_k,
            "ndcg_at_k": self.ndcg_at_k,
            "map": self.map,
            "mrr": self.mrr,
            "query_count": self.query_count,
        }


def precision_at_k(ranked_doc_ids: Sequence[str], relevant: Mapping[str, int], k: int) -> float:
    if k <= 0:
        return 0.0
    hits = sum(1 for doc_id in ranked_doc_ids[:k] if relevant.get(doc_id, 0) > 0)
    return hits / k


def recall_at_k(ranked_doc_ids: Sequence[str], relevant: Mapping[str, int], k: int) -> float:
    relevant_count = sum(1 for score in relevant.values() if score > 0)
    if relevant_count == 0:
        return 0.0
    hits = sum(1 for doc_id in ranked_doc_ids[:k] if relevant.get(doc_id, 0) > 0)
    return hits / relevant_count


def average_precision(ranked_doc_ids: Sequence[str], relevant: Mapping[str, int], k: int) -> float:
    relevant_count = sum(1 for score in relevant.values() if score > 0)
    if relevant_count == 0:
        return 0.0
    hits = 0
    score = 0.0
    for index, doc_id in enumerate(ranked_doc_ids[:k], start=1):
        if relevant.get(doc_id, 0) > 0:
            hits += 1
            score += hits / index
    return score / min(relevant_count, k)


def reciprocal_rank(ranked_doc_ids: Sequence[str], relevant: Mapping[str, int], k: int) -> float:
    for index, doc_id in enumerate(ranked_doc_ids[:k], start=1):
        if relevant.get(doc_id, 0) > 0:
            return 1.0 / index
    return 0.0


def dcg_at_k(ranked_doc_ids: Sequence[str], relevant: Mapping[str, int], k: int) -> float:
    total = 0.0
    for index, doc_id in enumerate(ranked_doc_ids[:k], start=1):
        gain = max(0, int(relevant.get(doc_id, 0)))
        if gain:
            total += ((2**gain) - 1) / math.log2(index + 1)
    return total


def ndcg_at_k(ranked_doc_ids: Sequence[str], relevant: Mapping[str, int], k: int) -> float:
    ideal = sorted((score for score in relevant.values() if score > 0), reverse=True)
    if not ideal:
        return 0.0
    ideal_doc_ids = [f"ideal-{index}" for index, _ in enumerate(ideal)]
    ideal_relevance = {doc_id: score for doc_id, score in zip(ideal_doc_ids, ideal)}
    ideal_dcg = dcg_at_k(ideal_doc_ids, ideal_relevance, k)
    if ideal_dcg == 0:
        return 0.0
    return dcg_at_k(ranked_doc_ids, relevant, k) / ideal_dcg


def summarize_rankings(
    rankings: Mapping[str, Sequence[Tuple[str, float]]],
    qrels: Mapping[str, Mapping[str, int]],
    k: int,
) -> MetricSummary:
    query_ids = [query_id for query_id in rankings if query_id in qrels]
    if not query_ids:
        return MetricSummary(0.0, 0.0, 0.0, 0.0, 0.0, 0)

    precision = []
    recall = []
    ndcg = []
    ap = []
    rr = []
    for query_id in query_ids:
        ranked_doc_ids = [doc_id for doc_id, _ in rankings[query_id]]
        relevant = qrels[query_id]
        precision.append(precision_at_k(ranked_doc_ids, relevant, k))
        recall.append(recall_at_k(ranked_doc_ids, relevant, k))
        ndcg.append(ndcg_at_k(ranked_doc_ids, relevant, k))
        ap.append(average_precision(ranked_doc_ids, relevant, k))
        rr.append(reciprocal_rank(ranked_doc_ids, relevant, k))

    return MetricSummary(
        precision_at_k=sum(precision) / len(precision),
        recall_at_k=sum(recall) / len(recall),
        ndcg_at_k=sum(ndcg) / len(ndcg),
        map=sum(ap) / len(ap),
        mrr=sum(rr) / len(rr),
        query_count=len(query_ids),
    )

