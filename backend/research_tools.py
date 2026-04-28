from __future__ import annotations

import json
import os
import re
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
    return [PUBMED_SEARCH_TOOL, READ_LOCAL_PDF_TOOL]


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
        articles.append(
            {
                "pmid": pmid,
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
        "search_pubmed": search_pubmed,
        "read_local_pdf": read_local_pdf,
    }
