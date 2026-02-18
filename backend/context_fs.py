from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional
import os
import re

CONTEXT_ROOT = Path(__file__).resolve().parent / "data" / "context"


@dataclass(frozen=True)
class ContextEntry:
    name: str
    path: str
    type: str
    size: int
    modified_at: str


@dataclass(frozen=True)
class SearchMatch:
    path: str
    line: int
    snippet: str


def ensure_context_root() -> None:
    CONTEXT_ROOT.mkdir(parents=True, exist_ok=True)


def resolve_context_path(request_path: Optional[str]) -> Path:
    ensure_context_root()
    if not request_path:
        return CONTEXT_ROOT
    cleaned = request_path.strip()
    if cleaned.startswith("/context"):
        cleaned = cleaned[len("/context"):]
    cleaned = cleaned.lstrip("/")
    candidate = (CONTEXT_ROOT / cleaned).resolve()
    if CONTEXT_ROOT not in candidate.parents and candidate != CONTEXT_ROOT:
        raise ValueError("Path escapes context root")
    return candidate


def list_context_dir(request_path: Optional[str]) -> List[ContextEntry]:
    target = resolve_context_path(request_path)
    if not target.exists():
        raise FileNotFoundError("Path not found")
    if not target.is_dir():
        raise NotADirectoryError("Path is not a directory")

    entries: List[ContextEntry] = []
    for item in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        stat = item.stat()
        entry_path = "/context" + str(item.relative_to(CONTEXT_ROOT)).replace(os.sep, "/")
        entries.append(
            ContextEntry(
                name=item.name,
                path=entry_path,
                type="dir" if item.is_dir() else "file",
                size=stat.st_size,
                modified_at=str(int(stat.st_mtime)),
            )
        )
    return entries


def read_context_file(request_path: str, offset: int = 1, limit: int = 2000) -> dict:
    target = resolve_context_path(request_path)
    if not target.exists():
        raise FileNotFoundError("Path not found")
    if not target.is_file():
        raise IsADirectoryError("Path is a directory")

    if offset < 1:
        offset = 1
    if limit < 1:
        limit = 1

    with target.open("r", encoding="utf-8", errors="replace") as handle:
        lines = handle.readlines()

    total_lines = len(lines)
    start_index = offset - 1
    end_index = min(start_index + limit, total_lines)
    sliced = lines[start_index:end_index]
    content = "".join(sliced)
    return {
        "path": "/context" + str(target.relative_to(CONTEXT_ROOT)).replace(os.sep, "/"),
        "content": content,
        "offset": offset,
        "limit": limit,
        "total_lines": total_lines,
        "truncated": end_index < total_lines,
    }


def write_context_file(request_path: str, content: str, overwrite: bool = False) -> dict:
    target = resolve_context_path(request_path)
    if target.exists() and not overwrite:
        raise FileExistsError("File already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        handle.write(content)
    return {
        "path": "/context" + str(target.relative_to(CONTEXT_ROOT)).replace(os.sep, "/"),
        "bytes_written": target.stat().st_size,
    }


def search_context(
    query: str,
    request_path: Optional[str] = None,
    regex: bool = False,
    case_sensitive: bool = False,
    max_results: int = 200,
) -> List[SearchMatch]:
    target = resolve_context_path(request_path)
    if not target.exists():
        raise FileNotFoundError("Path not found")

    pattern = query
    flags = 0 if case_sensitive else re.IGNORECASE
    matcher = None
    if regex:
        matcher = re.compile(pattern, flags)

    matches: List[SearchMatch] = []
    paths: Iterable[Path]
    if target.is_file():
        paths = [target]
    else:
        paths = target.rglob("*")

    for file_path in paths:
        if file_path.is_dir():
            continue
        try:
            with file_path.open("r", encoding="utf-8", errors="replace") as handle:
                for idx, line in enumerate(handle, start=1):
                    if matcher:
                        found = matcher.search(line) is not None
                    else:
                        hay = line if case_sensitive else line.lower()
                        needle = query if case_sensitive else query.lower()
                        found = needle in hay
                    if found:
                        rel_path = "/context" + str(file_path.relative_to(CONTEXT_ROOT)).replace(os.sep, "/")
                        matches.append(SearchMatch(path=rel_path, line=idx, snippet=line.strip()))
                        if len(matches) >= max_results:
                            return matches
        except OSError:
            continue
    return matches
