import re
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from models import (
    AgenticPlan,
    BuildPaperOntologyRequest,
    BuildOntologyPreviewRequest,
    OntologyEdge,
    OntologyNode,
    OntologyPreviewResponse,
    OntologyQueryAugmentation,
    ResearchWorkTemplate,
    TacitMemoryItem,
)


STOPWORDS = {
    "about",
    "after",
    "also",
    "analysis",
    "and",
    "are",
    "based",
    "because",
    "before",
    "between",
    "both",
    "can",
    "data",
    "does",
    "during",
    "each",
    "from",
    "have",
    "into",
    "more",
    "most",
    "next",
    "not",
    "paper",
    "project",
    "result",
    "results",
    "should",
    "show",
    "study",
    "that",
    "the",
    "their",
    "then",
    "there",
    "these",
    "this",
    "through",
    "using",
    "with",
}

BIOTECH_TERMS = {
    "assay",
    "bioreactor",
    "biosynthesis",
    "cofactor",
    "construct",
    "downstream",
    "enzyme",
    "expression",
    "feedstock",
    "fermentation",
    "flux",
    "gene",
    "host",
    "media",
    "metabolic",
    "omics",
    "pathway",
    "precursor",
    "protein",
    "scale",
    "strain",
    "titer",
    "toxicity",
    "upstream",
    "yield",
}


def _slug(value: str, prefix: str = "node") -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")
    return f"{prefix}_{cleaned[:72]}" if cleaned else f"{prefix}_unknown"


def _compact(value: Optional[str], limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _source_ref_from_ids(source_ids: Dict[str, Any]) -> List[str]:
    refs: List[str] = []
    for key in ("doi", "pmid", "pmcid", "pdf_url"):
        value = str(source_ids.get(key) or "").strip()
        if value:
            refs.append(f"{key}:{value}")
    return refs


def _tokens(text: str) -> List[str]:
    return [token.lower() for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text or "")]


def _candidate_terms(texts: Iterable[str], limit: int = 18) -> List[str]:
    counts: Counter[str] = Counter()
    for text in texts:
        toks = [token for token in _tokens(text) if token not in STOPWORDS]
        for token in toks:
            if token in BIOTECH_TERMS or len(token) >= 5:
                counts[token] += 1
        for left, right in zip(toks, toks[1:]):
            if left not in STOPWORDS and right not in STOPWORDS and (left in BIOTECH_TERMS or right in BIOTECH_TERMS):
                counts[f"{left} {right}"] += 2
    return [term for term, _ in counts.most_common(limit)]


class OntologyBuilder:
    def __init__(self, project_id: int):
        self.project_id = project_id
        self.nodes: Dict[str, OntologyNode] = {}
        self.edges: Dict[str, OntologyEdge] = {}

    def add_node(
        self,
        node_id: str,
        node_type: str,
        label: str,
        description: str = "",
        source_refs: Optional[List[str]] = None,
        attributes: Optional[Dict[str, Any]] = None,
        confidence: float = 0.7,
        status: str = "inferred",
    ) -> str:
        if not label:
            return node_id
        existing = self.nodes.get(node_id)
        if existing:
            refs = sorted(set(existing.source_refs + (source_refs or [])))
            attrs = {**existing.attributes, **(attributes or {})}
            self.nodes[node_id] = existing.model_copy(update={"source_refs": refs, "attributes": attrs})
            return node_id
        self.nodes[node_id] = OntologyNode(
            id=node_id,
            type=node_type,
            label=label,
            description=_compact(description),
            source_refs=source_refs or [],
            attributes=attributes or {},
            confidence=confidence,
            status=status,
        )
        return node_id

    def add_edge(
        self,
        source: str,
        target: str,
        relation: str,
        evidence: Optional[List[str]] = None,
        confidence: float = 0.7,
    ) -> None:
        if not source or not target or source == target:
            return
        edge_id = _slug(f"{source}_{relation}_{target}", "edge")
        existing = self.edges.get(edge_id)
        if existing:
            merged = sorted(set(existing.evidence + (evidence or [])))
            self.edges[edge_id] = existing.model_copy(update={"evidence": merged, "confidence": max(existing.confidence, confidence)})
            return
        self.edges[edge_id] = OntologyEdge(
            id=edge_id,
            source=source,
            target=target,
            relation=relation,
            evidence=[_compact(item, 160) for item in (evidence or []) if item],
            confidence=confidence,
        )

    def concept(self, label: str, source_ref: Optional[str] = None) -> str:
        node_id = _slug(label, "concept")
        self.add_node(node_id, "concept", label, source_refs=[source_ref] if source_ref else [])
        return node_id


def _add_project_context(builder: OntologyBuilder, request: BuildOntologyPreviewRequest) -> Tuple[str, Optional[str]]:
    project_label = request.project_end_product or request.project_goal or f"Project {builder.project_id}"
    project_id = builder.add_node(
        f"project_{builder.project_id}",
        "project",
        project_label,
        request.project_goal or "",
        attributes={"target_host": request.project_target_host, "end_product": request.project_end_product},
    )

    query_id = None
    if request.query:
        query_id = builder.add_node(_slug(request.query, "query"), "query", request.query, request.objective_definition or "")
        builder.add_edge(query_id, project_id, "asks_about", [request.query], 0.9)

    if request.persona_id:
        persona_id = builder.add_node(f"persona_{request.persona_id}", "persona", f"Persona {request.persona_id}")
        builder.add_edge(persona_id, project_id, "works_on", confidence=0.8)

    for label, relation in ((request.project_end_product, "targets_product"), (request.project_target_host, "uses_host")):
        if label:
            concept_id = builder.concept(label)
            builder.add_edge(project_id, concept_id, relation, [request.project_goal or ""], 0.8)

    if request.objective_title:
        objective_id = builder.add_node(
            request.objective_id or _slug(request.objective_title, "objective"),
            "objective",
            request.objective_title,
            request.objective_definition or "",
        )
        builder.add_edge(project_id, objective_id, "frames_decision", [request.objective_definition or ""], 0.8)
        if query_id:
            builder.add_edge(query_id, objective_id, "uses_lens", [request.objective_title], 0.8)

    return project_id, query_id


def _add_work_template(builder: OntologyBuilder, root_id: str, work_template: Optional[ResearchWorkTemplate]) -> None:
    if not work_template:
        return

    concept_edges: Set[Tuple[str, str]] = set()
    for index, finding in enumerate(work_template.literature_findings[:18], start=1):
        source_refs = _source_ref_from_ids(finding.source_ids or {})
        paper_id = builder.add_node(
            finding.id or f"paper_{index}",
            "paper",
            finding.citation or f"Paper {index}",
            finding.relevance or "; ".join((finding.knowns or [])[:2]),
            source_refs=source_refs,
            attributes={"labels": finding.labels, "source_ids": finding.source_ids},
        )
        builder.add_edge(paper_id, root_id, "supports_project", finding.knowns[:2] or [finding.relevance], 0.75)

        terms = list(dict.fromkeys([*(finding.labels or []), *_candidate_terms([finding.relevance, *finding.knowns, *finding.unknowns], 10)]))
        for term in terms[:12]:
            concept_id = builder.concept(term, source_refs[0] if source_refs else None)
            pair = (paper_id, concept_id)
            if pair not in concept_edges:
                builder.add_edge(paper_id, concept_id, "mentions", finding.knowns[:1] or finding.unknowns[:1], 0.7)
                concept_edges.add(pair)

        for judgment in finding.judgment_calls[:6]:
            stance = str(judgment.get("stance") or "").strip()
            if not stance:
                continue
            judgment_id = builder.add_node(
                judgment.get("id") or _slug(f"{finding.id}_{stance}", "judgment"),
                "judgment",
                stance,
                str(judgment.get("rationale") or ""),
            )
            builder.add_edge(judgment_id, paper_id, "interprets", [str(judgment.get("implication") or "")], 0.8)

        for track in finding.validation_tracks[:6]:
            target = str(track.get("target") or "").strip()
            if not target:
                continue
            validation_id = builder.add_node(
                track.get("id") or _slug(f"{finding.id}_{target}", "validation"),
                "validation",
                target,
                str(track.get("method") or ""),
            )
            builder.add_edge(validation_id, paper_id, "tests_claim_from", [str(track.get("success_signal") or "")], 0.75)

    for index, gap in enumerate(work_template.common_gaps[:10], start=1):
        gap_id = builder.add_node(gap.id or f"gap_{index}", "gap", gap.theme, gap.next_question)
        builder.add_edge(root_id, gap_id, "has_open_gap", gap.supporting_signals[:3], 0.75)
        for term in _candidate_terms([gap.theme, gap.next_question, *gap.supporting_signals], 5):
            builder.add_edge(gap_id, builder.concept(term), "needs_knowledge_about", gap.supporting_signals[:1], 0.65)

    for index, proposal in enumerate(work_template.proposal_candidates[:10], start=1):
        proposal_id = builder.add_node(proposal.id or f"proposal_{index}", "proposal", proposal.title, proposal.experiment_outline)
        builder.add_edge(proposal_id, root_id, "proposes_experiment_for", [proposal.why_now], 0.75)
        for readout in proposal.readouts[:8]:
            builder.add_edge(proposal_id, builder.concept(readout), "measured_by", [proposal.experiment_outline], 0.7)


def _add_plan(builder: OntologyBuilder, root_id: str, plan: Optional[AgenticPlan]) -> None:
    if not plan:
        return
    plan_id = builder.add_node(_slug(plan.plan_title, "plan"), "plan", plan.plan_title, plan.strategy_summary)
    builder.add_edge(plan_id, root_id, "operationalizes", plan.success_criteria[:3], 0.8)
    for step in plan.steps[:12]:
        step_id = builder.add_node(step.id, "plan_step", step.title, step.description, attributes={"confidence": step.confidence})
        builder.add_edge(plan_id, step_id, "contains_step", [step.expected_outcome], 0.8)
        for fact in step.evidence_facts[:4]:
            builder.add_edge(step_id, builder.concept(fact), "depends_on_fact", [step.why_this_step], 0.7)


def _add_paper_subgraph(builder: OntologyBuilder, root_id: str, request: BuildPaperOntologyRequest) -> str:
    finding = request.finding
    source_refs = _source_ref_from_ids(finding.source_ids or {})
    paper_seed = source_refs[0] if source_refs else finding.citation or finding.id or "paper"
    paper_id = builder.add_node(
        finding.id or _slug(paper_seed, "paper"),
        "paper",
        finding.citation or "Untitled literature source",
        finding.relevance or "; ".join((finding.knowns or [])[:2]),
        source_refs=source_refs,
        attributes={
            "labels": finding.labels,
            "source_ids": finding.source_ids,
            "paper_scoped": True,
            "ontology_scope": "paper",
        },
        confidence=0.8,
    )
    builder.add_edge(paper_id, root_id, "supports_project", finding.knowns[:2] or [finding.relevance], 0.75)

    if request.objective_title:
        objective_id = request.objective_id or _slug(request.objective_title, "objective")
        builder.add_node(objective_id, "objective", request.objective_title, request.objective_definition or "", confidence=0.75)
        builder.add_edge(paper_id, objective_id, "read_through_lens", [request.objective_definition or request.objective_title], 0.75)

    claim_texts = [(text, "reported_claim") for text in finding.knowns[:10]]
    claim_texts.extend((text, "open_question") for text in finding.unknowns[:10])
    claim_texts.extend((text, "annotation_insight") for text in (finding.annotation_insights or [])[:8])
    claim_texts.extend((text, "generated_research_question") for text in (finding.generated_questions or [])[:8])
    if finding.relevance:
        claim_texts.append((finding.relevance, "project_relevance"))

    for index, (text, claim_type) in enumerate(claim_texts, start=1):
        clean = _compact(text, 260)
        if not clean:
            continue
        claim_id = _slug(f"{paper_id}_{claim_type}_{index}_{clean[:48]}", "claim")
        builder.add_node(
            claim_id,
            "claim",
            clean,
            clean,
            source_refs=source_refs,
            attributes={"claim_type": claim_type, "paper_id": paper_id},
            confidence=0.72 if claim_type in {"reported_claim", "annotation_insight"} else 0.62,
        )
        relation = "reports_claim" if claim_type == "reported_claim" else "raises_question" if claim_type == "open_question" else "contains_interpretation"
        builder.add_edge(paper_id, claim_id, relation, [clean], 0.72)
        for term in _candidate_terms([clean], 6):
            builder.add_edge(claim_id, builder.concept(term, source_refs[0] if source_refs else None), "mentions_concept", [clean], 0.65)

    for label in finding.labels[:10]:
        concept_id = builder.concept(label, source_refs[0] if source_refs else None)
        builder.add_edge(paper_id, concept_id, "tagged_with", [label], 0.7)

    for judgment in finding.judgment_calls[:8]:
        stance = str(judgment.get("stance") or "").strip()
        if not stance:
            continue
        judgment_id = builder.add_node(
            judgment.get("id") or _slug(f"{paper_id}_{stance}", "judgment"),
            "judgment",
            stance,
            str(judgment.get("rationale") or ""),
            source_refs=source_refs,
            attributes={"paper_id": paper_id},
            confidence=0.85,
        )
        builder.add_edge(judgment_id, paper_id, "interprets", [str(judgment.get("implication") or "")], 0.85)

    for track in finding.validation_tracks[:8]:
        target = str(track.get("target") or "").strip()
        if not target:
            continue
        validation_id = builder.add_node(
            track.get("id") or _slug(f"{paper_id}_{target}", "validation"),
            "validation",
            target,
            str(track.get("method") or ""),
            source_refs=source_refs,
            attributes={"paper_id": paper_id, "execution_result": track.get("execution_result") or {}},
            confidence=0.78,
        )
        builder.add_edge(validation_id, paper_id, "tests_claim_from", [str(track.get("success_signal") or "")], 0.78)
        for question in (track.get("questions") or [])[:5]:
            builder.add_edge(validation_id, builder.concept(str(question)), "asks_about", [str(question)], 0.65)

    return paper_id


def _add_tacit_memory(builder: OntologyBuilder, root_id: str, tacit_state: List[TacitMemoryItem]) -> List[str]:
    usable: List[str] = []
    for item in tacit_state[:12]:
        if item.status == "rejected":
            continue
        memory_id = builder.add_node(item.id, "tacit_memory", item.label, item.inference, attributes={"status": item.status})
        builder.add_edge(root_id, memory_id, "has_tacit_context", item.evidence[:3], max(0.45, item.confidence))
        usable.append(f"{item.label}: {item.inference}")
        for term in _candidate_terms([item.label, item.inference, *(item.evidence or [])], 4):
            builder.add_edge(memory_id, builder.concept(term), "makes_explicit", item.evidence[:1], max(0.45, item.confidence))
    return usable


def _query_augmentation(builder: OntologyBuilder, tacit_context: List[str]) -> OntologyQueryAugmentation:
    return _query_augmentation_from_items(list(builder.nodes.values()), list(builder.edges.values()), tacit_context)


def _query_augmentation_from_items(
    nodes: List[OntologyNode],
    edges: List[OntologyEdge],
    tacit_context: Optional[List[str]] = None,
) -> OntologyQueryAugmentation:
    degree: Dict[str, int] = defaultdict(int)
    for edge in edges:
        if edge.status == "rejected":
            continue
        degree[edge.source] += 1
        degree[edge.target] += 1

    concepts = [
        node
        for node in nodes
        if node.status != "rejected" and node.type == "concept" and len(node.label) > 2
    ]
    concepts.sort(key=lambda node: (-degree[node.id], node.label))

    filters: Dict[str, List[str]] = {"pmid": [], "pmcid": [], "doi": []}
    for node in nodes:
        if node.status == "rejected":
            continue
        for ref in node.source_refs:
            key, _, value = ref.partition(":")
            if key in filters and value and value not in filters[key]:
                filters[key].append(value)

    lenses = [
        node.label
        for node in nodes
        if node.status != "rejected" and node.type in {"objective", "gap", "validation", "plan_step"}
    ][:10]

    routing: List[str] = []
    if any(node.status != "rejected" and node.type == "paper" for node in nodes):
        routing.append("literature")
    if any(node.status != "rejected" and node.type == "validation" for node in nodes):
        routing.append("experiment_validation")
    tacit_context = tacit_context or [
        f"{node.label}: {node.description}"
        for node in nodes
        if node.status != "rejected" and node.type == "tacit_memory" and node.description
    ][:8]
    if tacit_context:
        routing.append("tacit_memory")
    if any(node.status != "rejected" and node.type == "plan_step" for node in nodes):
        routing.append("planning")

    return OntologyQueryAugmentation(
        expanded_terms=[node.label for node in concepts[:18]],
        filters={key: values[:12] for key, values in filters.items() if values},
        reasoning_lenses=lenses,
        tacit_context=tacit_context[:8],
        search_routing=routing or ["general_project_context"],
    )


def build_ontology_preview(project_id: int, request: BuildOntologyPreviewRequest) -> OntologyPreviewResponse:
    builder = OntologyBuilder(project_id)
    root_id, _ = _add_project_context(builder, request)
    _add_work_template(builder, root_id, request.work_template)
    _add_plan(builder, root_id, request.plan)
    tacit_context = _add_tacit_memory(builder, root_id, request.tacit_state)

    augmentation = _query_augmentation(builder, tacit_context)
    summary = (
        f"Ontology preview links {len(builder.nodes)} entities through {len(builder.edges)} relationships. "
        f"It can expand search with {len(augmentation.expanded_terms)} terms and route queries through "
        f"{', '.join(augmentation.search_routing)}."
    )


def build_paper_ontology(project_id: int, request: BuildPaperOntologyRequest) -> OntologyPreviewResponse:
    builder = OntologyBuilder(project_id)
    project_request = BuildOntologyPreviewRequest(
        persona_id=request.persona_id,
        query=request.query,
        objective_id=request.objective_id,
        objective_title=request.objective_title,
        objective_definition=request.objective_definition,
        project_goal=request.project_goal,
        project_end_product=request.project_end_product,
        project_target_host=request.project_target_host,
    )
    root_id, _ = _add_project_context(builder, project_request)
    paper_id = _add_paper_subgraph(builder, root_id, request)
    augmentation = _query_augmentation_from_items(list(builder.nodes.values()), list(builder.edges.values()))
    summary = (
        f"Paper ontology extracted {len(builder.nodes)} entities and {len(builder.edges)} relationships from "
        f"{builder.nodes.get(paper_id).label if builder.nodes.get(paper_id) else 'the selected paper'}."
    )
    return OntologyPreviewResponse(
        project_id=project_id,
        summary=summary,
        nodes=list(builder.nodes.values()),
        edges=list(builder.edges.values()),
        query_augmentation=augmentation,
        persisted=False,
        sync_message=summary,
    )
    return OntologyPreviewResponse(
        project_id=project_id,
        summary=summary,
        nodes=list(builder.nodes.values()),
        edges=list(builder.edges.values()),
        query_augmentation=augmentation,
    )


def ontology_response_from_graph(
    project_id: int,
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    *,
    persisted: bool,
    last_synced_at: Optional[str] = None,
    sync_message: str = "",
) -> OntologyPreviewResponse:
    validated_nodes = [OntologyNode.model_validate(node) for node in nodes]
    validated_edges = [OntologyEdge.model_validate(edge) for edge in edges]
    augmentation = _query_augmentation_from_items(validated_nodes, validated_edges)
    summary = (
        f"Stored ontology contains {len(validated_nodes)} entities and {len(validated_edges)} relationships. "
        f"It can expand search with {len(augmentation.expanded_terms)} terms and route queries through "
        f"{', '.join(augmentation.search_routing)}."
    )
    if last_synced_at:
        summary = f"{summary} Last synced: {last_synced_at}."
    return OntologyPreviewResponse(
        project_id=project_id,
        summary=summary,
        nodes=validated_nodes,
        edges=validated_edges,
        query_augmentation=augmentation,
        persisted=persisted,
        sync_message=sync_message,
    )
