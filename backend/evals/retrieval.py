from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

from .datasets import Document


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "what",
    "which",
    "with",
}


def tokenize(text: str) -> List[str]:
    return [token for token in re.findall(r"[a-z0-9][a-z0-9\-]{1,}", text.lower()) if token not in STOPWORDS]


@dataclass
class BM25Index:
    doc_ids: List[str]
    doc_lengths: Dict[str, int]
    term_freqs: Dict[str, Counter]
    doc_freqs: Counter
    avg_doc_length: float
    k1: float = 1.5
    b: float = 0.75

    @classmethod
    def from_documents(cls, documents: Mapping[str, Document]) -> "BM25Index":
        doc_ids: List[str] = []
        doc_lengths: Dict[str, int] = {}
        term_freqs: Dict[str, Counter] = {}
        doc_freqs: Counter = Counter()
        for doc_id, document in documents.items():
            tokens = tokenize(f"{document.title} {document.text}")
            counts = Counter(tokens)
            doc_ids.append(doc_id)
            doc_lengths[doc_id] = len(tokens)
            term_freqs[doc_id] = counts
            for term in counts:
                doc_freqs[term] += 1
        avg_doc_length = sum(doc_lengths.values()) / len(doc_lengths) if doc_lengths else 0.0
        return cls(doc_ids, doc_lengths, term_freqs, doc_freqs, avg_doc_length)

    def search(self, query: str, top_k: int = 100) -> List[Tuple[str, float]]:
        query_terms = tokenize(query)
        if not query_terms:
            return []
        query_counts = Counter(query_terms)
        doc_count = len(self.doc_ids)
        scores: Dict[str, float] = defaultdict(float)
        for term, query_weight in query_counts.items():
            df = self.doc_freqs.get(term, 0)
            if df <= 0:
                continue
            idf = math.log(1 + ((doc_count - df + 0.5) / (df + 0.5)))
            for doc_id in self.doc_ids:
                tf = self.term_freqs[doc_id].get(term, 0)
                if tf <= 0:
                    continue
                doc_length = self.doc_lengths[doc_id] or 1
                denominator = tf + self.k1 * (1 - self.b + self.b * (doc_length / (self.avg_doc_length or 1)))
                scores[doc_id] += query_weight * idf * ((tf * (self.k1 + 1)) / denominator)
        return sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:top_k]


def augmentation_terms(augmentation: Mapping[str, object]) -> List[str]:
    terms: List[str] = []
    for key in ["expanded_terms", "reasoning_lenses", "tacit_context"]:
        value = augmentation.get(key)
        if isinstance(value, str):
            terms.append(value)
        elif isinstance(value, Sequence):
            terms.extend(str(item) for item in value if str(item).strip())
    seen = set()
    unique_terms = []
    for term in terms:
        cleaned = re.sub(r"\s+", " ", str(term)).strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            unique_terms.append(cleaned)
    return unique_terms


def augmented_query(query: str, augmentation: Mapping[str, object] | None) -> str:
    if not augmentation:
        return query
    additions = augmentation_terms(augmentation)
    if not additions:
        return query
    return f"{query}\nOntology augmentation: {', '.join(additions)}"

