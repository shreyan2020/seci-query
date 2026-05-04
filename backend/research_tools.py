from __future__ import annotations

import json
import os
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List

import httpx


PUBMED_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_pubmed",
        "description": "Search PubMed for scientific literature relevant to the current biotech question and return citation-ready records.",
        "parameters": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {
                    "type": "string",
                    "description": "PubMed search query for the current project question.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of papers to return.",
                    "minimum": 1,
                    "maximum": 8,
                    "default": 5,
                },
            },
        },
    },
}

LITERATURE_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_literature",
        "description": "Search PubMed plus scholarly metadata APIs for literature relevant to the current biotech question.",
        "parameters": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "description": "Scientific literature query for the current project question."},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 12, "default": 5},
            },
        },
    },
}

READ_LOCAL_PDF_TOOL = {
    "type": "function",
    "function": {
        "name": "read_local_pdf",
        "description": "Read a local PDF and return extracted text from the first pages for evidence synthesis.",
        "parameters": {
            "type": "object",
            "required": ["path"],
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative path to a local PDF file.",
                },
                "max_pages": {
                    "type": "integer",
                    "description": "Maximum number of pages to read from the start of the PDF.",
                    "minimum": 1,
                    "maximum": 12,
                    "default": 5,
                },
            },
        },
    },
}


_PUBMED_STOPWORDS = {
    "about",
    "above",
    "after",
    "again",
    "against",
    "also",
    "among",
    "and",
    "are",
    "based",
    "below",
    "between",
    "both",
    "can",
    "case",
    "could",
    "does",
    "done",
    "each",
    "examples",
    "experiment",
    "experiments",
    "find",
    "following",
    "from",
    "future",
    "have",
    "having",
    "how",
    "into",
    "key",
    "latest",
    "like",
    "more",
    "most",
    "options",
    "other",
    "our",
    "over",
    "paper",
    "papers",
    "project",
    "question",
    "research",
    "result",
    "results",
    "should",
    "some",
    "strategies",
    "successful",
    "that",
    "the",
    "their",
    "then",
    "there",
    "these",
    "this",
    "those",
    "through",
    "using",
    "what",
    "when",
    "where",
    "which",
    "with",
    "would",
}

_PUBMED_DOMAIN_TERMS = {
    "activity",
    "ai",
    "biosynthesis",
    "biosynthetic",
    "biosensor",
    "cell",
    "cerevisiae",
    "chalcone",
    "co-culture",
    "coculture",
    "cofactor",
    "crispr",
    "evolution",
    "enzyme",
    "enzymes",
    "eriodictyol",
    "expression",
    "factory",
    "f3h",
    "fls",
    "fermentation",
    "flavonoid",
    "flavonoids",
    "flavonol",
    "flux",
    "genistein",
    "heterologous",
    "improvement",
    "kaempferol",
    "malonyl",
    "metabolic",
    "modeling",
    "microbial",
    "microorganism",
    "naringenin",
    "naringenin",
    "pathway",
    "production",
    "quercetin",
    "saccharomyces",
    "screening",
    "strain",
    "synthesis",
    "titer",
    "ugt",
    "ugts",
    "yeast",
}

_PUBMED_SYNONYMS = {
    "saccharomyces": "yeast",
    "cerevisiae": "yeast",
    "microorganism": "microbial",
    "microorganisms": "microbial",
    "flavonoid": "flavonoids",
    "ugts": "ugt",
}


def available_research_tools() -> List[Dict[str, Any]]:
    return [LITERATURE_SEARCH_TOOL, PUBMED_SEARCH_TOOL, READ_LOCAL_PDF_TOOL]


def _tool_user_agent() -> str:
    email = os.getenv("NCBI_EMAIL") or "local-agent@example.com"
    tool_name = os.getenv("NCBI_TOOL_NAME") or "dsm_interface_agent"
    return tool_name, email


def _unique_in_order(values: List[str]) -> List[str]:
    seen = set()
    out = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _clean_doi(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text, flags=re.IGNORECASE)
    return text.strip().rstrip(".").lower()


def _title_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()[:180]


def _record_key(record: Dict[str, Any]) -> str:
    doi = _clean_doi(record.get("doi"))
    if doi:
        return f"doi:{doi}"
    pmid = str(record.get("pmid") or "").strip()
    if pmid:
        return f"pmid:{pmid}"
    pmcid = str(record.get("pmcid") or "").strip().upper()
    if pmcid:
        return f"pmcid:{pmcid}"
    return f"title:{_title_key(str(record.get('title') or record.get('citation') or ''))}"


def _merge_record(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    merged = {**existing}
    for key, value in incoming.items():
        if key == "sources":
            merged["sources"] = _unique_in_order([*(merged.get("sources") or []), *(value or [])])
        elif key == "abstract":
            if len(str(value or "")) > len(str(merged.get("abstract") or "")):
                merged[key] = value
        elif value and not merged.get(key):
            merged[key] = value
    return merged


def _tokenize_pubmed_text(value: str) -> List[str]:
    cleaned = re.sub(r"[^\w\s-]", " ", str(value or "").lower())
    tokens = [
        token.strip("-")
        for token in re.split(r"\s+", cleaned)
        if len(token.strip("-")) >= 3 and token.strip("-") not in _PUBMED_STOPWORDS
    ]
    return [_PUBMED_SYNONYMS.get(token, token) for token in tokens]


def formulate_pubmed_query(
    query: str,
    *,
    project_goal: str = "",
    objective_title: str = "",
    objective_definition: str = "",
    objective_signals: List[str] | None = None,
    user_inputs: List[str] | None = None,
    max_terms: int = 6,
) -> str:
    """Turn workspace context into a compact PubMed query.

    PubMed often returns zero records for full natural-language research questions.
    This keeps high-signal biomedical terms from the project, objective, and user
    inputs while avoiding too many terms, which would make ESearch overly narrow.
    """
    weighted_sources = [
        (project_goal, 4),
        (query, 4),
        (objective_title, 3),
        (objective_definition, 2),
        (" ".join(objective_signals or []), 2),
        (" ".join(user_inputs or []), 1),
    ]
    scores: Dict[str, int] = {}
    first_seen: Dict[str, int] = {}
    order = 0
    for text, weight in weighted_sources:
        for token in _tokenize_pubmed_text(text):
            if token not in first_seen:
                first_seen[token] = order
                order += 1
            scores[token] = scores.get(token, 0) + weight + (4 if token in _PUBMED_DOMAIN_TERMS else 0)

    if not scores:
        return " ".join(str(query or "").split()).strip()

    domain_tokens = [token for token in scores if token in _PUBMED_DOMAIN_TERMS]
    selected: List[str] = []
    anchors = [
        token
        for token in ["flavonoids", "flavonoid", "yeast", "microbial", "production", "biosynthesis", "pathway"]
        if token in scores
    ]
    for token in anchors:
        if token not in selected:
            selected.append(token)

    ranked_domain = sorted(domain_tokens, key=lambda token: (-scores[token], first_seen[token]))
    ranked_other = sorted(
        [token for token in scores if token not in _PUBMED_DOMAIN_TERMS],
        key=lambda token: (-scores[token], first_seen[token]),
    )
    for token in ranked_domain + ranked_other:
        if token not in selected:
            selected.append(token)
        if len(selected) >= max_terms:
            break

    return " ".join(selected[:max_terms]).strip()


def _pubmed_query_candidates(query: str, context_query: str = "") -> List[str]:
    tokens = _unique_in_order(_tokenize_pubmed_text(query))

    domain_tokens = [token for token in tokens if token in _PUBMED_DOMAIN_TERMS]
    other_tokens = [token for token in tokens if token not in _PUBMED_DOMAIN_TERMS]
    candidates = [context_query, query]

    if domain_tokens:
        candidates.append(" ".join(domain_tokens[:6]))
    if "flavonoid" in domain_tokens and "flavonoids" not in domain_tokens:
        candidates.append(" ".join(["flavonoids" if token == "flavonoid" else token for token in domain_tokens[:6]]))
    if domain_tokens and other_tokens:
        candidates.append(" ".join((domain_tokens[:4] + other_tokens[:2])[:6]))
    if len(tokens) >= 3:
        candidates.append(" ".join(tokens[:6]))

    return [candidate for candidate in _unique_in_order([" ".join(item.split()) for item in candidates]) if candidate]


async def search_pubmed(
    query: str,
    max_results: int = 5,
    *,
    project_goal: str = "",
    objective_title: str = "",
    objective_definition: str = "",
    objective_signals: List[str] | None = None,
    user_inputs: List[str] | None = None,
) -> Dict[str, Any]:
    query = " ".join(str(query or "").split()).strip()
    if not query:
        return {"query": "", "results": [], "error": "query is required"}

    max_results = max(1, min(int(max_results or 5), 8))
    tool_name, email = _tool_user_agent()
    timeout = httpx.Timeout(40.0, connect=10.0)
    formulated_query = formulate_pubmed_query(
        query,
        project_goal=project_goal,
        objective_title=objective_title,
        objective_definition=objective_definition,
        objective_signals=objective_signals,
        user_inputs=user_inputs,
    )

    async with httpx.AsyncClient(timeout=timeout) as client:
        ids: List[str] = []
        effective_query = query
        attempts: List[Dict[str, Any]] = []
        for candidate in _pubmed_query_candidates(query, formulated_query):
            search_response = await client.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                params={
                    "db": "pubmed",
                    "term": candidate,
                    "retmode": "json",
                    "retmax": max_results,
                    "sort": "relevance",
                    "tool": tool_name,
                    "email": email,
                },
            )
            search_response.raise_for_status()
            id_list = (((search_response.json() or {}).get("esearchresult") or {}).get("idlist") or [])
            ids = [str(item).strip() for item in id_list if str(item).strip()]
            attempts.append({"query": candidate, "result_count": len(ids)})
            effective_query = candidate
            if ids:
                break

        if not ids:
            return {
                "query": query,
                "formulated_query": formulated_query,
                "search_query": effective_query,
                "attempts": attempts,
                "results": [],
            }

        fetch_response = await client.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            params={
                "db": "pubmed",
                "id": ",".join(ids),
                "retmode": "xml",
                "tool": tool_name,
                "email": email,
            },
        )
        fetch_response.raise_for_status()

    root = ET.fromstring(fetch_response.text)
    articles: List[Dict[str, Any]] = []
    for article in root.findall(".//PubmedArticle"):
        pmid = (article.findtext(".//PMID") or "").strip()
        title = re.sub(r"\s+", " ", "".join(article.find(".//ArticleTitle").itertext()) if article.find(".//ArticleTitle") is not None else "").strip()
        journal = re.sub(r"\s+", " ", article.findtext(".//Journal/Title") or article.findtext(".//MedlineJournalInfo/MedlineTA") or "").strip()
        year = (
            (article.findtext(".//PubDate/Year") or "").strip()
            or (article.findtext(".//ArticleDate/Year") or "").strip()
            or (article.findtext(".//PubMedPubDate[@PubStatus='pubmed']/Year") or "").strip()
        )
        authors = []
        for author in article.findall(".//AuthorList/Author"):
            last_name = (author.findtext("LastName") or "").strip()
            initials = (author.findtext("Initials") or "").strip()
            collective = (author.findtext("CollectiveName") or "").strip()
            name = collective or " ".join(part for part in [last_name, initials] if part).strip()
            if name:
                authors.append(name)

        abstract_parts = []
        for node in article.findall(".//Abstract/AbstractText"):
            label = (node.attrib.get("Label") or "").strip()
            text = re.sub(r"\s+", " ", "".join(node.itertext())).strip()
            if not text:
                continue
            abstract_parts.append(f"{label}: {text}" if label else text)
        abstract = "\n".join(abstract_parts).strip()

        citation = ". ".join(part for part in [title, journal, year, f"PMID: {pmid}"] if part).strip()
        article_ids = {}
        for node in article.findall(".//PubmedData/ArticleIdList/ArticleId"):
            id_type = (node.attrib.get("IdType") or "").strip().lower()
            value = (node.text or "").strip()
            if id_type and value:
                article_ids[id_type] = value
        pmcid = article_ids.get("pmc", "")
        articles.append(
            {
                "pmid": pmid,
                "pmcid": pmcid,
                "doi": article_ids.get("doi", ""),
                "title": title,
                "journal": journal,
                "year": year,
                "authors": authors[:8],
                "abstract": abstract[:5000],
                "citation": citation,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
            }
        )

    return {
        "query": query,
        "formulated_query": formulated_query,
        "search_query": effective_query,
        "attempts": attempts,
        "results": articles,
    }


async def search_semantic_scholar(query: str, max_results: int = 5) -> Dict[str, Any]:
    query = " ".join(str(query or "").split()).strip()
    if not query:
        return {"query": "", "results": [], "error": "query is required"}
    max_results = max(1, min(int(max_results or 5), 10))
    timeout = httpx.Timeout(30.0, connect=10.0)
    fields = "title,abstract,year,authors,journal,externalIds,url,citationCount,openAccessPdf,isOpenAccess,publicationVenue"
    headers = {}
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        response = await client.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={"query": query, "limit": max_results, "fields": fields},
        )
        response.raise_for_status()
    records = []
    for item in (response.json() or {}).get("data", []) or []:
        external = item.get("externalIds") or {}
        doi = _clean_doi(external.get("DOI"))
        pmid = str(external.get("PubMed") or "").strip()
        pmcid = str(external.get("PubMedCentral") or "").strip()
        pdf_url = str((item.get("openAccessPdf") or {}).get("url") or "").strip()
        venue = (item.get("journal") or {}).get("name") or (item.get("publicationVenue") or {}).get("name") or ""
        title = str(item.get("title") or "").strip()
        year = str(item.get("year") or "").strip()
        citation = ". ".join(part for part in [title, venue, year, f"DOI: {doi}" if doi else "", f"PMID: {pmid}" if pmid else ""] if part)
        records.append(
            {
                "source": "semantic_scholar",
                "sources": ["semantic_scholar"],
                "pmid": pmid,
                "pmcid": pmcid,
                "doi": doi,
                "pdf_url": pdf_url,
                "title": title,
                "journal": venue,
                "year": year,
                "authors": [str(author.get("name") or "").strip() for author in (item.get("authors") or [])[:8] if str(author.get("name") or "").strip()],
                "abstract": str(item.get("abstract") or "")[:5000],
                "citation": citation or title,
                "url": str(item.get("url") or "").strip(),
                "cited_by_count": item.get("citationCount"),
                "is_open_access": bool(item.get("isOpenAccess")),
            }
        )
    return {"query": query, "search_query": query, "attempts": [{"query": query, "result_count": len(records)}], "results": records}


async def search_openalex(query: str, max_results: int = 5) -> Dict[str, Any]:
    query = " ".join(str(query or "").split()).strip()
    if not query:
        return {"query": "", "results": [], "error": "query is required"}
    max_results = max(1, min(int(max_results or 5), 10))
    _, email = _tool_user_agent()
    timeout = httpx.Timeout(30.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(
            "https://api.openalex.org/works",
            params={"search": query, "per-page": max_results, "mailto": email},
        )
        response.raise_for_status()
    records = []
    for item in (response.json() or {}).get("results", []) or []:
        ids = item.get("ids") or {}
        doi = _clean_doi(ids.get("doi") or item.get("doi"))
        pmid = str(ids.get("pmid") or "").rstrip("/").split("/")[-1] if ids.get("pmid") else ""
        title = str(item.get("title") or "").strip()
        year = str(item.get("publication_year") or "").strip()
        primary_location = item.get("primary_location") or {}
        source = primary_location.get("source") or {}
        journal = str(source.get("display_name") or "").strip()
        open_access = item.get("open_access") or {}
        pdf_url = str(open_access.get("oa_url") or (primary_location.get("pdf_url") or "")).strip()
        authors = []
        for authorship in (item.get("authorships") or [])[:8]:
            author = authorship.get("author") or {}
            name = str(author.get("display_name") or "").strip()
            if name:
                authors.append(name)
        abstract = ""
        inv = item.get("abstract_inverted_index") or {}
        if isinstance(inv, dict):
            words: List[tuple[int, str]] = []
            for word, positions in inv.items():
                for pos in positions or []:
                    words.append((int(pos), str(word)))
            abstract = " ".join(word for _, word in sorted(words))[:5000]
        citation = ". ".join(part for part in [title, journal, year, f"DOI: {doi}" if doi else "", f"PMID: {pmid}" if pmid else ""] if part)
        records.append(
            {
                "source": "openalex",
                "sources": ["openalex"],
                "pmid": pmid,
                "pmcid": "",
                "doi": doi,
                "pdf_url": pdf_url,
                "title": title,
                "journal": journal,
                "year": year,
                "authors": authors,
                "abstract": abstract,
                "citation": citation or title,
                "url": str(ids.get("openalex") or "").strip(),
                "cited_by_count": item.get("cited_by_count"),
                "is_open_access": bool(open_access.get("is_oa")),
            }
        )
    return {"query": query, "search_query": query, "attempts": [{"query": query, "result_count": len(records)}], "results": records}


async def search_crossref(query: str, max_results: int = 5) -> Dict[str, Any]:
    query = " ".join(str(query or "").split()).strip()
    if not query:
        return {"query": "", "results": [], "error": "query is required"}
    max_results = max(1, min(int(max_results or 5), 10))
    _, email = _tool_user_agent()
    headers = {"User-Agent": f"dsm_interface_agent (mailto:{email})"}
    timeout = httpx.Timeout(30.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        response = await client.get(
            "https://api.crossref.org/works",
            params={"query": query, "rows": max_results, "sort": "relevance"},
        )
        response.raise_for_status()
    records = []
    for item in ((response.json() or {}).get("message") or {}).get("items", []) or []:
        title = str((item.get("title") or [""])[0] or "").strip()
        doi = _clean_doi(item.get("DOI"))
        year_parts = (((item.get("published-print") or item.get("published-online") or item.get("issued") or {}).get("date-parts") or [[]])[0])
        year = str(year_parts[0]) if year_parts else ""
        journal = str((item.get("container-title") or [""])[0] or "").strip()
        authors = []
        for author in (item.get("author") or [])[:8]:
            name = " ".join(part for part in [author.get("given"), author.get("family")] if part).strip()
            if name:
                authors.append(name)
        citation = ". ".join(part for part in [title, journal, year, f"DOI: {doi}" if doi else ""] if part)
        records.append(
            {
                "source": "crossref",
                "sources": ["crossref"],
                "pmid": "",
                "pmcid": "",
                "doi": doi,
                "pdf_url": "",
                "title": title,
                "journal": journal,
                "year": year,
                "authors": authors,
                "abstract": re.sub(r"<[^>]+>", " ", str(item.get("abstract") or ""))[:5000],
                "citation": citation or title,
                "url": str(item.get("URL") or "").strip(),
                "cited_by_count": item.get("is-referenced-by-count"),
            }
        )
    return {"query": query, "search_query": query, "attempts": [{"query": query, "result_count": len(records)}], "results": records}


async def search_literature(
    query: str,
    max_results: int = 5,
    *,
    project_goal: str = "",
    objective_title: str = "",
    objective_definition: str = "",
    objective_signals: List[str] | None = None,
    user_inputs: List[str] | None = None,
) -> Dict[str, Any]:
    query = " ".join(str(query or "").split()).strip()
    max_results = max(1, min(int(max_results or 5), 12))
    if not query:
        return {"query": "", "results": [], "error": "query is required"}
    formulated_query = formulate_pubmed_query(
        query,
        project_goal=project_goal,
        objective_title=objective_title,
        objective_definition=objective_definition,
        objective_signals=objective_signals,
        user_inputs=user_inputs,
        max_terms=8,
    )
    source_calls = [
        ("pubmed", search_pubmed(query, max_results=max_results, project_goal=project_goal, objective_title=objective_title, objective_definition=objective_definition, objective_signals=objective_signals, user_inputs=user_inputs)),
        ("semantic_scholar", search_semantic_scholar(formulated_query or query, max_results=max_results)),
        ("openalex", search_openalex(formulated_query or query, max_results=max_results)),
        ("crossref", search_crossref(formulated_query or query, max_results=max_results)),
    ]
    results_by_key: Dict[str, Dict[str, Any]] = {}
    attempts: List[Dict[str, Any]] = []
    source_counts: Dict[str, int] = {}
    errors: Dict[str, str] = {}
    for source_name, call in source_calls:
        try:
            payload = await call
            records = payload.get("results") or []
            source_counts[source_name] = len(records)
            for attempt in payload.get("attempts") or [{"query": payload.get("search_query") or query, "result_count": len(records)}]:
                attempts.append({"source": source_name, **attempt})
            for record in records:
                record["sources"] = _unique_in_order([*(record.get("sources") or []), source_name])
                key = _record_key(record)
                if not key or key == "title:":
                    continue
                results_by_key[key] = _merge_record(results_by_key[key], record) if key in results_by_key else record
        except Exception as exc:
            source_counts[source_name] = 0
            errors[source_name] = str(exc)
            attempts.append({"source": source_name, "query": formulated_query or query, "result_count": 0, "error": str(exc)})

    results = list(results_by_key.values())
    ranked_results = sorted(
        results,
        key=lambda item: (
            0 if "pubmed" in (item.get("sources") or []) else 1,
            -int(item.get("cited_by_count") or 0),
            -(int(item.get("year") or 0) if str(item.get("year") or "").isdigit() else 0),
        )
    )
    selected: List[Dict[str, Any]] = []
    selected_keys = set()
    source_order = ["pubmed", "semantic_scholar", "openalex", "crossref"]
    while len(selected) < max_results:
        added = False
        for source_name in source_order:
            for item in ranked_results:
                key = _record_key(item)
                if key in selected_keys or source_name not in (item.get("sources") or []):
                    continue
                selected.append(item)
                selected_keys.add(key)
                added = True
                break
            if len(selected) >= max_results:
                break
        if not added:
            break
    for item in ranked_results:
        if len(selected) >= max_results:
            break
        key = _record_key(item)
        if key not in selected_keys:
            selected.append(item)
            selected_keys.add(key)
    return {
        "query": query,
        "formulated_query": formulated_query,
        "search_query": formulated_query or query,
        "attempts": attempts,
        "source_counts": source_counts,
        "errors": errors,
        "results": selected,
    }


def extract_paper_ids(*values: str) -> Dict[str, str]:
    text = "\n".join(str(value or "") for value in values)
    pmid_match = re.search(r"\bPMID\s*:?\s*(\d+)\b|pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", text, re.IGNORECASE)
    pmcid_match = re.search(r"\bPMCID\s*:?\s*(PMC\d+)\b|\b(PMC\d+)\b", text, re.IGNORECASE)
    doi_match = re.search(r"\b(?:DOI\s*:?\s*)?(10\.\d{4,9}/[-._;()/:A-Z0-9]+)\b", text, re.IGNORECASE)
    return {
        "pmid": next((group for group in (pmid_match.groups() if pmid_match else ()) if group), "") if pmid_match else "",
        "pmcid": next((group for group in (pmcid_match.groups() if pmcid_match else ()) if group), "").upper() if pmcid_match else "",
        "doi": doi_match.group(1) if doi_match else "",
    }


async def resolve_pmcid_from_pmid(pmid: str) -> str:
    pmid = str(pmid or "").strip()
    if not pmid:
        return ""
    tool_name, email = _tool_user_agent()
    timeout = httpx.Timeout(30.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi",
            params={
                "dbfrom": "pubmed",
                "db": "pmc",
                "id": pmid,
                "retmode": "json",
                "tool": tool_name,
                "email": email,
            },
        )
        response.raise_for_status()
    payload = response.json() or {}
    for linkset in payload.get("linksets", []):
        for linkdb in linkset.get("linksetdbs", []):
            for link in linkdb.get("links", []):
                value = str(link or "").strip()
                if value:
                    return f"PMC{value}" if not value.upper().startswith("PMC") else value.upper()
    return ""


def _safe_paper_id(pmid: str = "", pmcid: str = "", doi: str = "") -> str:
    raw = pmcid or (f"PMID{pmid}" if pmid else "") or doi or "paper"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("_")[:80] or "paper"


async def download_open_access_pdf(
    *,
    pmid: str = "",
    pmcid: str = "",
    doi: str = "",
    pdf_url: str = "",
    output_dir: str | Path,
) -> Dict[str, Any]:
    if pdf_url:
        paper_id = _safe_paper_id(pmid=pmid, pmcid=pmcid, doi=doi or pdf_url)
        target_dir = Path(output_dir) / paper_id
        target_dir.mkdir(parents=True, exist_ok=True)
        original_path = target_dir / "original.pdf"
        timeout = httpx.Timeout(60.0, connect=15.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            try:
                response = await client.get(pdf_url, headers={"Accept": "application/pdf,*/*"})
                content_type = response.headers.get("content-type", "").lower()
                if response.status_code < 400 and (response.content.startswith(b"%PDF") or "pdf" in content_type):
                    original_path.write_bytes(response.content)
                    return {
                        "status": "success",
                        "paper_id": paper_id,
                        "pmcid": pmcid,
                        "pmid": pmid,
                        "source_pdf_url": pdf_url,
                        "original_pdf_path": str(original_path),
                    }
            except Exception:
                pass

    if not pmcid and pmid:
        pmcid = await resolve_pmcid_from_pmid(pmid)
    if not pmcid:
        return {"status": "not_open_access", "message": "No PubMed Central open-access full text link was found."}

    paper_id = _safe_paper_id(pmid=pmid, pmcid=pmcid, doi=doi)
    target_dir = Path(output_dir) / paper_id
    target_dir.mkdir(parents=True, exist_ok=True)
    original_path = target_dir / "original.pdf"
    candidates = [
        f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/pdf/",
        f"https://europepmc.org/articles/{pmcid}?pdf=render",
    ]
    timeout = httpx.Timeout(60.0, connect=15.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        for url in candidates:
            try:
                response = await client.get(url, headers={"Accept": "application/pdf,*/*"})
                content_type = response.headers.get("content-type", "").lower()
                if response.status_code < 400 and (response.content.startswith(b"%PDF") or "pdf" in content_type):
                    original_path.write_bytes(response.content)
                    return {
                        "status": "success",
                        "paper_id": paper_id,
                        "pmcid": pmcid,
                        "pmid": pmid,
                        "source_pdf_url": url,
                        "original_pdf_path": str(original_path),
                    }
            except Exception:
                continue
    return {"status": "not_open_access", "paper_id": paper_id, "pmcid": pmcid, "pmid": pmid, "message": "Could not download an open-access PDF."}


def _annotation_terms(query: str, objective_text: str) -> List[str]:
    tokens = _tokenize_pubmed_text(f"{query} {objective_text}")
    terms = [token for token in tokens if token in _PUBMED_DOMAIN_TERMS or len(token) >= 5]
    return _unique_in_order(terms)[:24]


_ANNOTATION_WEAK_TERMS = {
    "article",
    "attribution",
    "author",
    "authors",
    "available",
    "background",
    "common",
    "commons",
    "copyright",
    "creative",
    "distributed",
    "figure",
    "figures",
    "international",
    "license",
    "licenses",
    "material",
    "materials",
    "method",
    "methods",
    "original",
    "provided",
    "published",
    "publisher",
    "reference",
    "references",
    "review",
    "rights",
    "section",
    "supplementary",
    "table",
    "terms",
}

_ANNOTATION_BOILERPLATE_PATTERNS = [
    "creative commons",
    "attribution 4.0",
    "copyright",
    "license",
    "distributed under the terms",
    "correspondence",
    "full list of author information",
    "supplementary material",
    "publisher's note",
    "all rights reserved",
    "received:",
    "accepted:",
]


def _weighted_annotation_terms(contexts: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    weights = {
        "query": 6,
        "project_goal": 5,
        "end_product": 6,
        "host": 5,
        "objective": 5,
        "persona": 3,
        "paper": 4,
    }
    labels = {
        "query": "the investigation query",
        "project_goal": "the project goal",
        "end_product": "the target end product",
        "host": "the target host",
        "objective": "the selected objective",
        "objective_title": "the selected objective",
        "persona": "the collaborator lens",
        "persona_name": "the collaborator lens",
        "paper": "the fetched paper summary",
    }
    terms: Dict[str, Dict[str, Any]] = {}
    for source, text in contexts.items():
        for token in _tokenize_pubmed_text(text):
            if token in _ANNOTATION_WEAK_TERMS or len(token) < 4:
                continue
            if token not in _PUBMED_DOMAIN_TERMS and len(token) < 6:
                continue
            entry = terms.setdefault(token, {"score": 0, "sources": []})
            entry["score"] += weights.get(source, 1) + (3 if token in _PUBMED_DOMAIN_TERMS else 0)
            if labels.get(source) not in entry["sources"]:
                entry["sources"].append(labels.get(source, source))
    return dict(sorted(terms.items(), key=lambda item: -item[1]["score"])[:40])


def _is_boilerplate_line(line: str) -> bool:
    lower = line.lower()
    return any(pattern in lower for pattern in _ANNOTATION_BOILERPLATE_PATTERNS)


def _annotation_reason(item: Dict[str, Any], term_info: Dict[str, Dict[str, Any]], contexts: Dict[str, str]) -> str:
    matched = item.get("matched_terms") or []
    source_labels: List[str] = []
    for term in matched:
        for label in term_info.get(term, {}).get("sources", []):
            if label not in source_labels:
                source_labels.append(label)
    anchor_bits = []
    if contexts.get("end_product"):
        anchor_bits.append(f"end product '{contexts['end_product']}'")
    if contexts.get("host"):
        anchor_bits.append(f"host '{contexts['host']}'")
    if contexts.get("objective_title"):
        anchor_bits.append(f"objective '{contexts['objective_title']}'")
    if contexts.get("persona_name"):
        anchor_bits.append(f"collaborator '{contexts['persona_name']}'")
    source_text = ", ".join(source_labels[:3]) or "the current workspace context"
    anchor_text = "; ".join(anchor_bits[:3])
    term_text = ", ".join(matched[:5])
    if item.get("is_figure_caption"):
        if anchor_text:
            return f"Figure/caption evidence relevant to {source_text} ({anchor_text}); matched terms: {term_text}. Use this mainly to locate the associated pathway, construct, or result figure, then verify details in the surrounding text."
        return f"Figure/caption evidence relevant to {source_text}; matched terms: {term_text}. Use this mainly to locate the associated figure, then verify details in the surrounding text."
    if anchor_text:
        return f"Relevant to {source_text} ({anchor_text}); matched evidence terms: {term_text}. Use this passage to judge whether the paper informs this specific project context."
    return f"Relevant to {source_text}; matched evidence terms: {term_text}. Use this passage to judge whether the paper informs the current query."


def _trim_to_word_boundary(text: str, max_chars: int = 650) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if len(cleaned) <= max_chars:
        return cleaned
    clipped = cleaned[:max_chars].rstrip()
    boundary = max(clipped.rfind(". "), clipped.rfind("? "), clipped.rfind("! "))
    if boundary >= 180:
        return clipped[: boundary + 1].strip()
    word_boundary = clipped.rfind(" ")
    if word_boundary >= 180:
        return clipped[:word_boundary].rstrip(" ,;:")
    return clipped.rstrip(" ,;:")


def _looks_like_figure_caption(text: str) -> bool:
    return bool(re.match(r"^\s*(fig\.?|figure|scheme|table)\s*\d+", text or "", flags=re.IGNORECASE))


def _sentence_window_for_terms(text: str, matched_terms: List[str], max_chars: int = 650) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return ""
    if _looks_like_figure_caption(cleaned):
        return _trim_to_word_boundary(cleaned, max_chars=max_chars)

    sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", cleaned) if sentence.strip()]
    if len(sentences) <= 1:
        return _trim_to_word_boundary(cleaned, max_chars=max_chars)

    lower_terms = [term.lower() for term in matched_terms]
    best_index = 0
    best_score = -1
    for index, sentence in enumerate(sentences):
        lower = sentence.lower()
        score = sum(1 for term in lower_terms if term in lower)
        score += 2 if re.search(r"\b(we|this study|result|produced|engineered|increased|titer|yield|pathway)\b", lower) else 0
        if score > best_score:
            best_index = index
            best_score = score

    selected = [sentences[best_index]]
    if best_index > 0 and len(" ".join(selected)) < max_chars * 0.55:
        selected.insert(0, sentences[best_index - 1])
    if best_index + 1 < len(sentences) and len(" ".join(selected)) < max_chars * 0.75:
        selected.append(sentences[best_index + 1])
    return _trim_to_word_boundary(" ".join(selected), max_chars=max_chars)


def _split_page_lines(text: str) -> List[str]:
    lines = []
    for line in re.split(r"[\n\r]+", text or ""):
        cleaned = re.sub(r"\s+", " ", line).strip()
        if len(cleaned) >= 50:
            lines.append(cleaned)
    if lines:
        return lines
    sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text or "").strip())
    return [sentence.strip() for sentence in sentences if len(sentence.strip()) >= 50]


_ANNOTATION_SECTION_TERMS = {
    "activity",
    "biosynthesis",
    "co-culture",
    "coculture",
    "enzyme",
    "engineering",
    "fermentation",
    "flavonoid",
    "glucose",
    "improved",
    "increase",
    "malonyl-coa",
    "metabolic",
    "pathway",
    "precursor",
    "productivity",
    "production",
    "strain",
    "substrate",
    "titer",
    "titre",
    "yield",
}


def _page_text_blocks(page: Any) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []
    page_dict = page.get_text("dict") or {}
    for block_index, block in enumerate(page_dict.get("blocks") or []):
        if block.get("type") != 0:
            continue
        line_items: List[Dict[str, Any]] = []
        for line in block.get("lines") or []:
            spans = [str(span.get("text") or "") for span in (line.get("spans") or [])]
            text = re.sub(r"\s+", " ", "".join(spans)).strip()
            if text:
                bbox = line.get("bbox") or block.get("bbox")
                if bbox:
                    line_items.append({"text": text, "rect": tuple(float(x) for x in bbox)})
                else:
                    line_items.append({"text": text, "rect": None})
        lines = [item["text"] for item in line_items]
        joined = re.sub(r"\s+", " ", " ".join(lines)).strip()
        if len(joined) < 50 or _is_boilerplate_line(joined):
            continue
        block_rect = tuple(float(x) for x in (block.get("bbox") or []))
        rects = [item["rect"] for item in line_items if item.get("rect")]
        blocks.append(
            {
                "block_index": block_index,
                "text": joined,
                "lines": line_items,
                "rects": rects or ([block_rect] if len(block_rect) == 4 else []),
            }
        )
    return blocks


def _focused_block_rects(block: Dict[str, Any], matched_terms: List[str]) -> List[tuple[float, float, float, float]]:
    line_items = block.get("lines") or []
    rects = [item.get("rect") for item in line_items if item.get("rect") and len(item.get("rect")) == 4]
    if not rects:
        return [rect for rect in (block.get("rects") or []) if len(rect) == 4][:6]
    if len(rects) <= 3:
        return rects
    selected_indexes = set()
    lower_terms = [term.lower() for term in matched_terms]
    for index, item in enumerate(line_items[: len(rects)]):
        line = str(item.get("text") or "").lower()
        if any(term.lower() in line for term in matched_terms):
            selected_indexes.add(index)
            if index > 0:
                selected_indexes.add(index - 1)
            if index + 1 < len(rects):
                selected_indexes.add(index + 1)
        elif any(term in line for term in lower_terms):
            selected_indexes.add(index)
    if not selected_indexes:
        return rects[: min(len(rects), 5)]
    return [rects[index] for index in sorted(selected_indexes) if index < len(rects)][:8]


def _candidate_signature(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()[:180]


def _annotation_candidate_score(text: str, matched_terms: List[str], term_info: Dict[str, Dict[str, Any]], *, is_caption: bool = False) -> float:
    lower = text.lower()
    score = sum(term_info.get(term, {}).get("score", 1) for term in set(matched_terms))
    score += min(len(text) / 700.0, 1.5)
    score += sum(1.25 for term in _ANNOTATION_SECTION_TERMS if term in lower)
    if re.search(r"\b\d+(\.\d+)?\s*(g/l|mg/l|ug/l|microg/l|fold|%)\b", lower):
        score += 4.0
    if re.search(r"\b(result|results|discussion|conclusion|we show|we found|we developed|we engineered)\b", lower):
        score += 2.5
    if is_caption:
        score -= 3.0
        if re.search(r"\b(pathway|production|titer|yield|strain|construct|enzyme|genes?)\b", lower):
            score += 1.5
    if re.search(r"\b(reference|references|et al\.|doi:|copyright|license)\b", lower):
        score -= 8.0
    if len(text) < 90:
        score -= 2.0
    return round(score, 3)


def _page_passage_candidates(
    *,
    page: Any,
    page_number: int,
    terms: List[str],
    term_info: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for block in _page_text_blocks(page):
        text = block.get("text") or ""
        if _is_boilerplate_line(text):
            continue
        lower = text.lower()
        matched = [term for term in terms if term.lower() in lower]
        strong_matched = [
            term
            for term in matched
            if term in _PUBMED_DOMAIN_TERMS or term_info.get(term, {}).get("score", 0) >= 8
        ]
        if len(set(strong_matched)) < 2:
            continue
        strong_matched = _unique_in_order(strong_matched)[:12]
        is_caption = _looks_like_figure_caption(text)
        snippet = _sentence_window_for_terms(text, strong_matched, max_chars=700)
        if len(snippet) < 70:
            continue
        rects = _focused_block_rects(block, strong_matched)
        score = _annotation_candidate_score(snippet, strong_matched, term_info, is_caption=is_caption)
        candidates.append(
            {
                "candidate_id": f"p{page_number}_b{block.get('block_index', len(candidates))}",
                "page": page_number,
                "snippet": snippet,
                "matched_terms": strong_matched,
                "score": score,
                "is_figure_caption": is_caption,
                "_rects": rects,
            }
        )
    return candidates


async def _llm_refine_annotation_candidates(
    *,
    candidates: List[Dict[str, Any]],
    contexts: Dict[str, str],
    max_annotations: int,
) -> List[Dict[str, Any]]:
    if not candidates or os.getenv("DISABLE_PDF_ANNOTATION_LLM") == "1":
        return []
    try:
        from ollama_client import ollama
    except Exception:
        return []

    compact_candidates = [
        {
            "candidate_id": item["candidate_id"],
            "page": item["page"],
            "snippet": item["snippet"][:900],
            "matched_terms": item.get("matched_terms") or [],
            "is_figure_caption": bool(item.get("is_figure_caption")),
        }
        for item in candidates[:24]
    ]
    prompt = f"""
You are selecting evidence passages from a scientific PDF for a user's project.

Project goal: {contexts.get('project_goal') or 'not provided'}
Investigation query: {contexts.get('query') or 'not provided'}
End product: {contexts.get('end_product') or 'not provided'}
Target host: {contexts.get('host') or 'not provided'}
Selected objective: {contexts.get('objective_title') or contexts.get('objective') or 'not provided'}
Collaborator lens: {contexts.get('persona_name') or contexts.get('persona') or 'not provided'}

Choose up to {max_annotations} candidates that are actually useful evidence for this project.
Reject boilerplate, generic background, license text, author information, and vague passages.
Treat figure/table captions as lower-priority location aids: select them only when they directly identify a pathway, construct, measurement, or result the user should inspect.
For each selected candidate, write a specific reason that references the user context it informs.

Candidates:
{json.dumps(compact_candidates, indent=2)}

Return JSON:
{{
  "selected": [
    {{
      "candidate_id": "candidate id",
      "reason": "specific reason tied to query/project/objective/persona",
      "evidence_role": "benchmark|method|challenge|transferability|boundary_condition|background"
    }}
  ]
}}
""".strip()
    try:
        payload = await ollama.generate_json(prompt, max_retries=1, temperature=0.1, top_p=0.8)
    except Exception:
        return []
    selected = payload.get("selected") if isinstance(payload, dict) else None
    if not isinstance(selected, list):
        return []
    by_id = {item["candidate_id"]: item for item in candidates}
    refined: List[Dict[str, Any]] = []
    seen = set()
    for item in selected:
        if not isinstance(item, dict):
            continue
        candidate_id = str(item.get("candidate_id") or "").strip()
        if not candidate_id or candidate_id in seen or candidate_id not in by_id:
            continue
        seen.add(candidate_id)
        reason = str(item.get("reason") or "").strip()
        evidence_role = str(item.get("evidence_role") or "").strip()
        candidate = dict(by_id[candidate_id])
        if reason:
            candidate["reason"] = reason
        if evidence_role:
            candidate["evidence_role"] = evidence_role
        refined.append(candidate)
        if len(refined) >= max_annotations:
            break
    return refined


def _extract_research_questions_from_text(text: str, max_questions: int = 8, page_label: str = "") -> List[str]:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    cues = [
        "future",
        "challenge",
        "remain",
        "unknown",
        "further",
        "improve",
        "optimization",
        "potential",
        "need",
        "could",
        "should",
        "limitation",
        "bottleneck",
    ]
    questions: List[str] = []
    seen = set()
    for sentence in sentences:
        sentence = sentence.strip()
        lower = sentence.lower()
        if len(sentence) < 70 or _is_boilerplate_line(sentence):
            continue
        if not any(cue in lower for cue in cues) and "?" not in sentence:
            continue
        if re.search(r"\b(reference|copyright|license|supplementary|publisher)\b", lower):
            continue
        question = sentence if sentence.endswith("?") else f"What project-relevant uncertainty follows from: {sentence[:260].rstrip('.')}?"
        if page_label:
            question = f"{page_label}: {question}"
        key = re.sub(r"\W+", " ", question.lower())[:140]
        if key in seen:
            continue
        seen.add(key)
        questions.append(question)
        if len(questions) >= max_questions:
            break
    return questions


def _extract_research_questions_from_doc(doc: Any, max_questions: int = 8) -> List[str]:
    page_count = len(doc)
    section_cues = [
        "conclusion",
        "conclusions",
        "discussion",
        "future perspective",
        "future directions",
        "challenges",
        "limitations",
        "outlook",
    ]
    candidate_pages: List[int] = []
    page_texts: Dict[int, str] = {}
    for index in range(page_count):
        text = doc[index].get_text("text") or ""
        page_texts[index] = text
        head = text[:1800].lower()
        if any(cue in head for cue in section_cues):
            candidate_pages.append(index)
    candidate_pages.extend(range(max(0, page_count - 5), page_count))

    questions: List[str] = []
    seen = set()
    for index in dict.fromkeys(candidate_pages):
        if index < 0 or index >= page_count:
            continue
        page_questions = _extract_research_questions_from_text(
            page_texts.get(index, ""),
            max_questions=max_questions,
            page_label=f"Page {index + 1}",
        )
        for question in page_questions:
            key = re.sub(r"\W+", " ", question.lower())[:160]
            if key in seen:
                continue
            seen.add(key)
            questions.append(question)
            if len(questions) >= max_questions:
                return questions
    return questions


async def annotate_pdf_for_objective(
    *,
    pdf_path: str | Path,
    query: str,
    project_goal: str = "",
    project_end_product: str = "",
    project_target_host: str = "",
    persona_name: str = "",
    persona_focus: str = "",
    objective_title: str = "",
    objective_definition: str = "",
    objective_signals: List[str] | None = None,
    paper_context: str = "",
    output_path: str | Path | None = None,
    max_annotations: int = 8,
) -> Dict[str, Any]:
    pdf_path = Path(pdf_path)
    output_path = Path(output_path) if output_path else pdf_path.with_name("annotated.pdf")
    contexts = {
        "query": query or "",
        "project_goal": project_goal or "",
        "end_product": project_end_product or "",
        "host": project_target_host or "",
        "objective": " ".join([objective_title or "", objective_definition or "", " ".join(objective_signals or [])]),
        "objective_title": objective_title or "",
        "persona": " ".join([persona_name or "", persona_focus or ""]),
        "persona_name": persona_name or "",
        "paper": paper_context or "",
    }
    term_info = _weighted_annotation_terms(contexts)
    terms = list(term_info.keys())

    try:
        import fitz  # PyMuPDF
    except Exception:
        shutil.copyfile(pdf_path, output_path)
        return {
            "annotated_pdf_path": str(output_path),
            "annotations": [],
            "insights": ["PyMuPDF is not installed, so visual PDF annotations could not be generated."],
            "visual_annotations": False,
        }

    doc = fitz.open(str(pdf_path))
    research_questions = _extract_research_questions_from_doc(doc, max_questions=8)
    candidates: List[Dict[str, Any]] = []
    for page_index, page in enumerate(doc):
        candidates.extend(
            _page_passage_candidates(
                page=page,
                page_number=page_index + 1,
                terms=terms,
                term_info=term_info,
            )
        )

    candidates.sort(key=lambda item: item["score"], reverse=True)
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for item in candidates:
        key = _candidate_signature(item["snippet"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    selected = await _llm_refine_annotation_candidates(
        candidates=deduped[:24],
        contexts=contexts,
        max_annotations=max(1, min(max_annotations, 20)),
    )
    selected_keys = {item.get("candidate_id") for item in selected}
    for item in deduped:
        if len(selected) >= max(1, min(max_annotations, 20)):
            break
        if item.get("candidate_id") in selected_keys:
            continue
        selected.append({**item, "reason": _annotation_reason(item, term_info, contexts)})
        selected_keys.add(item.get("candidate_id"))

    public_selected: List[Dict[str, Any]] = []
    for item in selected:
        if not str(item.get("reason") or "").strip():
            item["reason"] = _annotation_reason(item, term_info, contexts)
        page = doc[item["page"] - 1]
        rects = []
        for rect in item.get("_rects") or []:
            if len(rect) == 4:
                rects.append(fitz.Rect(rect))
        if not rects:
            snippet = item["snippet"]
            rects = page.search_for(snippet)
        if not rects:
            snippet = item["snippet"]
            words = snippet.split()
            for size in [18, 12, 8, 5]:
                if len(words) >= size:
                    rects = page.search_for(" ".join(words[:size]))
                    if rects:
                        break
        if rects:
            annot = page.add_highlight_annot(rects[:8])
            annot.set_info(content=item["reason"])
            annot.update()
        else:
            page.add_text_annot((36, 36), item["reason"])
        public_selected.append(
            {
                "page": int(item.get("page") or 0),
                "snippet": _trim_to_word_boundary(str(item.get("snippet") or ""), max_chars=900),
                "reason": str(item.get("reason") or ""),
                "matched_terms": item.get("matched_terms") or [],
                "score": float(item.get("score") or 0),
            }
        )

    doc.save(str(output_path), garbage=4, deflate=True)
    doc.close()
    insights = [
        f"Page {item['page']}: {item['reason']} Evidence: {_trim_to_word_boundary(item['snippet'], max_chars=320)}"
        for item in public_selected[:5]
    ]
    return {
        "annotated_pdf_path": str(output_path),
        "annotations": public_selected,
        "insights": insights,
        "research_questions": research_questions,
        "visual_annotations": True,
    }


def _resolve_pdf_path(path: str) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    return candidate.resolve()


async def read_local_pdf(path: str, max_pages: int = 5) -> Dict[str, Any]:
    pdf_path = _resolve_pdf_path(path)
    if not pdf_path.exists():
        return {"path": str(pdf_path), "error": "file_not_found"}
    if pdf_path.suffix.lower() != ".pdf":
        return {"path": str(pdf_path), "error": "not_a_pdf"}

    try:
        from pypdf import PdfReader
    except Exception:
        return {"path": str(pdf_path), "error": "pypdf_not_installed"}

    max_pages = max(1, min(int(max_pages or 5), 12))
    reader = PdfReader(str(pdf_path))
    extracted_pages: List[Dict[str, Any]] = []
    text_parts: List[str] = []

    for index, page in enumerate(reader.pages[:max_pages]):
        try:
            text = re.sub(r"\s+", " ", page.extract_text() or "").strip()
        except Exception:
            text = ""
        extracted_pages.append(
            {
                "page_number": index + 1,
                "text_excerpt": text[:1500],
            }
        )
        if text:
            text_parts.append(text[:4000])

    return {
        "path": str(pdf_path),
        "page_count": len(reader.pages),
        "pages_read": min(max_pages, len(reader.pages)),
        "pages": extracted_pages,
        "text_excerpt": "\n\n".join(text_parts)[:12000],
    }


def collect_pdf_paths(*values: str) -> List[str]:
    found: List[str] = []
    seen = set()
    pattern = re.compile(r"([A-Za-z]:\\[^\n\r\t\"']+?\.pdf|/[^\n\r\t\"']+?\.pdf)", re.IGNORECASE)
    for value in values:
        for match in pattern.findall(str(value or "")):
            candidate = match.strip()
            key = candidate.lower()
            if key in seen:
                continue
            seen.add(key)
            found.append(candidate)
    return found[:5]


def get_research_tool_handlers() -> Dict[str, Any]:
    return {
        "search_literature": search_literature,
        "search_pubmed": search_pubmed,
        "read_local_pdf": read_local_pdf,
    }
