from __future__ import annotations

from typing import Any, Dict, List, Tuple

from main import _fallback_objective_clusters, _fallback_tacit_memory
from models import BuildOntologyPreviewRequest, InferWorkspaceMemoryRequest, ObjectivesRequest
from ontology_service import build_ontology_preview
from research_tools import formulate_pubmed_query


DEFAULT_COLLABORATOR_LENS = "Evidence-focused literature collaborator"
RETRIEVAL_UNSAFE_TERMS = {
    "being",
    "collaborator",
    "currently",
    "framing",
    "persona",
    "reasoning",
    "selected",
    "evidence",
    "synthesis",
}


def _select_retrieval_objective(objectives: List[Any]) -> Any:
    for objective in objectives:
        if getattr(objective, "id", "") == "obj_evidence":
            return objective
    return objectives[0] if objectives else None


def _unique_terms(items: List[str]) -> List[str]:
    seen = set()
    unique = []
    for item in items:
        term = " ".join(str(item or "").split()).strip()
        key = term.lower()
        if not term or key in seen or key in RETRIEVAL_UNSAFE_TERMS:
            continue
        seen.add(key)
        unique.append(term)
    return unique


def build_query_only_system_augmentation(query: str, project_id: int = 0) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Derive retrieval augmentation from the same query-planning pieces used by the app.

    This intentionally uses only the benchmark query. It does not inject gold labels,
    relevant paper ids, user answers, or external dataset metadata.
    """
    objective_response = _fallback_objective_clusters(ObjectivesRequest(query=query, k=5))
    selected_objective = _select_retrieval_objective(objective_response.objectives)
    selected_objective_payload = selected_objective.model_dump() if selected_objective else {}

    explicit_state = {
        "query": query,
        "selected_project": {"project_goal": query},
        "selected_objective": selected_objective_payload,
        "persona": DEFAULT_COLLABORATOR_LENS,
    }
    memory = _fallback_tacit_memory(
        InferWorkspaceMemoryRequest(
            workspace_key=f"benchmark:{project_id}",
            scope="benchmark",
            explicit_state=explicit_state,
        )
    )
    objective_definition = ""
    if selected_objective:
        signals = ", ".join(getattr(selected_objective, "signals", []) or [])
        objective_definition = " ".join(
            part
            for part in [
                getattr(selected_objective, "definition", ""),
                f"Signals: {signals}" if signals else "",
            ]
            if part
        )
    objective_signals = list(getattr(selected_objective, "signals", []) or []) if selected_objective else []
    preview = build_ontology_preview(
        project_id,
        BuildOntologyPreviewRequest(
            query=query,
            project_goal=query,
            objective_id=getattr(selected_objective, "id", None),
            objective_title=getattr(selected_objective, "title", None),
            objective_definition=objective_definition,
            explicit_state=explicit_state,
            tacit_state=memory.tacit_state,
        ),
    )
    preview_augmentation = preview.query_augmentation.model_dump()
    formulated_query = formulate_pubmed_query(
        query,
        project_goal=query,
        objective_title=getattr(selected_objective, "title", "") if selected_objective else "",
        objective_definition=objective_definition,
        objective_signals=objective_signals,
        user_inputs=[],
        max_terms=8,
    )
    retrieval_terms = _unique_terms(
        formulated_query.split()
        + list(preview_augmentation.get("expanded_terms") or [])
        + objective_signals
    )[:18]
    augmentation = {
        "expanded_terms": retrieval_terms,
        "filters": preview_augmentation.get("filters", {}),
        "reasoning_lenses": [],
        "tacit_context": [],
        "search_routing": preview_augmentation.get("search_routing", []),
    }
    audit = {
        "query": query,
        "project_goal": query,
        "collaborator_lens": DEFAULT_COLLABORATOR_LENS,
        "selected_objective": selected_objective_payload,
        "global_questions": objective_response.global_questions,
        "tacit_state": [item.model_dump() for item in memory.tacit_state],
        "elicitation_questions": [item.model_dump() for item in memory.elicitation_questions],
        "ontology_summary": preview.summary,
        "ontology_node_count": len(preview.nodes),
        "ontology_edge_count": len(preview.edges),
        "formulated_query": formulated_query,
        "raw_ontology_query_augmentation": preview_augmentation,
        "query_augmentation": augmentation,
    }
    return augmentation, audit
