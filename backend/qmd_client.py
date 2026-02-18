from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class QmdMatch:
    path: str
    snippet: str
    score: Optional[float] = None
    doc_id: Optional[str] = None
    line: int = 0


@dataclass(frozen=True)
class QmdDocument:
    path: str
    content: str
    doc_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class QmdCollection:
    name: str
    path: str
    document_count: int


class QmdError(Exception):
    pass


def _run_qmd(args: List[str]) -> Tuple[int, str, str]:
    """Execute qmd command and return (returncode, stdout, stderr)."""
    try:
        completed = subprocess.run(
            ["qmd"] + args,
            capture_output=True,
            text=True,
            check=False
        )
        return completed.returncode, completed.stdout, completed.stderr
    except FileNotFoundError as exc:
        raise QmdError("qmd is not installed or not available in PATH") from exc


def _extract_items(payload: Any) -> List[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("results", "matches", "documents", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [payload]
    return []


def _to_match(item: dict) -> QmdMatch:
    path = (
        item.get("path")
        or item.get("file")
        or item.get("source")
        or item.get("uri")
        or item.get("id")
        or ""
    )
    snippet = (
        item.get("snippet")
        or item.get("content")
        or item.get("text")
        or item.get("preview")
        or ""
    )
    score_raw = item.get("score")
    score = None
    if isinstance(score_raw, (int, float)):
        score = float(score_raw)

    doc_id = item.get("docid") or item.get("doc_id") or item.get("id")
    line_raw = item.get("line")
    line = int(line_raw) if isinstance(line_raw, int) else 0

    return QmdMatch(
        path=str(path),
        snippet=str(snippet),
        score=score,
        doc_id=str(doc_id) if doc_id else None,
        line=line
    )


def _to_document(item: dict) -> QmdDocument:
    """Convert a QMD result item to a QmdDocument."""
    path = (
        item.get("path")
        or item.get("file")
        or item.get("source")
        or item.get("uri")
        or ""
    )
    content = (
        item.get("content")
        or item.get("text")
        or item.get("full")
        or item.get("snippet")
        or ""
    )
    doc_id = item.get("docid") or item.get("doc_id") or item.get("id")
    
    # Extract any other fields as metadata
    metadata = {k: v for k, v in item.items() 
                if k not in ("path", "file", "source", "uri", "content", "text", "full", "snippet", "docid", "doc_id", "id")}
    
    return QmdDocument(
        path=str(path),
        content=str(content),
        doc_id=str(doc_id) if doc_id else None,
        metadata=metadata if metadata else None
    )


def qmd_search(
    query: str,
    mode: str = "hybrid",
    collection: Optional[str] = None,
    limit: int = 10,
    min_score: Optional[float] = None
) -> List[QmdMatch]:
    """
    Search documents using QMD.
    
    Args:
        query: Search query string
        mode: Search mode - "hybrid" (default), "keyword", or "semantic"
        collection: Optional collection name to search within
        limit: Maximum number of results (default: 10)
        min_score: Minimum relevance score threshold
    """
    command_name = "query"
    if mode == "keyword":
        command_name = "search"
    elif mode == "semantic":
        command_name = "vsearch"

    args = [command_name, query, "--json", "-n", str(limit)]
    
    if collection:
        args.extend(["-c", collection])
    
    if min_score is not None:
        args.extend(["--min-score", str(min_score)])

    returncode, stdout, stderr = _run_qmd(args)

    if returncode != 0:
        error_msg = stderr.strip() or stdout.strip() or "unknown error"
        raise QmdError(f"qmd command failed: {error_msg}")

    output = stdout.strip()
    if not output:
        return []

    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        raise QmdError("qmd returned non-JSON output") from exc

    items = _extract_items(payload)
    return [_to_match(item) for item in items]


def qmd_get(path_or_docid: str, full: bool = True) -> Optional[QmdDocument]:
    """
    Get a single document by path or docid.
    
    Args:
        path_or_docid: Document path or docid (prefix with # for docid)
        full: Return full content (default: True)
    
    Returns:
        QmdDocument or None if not found
    """
    args = ["get", path_or_docid, "--json"]
    
    if full:
        args.append("--full")
    
    returncode, stdout, stderr = _run_qmd(args)
    
    if returncode != 0:
        error_msg = stderr.strip() or stdout.strip() or "unknown error"
        if "not found" in error_msg.lower():
            return None
        raise QmdError(f"qmd get failed: {error_msg}")
    
    output = stdout.strip()
    if not output:
        return None
    
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        raise QmdError("qmd returned non-JSON output") from exc
    
    items = _extract_items(payload)
    if not items:
        return None
    
    return _to_document(items[0])


def qmd_multi_get(pattern: str, full: bool = True) -> List[QmdDocument]:
    """
    Get multiple documents matching a glob pattern.
    
    Args:
        pattern: Glob pattern (e.g., "journals/2025-05*.md")
        full: Return full content (default: True)
    
    Returns:
        List of QmdDocument objects
    """
    args = ["multi-get", pattern, "--json"]
    
    if full:
        args.append("--full")
    
    returncode, stdout, stderr = _run_qmd(args)
    
    if returncode != 0:
        error_msg = stderr.strip() or stdout.strip() or "unknown error"
        raise QmdError(f"qmd multi-get failed: {error_msg}")
    
    output = stdout.strip()
    if not output:
        return []
    
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        raise QmdError("qmd returned non-JSON output") from exc
    
    items = _extract_items(payload)
    return [_to_document(item) for item in items]


def qmd_list_collections() -> List[QmdCollection]:
    """
    List all configured QMD collections.
    
    Returns:
        List of QmdCollection objects
    """
    # Try to get collection info from qmd
    returncode, stdout, stderr = _run_qmd(["collection", "list", "--json"])
    
    if returncode != 0:
        # Fallback: qmd might not have a collection list command
        # In that case, we'll need to parse the config or return empty
        return []
    
    output = stdout.strip()
    if not output:
        return []
    
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return []
    
    items = _extract_items(payload)
    collections = []
    
    for item in items:
        name = item.get("name") or item.get("collection") or ""
        path = item.get("path") or item.get("location") or ""
        count = item.get("count") or item.get("documents") or item.get("size") or 0
        
        if name:
            collections.append(QmdCollection(
                name=str(name),
                path=str(path),
                document_count=int(count) if isinstance(count, (int, float, str)) else 0
            ))
    
    return collections


def qmd_embed() -> bool:
    """
    Regenerate embeddings for all collections.
    
    Returns:
        True if successful, False otherwise
    """
    returncode, _, stderr = _run_qmd(["embed"])
    
    if returncode != 0:
        error_msg = stderr.strip() or "embedding failed"
        raise QmdError(f"qmd embed failed: {error_msg}")
    
    return True


def qmd_add_collection(path: str, name: str) -> bool:
    """
    Add a new collection to QMD.
    
    Args:
        path: Directory path for the collection
        name: Collection name
    
    Returns:
        True if successful
    """
    returncode, _, stderr = _run_qmd(["collection", "add", path, "--name", name])
    
    if returncode != 0:
        error_msg = stderr.strip() or "failed to add collection"
        # Collection might already exist, which is fine
        if "already" in error_msg.lower():
            return True
        raise QmdError(f"qmd collection add failed: {error_msg}")
    
    return True


def qmd_add_context(collection_uri: str, description: str) -> bool:
    """
    Add context metadata to a collection.
    
    Args:
        collection_uri: Collection URI (e.g., "qmd://socialization")
        description: Context description
    
    Returns:
        True if successful
    """
    returncode, _, stderr = _run_qmd(["context", "add", collection_uri, description])
    
    if returncode != 0:
        error_msg = stderr.strip() or "failed to add context"
        raise QmdError(f"qmd context add failed: {error_msg}")
    
    return True


def qmd_sync_fs_to_index(context_root: str) -> Tuple[int, int]:
    """
    Sync filesystem changes to QMD index.
    Re-embeds all documents to pick up new/changed files.
    
    Args:
        context_root: Root directory of context files
    
    Returns:
        Tuple of (collections_updated, documents_indexed)
    """
    # Regenerate embeddings - this will pick up new files
    qmd_embed()
    
    # Try to get stats
    collections = qmd_list_collections()
    total_docs = sum(c.document_count for c in collections)
    
    return len(collections), total_docs


def health_check() -> Dict[str, Any]:
    """
    Check QMD health and configuration.
    
    Returns:
        Dict with status info
    """
    try:
        returncode, stdout, _ = _run_qmd(["--version"])
        
        if returncode != 0:
            return {"healthy": False, "error": "qmd command failed"}
        
        version = stdout.strip()
        collections = qmd_list_collections()
        
        return {
            "healthy": True,
            "version": version,
            "collections_count": len(collections),
            "collections": [{"name": c.name, "path": c.path, "documents": c.document_count} 
                          for c in collections]
        }
    except QmdError as e:
        return {"healthy": False, "error": str(e)}
