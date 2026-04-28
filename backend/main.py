from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from typing import Optional, List, Dict, Any
import asyncio
import os
from pathlib import Path
import json
import re

from models import (
    ObjectivesRequest, ObjectivesResponse, Objective,
    AugmentRequest, AugmentResponse, EvidenceItem,
    FinalizeRequest, FinalizeResponse, LogEventRequest,
    ContextListEntry, ContextListResponse, ContextReadResponse,
    ContextWriteRequest, ContextWriteResponse,
    ContextSearchMatch, ContextSearchRequest, ContextSearchResponse,
    ContextGetRequest, ContextGetResponse,
    ContextMultiGetRequest, ContextMultiGetResponse,
    ContextCollectionInfo, ContextCollectionsResponse,
    ContextSyncResponse, QmdHealthResponse,
    CreateReportRequest, CreateReportResponse, ReportMetadataResponse,
    UpdateReportQmdRequest, RenderReportRequest, RenderReportResponse, ReportLogsResponse,
    CreateInterviewRequest, CreateInterviewResponse,
    ImportInterviewTextsRequest, ImportInterviewTextsResponse,
    InterviewResponse, InterviewListResponse,
    PersonaFromInterviewsRequest, PersonaFromInterviewsResponse,
    ExtractAllPersonasRequest, ExtractAllPersonasResponse,
    GeneratePlanRequest, GeneratePlanResponse, AgenticPlan, PlanStep,
    InferWorkspaceMemoryRequest, InferWorkspaceMemoryResponse,
    FeedbackRequest, FeedbackResponse,
    PersonaRefactorResponse, PersonaRefactorItem,
    UpdatePersonaRequest,
    PersonaResponse, PersonaListResponse,
    PersonaPayload, PersonaChangeLogResponse, PersonaChangeLogItem,
    PersonaBootstrapRequest, PersonaBootstrapResponse,
    PersonaTemplateListResponse, PersonaTemplateSummary,
    CreatePersonaFromTemplateRequest, CreatePersonaFromTemplateResponse,
    ResetPersonasRequest, ResetPersonasResponse,
    ImportPersonaMarkdownRequest, ImportPersonaMarkdownResponse,
    CreateProjectRequest, CreateProjectResponse,
    ProjectResponse, ProjectListResponse, ProjectWorkflowPersona,
    GenerateProjectPlanRequest, ResearchWorkTemplate,
    ProjectWorkspaceState, ProjectWorkspaceRequest, ProjectWorkspaceResponse,
    StartProjectExecutionRequest, ProjectExecutionEvent, ProjectExecutionRunResponse,
    FetchProjectLiteratureRequest, FetchProjectLiteratureResponse, LiteratureToolTrace, ResearchFinding,
    TacitMemoryItem, WorkspaceMemory, WorkspaceMemoryRequest, WorkspaceMemoryResponse,
)
from ollama_client import ollama
from database import db
from report_service import (
    default_qmd_skeleton,
    write_qmd,
    read_qmd,
    compute_content_hash,
    manifest_cache_hit,
    read_log_tail,
)
from persona_extractor import (
    extract_persona_from_interviews,
    save_persona_snapshot,
    merge_persona_payloads,
    build_persona_summary,
)
from context_fs import (
    list_context_dir,
    read_context_file,
    write_context_file,
    ensure_context_root
)
from qmd_client import (
    qmd_search, qmd_get, qmd_multi_get, qmd_list_collections,
    qmd_sync_fs_to_index, QmdError
)
from qmd_client import health_check as qmd_health_check
from persona_templates import list_persona_templates, get_persona_template
from project_workflows import build_project_personas
from agent_execution import run_agentic_execution, to_execution_response
from research_tools import search_pubmed

app = FastAPI(title="SECI Query Explorer API", version="1.0.0")

_persona_refactor_task: Optional[asyncio.Task] = None
_persona_refactor_lock = asyncio.Lock()
_persona_display_name_cache: Dict[int, Dict[str, str]] = {}
_project_execution_tasks: Dict[int, asyncio.Task] = {}
_PROJECT_STAGE_ORDER = {
    "feedstock": 0,
    "strain_engineering": 1,
    "upstream_process": 2,
    "downstream_processing": 3,
    "economics": 4,
}

ensure_context_root()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _persona_header(persona_id: Optional[int]) -> str:
    if not persona_id:
        return ""
    persona = db.get_persona(persona_id)
    if not persona:
        return ""
    summary = persona.get("last_summary") or ""
    if not summary:
        return ""
    return f"\nPersona Header:\n{summary}\n"


def _assemble_prompt(system_instruction: str, persona_id: Optional[int], task_context: str) -> str:
    return (
        f"SYSTEM:\n{system_instruction}\n"
        f"{_persona_header(persona_id)}\n"
        f"TASK_CONTEXT:\n{task_context}"
    )


def _extract_context_value(context: Optional[str], label: str) -> str:
    if not context:
        return ""
    match = re.search(rf"(?im)^{re.escape(label)}:\s*(.+)$", context)
    return match.group(1).strip() if match else ""


def _truncate_text(value: str, limit: int = 120) -> str:
    text = " ".join(str(value or "").split()).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _fallback_objective_clusters(request: ObjectivesRequest) -> ObjectivesResponse:
    query = " ".join((request.query or "").split()).strip() or "the project question"
    context = request.context or ""
    end_product = _extract_context_value(context, "End product")
    target_host = _extract_context_value(context, "Target host")
    topic = end_product or _truncate_text(query, 90)
    host_suffix = f" in {target_host}" if target_host else ""
    source_text = f"{query}\n{context}".lower()

    specs = [
        {
            "id": "obj_evidence",
            "title": "Evidence synthesis",
            "subtitle": "Review reported strategies, benchmark examples, and open questions.",
            "definition": (
                f"Map the strongest published approaches for {topic}{host_suffix}. Compare benchmark examples, "
                "common engineering strategies, recent improvement options, and unresolved bottlenecks before choosing the next move."
            ),
            "signals": ["literature", "benchmarks", "examples", "papers", "recent work", "open questions"],
            "facet_questions": [
                "Should the synthesis prioritize strategy patterns, quantitative benchmarks, or both?",
                "Do you want the output to end with concrete next experiments or stay as a literature review?",
                "Should the review focus tightly on the selected host or include broader microbial examples too?",
            ],
            "exemplar_answer": (
                "Summarize the strongest examples, compare what actually improved performance, identify recurring bottlenecks, "
                "and end with the most credible next hypotheses."
            ),
            "keywords": ["literature", "benchmark", "examples", "review", "latest", "papers", "future", "challenge", "open questions"],
        },
        {
            "id": "obj_experiments",
            "title": "Experiment design",
            "subtitle": "Turn the goal into hypotheses, interventions, controls, and decision gates.",
            "definition": (
                f"Design the next experiment plan for {topic}{host_suffix}. Focus on tractable hypotheses, pathway edits, "
                "construct choices, measurements, controls, and the criteria for deciding what to test next."
            ),
            "signals": ["experiments", "hypotheses", "controls", "assays", "constructs", "decision gates"],
            "facet_questions": [
                "Is the next priority pathway construction, screening, analytical validation, or design-of-experiments?",
                "Do you need a first-pass plan or a tightly scoped plan for the next lab cycle?",
                "Which readouts matter most right now: titer, yield, rate, toxicity, or pathway balance?",
            ],
            "exemplar_answer": (
                "Propose the highest-leverage hypotheses first, define the minimum experiment set, and make the success and stop criteria explicit."
            ),
            "keywords": ["experiment", "plan", "assay", "hypothesis", "screen", "construct", "test"],
        },
        {
            "id": "obj_data",
            "title": "Data analysis",
            "subtitle": "Interpret datasets, compare patterns, and define the next decision threshold.",
            "definition": (
                f"Analyze the available data for {topic}{host_suffix}. Focus on extracting patterns, comparing conditions, "
                "identifying statistically meaningful differences, and turning the results into the next project decision."
            ),
            "signals": ["datasets", "patterns", "statistics", "omics", "comparisons", "decision thresholds"],
            "facet_questions": [
                "What kind of data is being interpreted: screening data, fermentation runs, omics, analytical assays, or mixed evidence?",
                "Should the output emphasize statistical confidence, pattern discovery, or decision thresholds for the next experiment?",
                "Do you want a quick interpretation pass or a more structured analysis plan?",
            ],
            "exemplar_answer": (
                "Explain the strongest patterns in the data, separate signal from noise, and show how the analysis should change the next project action."
            ),
            "keywords": ["data analysis", "dataset", "statistics", "statistical", "regression", "correlation", "omics", "analyze data"],
        },
        {
            "id": "obj_strain",
            "title": "Strain and pathway strategy",
            "subtitle": "Decide which biological interventions matter most before broader optimization.",
            "definition": (
                f"Prioritize the biological levers for {topic}{host_suffix}. Focus on precursor supply, pathway bottlenecks, "
                "enzyme choice, cofactor balance, regulation, toxicity, and host engineering strategy."
            ),
            "signals": ["pathway", "enzymes", "precursors", "host engineering", "bottlenecks", "toxicity"],
            "facet_questions": [
                "Should the strategy focus on precursor flux, enzyme performance, host tolerance, or regulatory control first?",
                "Do you want a broad option map or a ranked shortlist of likely high-leverage interventions?",
                "Is the goal exploratory strain design or a near-term build plan?",
            ],
            "exemplar_answer": (
                "Rank the likely biological bottlenecks, explain why they matter, and show which intervention sequence is worth testing first."
            ),
            "keywords": ["pathway", "strain", "gene", "enzyme", "biosynthesis", "toxicity", "precursor"],
        },
        {
            "id": "obj_process",
            "title": "Process development",
            "subtitle": "Translate a viable biology concept into upstream or scale-up decisions.",
            "definition": (
                f"Frame the upstream process questions for {topic}{host_suffix}. Focus on culture strategy, media and feeds, "
                "process variables, DOE structure, scale-up readiness, and what operating ranges should be explored next."
            ),
            "signals": ["fermentation", "media", "feeds", "DOE", "scale-up", "process variables"],
            "facet_questions": [
                "Is the process question mainly about screening variables, improving performance, or preparing for scale-up?",
                "Do you want a minimal DOE or a broader process map?",
                "Which metrics should anchor the process decisions: titer, yield, robustness, or cost?",
            ],
            "exemplar_answer": (
                "Define the process variables that matter, propose a practical screening structure, and clarify what evidence is needed before scaling."
            ),
            "keywords": ["fermentation", "media", "bioreactor", "culture", "yield", "titer", "doe", "scale-up", "process"],
        },
        {
            "id": "obj_economics",
            "title": "Economics and sourcing",
            "subtitle": "Translate the technical path into cost drivers, feedstock choices, and program gates.",
            "definition": (
                f"Evaluate the economic and sourcing implications for {topic}{host_suffix}. Focus on feedstock or precursor costs, "
                "key cost drivers, scale assumptions, commercial gating questions, and where economics should change technical priorities."
            ),
            "signals": ["cost drivers", "feedstock", "sourcing", "commercial viability", "scale assumptions", "TEA"],
            "facet_questions": [
                "Is the main concern raw materials, process cost, downstream burden, or overall commercial viability?",
                "Do you want a rough gating view or a deeper techno-economic framing?",
                "Should the output emphasize cost-reduction opportunities or investment stop/go criteria?",
            ],
            "exemplar_answer": (
                "Identify the dominant economic assumptions, show which technical choices change them most, and define the next gating questions."
            ),
            "keywords": ["cost", "economics", "tea", "commercial", "margin", "raw material", "feedstock", "sourcing", "scale"],
        },
    ]

    scored = []
    for index, spec in enumerate(specs):
        score = 0
        for keyword in spec["keywords"]:
            if keyword in source_text:
                score += 2
        if spec["id"] == "obj_evidence":
            score += 1
        if "draft experiment plan" in source_text and spec["id"] == "obj_experiments":
            score += 4
        scored.append((score, index, spec))

    scored.sort(key=lambda item: (-item[0], item[1]))
    limit = max(2, min(request.k or 4, len(scored)))
    objectives = [
        Objective(
            id=spec["id"],
            title=spec["title"],
            subtitle=spec["subtitle"],
            definition=spec["definition"],
            signals=spec["signals"],
            facet_questions=spec["facet_questions"],
            exemplar_answer=spec["exemplar_answer"],
        )
        for _, _, spec in scored[:limit]
    ]

    global_questions = [
        "What concrete decision should this answer unlock next for the project team?",
        "How broad should the answer be: literature-first, experiment-ready, or decision-gating only?",
        "Which constraints matter most right now: time, budget, host choice, scale, or analytical certainty?",
    ]

    return ObjectivesResponse(objectives=objectives, global_questions=global_questions)


def _extract_selected_objective_title(reasoning_notes: Optional[str]) -> str:
    if not reasoning_notes:
        return ""
    match = re.search(r"(?im)^Selected objective cluster:\s*(.+)$", reasoning_notes)
    return match.group(1).strip() if match else ""


def _trim_work_template_lines(values: Optional[List[str]], limit: int = 6) -> List[str]:
    out: List[str] = []
    for value in values or []:
        text = str(value or "").strip()
        if not text:
            continue
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _work_template_has_content(work_template: Optional[ResearchWorkTemplate]) -> bool:
    if not work_template:
        return False
    return any(
        [
            work_template.initial_query.strip(),
            work_template.synthesis_memo.strip(),
            work_template.literature_findings,
            work_template.common_gaps,
            work_template.judgment_calls,
            work_template.validation_tracks,
            work_template.proposal_candidates,
        ]
    )


def _work_template_mode_text(work_template: Optional[ResearchWorkTemplate]) -> str:
    if not work_template:
        return ""
    parts: List[str] = []
    if work_template.initial_query.strip():
        parts.append(work_template.initial_query.strip())
    parts.extend(item.theme.strip() for item in work_template.common_gaps if item.theme.strip())
    parts.extend(item.target.strip() for item in work_template.validation_tracks if item.target.strip())
    parts.extend(item.title.strip() for item in work_template.proposal_candidates if item.title.strip())
    parts.extend(item.stance.strip() for item in work_template.judgment_calls if item.stance.strip())
    return " ".join(parts[:24])


def _work_template_to_prompt_text(work_template: Optional[ResearchWorkTemplate]) -> str:
    if not _work_template_has_content(work_template):
        return "none"

    sections: List[str] = []

    if work_template and work_template.initial_query.strip():
        sections.append(f"Initial query:\n{work_template.initial_query.strip()}")

    if work_template and work_template.literature_findings:
        entries: List[str] = []
        for index, finding in enumerate(work_template.literature_findings[:6], start=1):
            lines = [f"{index}. {finding.citation.strip() or f'Finding {index}'}"]
            labels = _trim_work_template_lines(finding.labels, limit=6)
            if labels:
                lines.append(f"   Labels: {', '.join(labels)}")
            knowns = _trim_work_template_lines(finding.knowns, limit=5)
            if knowns:
                lines.append("   Knowns:")
                lines.extend(f"   - {item}" for item in knowns)
            unknowns = _trim_work_template_lines(finding.unknowns, limit=5)
            if unknowns:
                lines.append("   Unknowns:")
                lines.extend(f"   - {item}" for item in unknowns)
            if finding.relevance.strip():
                lines.append(f"   Why it matters: {finding.relevance.strip()}")
            entries.append("\n".join(lines))
        sections.append("Literature findings:\n" + "\n".join(entries))

    if work_template and work_template.common_gaps:
        entries = []
        for index, gap in enumerate(work_template.common_gaps[:6], start=1):
            lines = [f"{index}. {gap.theme.strip() or f'Gap {index}'}"]
            signals = _trim_work_template_lines(gap.supporting_signals, limit=5)
            if signals:
                lines.append("   Signals:")
                lines.extend(f"   - {item}" for item in signals)
            if gap.next_question.strip():
                lines.append(f"   Next question: {gap.next_question.strip()}")
            if gap.priority_note.strip():
                lines.append(f"   Priority note: {gap.priority_note.strip()}")
            entries.append("\n".join(lines))
        sections.append("Recurring gaps and transfer questions:\n" + "\n".join(entries))

    if work_template and work_template.judgment_calls:
        entries = []
        for index, judgment in enumerate(work_template.judgment_calls[:6], start=1):
            lines = [f"{index}. {judgment.stance.strip() or f'Judgment {index}'}"]
            if judgment.rationale.strip():
                lines.append(f"   Rationale: {judgment.rationale.strip()}")
            if judgment.implication.strip():
                lines.append(f"   Implication: {judgment.implication.strip()}")
            entries.append("\n".join(lines))
        sections.append("User judgment and boundaries:\n" + "\n".join(entries))

    if work_template and work_template.validation_tracks:
        entries = []
        for index, track in enumerate(work_template.validation_tracks[:6], start=1):
            lines = [f"{index}. {track.target.strip() or f'Validation track {index}'}"]
            if track.method.strip():
                lines.append(f"   Method: {track.method.strip()}")
            questions = _trim_work_template_lines(track.questions, limit=5)
            if questions:
                lines.append("   Questions to resolve:")
                lines.extend(f"   - {item}" for item in questions)
            if track.success_signal.strip():
                lines.append(f"   Success signal: {track.success_signal.strip()}")
            entries.append("\n".join(lines))
        sections.append("Validation or tool-use agenda:\n" + "\n".join(entries))

    if work_template and work_template.proposal_candidates:
        entries = []
        for index, proposal in enumerate(work_template.proposal_candidates[:6], start=1):
            lines = [f"{index}. {proposal.title.strip() or f'Proposal {index}'}"]
            if proposal.why_now.strip():
                lines.append(f"   Why now: {proposal.why_now.strip()}")
            if proposal.experiment_outline.strip():
                lines.append(f"   Experiment outline: {proposal.experiment_outline.strip()}")
            readouts = _trim_work_template_lines(proposal.readouts, limit=5)
            if readouts:
                lines.append("   Readouts:")
                lines.extend(f"   - {item}" for item in readouts)
            entries.append("\n".join(lines))
        sections.append("Proposal seeds:\n" + "\n".join(entries))

    if work_template and work_template.synthesis_memo.strip():
        sections.append(f"Synthesis memo:\n{work_template.synthesis_memo.strip()}")

    return "\n\n".join(sections) if sections else "none"


def _work_template_counts(work_template: Optional[ResearchWorkTemplate]) -> Dict[str, int]:
    if not work_template:
        return {
            "literature_findings": 0,
            "common_gaps": 0,
            "judgment_calls": 0,
            "validation_tracks": 0,
            "proposal_candidates": 0,
        }
    return {
        "literature_findings": len(work_template.literature_findings),
        "common_gaps": len(work_template.common_gaps),
        "judgment_calls": len(work_template.judgment_calls),
        "validation_tracks": len(work_template.validation_tracks),
        "proposal_candidates": len(work_template.proposal_candidates),
    }


def _infer_project_plan_mode(project: dict, request: GenerateProjectPlanRequest) -> str:
    objective_title = _extract_selected_objective_title(request.reasoning_notes)
    source_text = " ".join(
        [
            str(objective_title or ""),
            str(request.focus_question or ""),
            str(request.reasoning_notes or ""),
            _work_template_mode_text(request.work_template),
            str(project.get("project_goal") or ""),
        ]
    ).lower()

    if any(term in source_text for term in ["evidence synthesis", "literature", "benchmark", "examples", "review", "papers", "open questions"]):
        return "evidence"
    if any(term in source_text for term in ["data analysis", "dataset", "statistics", "omics", "correlation", "regression"]):
        return "data"
    if any(term in source_text for term in ["experiment", "hypothesis", "assay", "construct", "screen"]):
        return "experiment"
    if any(term in source_text for term in ["process", "fermentation", "media", "scale-up", "doe", "bioreactor"]):
        return "process"
    if any(term in source_text for term in ["economics", "tea", "cost", "commercial", "margin", "viability"]):
        return "economics"
    if any(term in source_text for term in ["sourcing", "feedstock", "raw material", "substrate", "carbon source"]):
        return "sourcing"
    return "general"


def _fallback_project_plan(project: dict, persona: dict, request: GenerateProjectPlanRequest) -> AgenticPlan:
    end_product = str(project.get("end_product") or "the target product").strip()
    target_host = str(project.get("target_host") or "the selected host").strip()
    persona_name = str(persona.get("name") or "Project collaborator").strip()
    persona_json = persona.get("persona_json") or {}
    workflow_focus = [str(item).strip() for item in (persona_json.get("workflow_focus") or []) if str(item).strip()]
    goals = [str(item).strip() for item in (persona_json.get("goals") or []) if str(item).strip()]
    clarifying_answers = {k: v for k, v in (request.clarifying_answers or {}).items() if str(v or "").strip()}
    focus_question = (request.focus_question or project.get("project_goal") or "").strip() or f"Advance {end_product} development in {target_host}"
    work_template = request.work_template
    template_has_content = _work_template_has_content(work_template)
    finding_citations = [
        item.citation.strip() for item in (work_template.literature_findings if work_template else []) if item.citation.strip()
    ][:4]
    gap_themes = [item.theme.strip() for item in (work_template.common_gaps if work_template else []) if item.theme.strip()][:4]
    judgment_stances = [item.stance.strip() for item in (work_template.judgment_calls if work_template else []) if item.stance.strip()][:4]
    validation_targets = [item.target.strip() for item in (work_template.validation_tracks if work_template else []) if item.target.strip()][:4]
    proposal_titles = [item.title.strip() for item in (work_template.proposal_candidates if work_template else []) if item.title.strip()][:4]
    mode = _infer_project_plan_mode(project, request)
    objective_title = _extract_selected_objective_title(request.reasoning_notes) or {
        "evidence": "Evidence synthesis",
        "data": "Data analysis",
        "experiment": "Experiment design",
        "process": "Process development",
        "economics": "Economics and gating",
        "sourcing": "Feedstock and sourcing",
        "general": "Working draft",
    }[mode]

    step_templates: Dict[str, List[Dict[str, Any]]] = {
        "evidence": [
            {
                "title": "Frame the literature scope",
                "description": f"Define which literature, benchmark examples, and comparison axes matter most for {end_product} in {target_host}.",
                "why": "A narrow review frame prevents the draft from turning into a broad unfocused summary.",
                "outcome": "A clear evidence scope with inclusion criteria and benchmark dimensions.",
                "facts": [f"Anchor the review around {focus_question}.", "Separate host-specific evidence from broader microbial precedents."],
            },
            {
                "title": "Collect benchmark examples",
                "description": "Assemble the strongest reported strategies, representative examples, and the outcome metrics they improved.",
                "why": "Concrete benchmark examples are needed before judging which technical strategies are actually credible.",
                "outcome": "A shortlist of reference examples the team can compare side by side.",
                "facts": ["Capture strategy type, host context, and performance deltas.", "Prefer exemplars that reveal what changed and why."],
            },
            {
                "title": "Compare recurring strategy patterns",
                "description": "Group the examples by intervention pattern, bottleneck targeted, and quantitative effect size.",
                "why": "Pattern comparison turns isolated papers into reusable design knowledge.",
                "outcome": "A ranked view of which strategy families look most transferable.",
                "facts": ["Track precursor supply, pathway balancing, toxicity, and enzyme engineering themes.", "Highlight where gains were context-dependent."],
            },
            {
                "title": "Extract open questions and bottlenecks",
                "description": "Map the unresolved issues, recurring bottlenecks, and future improvement levers across the evidence set.",
                "why": "The open-question map defines where the next draft should become hypothesis-driven instead of purely descriptive.",
                "outcome": "A concise bottleneck and open-question register for the program.",
                "facts": ["Differentiate technical unknowns from data gaps.", "Note where evidence is contradictory or incomplete."],
            },
            {
                "title": "Translate evidence into next hypotheses",
                "description": "Convert the synthesized literature into the next decision options, hypotheses, or experiments the project team can edit.",
                "why": "The value of evidence synthesis is in turning reading into next project moves.",
                "outcome": "A directly editable set of next actions linked back to the strongest evidence patterns.",
                "facts": ["Tie each proposed next move to the most relevant benchmark pattern.", "Make the assumptions behind each hypothesis explicit."],
            },
        ],
        "data": [
            {
                "title": "Audit the available dataset",
                "description": "Define what data is available, what comparisons are valid, and which variables should anchor interpretation.",
                "why": "A clean dataset scope is needed before patterns can be trusted.",
                "outcome": "An agreed analysis frame with usable variables and comparison groups.",
                "facts": ["Separate primary measurements from contextual metadata.", "Identify missing data or confounders early."],
            },
            {
                "title": "Set analysis questions and thresholds",
                "description": "Turn the working question into explicit comparison tests, thresholds, or ranking rules.",
                "why": "Without explicit analysis questions, interpretation drifts into narrative overfitting.",
                "outcome": "A practical checklist for what the analysis must answer.",
                "facts": ["Define what counts as a meaningful change.", "Distinguish exploratory patterns from decision thresholds."],
            },
            {
                "title": "Compare patterns and outliers",
                "description": "Interpret the strongest trends, divergences, and outlier conditions in the dataset.",
                "why": "Pattern comparison is the core of turning raw data into project guidance.",
                "outcome": "A shortlist of the signals most likely to influence the next project decision.",
                "facts": ["Explain both favorable and unfavorable trends.", "Keep alternative explanations in play where evidence is weak."],
            },
            {
                "title": "Stress-test the interpretation",
                "description": "Check whether the observed patterns survive alternative explanations, noise, or missing-context concerns.",
                "why": "This prevents fragile interpretations from driving the next experiment or process move.",
                "outcome": "A more defensible analysis narrative with stated caveats.",
                "facts": ["Flag uncertainty explicitly.", "Separate robust conclusions from tentative ones."],
            },
            {
                "title": "Convert analysis into the next decision",
                "description": "Translate the analysis into the next recommended experiment, process choice, or data-collection need.",
                "why": "The output should change what the team does next, not just summarize what happened.",
                "outcome": "A decision-ready interpretation with clear next actions.",
                "facts": ["State what new data would most reduce uncertainty.", "Tie the recommendation to the strongest pattern."],
            },
        ],
        "experiment": [
            {
                "title": "Define the leading hypothesis",
                "description": f"Rewrite the working question as the most testable hypothesis for {end_product} in {target_host}.",
                "why": "A crisp hypothesis keeps the experiment plan specific and measurable.",
                "outcome": "A hypothesis statement with a clear success condition.",
                "facts": ["State the biological lever being tested.", "Clarify what outcome would support or reject it."],
            },
            {
                "title": "Choose the intervention set",
                "description": "Select the minimum constructs, strains, or process conditions needed to test the hypothesis well.",
                "why": "The first experiment set should maximize learning per build rather than cover every possibility.",
                "outcome": "A tightly scoped intervention list for the next cycle.",
                "facts": ["Prefer the highest-leverage variants first.", "Keep the scope compatible with the next iteration window."],
            },
            {
                "title": "Define readouts and controls",
                "description": "Specify the measurements, controls, and analytical checks that make the results interpretable.",
                "why": "Poor readout design creates ambiguous outcomes even when the intervention is sound.",
                "outcome": "A measurement and control plan that supports strong interpretation.",
                "facts": ["Include both performance and failure-mode readouts.", "Make control logic explicit."],
            },
            {
                "title": "Set decision gates",
                "description": "Define what outcomes count as progress, what counts as a stop signal, and what triggers the next iteration.",
                "why": "Decision gates prevent the draft from ending at execution without interpretation rules.",
                "outcome": "A go/no-go logic the team can edit before running the work.",
                "facts": ["Use thresholds the team can actually observe in the next cycle.", "Tie gates to the stated hypothesis."],
            },
            {
                "title": "Queue the follow-on experiments",
                "description": "List the next experimental branches depending on whether the initial hypothesis is supported or rejected.",
                "why": "A good experiment plan already anticipates the most likely next branch points.",
                "outcome": "A hypothesis queue that preserves learning momentum.",
                "facts": ["Map each branch to the most likely failure mode.", "Keep the second-round options editable, not fixed."],
            },
        ],
        "process": [
            {
                "title": "Define the process objective",
                "description": "Clarify which operating metric or transition question the process work should answer first.",
                "why": "Process development needs a single priority question before variables are expanded.",
                "outcome": "A process objective anchored to the most relevant metric.",
                "facts": ["Choose the metric that should drive the next decision.", "Separate screening goals from scale-up goals."],
            },
            {
                "title": "Map the controllable variables",
                "description": "List the process variables, media/feed levers, and operating ranges most likely to matter next.",
                "why": "A useful process draft narrows the variable set to the factors worth testing.",
                "outcome": "A ranked variable map for the next process pass.",
                "facts": ["Include both biological and operational levers.", "Note variables likely to interact."],
            },
            {
                "title": "Design a minimum DOE structure",
                "description": "Propose a practical screen or DOE that distinguishes the most important process effects.",
                "why": "The draft should support learning efficiently, not just expand the design space.",
                "outcome": "A minimal experimental matrix for process learning.",
                "facts": ["Keep run count realistic.", "Match the DOE scope to the maturity of the biology."],
            },
            {
                "title": "Define transition criteria",
                "description": "State what evidence is needed before moving to broader optimization or scale-up.",
                "why": "Transition criteria keep the program from scaling weak operating conditions prematurely.",
                "outcome": "A set of process readiness gates.",
                "facts": ["Tie readiness to stability and repeatability, not just peak performance.", "Make scale-up assumptions explicit."],
            },
            {
                "title": "Translate findings into the next process move",
                "description": "Recommend the next operating decision, follow-up study, or scale-up preparation task.",
                "why": "The process draft should tell the team what to do next after the first screen.",
                "outcome": "A process-forward recommendation linked to decision criteria.",
                "facts": ["State what additional evidence would change the recommendation.", "Connect the recommendation to the current process objective."],
            },
        ],
        "economics": [
            {
                "title": "Define the economic question",
                "description": "Clarify whether the immediate concern is cost drivers, program gating, or commercial feasibility.",
                "why": "Economic analysis should answer a specific program decision rather than remain abstract.",
                "outcome": "A bounded economic framing for the next draft.",
                "facts": ["Tie the analysis to a decision horizon.", "Separate strategic gating from detailed costing."],
            },
            {
                "title": "List first-order cost drivers",
                "description": "Identify the technical factors most likely to dominate cost or commercial viability.",
                "why": "First-order drivers determine which technical choices matter economically.",
                "outcome": "A shortlist of the assumptions that most influence viability.",
                "facts": ["Include upstream, downstream, and material drivers where relevant.", "Mark assumptions that are still weakly supported."],
            },
            {
                "title": "Stress-test the assumptions",
                "description": "Bound the critical assumptions and compare optimistic, base, and limiting scenarios.",
                "why": "Decision-useful economics depends on understanding sensitivity, not just a single estimate.",
                "outcome": "A simple scenario map for the current program stage.",
                "facts": ["Use assumption ranges that the current evidence can defend.", "Highlight which uncertainties are most decision-relevant."],
            },
            {
                "title": "Map technical-to-economic links",
                "description": "Show which technical improvements would most improve the economic picture or de-risk the program.",
                "why": "The team needs to know which scientific improvements actually matter financially.",
                "outcome": "A ranked translation between technical levers and economic effect.",
                "facts": ["Differentiate likely impact from speculative impact.", "Flag where sourcing or downstream burden changes the picture."],
            },
            {
                "title": "Recommend the next gating move",
                "description": "Define the next data, experiment, or analysis needed before advancing the economic case.",
                "why": "The output should help the team decide what evidence would most improve confidence.",
                "outcome": "A clear gating recommendation for the next program checkpoint.",
                "facts": ["State the minimum evidence needed to update the go/no-go view.", "Make commercial assumptions explicit."],
            },
        ],
        "sourcing": [
            {
                "title": "Define the sourcing requirement",
                "description": "Clarify which input, substrate, or precursor requirement matters most for the current question.",
                "why": "Feedstock strategy should start from a specific technical or cost concern.",
                "outcome": "A sourcing problem statement tied to the program need.",
                "facts": ["Differentiate must-have input properties from preferences.", "Link the sourcing frame to the product route."],
            },
            {
                "title": "Screen candidate input options",
                "description": "List the most credible raw material or substrate options and the criteria for comparing them.",
                "why": "A good sourcing draft compares options on both technical fit and supply realism.",
                "outcome": "A candidate shortlist with comparison criteria.",
                "facts": ["Track quality, price, availability, and process compatibility.", "Identify which assumptions need validation."],
            },
            {
                "title": "Map technical and economic tradeoffs",
                "description": "Compare how each input option changes biology, process complexity, and likely cost.",
                "why": "Sourcing choices matter only insofar as they change the rest of the workflow.",
                "outcome": "A tradeoff map connecting input choice to downstream consequences.",
                "facts": ["Show where a cheaper input may create process burden.", "Note where better inputs improve robustness."],
            },
            {
                "title": "Identify supply risks",
                "description": "Flag the practical sourcing, quality, or supply-chain risks that could block scale or reproducibility.",
                "why": "A sourcing recommendation is incomplete without a realistic risk view.",
                "outcome": "A short risk register for feedstock decisions.",
                "facts": ["Include quality variability and vendor risk where relevant.", "Distinguish manageable risk from blocking risk."],
            },
            {
                "title": "Recommend the next sourcing action",
                "description": "Define the next validation step, supplier screen, or feed experiment needed to move the program forward.",
                "why": "The goal is to convert sourcing analysis into a concrete next action.",
                "outcome": "An input strategy recommendation the team can test or validate next.",
                "facts": ["Prefer the next action that reduces the most important uncertainty.", "Tie the recommendation back to cost and technical fit."],
            },
        ],
        "general": [
            {
                "title": "Clarify the immediate decision",
                "description": "Restate the working question as the specific decision the team wants to unlock next.",
                "why": "A strong draft starts with the decision, not just the topic.",
                "outcome": "A project-framed decision statement for the next cycle.",
                "facts": ["Separate near-term next actions from longer-term ambitions.", "Keep the scope aligned to the current question."],
            },
            {
                "title": "Map knowns and unknowns",
                "description": "Identify what is already known, what assumptions are being made, and which unknowns are blocking progress.",
                "why": "This turns the draft into a decision aid rather than a generic plan.",
                "outcome": "A clear boundary between available evidence and unresolved gaps.",
                "facts": ["List assumptions explicitly.", "Call out what evidence would change the plan most."],
            },
            {
                "title": "Prioritize the workstreams",
                "description": "Rank the most important workstreams or questions that need attention first.",
                "why": "Prioritization is the core of a useful working draft.",
                "outcome": "A short ranked list of next workstreams.",
                "facts": ["Use leverage and urgency to rank them.", "Avoid expanding into unrelated workflow areas."],
            },
            {
                "title": "Define the evidence needed next",
                "description": "Specify what evidence, experiments, or analyses are needed to make the next decision confidently.",
                "why": "The team needs to know what to learn next, not just what to discuss.",
                "outcome": "A concise evidence plan for the next iteration.",
                "facts": ["Tie each evidence need to a specific decision.", "Prefer minimum useful evidence over exhaustive requests."],
            },
            {
                "title": "Commit to the next move",
                "description": "Turn the prioritized work into an immediate next action and a follow-on checkpoint.",
                "why": "The draft should end in action, not only synthesis.",
                "outcome": "A near-term move plus the next review point.",
                "facts": ["State what success looks like for the immediate next move.", "Keep the follow-on checkpoint editable."],
            },
        ],
    }

    selected_steps = step_templates.get(mode, step_templates["general"])
    steps: List[PlanStep] = []
    for index, item in enumerate(selected_steps, start=1):
        step_id = f"step_{index}"
        dependencies = [f"step_{index - 1}"] if index > 1 else []
        examples = []
        if workflow_focus:
            examples.append(f"Use {workflow_focus[min(index - 1, len(workflow_focus) - 1)]} as a concrete lens for this step.")
        if goals:
            examples.append(f"Keep the draft aligned to: {goals[min(index - 1, len(goals) - 1)]}")
        if finding_citations and index <= len(finding_citations):
            examples.append(f"Ground the step in the literature example '{finding_citations[index - 1]}'.")
        if gap_themes and index in {2, 4}:
            gap_index = min(index // 2 - 1, len(gap_themes) - 1)
            examples.append(f"Keep the recurring gap '{gap_themes[gap_index]}' visible in the reasoning.")
        if validation_targets and mode in {"evidence", "experiment", "data"} and index in {3, 4}:
            validation_index = min(index - 3, len(validation_targets) - 1)
            examples.append(f"Use the validation track on {validation_targets[validation_index]} as a concrete thread.")
        if proposal_titles and index == len(selected_steps):
            examples.append(f"Translate the work toward the proposal candidate '{proposal_titles[0]}'.")
        if judgment_stances and index == 1:
            examples.append(f"Honor the user judgment: {judgment_stances[0]}.")
        steps.append(
            PlanStep(
                id=step_id,
                title=item["title"],
                description=item["description"],
                why_this_step=item["why"],
                objective_link=f"Supports the active mode '{objective_title}' for the question: {focus_question}",
                persona_link=f"Uses {persona_name} as the collaborator lens, with emphasis on {workflow_focus[0] if workflow_focus else 'project decision support'}.",
                evidence_facts=item["facts"],
                examples=examples,
                dependencies=dependencies,
                expected_outcome=item["outcome"],
                confidence=max(0.45, 0.82 - (index - 1) * 0.06),
            )
        )

    assumptions = [
        f"Assumes the current focus remains: {focus_question}",
        f"Assumes {persona_name} is the right collaborator lens for the next iteration.",
    ]
    if not clarifying_answers:
        assumptions.append("Assumes no additional clarifying constraints beyond the current project brief and saved reasoning.")
    if request.notes:
        assumptions.append("Assumes the supplied program context is the most relevant non-query constraint for this pass.")
    if template_has_content:
        assumptions.append("Assumes the structured research template reflects the latest literature synthesis, judgment calls, and proposal direction.")

    success_criteria = [
        "The next project decision is explicit and editable.",
        "Each step is traceable to the current question and collaborator lens.",
        "Risks, assumptions, and evidence needs are visible before the next iteration.",
    ]
    if template_has_content:
        success_criteria.append("The draft preserves the known vs unknown split, validation agenda, and proposal seeds captured in the work template.")
    if mode == "evidence":
        success_criteria.append("The synthesis ends in concrete next hypotheses or decisions, not only a literature recap.")
    elif mode == "experiment":
        success_criteria.append("The draft includes measurable readouts, controls, and decision gates.")

    risks = [
        {
            "risk": "The fallback draft may be more generic than a model-grounded answer.",
            "mitigation": "Keep the structure editable and use the saved reasoning panel to tailor the next iteration.",
        },
        {
            "risk": "Key constraints may still be missing from the current query and clarifying answers.",
            "mitigation": "Add missing constraints in the collaborator prompts or reasoning notes before regenerating.",
        },
    ]
    if judgment_stances:
        risks.append(
            {
                "risk": "A strong user preference or exclusion may narrow the plan faster than the current evidence supports.",
                "mitigation": "Call out which parts of the draft are preference-driven versus evidence-driven and validate the highest-impact exclusions explicitly.",
            }
        )
    if mode == "evidence":
        risks.append(
            {
                "risk": "Benchmark examples may overrepresent better-studied systems rather than the exact project context.",
                "mitigation": "Separate host-specific examples from broader analogs when editing the draft.",
            }
        )

    return AgenticPlan(
        plan_title=f"{objective_title} draft for {end_product} in {target_host}",
        strategy_summary=(
            f"A fallback working draft built for '{focus_question}', using {persona_name} as the collaborator lens "
            f"and organizing the next steps around {objective_title.lower()}."
            + (
                f" It incorporates {len(finding_citations)} literature findings, {len(gap_themes)} recurring gaps, "
                f"{len(validation_targets)} validation tracks, and {len(proposal_titles)} proposal seeds from the structured work template."
                if template_has_content
                else ""
            )
        ),
        success_criteria=success_criteria,
        assumptions=assumptions,
        risks=risks,
        steps=steps,
    )


def _events_for_persona(persona_id: int, after_event_id: int = 0, limit: int = 500) -> List[Dict[str, Any]]:
    rows = db.list_events(min_id=after_event_id, limit=limit)
    out: List[Dict[str, Any]] = []
    for row in rows:
        payload = row.get("payload") or {}
        if isinstance(payload, dict) and payload.get("persona_id") == persona_id:
            out.append(row)
    return out


def _flatten_json(value: Any, prefix: str = "") -> Dict[str, Any]:
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            out.update(_flatten_json(child, child_prefix))
        return out
    if isinstance(value, list):
        return {prefix: value}
    return {prefix: value}


def _persona_change_summary(before: Dict[str, Any], after: Dict[str, Any], max_items: int = 12) -> List[str]:
    before_flat = _flatten_json(before)
    after_flat = _flatten_json(after)
    changes: List[str] = []
    all_keys = sorted(set(before_flat.keys()) | set(after_flat.keys()))
    for key in all_keys:
        before_val = before_flat.get(key, None)
        after_val = after_flat.get(key, None)
        if before_val == after_val:
            continue
        if key not in before_flat:
            changes.append(f"Added {key}")
        elif key not in after_flat:
            changes.append(f"Removed {key}")
        else:
            changes.append(f"Updated {key}: {json.dumps(before_val)} -> {json.dumps(after_val)}")
        if len(changes) >= max_items:
            break
    if not changes and before != after:
        changes.append("Updated persona JSON")
    return changes


def _event_type_counts(events: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for event in events:
        event_type = str(event.get("event_type") or "unknown")
        counts[event_type] = counts.get(event_type, 0) + 1
    return counts


def _persona_refactor_reasons(events: List[Dict[str, Any]]) -> List[str]:
    reasons: List[str] = []
    feedback_comments: List[str] = []
    for event in events:
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        if event.get("event_type") == "explicit_feedback":
            rating = payload.get("rating")
            comment = str(payload.get("feedback_text") or "").strip()
            if rating is not None:
                reasons.append(f"Captured explicit feedback rating: {rating}/5")
            if comment:
                feedback_comments.append(comment)
    for comment in feedback_comments[:2]:
        reasons.append(f"Feedback note: {comment}")
    if not reasons:
        counts = _event_type_counts(events)
        reasons.append(f"Behavioral telemetry observed: {json.dumps(counts)}")
    return reasons[:6]

async def _refactor_persona_from_events(persona_id: int) -> Optional[PersonaRefactorItem]:
    persona = db.get_persona(persona_id)
    if not persona:
        return None

    checkpoint = db.get_persona_refactor_checkpoint(persona_id)
    events = _events_for_persona(persona_id, after_event_id=checkpoint, limit=1000)
    if len(events) < 3:
        return None

    planner_model = os.getenv("OLLAMA_PLANNER_MODEL") or os.getenv("OLLAMA_SOTA_MODEL") or ollama.model
    prompt = ollama.get_persona_refactor_prompt(
        current_persona_json=persona.get("persona_json") or {},
        current_summary=persona.get("last_summary") or "",
        interaction_events=events,
    )
    response = await ollama.generate_json(
        prompt,
        max_retries=2,
        temperature=0.1,
        top_p=0.9,
        model=planner_model,
    )
    incoming_payload = response.get("persona") if isinstance(response, dict) else None
    if incoming_payload is None:
        incoming_payload = response

    previous_payload = persona.get("persona_json") or {}
    merged_payload = merge_persona_payloads(previous_payload, incoming_payload)
    if merged_payload == previous_payload:
        max_event_id = max(int(e.get("id", 0)) for e in events)
        db.set_persona_refactor_checkpoint(persona_id, max_event_id)
        return None

    merged_summary = build_persona_summary(PersonaPayload.model_validate(merged_payload))
    identity_key = persona.get("identity_key")
    scope = persona.get("scope") or "default"
    name = persona.get("name") or "persona"

    if identity_key:
        versions = db.list_personas_by_scope_identity(scope, identity_key)
    else:
        versions = db.list_personas_by_scope_name_normalized(scope, name)
    max_version = max((v.get("version", 1) for v in versions), default=0)
    new_version = max_version + 1

    new_persona_id = db.create_persona(
        name=name,
        scope=scope,
        persona_json=merged_payload,
        last_summary=merged_summary,
        identity_key=identity_key,
        version=new_version,
    )
    _write_persona_context(scope, name, merged_payload, merged_summary, identity_key)
    save_persona_snapshot(new_persona_id, merged_payload, [])

    max_event_id = max(int(e.get("id", 0)) for e in events)
    db.set_persona_refactor_checkpoint(persona_id, max_event_id)

    db.log_event(
        LogEventRequest(
            event_type="persona_refactored",
            payload={
                "persona_id": persona_id,
                "source_persona_id": persona_id,
                "new_persona_id": new_persona_id,
                "version": new_version,
                "changes": _persona_change_summary(previous_payload, merged_payload),
                "reasons": _persona_refactor_reasons(events),
                "supporting_events": _event_type_counts(events),
            },
        )
    )

    return PersonaRefactorItem(
        source_persona_id=persona_id,
        new_persona_id=new_persona_id,
        events_used=len(events),
        version=new_version,
    )

async def _run_persona_refactor_pass() -> PersonaRefactorResponse:
    updated: List[PersonaRefactorItem] = []
    skipped: List[Dict[str, Any]] = []
    async with _persona_refactor_lock:
        personas = db.list_personas()
        for persona in personas:
            pid = int(persona["id"])
            try:
                result = await _refactor_persona_from_events(pid)
                if result:
                    updated.append(result)
                else:
                    skipped.append({"persona_id": pid, "reason": "insufficient_new_events"})
            except Exception as ex:
                skipped.append({"persona_id": pid, "reason": f"failed: {ex}"})
    return PersonaRefactorResponse(updated=updated, skipped=skipped)


async def _persona_refactor_loop(interval_sec: int):
    while True:
        try:
            result = await _run_persona_refactor_pass()
            if result.updated:
                await log_event_safe(
                    "persona_refactor_pass",
                    {"updated": len(result.updated), "skipped": len(result.skipped)},
                )
        except Exception as ex:
            print(f"persona_refactor_loop_error: {ex}")
        await asyncio.sleep(interval_sec)


def _report_metadata_response(row: dict) -> ReportMetadataResponse:
    return ReportMetadataResponse(
        id=row["id"],
        title=row["title"],
        objective_id=row.get("objective_id"),
        persona_id=row.get("persona_id"),
        status=row["status"],
        qmd_path=row["qmd_path"],
        last_output_html_path=row.get("last_output_html_path"),
        last_output_pdf_path=row.get("last_output_pdf_path"),
        last_render_at=row.get("last_render_at"),
        last_manifest_path=row.get("last_manifest_path"),
        last_log_path=row.get("last_log_path"),
        error_message=row.get("error_message"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _ensure_under_artifact_root(candidate: str):
    artifact_root = Path(os.getenv("ARTIFACT_ROOT", "data/artifacts")).resolve()
    path = Path(candidate).resolve()
    if artifact_root not in path.parents and path != artifact_root:
        raise HTTPException(status_code=400, detail="Invalid artifact path")


def _persona_row_to_response(row: dict) -> PersonaResponse:
    return PersonaResponse(
        id=row["id"],
        name=row["name"],
        scope=row["scope"],
        project_id=row.get("project_id"),
        identity_key=row.get("identity_key"),
        source=row["source"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        version=row["version"],
        last_summary=row["last_summary"],
        persona_json=row["persona_json"],
    )


def _project_scope_id(project_id: int) -> str:
    return f"project:{project_id}"


def _project_persona_row_to_response(row: dict) -> ProjectWorkflowPersona:
    persona_json = row.get("persona_json") or {}
    project_context = persona_json.get("project_context") or {}
    workflow_focus = [str(x) for x in (persona_json.get("workflow_focus") or []) if str(x).strip()]
    starter_questions = [str(x) for x in (project_context.get("starter_questions") or []) if str(x).strip()]
    focus_area = str(project_context.get("focus_area") or (workflow_focus[0] if workflow_focus else "Workflow support")).strip()
    return ProjectWorkflowPersona(
        persona_id=int(row["id"]),
        name=str(row.get("name") or "Workflow Persona"),
        role=str(persona_json.get("role") or "workflow_partner"),
        workflow_stage=str(persona_json.get("workflow_stage") or "general"),
        focus_area=focus_area or "Workflow support",
        summary=str(row.get("last_summary") or ""),
        goals=[str(x) for x in (persona_json.get("goals") or []) if str(x).strip()][:4],
        workflow_focus=workflow_focus[:4],
        starter_questions=starter_questions[:3],
        version=int(row.get("version") or 1),
    )


def _workspace_state_to_response(state: Optional[dict]) -> ProjectWorkspaceResponse:
    if not state:
        return ProjectWorkspaceResponse(state=None)
    plan_payload = state.get("plan")
    work_template_payload = state.get("work_template")
    return ProjectWorkspaceResponse(
        state=ProjectWorkspaceState(
            project_id=int(state["project_id"]),
            persona_id=int(state["persona_id"]),
            focus_question=state.get("focus_question"),
            clarifying_answers=state.get("clarifying_answers") or {},
            reasoning_notes=state.get("reasoning_notes"),
            work_template=ResearchWorkTemplate.model_validate(work_template_payload) if work_template_payload else None,
            plan=AgenticPlan.model_validate(plan_payload) if plan_payload else None,
            selected_step_id=state.get("selected_step_id"),
            updated_at=state.get("updated_at"),
        )
    )


def _execution_event_to_response(row: dict) -> ProjectExecutionEvent:
    return ProjectExecutionEvent(
        id=int(row["id"]),
        run_id=int(row["run_id"]),
        event_type=str(row.get("event_type") or ""),
        stage_key=row.get("stage_key"),
        title=str(row.get("title") or ""),
        detail=str(row.get("detail") or ""),
        payload=row.get("payload") or {},
        created_at=row["created_at"],
    )


def _execution_run_to_response(run: Optional[dict], events: Optional[List[dict]] = None) -> ProjectExecutionRunResponse:
    return ProjectExecutionRunResponse(
        run=to_execution_response(run),
        events=[_execution_event_to_response(row) for row in (events or [])],
    )


def _pubmed_record_to_research_finding(record: dict, index: int) -> ResearchFinding:
    title = str(record.get("title") or "").strip()
    abstract = str(record.get("abstract") or "").strip()
    year = str(record.get("year") or "").strip()
    labels = ["pubmed", "literature fetch"]
    if year:
        labels.append(year)
    return ResearchFinding(
        id=f"lit_fetch_{index}",
        citation=str(record.get("citation") or title or f"PubMed result {index}").strip(),
        labels=labels,
        knowns=[title] if title else [],
        unknowns=[],
        relevance=abstract[:900],
    )


def _literature_objective_lens(request: FetchProjectLiteratureRequest) -> str:
    parts = [
        (request.objective_title or "").strip(),
        (request.objective_definition or "").strip(),
        *[str(signal or "").strip() for signal in (request.objective_signals or [])],
    ]
    lens = " ".join(part for part in parts if part)
    return lens or "General evidence review for the current project objective."


def _fallback_literature_processing(
    request: FetchProjectLiteratureRequest,
    findings: List[ResearchFinding],
) -> Dict[str, Any]:
    objective_lens = _literature_objective_lens(request)
    count = len(findings)
    query = " ".join((request.query or "").split()).strip()
    return {
        "objective_lens": objective_lens,
        "processing_summary": (
            f"Fetched {count} new literature item{'s' if count != 1 else ''} for '{query}' and placed them into the evidence library. "
            "The first-pass extraction is conservative: titles and abstracts are captured as known evidence, while transferability, "
            "feasibility, and priority still need the user's domain judgment."
        ),
        "elicitation_questions": [
            "Which fetched papers look most transferable to your target flavonoid and yeast strain, and why?",
            "Which reported methods are infeasible, too expensive, or outside the lab's current capability?",
            "Which results should be treated as strong evidence versus only a loose analogy for this objective?",
            "What boundary conditions matter most before these findings become experiment-plan inputs?",
        ],
    }


async def _synthesize_literature_processing(
    project: dict,
    persona: dict,
    request: FetchProjectLiteratureRequest,
    records: List[dict],
    fallback_findings: List[ResearchFinding],
) -> Dict[str, Any]:
    if not records:
        return _fallback_literature_processing(request, fallback_findings)

    objective_lens = _literature_objective_lens(request)
    compact_records = []
    for index, record in enumerate(records, start=1):
        compact_records.append(
            {
                "index": index,
                "title": str(record.get("title") or "")[:500],
                "citation": str(record.get("citation") or "")[:500],
                "year": str(record.get("year") or ""),
                "abstract_excerpt": str(record.get("abstract") or "")[:1200],
            }
        )

    prompt = f"""
You are helping a scientist review fetched literature before drafting an experiment plan.
Use only the PubMed records below. Do not invent paper details that are not in titles, citations, or abstract excerpts.

Project goal: {project.get("project_goal") or project.get("name") or ""}
Target host: {project.get("target_host") or ""}
Persona / collaborator: {persona.get("name") or ""}
Selected objective lens: {objective_lens}
Initial literature query: {request.query}

Fetched records:
{json.dumps(compact_records, ensure_ascii=False, indent=2)}

Return JSON with this exact shape:
{{
  "objective_lens": "one sentence explaining how the selected objective conditions this literature read",
  "processing_summary": "2-4 sentences describing what was fetched, how it was interpreted, and what remains user-judgment-dependent",
  "elicitation_questions": [
    "question that asks the user for tacit transferability or feasibility information",
    "question that asks the user to mark a boundary condition, constraint, or non-goal",
    "question that asks which evidence should be prioritized or discounted"
  ],
  "findings": [
    {{
      "citation": "citation from the fetched record",
      "labels": ["short label", "objective-conditioned"],
      "knowns": ["what the fetched title/abstract directly supports"],
      "unknowns": ["what remains unresolved for this project/objective"],
      "relevance": "why this item may matter for the selected objective"
    }}
  ]
}}
""".strip()
    try:
        payload = await ollama.generate_json(prompt)
        raw_findings = payload.get("findings") if isinstance(payload, dict) else None
        findings: List[ResearchFinding] = []
        if isinstance(raw_findings, list):
            for index, item in enumerate(raw_findings, start=1):
                if not isinstance(item, dict):
                    continue
                source_finding = fallback_findings[index - 1] if index - 1 < len(fallback_findings) else None
                citation = str(
                    item.get("citation")
                    or (source_finding.citation if source_finding else "")
                    or f"PubMed result {index}"
                ).strip()
                findings.append(
                    ResearchFinding(
                        id=f"lit_fetch_{index}",
                        citation=citation,
                        labels=[str(label).strip() for label in (item.get("labels") or []) if str(label).strip()][:6]
                        or (source_finding.labels if source_finding else ["pubmed", "literature fetch"]),
                        knowns=[str(value).strip() for value in (item.get("knowns") or []) if str(value).strip()][:5]
                        or (source_finding.knowns if source_finding else []),
                        unknowns=[str(value).strip() for value in (item.get("unknowns") or []) if str(value).strip()][:5],
                        relevance=str(item.get("relevance") or (source_finding.relevance if source_finding else "")).strip()[:1200],
                    )
                )

        fallback = _fallback_literature_processing(request, fallback_findings)
        questions = payload.get("elicitation_questions") if isinstance(payload, dict) else []
        return {
            "objective_lens": str(payload.get("objective_lens") or fallback["objective_lens"]).strip(),
            "processing_summary": str(payload.get("processing_summary") or fallback["processing_summary"]).strip(),
            "elicitation_questions": [str(question).strip() for question in questions if str(question).strip()][:5]
            or fallback["elicitation_questions"],
            "findings": findings or fallback_findings,
        }
    except Exception:
        return _fallback_literature_processing(request, fallback_findings) | {"findings": fallback_findings}


async def _run_project_execution_task(run_id: int, project: dict, persona: dict, request: StartProjectExecutionRequest):
    try:
        await run_agentic_execution(run_id=run_id, project=project, persona=persona, request=request)
    finally:
        _project_execution_tasks.pop(run_id, None)


def _load_project_personas(project_id: int, scope_id: str) -> List[ProjectWorkflowPersona]:
    if not scope_id and not project_id:
        return []
    rows = db.list_personas(project_id=project_id) if project_id else db.list_personas(scope=scope_id)
    rows.sort(
        key=lambda row: (
            _PROJECT_STAGE_ORDER.get(str((row.get("persona_json") or {}).get("workflow_stage") or "general"), 99),
            str(row.get("name") or "").lower(),
        )
    )
    return [_project_persona_row_to_response(row) for row in rows]


def _project_row_to_response(row: dict) -> ProjectResponse:
    scope_id = str(row.get("scope_id") or "")
    return ProjectResponse(
        id=int(row["id"]),
        name=str(row.get("name") or "Untitled Project"),
        scope_id=scope_id,
        end_product=str(row.get("end_product") or ""),
        target_host=str(row.get("target_host") or "Saccharomyces cerevisiae"),
        project_goal=str(row.get("project_goal") or ""),
        raw_material_focus=row.get("raw_material_focus"),
        notes=row.get("notes"),
        status=str(row.get("status") or "active"),
        created_at=str(row.get("created_at") or ""),
        updated_at=str(row.get("updated_at") or ""),
        personas=_load_project_personas(int(row["id"]), scope_id),
    )


def _persona_belongs_to_project(persona: dict, project: dict) -> bool:
    persona_project_id = persona.get("project_id")
    if persona_project_id is not None:
        return int(persona_project_id) == int(project["id"])
    return str(persona.get("scope") or "") == str(project.get("scope_id") or "")


async def _seed_project_workflow_personas(project: dict) -> List[int]:
    project_id = int(project["id"])
    scope_id = str(project.get("scope_id") or _project_scope_id(project_id))
    existing = db.list_personas(scope=scope_id)
    if any(str(row.get("identity_key") or "").startswith("project-workflow:") for row in existing):
        return [int(row["id"]) for row in existing]

    project_goal = str(project.get("project_goal") or "").strip()
    if not project_goal:
        project_goal = (
            f"Build a decision-ready biotech workflow to produce {project.get('end_product')} "
            f"in {project.get('target_host') or 'the selected host'}."
        )

    built = await build_project_personas(
        project_name=str(project.get("name") or f"Project {project_id}"),
        scope_id=scope_id,
        end_product=str(project.get("end_product") or ""),
        target_host=str(project.get("target_host") or "Saccharomyces cerevisiae"),
        project_goal=project_goal,
        raw_material_focus=str(project.get("raw_material_focus") or ""),
        notes=str(project.get("notes") or ""),
    )

    created_ids: List[int] = []
    for item in built:
        payload = item["payload"]
        summary = item["summary"]
        identity_key = item["identity_key"]
        name = item["name"]
        persona_id = db.create_persona(
            name=name,
            scope=scope_id,
            persona_json=payload,
            last_summary=summary,
            identity_key=identity_key,
            version=1,
            source="project_workflow",
            project_id=project_id,
        )
        _write_persona_context(scope_id, name, payload, summary, identity_key)
        save_persona_snapshot(persona_id, payload, [])
        created_ids.append(persona_id)
    return created_ids


def _interview_root() -> Path:
    return Path(os.getenv("INTERVIEW_TEXT_ROOT", "data/interviews")).resolve()


def _resolve_interview_folder(folder: Optional[str]) -> Path:
    root = _interview_root()
    root.mkdir(parents=True, exist_ok=True)
    if not folder:
        return root
    cleaned = folder.replace("\\", "/").strip().lstrip("/")
    candidate = (root / cleaned).resolve()
    if root not in candidate.parents and candidate != root:
        raise HTTPException(status_code=400, detail="Invalid folder path")
    return candidate


def _interview_row_to_response(row: dict) -> InterviewResponse:
    return InterviewResponse(
        id=row["id"],
        scope=row["scope"],
        transcript_path=row.get("transcript_path"),
        transcript_text=row.get("transcript_text"),
        created_at=row["created_at"],
        metadata_json=row.get("metadata_json") or {},
    )


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned or "item"


def _canonical_identity(value: str) -> str:
    lowered = (value or "").strip().lower()
    return re.sub(r"[^a-z0-9]+", "", lowered)


def _extract_participant_id(text: str) -> Optional[str]:
    if not text:
        return None
    match = re.search(r"^\s*Participant\s*ID\s*:\s*(.+?)\s*$", text, flags=re.IGNORECASE | re.MULTILINE)
    if not match:
        return None
    participant_id = match.group(1).strip()
    return participant_id or None


def _extract_participant_id_from_interviews(interviews: list[dict]) -> Optional[str]:
    for interview in interviews:
        meta = interview.get("metadata_json") or {}
        pid = meta.get("participant_id")
        if isinstance(pid, str) and pid.strip():
            return pid.strip()
        if interview.get("transcript_path"):
            path = Path(interview["transcript_path"])
            if path.exists() and path.is_file():
                text = path.read_text(encoding="utf-8", errors="replace")
                pid = _extract_participant_id(text)
                if pid:
                    return pid
        if interview.get("transcript_text"):
            pid = _extract_participant_id(interview["transcript_text"])
            if pid:
                return pid
    return None


def _persona_identity_key(scope: str, persona_name: str, interviews: list[dict]) -> str:
    participant_ids = set()
    for interview in interviews:
        meta = interview.get("metadata_json") or {}
        pid = meta.get("participant_id")
        if isinstance(pid, str) and pid.strip():
            participant_ids.add(_canonical_identity(pid))
            continue
        if interview.get("transcript_path"):
            path = Path(interview["transcript_path"])
            if path.exists() and path.is_file():
                text = path.read_text(encoding="utf-8", errors="replace")
                pid = _extract_participant_id(text)
                if pid:
                    participant_ids.add(_canonical_identity(pid))
        if interview.get("transcript_text"):
            pid = _extract_participant_id(interview["transcript_text"])
            if pid:
                participant_ids.add(_canonical_identity(pid))

    if len(participant_ids) == 1:
        return f"participant:{next(iter(participant_ids))}"

    return f"name:{_canonical_identity(scope)}:{_canonical_identity(persona_name)}"


def _find_persona_by_identity(scope: str, name: str, identity_key: Optional[str] = None) -> Optional[dict]:
    if identity_key:
        row = db.get_persona_by_scope_identity(scope, identity_key)
        if row:
            return row

    target_scope = _canonical_identity(scope)
    target_name = _canonical_identity(name)
    candidates = db.list_personas(scope=scope)
    for row in candidates:
        if _canonical_identity(row.get("scope", "")) == target_scope and _canonical_identity(row.get("name", "")) == target_name:
            return row
    if scope.strip() != scope:
        # defensive retry using trimmed scope in case caller provided padded scope
        candidates = db.list_personas(scope=scope.strip())
        for row in candidates:
            if _canonical_identity(row.get("scope", "")) == target_scope and _canonical_identity(row.get("name", "")) == target_name:
                return row
    return None


def _write_persona_context(
    scope: str,
    name: str,
    persona_payload: dict,
    summary: str,
    identity_key: Optional[str] = None,
):
    scope_slug = _slugify(scope)
    name_slug = _slugify(name)
    key_slug = _slugify(identity_key or "")
    suffix = f"__{key_slug}" if key_slug else ""
    base = f"persona/capabilities/{scope_slug}__{name_slug}{suffix}"
    write_context_file(f"{base}.json", json.dumps(persona_payload, indent=2), overwrite=True)
    write_context_file(
        f"persona/interaction_style/{scope_slug}__{name_slug}{suffix}.md",
        f"# Persona Summary\n\nScope: {scope}\nName: {name}\n\n{summary}\n",
        overwrite=True,
    )



def _extract_markdown_title(markdown: str) -> Optional[str]:
    for line in (markdown or '').splitlines():
        cleaned = line.strip()
        if cleaned.startswith('#'):
            title = cleaned.lstrip('#').strip()
            if title:
                return title
    return None


def _seed_starter_personas(scope_id: str = "default", reset: bool = False) -> Dict[str, Any]:
    removed_count = 0
    if reset:
        removed_count = db.clear_personas(scope=scope_id)

    existing = db.list_personas(scope=scope_id)
    if existing and not reset:
        return {"removed_count": 0, "created_ids": []}

    created_ids: List[int] = []
    for item in list_persona_templates():
        template_id = str(item.get("template_id") or "starter")
        detail = get_persona_template(template_id)
        if not detail:
            continue

        name = str(detail.get("name") or "Starter Persona")
        identity_key = f"starter:{template_id}:{_canonical_identity(scope_id)}"
        payload = dict(detail.get("payload") or {})
        payload["persona_id"] = _slugify(name)
        payload["scope_id"] = scope_id

        validated = PersonaPayload.model_validate(payload)
        payload = validated.model_dump()
        summary = build_persona_summary(validated)

        persona_id = db.create_persona(
            name=name,
            scope=scope_id,
            persona_json=payload,
            last_summary=summary,
            identity_key=identity_key,
            version=1,
        )
        _write_persona_context(scope_id, name, payload, summary, identity_key)
        save_persona_snapshot(persona_id, payload, [])
        created_ids.append(persona_id)

    return {"removed_count": removed_count, "created_ids": created_ids}

def _write_interview_context(scope: str, transcript_path: str, transcript_text: Optional[str] = None):
    scope_slug = _slugify(scope)
    file_name = Path(transcript_path).name if transcript_path else "interview.txt"
    dest = f"seci/S_socialization/shadowing_transcripts/{scope_slug}/{file_name}"
    text = transcript_text
    if text is None and transcript_path:
        path = Path(transcript_path)
        if path.exists() and path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
    write_context_file(dest, text or "", overwrite=True)


def _consolidate_persona_duplicates(scope: str, name: str, identity_key: str, canonical_id: int) -> Optional[dict]:
    matches = db.list_personas_by_scope_identity(scope, identity_key)
    if len(matches) <= 1:
        matches = db.list_personas_by_scope_name_normalized(scope, name)
    if len(matches) <= 1:
        return db.get_persona(canonical_id)

    canonical = db.get_persona(canonical_id)
    if not canonical:
        return None

    merged_payload = canonical.get("persona_json") or {}
    for row in matches:
        row_id = int(row["id"])
        if row_id == canonical_id:
            continue
        merged_payload = merge_persona_payloads(merged_payload, row.get("persona_json") or {})
        db.delete_persona(row_id)

    merged_summary = build_persona_summary(PersonaPayload.model_validate(merged_payload))
    db.update_persona(
        canonical_id,
        persona_json=merged_payload,
        last_summary=merged_summary,
        name=name,
        identity_key=identity_key,
    )
    _write_persona_context(scope, name, merged_payload, merged_summary, identity_key)
    save_persona_snapshot(canonical_id, merged_payload, [])
    return db.get_persona(canonical_id)


@app.post("/api/projects", response_model=CreateProjectResponse)
async def create_project(request: CreateProjectRequest):
    name = (request.name or "").strip()
    end_product = (request.end_product or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Project name is required")
    if not end_product:
        raise HTTPException(status_code=400, detail="End product is required")

    target_host = (request.target_host or "Saccharomyces cerevisiae").strip() or "Saccharomyces cerevisiae"
    project_goal = (request.project_goal or "").strip() or (
        f"Engineer a commercially relevant process for {end_product} production in {target_host}."
    )
    raw_material_focus = (request.raw_material_focus or "").strip() or None
    notes = (request.notes or "").strip() or None

    project_id = db.create_project(
        name=name,
        end_product=end_product,
        target_host=target_host,
        project_goal=project_goal,
        raw_material_focus=raw_material_focus,
        notes=notes,
        scope_id="",
    )
    scope_id = _project_scope_id(project_id)
    db.update_project_scope(project_id, scope_id)

    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=500, detail="Project creation failed")

    created_persona_ids = await _seed_project_workflow_personas(project)
    await log_event_safe(
        "project_created",
        {
            "project_id": project_id,
            "name": name,
            "end_product": end_product,
            "target_host": target_host,
            "persona_count": len(created_persona_ids),
        },
    )

    refreshed = db.get_project(project_id)
    if not refreshed:
        raise HTTPException(status_code=500, detail="Project creation failed")
    return CreateProjectResponse(
        project=_project_row_to_response(refreshed),
        created_persona_ids=created_persona_ids,
    )


@app.get("/api/projects", response_model=ProjectListResponse)
async def list_projects(status: Optional[str] = Query(default=None)):
    rows = db.list_projects(status=status)
    return ProjectListResponse(projects=[_project_row_to_response(row) for row in rows])


@app.get("/api/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: int):
    row = db.get_project(project_id)
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_row_to_response(row)


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: int):
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    deleted = db.delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete project")
    await log_event_safe(
        "project_deleted",
        {
            "project_id": project_id,
            "scope_id": project.get("scope_id"),
            "name": project.get("name"),
        },
    )
    return {"deleted": True, "project_id": project_id}


@app.get("/api/projects/{project_id}/workspace/{persona_id}", response_model=ProjectWorkspaceResponse)
async def get_project_workspace_state(project_id: int, persona_id: int):
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    persona = db.get_persona(persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    if not _persona_belongs_to_project(persona, project):
        raise HTTPException(status_code=400, detail="Selected persona does not belong to this project")
    return _workspace_state_to_response(db.get_project_workspace_state(project_id, persona_id))


@app.put("/api/projects/{project_id}/workspace/{persona_id}", response_model=ProjectWorkspaceResponse)
async def save_project_workspace_state(project_id: int, persona_id: int, request: ProjectWorkspaceRequest):
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    persona = db.get_persona(persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    if not _persona_belongs_to_project(persona, project):
        raise HTTPException(status_code=400, detail="Selected persona does not belong to this project")

    work_template_payload = request.work_template.model_dump() if request.work_template else None
    plan_payload = request.plan.model_dump() if request.plan else None
    state = db.upsert_project_workspace_state(
        project_id=project_id,
        persona_id=persona_id,
        focus_question=(request.focus_question or "").strip() or None,
        clarifying_answers=request.clarifying_answers,
        reasoning_notes=(request.reasoning_notes or "").strip() or None,
        work_template=work_template_payload,
        plan=plan_payload,
        selected_step_id=(request.selected_step_id or "").strip() or None,
    )
    await log_event_safe(
        "project_workspace_saved",
        {
            "project_id": project_id,
            "persona_id": persona_id,
            "has_plan": plan_payload is not None,
            "clarifying_answers": len(request.clarifying_answers or {}),
            "has_work_template": _work_template_has_content(request.work_template),
            **_work_template_counts(request.work_template),
        },
    )
    return _workspace_state_to_response(state)


@app.post("/api/projects/{project_id}/literature", response_model=FetchProjectLiteratureResponse)
async def fetch_project_literature(project_id: int, request: FetchProjectLiteratureRequest):
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    persona = db.get_persona(request.persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    if not _persona_belongs_to_project(persona, project):
        raise HTTPException(status_code=400, detail="Selected persona does not belong to this project")

    query = " ".join((request.query or "").split()).strip()
    if not query:
        raise HTTPException(status_code=400, detail="Literature query is required")

    max_results = max(1, min(int(request.max_results or 5), 8))
    try:
        result = await search_pubmed(
            query,
            max_results=max_results,
            project_goal=str(request.project_goal or project.get("project_goal") or ""),
            objective_title=request.objective_title or "",
            objective_definition=request.objective_definition or "",
            objective_signals=request.objective_signals or [],
            user_inputs=[
                str(request.project_end_product or ""),
                str(request.project_target_host or ""),
                " ".join(f"{question}: {answer}" for question, answer in (request.clarifying_answers or {}).items() if str(answer).strip()),
                " ".join(f"{question}: {answer}" for question, answer in (request.objective_answers or {}).items() if str(answer).strip()),
                " ".join(f"{question}: {answer}" for question, answer in (request.global_question_answers or {}).items() if str(answer).strip()),
                request.reasoning_notes or "",
                _work_template_to_prompt_text(request.work_template),
                str(project.get("end_product") or ""),
                str(project.get("target_host") or ""),
                str(project.get("raw_material_focus") or ""),
                str(project.get("notes") or ""),
            ],
        )
        records = result.get("results") or []
        existing = {str(item or "").strip().lower() for item in (request.existing_citations or []) if str(item or "").strip()}
        raw_findings: List[ResearchFinding] = []
        for index, record in enumerate(records, start=1):
            raw_findings.append(_pubmed_record_to_research_finding(record, index))

        processing = await _synthesize_literature_processing(project, persona, request, records, raw_findings)
        synthesized_findings = processing.get("findings") or raw_findings
        findings: List[ResearchFinding] = []
        for finding in synthesized_findings:
            if finding.citation.strip().lower() in existing:
                continue
            findings.append(finding)

        trace = LiteratureToolTrace(
            tool_name="search_pubmed",
            query=str(result.get("search_query") or result.get("formulated_query") or query),
            result_count=len(records),
            status="success",
        )
        await log_event_safe(
            "project_literature_fetched",
            {
                "project_id": project_id,
                "persona_id": request.persona_id,
                "objective_id": request.objective_id,
                "objective_title": request.objective_title,
                "tool_name": trace.tool_name,
                "query": query,
                "search_query": trace.query,
                "search_attempts": result.get("attempts") or [],
                "result_count": len(records),
                "new_findings": len(findings),
                "has_processing_summary": bool(processing.get("processing_summary")),
            },
        )
        return FetchProjectLiteratureResponse(
            findings=findings,
            tool_trace=trace,
            objective_lens=processing.get("objective_lens"),
            processing_summary=str(processing.get("processing_summary") or ""),
            elicitation_questions=processing.get("elicitation_questions") or [],
        )
    except Exception as exc:
        trace = LiteratureToolTrace(
            tool_name="search_pubmed",
            query=query,
            result_count=0,
            status="error",
            error_message=str(exc),
        )
        await log_event_safe(
            "project_literature_fetch_failed",
            {
                "project_id": project_id,
                "persona_id": request.persona_id,
                "objective_id": request.objective_id,
                "tool_name": trace.tool_name,
                "query": query,
                "error": str(exc),
            },
        )
        raise HTTPException(status_code=502, detail=f"Literature fetch failed via {trace.tool_name}: {exc}") from exc


@app.get("/api/projects/{project_id}/execution-runs/latest", response_model=ProjectExecutionRunResponse)
async def get_latest_project_execution_run(project_id: int, persona_id: int = Query(...)):
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    persona = db.get_persona(persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    if not _persona_belongs_to_project(persona, project):
        raise HTTPException(status_code=400, detail="Selected persona does not belong to this project")

    run = db.get_latest_project_execution_run(project_id, persona_id)
    if not run:
        return _execution_run_to_response(None, [])
    events = db.list_project_execution_events(int(run["id"]))
    return _execution_run_to_response(run, events)


@app.get("/api/projects/{project_id}/execution-runs/{run_id}", response_model=ProjectExecutionRunResponse)
async def get_project_execution_run(project_id: int, run_id: int):
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    run = db.get_project_execution_run(run_id)
    if not run or int(run.get("project_id") or 0) != project_id:
        raise HTTPException(status_code=404, detail="Execution run not found")
    events = db.list_project_execution_events(run_id)
    return _execution_run_to_response(run, events)


@app.post("/api/projects/{project_id}/execution-runs", response_model=ProjectExecutionRunResponse)
async def start_project_execution_run(project_id: int, request: StartProjectExecutionRequest):
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    persona = db.get_persona(request.persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    if not _persona_belongs_to_project(persona, project):
        raise HTTPException(status_code=400, detail="Selected persona does not belong to this project")

    existing = db.get_latest_project_execution_run(project_id, request.persona_id)
    if existing and str(existing.get("status") or "") in {"queued", "running"}:
        return _execution_run_to_response(existing, db.list_project_execution_events(int(existing["id"])))

    run = db.create_project_execution_run(
        project_id=project_id,
        persona_id=request.persona_id,
        run_kind="agentic_execution",
        objective_id=(request.objective_id or "").strip() or None,
        mode_label=(request.objective_title or request.objective_id or "").strip() or None,
        focus_question=(request.focus_question or "").strip() or None,
        input_payload=request.model_dump(),
    )
    task = asyncio.create_task(_run_project_execution_task(int(run["id"]), project, persona, request))
    _project_execution_tasks[int(run["id"])] = task

    await log_event_safe(
        "project_execution_started",
        {
            "project_id": project_id,
            "persona_id": request.persona_id,
            "run_id": int(run["id"]),
            "objective_id": request.objective_id,
            "mode_label": request.objective_title,
        },
    )
    return _execution_run_to_response(run, db.list_project_execution_events(int(run["id"])))


@app.post("/api/projects/{project_id}/plan", response_model=GeneratePlanResponse)
async def generate_project_plan(project_id: int, request: GenerateProjectPlanRequest):
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    persona = db.get_persona(request.persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    if not _persona_belongs_to_project(persona, project):
        raise HTTPException(status_code=400, detail="Selected persona does not belong to this project")

    persona_summary = persona.get("last_summary") or "No persona summary available."
    planner_model = (
        os.getenv("OLLAMA_PLANNER_MODEL")
        or os.getenv("OLLAMA_SOTA_MODEL")
        or ollama.model
    )

    prompt = _assemble_prompt(
        system_instruction=(
            "You are a biotech collaboration copilot. Produce strict JSON only. "
            "Make drafts concrete, question-aware, stage-aware when needed, and decision-useful."
        ),
        persona_id=request.persona_id,
        task_context=ollama.get_project_plan_prompt(
            project=project,
            persona_summary=persona_summary,
            focus_question=request.focus_question,
            notes=request.notes,
            clarifying_answers=request.clarifying_answers,
            reasoning_notes=request.reasoning_notes,
            work_template_summary=_work_template_to_prompt_text(request.work_template),
        ),
    )

    used_fallback = False
    fallback_reason = ""

    try:
        response_data = await ollama.generate_json(
            prompt,
            max_retries=2,
            temperature=0.2,
            top_p=0.9,
            model=planner_model,
        )
        raw_plan = response_data.get("plan") if isinstance(response_data, dict) else None
        if raw_plan is None:
            raw_plan = response_data
        plan = AgenticPlan.model_validate(raw_plan)
    except Exception as exc:
        used_fallback = True
        fallback_reason = str(exc)
        plan = _fallback_project_plan(project, persona, request)

    await log_event_safe(
        "project_plan_generated",
        {
            "project_id": project_id,
            "persona_id": request.persona_id,
            "focus_question": request.focus_question,
            "clarifying_answers": len(request.clarifying_answers or {}),
            "has_work_template": _work_template_has_content(request.work_template),
            **_work_template_counts(request.work_template),
            "steps": len(plan.steps),
            "model": planner_model,
            "used_fallback": used_fallback,
            "fallback_reason": fallback_reason[:200] if fallback_reason else None,
        },
    )
    db.upsert_project_workspace_state(
        project_id=project_id,
        persona_id=request.persona_id,
        focus_question=(request.focus_question or "").strip() or None,
        clarifying_answers=request.clarifying_answers,
        reasoning_notes=(request.reasoning_notes or "").strip() or None,
        work_template=request.work_template.model_dump() if request.work_template else None,
        plan=plan.model_dump(),
        selected_step_id=plan.steps[0].id if plan.steps else None,
    )
    return GeneratePlanResponse(plan=plan)

@app.post("/objectives", response_model=ObjectivesResponse)
async def generate_objectives(request: ObjectivesRequest):
    """Generate objective clusters for an underspecified query."""
    try:
        # Check for existing prior
        query_sig = db.query_signature(request.query)
        prior = db.get_prior(query_sig)
        
        used_fallback = False
        fallback_reason = ""
        try:
            prompt = _assemble_prompt(
                system_instruction="Follow safety and formatting policy. Return strict JSON only.",
                persona_id=request.persona_id,
                task_context=ollama.get_objectives_prompt(request.query, request.context, request.k),
            )
            print(f"DEBUG: Generated prompt length: {len(prompt)} chars")

            response_data = await ollama.generate_json(prompt)
            print(f"DEBUG: Raw response type: {type(response_data)}")
            print(f"DEBUG: Response keys: {list(response_data.keys()) if response_data else 'None'}")

            objectives = [Objective(**obj) for obj in response_data.get("objectives", [])]
            global_questions = response_data.get("global_questions", [])
            if not objectives:
                raise ValueError("Objective generation returned no objectives")

            print(f"DEBUG: Parsed {len(objectives)} objectives and {len(global_questions)} global questions")
        except Exception as llm_error:
            used_fallback = True
            fallback_reason = str(llm_error)
            fallback = _fallback_objective_clusters(request)
            objectives = fallback.objectives
            global_questions = fallback.global_questions
            print(f"DEBUG: Falling back to deterministic objective clusters: {fallback_reason}")
        
        # Log event
        await log_event_safe("objectives_generated", {
            "query": request.query,
            "has_context": bool(request.context),
            "num_objectives": len(objectives),
            "has_prior": prior is not None,
            "used_fallback": used_fallback,
            "fallback_reason": fallback_reason[:200] if fallback_reason else None,
        })
        
        return ObjectivesResponse(
            objectives=objectives,
            global_questions=global_questions
        )
        
    except Exception as e:
        import traceback
        print(f"DEBUG: Exception in generate_objectives: {str(e)}")
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to generate objectives: {str(e)}") from e

@app.post("/augment", response_model=AugmentResponse)
async def augment_with_context(request: AugmentRequest):
    """Augment selected objective with external context."""
    try:
        if not request.context_blob:
            # No context provided
            return AugmentResponse(
                evidence_items=[],
                augmented_answer=None
            )
        
        # Generate prompt and get response
        prompt = _assemble_prompt(
            system_instruction="Follow safety and formatting policy. Return strict JSON only.",
            persona_id=request.persona_id,
            task_context=ollama.get_augment_prompt(
                request.query,
                request.objective_id,
                request.objective_definition,
                request.context_blob,
            ),
        )
        response_data = await ollama.generate_json(prompt)
        
        # Convert to proper objects
        evidence_items = [EvidenceItem(**item) for item in response_data.get("evidence_items", [])]
        augmented_answer = response_data.get("augmented_answer")
        
        # Log event
        await log_event_safe("context_augmented", {
            "query": request.query,
            "objective_id": request.objective_id,
            "evidence_count": len(evidence_items)
        })
        
        return AugmentResponse(
            evidence_items=evidence_items,
            augmented_answer=augmented_answer
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to augment with context: {str(e)}") from e

@app.post("/finalize", response_model=FinalizeResponse)
async def finalize_answer(request: FinalizeRequest):
    """Generate final answer based on selected objective and user answers."""
    try:
        # Generate prompt and get response
        prompt = _assemble_prompt(
            system_instruction="Follow safety and formatting policy. Return strict JSON only.",
            persona_id=request.persona_id,
            task_context=ollama.get_finalize_prompt(
                request.query,
                request.objective,
                request.answers,
                request.evidence_items,
            ),
        )
        response_data = await ollama.generate_json(prompt)
        
        # Extract response data
        final_answer = response_data.get("final_answer", "")
        assumptions = response_data.get("assumptions", [])
        next_questions = response_data.get("next_questions", [])
        
        # Update prior for future queries
        query_sig = db.query_signature(request.query)
        db.update_prior(query_sig, request.objective.id, request.answers)
        
        # Log event
        await log_event_safe("answer_finalized", {
            "query": request.query,
            "objective_id": request.objective.id,
            "has_evidence": bool(request.evidence_items),
            "assumptions_count": len(assumptions)
        })
        
        return FinalizeResponse(
            final_answer=final_answer,
            assumptions=assumptions,
            next_questions=next_questions
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to finalize answer: {str(e)}") from e


@app.post("/api/plans/generate", response_model=GeneratePlanResponse)
async def generate_agentic_plan(request: GeneratePlanRequest):
    try:
        persona = db.get_persona(request.persona_id)
        if not persona:
            raise HTTPException(status_code=404, detail="Persona not found")

        persona_summary = persona.get("last_summary") or "No persona summary available."
        planner_model = (
            os.getenv("OLLAMA_PLANNER_MODEL")
            or os.getenv("OLLAMA_SOTA_MODEL")
            or ollama.model
        )

        prompt = _assemble_prompt(
            system_instruction=(
                "You are a planning copilot. Produce strict JSON only. "
                "Prioritize factual, verifiable reasoning and transparent step rationale."
            ),
            persona_id=request.persona_id,
            task_context=ollama.get_agentic_plan_prompt(
                query=request.query,
                objective=request.objective,
                persona_summary=persona_summary,
                facet_answers=request.facet_answers,
                context_blob=request.context_blob,
            ),
        )

        response_data = await ollama.generate_json(
            prompt,
            max_retries=2,
            temperature=0.2,
            top_p=0.9,
            model=planner_model,
        )

        raw_plan = response_data.get("plan") if isinstance(response_data, dict) else None
        if raw_plan is None:
            raw_plan = response_data

        plan = AgenticPlan.model_validate(raw_plan)

        await log_event_safe(
            "agentic_plan_generated",
            {
                "query": request.query,
                "objective_id": request.objective.id,
                "persona_id": request.persona_id,
                "steps": len(plan.steps),
                "model": planner_model,
            },
        )

        return GeneratePlanResponse(plan=plan)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate plan: {str(e)}") from e


def _workspace_memory_row_to_response(row: Optional[dict]) -> Optional[WorkspaceMemory]:
    if not row:
        return None
    return WorkspaceMemory(
        workspace_key=str(row.get("workspace_key") or ""),
        scope=str(row.get("scope") or "default"),
        explicit_state=row.get("explicit_state") or {},
        tacit_state=[TacitMemoryItem.model_validate(item) for item in (row.get("tacit_state") or [])],
        handoff_summary=str(row.get("handoff_summary") or ""),
        updated_at=row.get("updated_at"),
    )


def _compact_explicit_state_for_prompt(explicit_state: Dict[str, Any]) -> Dict[str, Any]:
    keys = [
        "query",
        "context_blob",
        "persona",
        "persona_id",
        "selected_project",
        "selected_objective",
        "clarifying_answers",
        "objective_answers",
        "global_question_answers",
        "reasoning_notes",
        "research_work_template",
        "agentic_plan",
        "execution_run",
    ]
    compact = {key: explicit_state.get(key) for key in keys if explicit_state.get(key) not in (None, "", [], {})}
    text = json.dumps(compact, ensure_ascii=False)
    if len(text) > 12000:
        compact["context_blob"] = str(compact.get("context_blob") or "")[:2000]
        if isinstance(compact.get("agentic_plan"), dict):
            plan = dict(compact["agentic_plan"])
            plan["steps"] = (plan.get("steps") or [])[:4]
            compact["agentic_plan"] = plan
    return compact


def _fallback_tacit_memory(request: InferWorkspaceMemoryRequest) -> InferWorkspaceMemoryResponse:
    state = request.explicit_state or {}
    objective = state.get("selected_objective") or {}
    answers = state.get("objective_answers") or state.get("clarifying_answers") or {}
    items = []
    if objective:
        items.append(
            TacitMemoryItem(
                id="objective_preference",
                label="Selected reasoning lens",
                inference=f"The user is currently framing the work through '{objective.get('title') or 'the selected objective'}'.",
                evidence=[objective.get("definition") or objective.get("subtitle") or "Objective mode was selected."],
                confidence=0.75,
            )
        )
    if answers:
        items.append(
            TacitMemoryItem(
                id="answered_constraints",
                label="User-supplied constraints",
                inference="The user's answers should be treated as project constraints or preferences until revised.",
                evidence=[f"{question}: {answer}" for question, answer in list(answers.items())[:4] if str(answer).strip()],
                confidence=0.7,
            )
        )
    if state.get("persona"):
        items.append(
            TacitMemoryItem(
                id="collaborator_lens",
                label="Collaborator lens",
                inference=f"The work is being shaped for the selected collaborator/persona: {state.get('persona')}.",
                evidence=["Persona/collaborator selected in the workspace."],
                confidence=0.65,
            )
        )
    return InferWorkspaceMemoryResponse(
        tacit_state=items,
        handoff_summary="Use the saved explicit state and confirmed tacit state as the starting context for future collaborators or onboarding.",
    )


@app.get("/api/workspace-memory/{workspace_key}", response_model=WorkspaceMemoryResponse)
async def get_workspace_memory(workspace_key: str):
    return WorkspaceMemoryResponse(memory=_workspace_memory_row_to_response(db.get_workspace_memory(workspace_key)))


@app.put("/api/workspace-memory/{workspace_key}", response_model=WorkspaceMemoryResponse)
async def save_workspace_memory(workspace_key: str, request: WorkspaceMemoryRequest):
    row = db.upsert_workspace_memory(
        workspace_key=workspace_key,
        scope=request.scope,
        explicit_state=request.explicit_state,
        tacit_state=[item.model_dump() for item in request.tacit_state],
        handoff_summary=request.handoff_summary,
    )
    await log_event_safe(
        "workspace_memory_saved",
        {
            "workspace_key": workspace_key,
            "scope": request.scope,
            "explicit_keys": sorted(list((request.explicit_state or {}).keys())),
            "tacit_items": len(request.tacit_state or []),
        },
    )
    return WorkspaceMemoryResponse(memory=_workspace_memory_row_to_response(row))


@app.post("/api/workspace-memory/infer", response_model=InferWorkspaceMemoryResponse)
async def infer_workspace_memory(request: InferWorkspaceMemoryRequest):
    compact_state = _compact_explicit_state_for_prompt(request.explicit_state or {})
    prompt = f"""
Infer reviewable tacit workspace memory for a scientific planning workspace.

The goal is not to make final decisions. The goal is to surface assumptions, preferences, constraints,
handoff knowledge, and collaborator-relevant context that a user should confirm, reject, or edit.

Rules:
- Return strict JSON only.
- Do not invent facts. Every inference needs evidence from the explicit state.
- Prefer concise items that would help onboard a new hire if the original user leaves.
- Mark uncertain items with lower confidence.
- Keep ids stable snake_case.

Explicit workspace state:
{json.dumps(compact_state, ensure_ascii=False, indent=2)}

Existing tacit state:
{json.dumps([item.model_dump() for item in request.existing_tacit_state], ensure_ascii=False, indent=2)}

Return:
{{
  "tacit_state": [
    {{
      "id": "stable_snake_case_id",
      "label": "short label",
      "inference": "what the system thinks is tacitly true or important",
      "evidence": ["specific user/objective/persona/evidence signal"],
      "confidence": 0.0,
      "status": "inferred",
      "reviewer_note": null
    }}
  ],
  "handoff_summary": "short onboarding-oriented summary of the current workspace state"
}}
""".strip()
    try:
        response_data = await ollama.generate_json(prompt, max_retries=2, temperature=0.2, top_p=0.9)
        items = [TacitMemoryItem.model_validate(item) for item in response_data.get("tacit_state", [])]
        handoff_summary = str(response_data.get("handoff_summary") or "").strip()
        if not items and not handoff_summary:
            return _fallback_tacit_memory(request)
        return InferWorkspaceMemoryResponse(tacit_state=items[:12], handoff_summary=handoff_summary)
    except Exception:
        return _fallback_tacit_memory(request)


@app.post("/log_event")
async def log_event(request: LogEventRequest):
    """Log an event for internalization/prior building."""
    try:
        db.log_event(request)
        return {"status": "logged"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to log event: {str(e)}") from e


@app.post("/api/feedback", response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackRequest):
    try:
        feedback_id = db.create_feedback(
            persona_id=request.persona_id,
            objective_id=request.objective_id,
            query=request.query,
            response_text=request.response_text,
            rating=request.rating,
            feedback_text=request.feedback_text,
            metadata=request.metadata,
        )
        db.log_event(
            LogEventRequest(
                event_type="explicit_feedback",
                payload={
                    "feedback_id": feedback_id,
                    "persona_id": request.persona_id,
                    "objective_id": request.objective_id,
                    "query": request.query,
                    "response_text": request.response_text,
                    "rating": request.rating,
                    "feedback_text": request.feedback_text,
                    "metadata": request.metadata,
                },
            )
        )
        return FeedbackResponse(status="recorded")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record feedback: {str(e)}") from e


@app.get("/api/feedback")
async def list_feedback(persona_id: Optional[int] = Query(default=None), limit: int = Query(default=100, ge=1, le=500)):
    try:
        return {"feedback": db.list_feedback(persona_id=persona_id, limit=limit)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read feedback: {str(e)}") from e


@app.get("/api/personas/{persona_id}/change-log", response_model=PersonaChangeLogResponse)
async def get_persona_change_log(persona_id: int, limit: int = Query(default=20, ge=1, le=100)):
    persona = db.get_persona(persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    events = db.list_events(min_id=0, limit=2000)
    items: List[PersonaChangeLogItem] = []
    for event in reversed(events):
        if event.get("event_type") != "persona_refactored":
            continue
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        source_id = payload.get("source_persona_id")
        new_id = payload.get("new_persona_id")
        if source_id != persona_id and new_id != persona_id:
            continue
        items.append(
            PersonaChangeLogItem(
                source_persona_id=int(source_id or persona_id),
                new_persona_id=int(new_id or persona_id),
                created_at=event.get("timestamp") or "",
                changes=[str(x) for x in (payload.get("changes") or [])],
                reasons=[str(x) for x in (payload.get("reasons") or [])],
                supporting_events={str(k): int(v) for k, v in (payload.get("supporting_events") or {}).items()},
            )
        )
        if len(items) >= limit:
            break

    return PersonaChangeLogResponse(persona_id=persona_id, items=items)
@app.post("/api/personas/refactor-from-interactions", response_model=PersonaRefactorResponse)
async def refactor_personas_from_interactions():
    try:
        return await _run_persona_refactor_pass()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refactor personas: {str(e)}") from e

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "SECI Query Explorer API"}

@app.get("/context/list", response_model=ContextListResponse)
async def context_list(path: Optional[str] = None):
    """List context files and directories under /context."""
    try:
        entries = [ContextListEntry(**entry.__dict__) for entry in list_context_dir(path)]
        return ContextListResponse(entries=entries)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to list context: {str(e)}")

@app.get("/context/read", response_model=ContextReadResponse)
async def context_read(path: str, offset: int = 1, limit: int = 2000):
    """Read a context file with optional line slicing."""
    try:
        payload = read_context_file(path, offset=offset, limit=limit)
        return ContextReadResponse(**payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read context: {str(e)}")

@app.post("/context/write", response_model=ContextWriteResponse)
async def context_write(request: ContextWriteRequest):
    """Write a context file under /context."""
    try:
        payload = write_context_file(request.path, request.content, overwrite=request.overwrite)
        return ContextWriteResponse(**payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to write context: {str(e)}")

@app.post("/context/search", response_model=ContextSearchResponse)
async def context_search(request: ContextSearchRequest):
    """Search context via qmd (hybrid, keyword, or semantic)."""
    try:
        matches = qmd_search(
            query=request.query,
            mode=request.mode,
            collection=request.collection,
            limit=request.max_results,
        )
        response_matches = [ContextSearchMatch(**match.__dict__) for match in matches]
        return ContextSearchResponse(matches=response_matches)
    except QmdError as e:
        raise HTTPException(status_code=400, detail=f"QMD search failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to search context: {str(e)}")

@app.get("/context/qmd/health", response_model=QmdHealthResponse)
async def qmd_health():
    """Check QMD health and configuration."""
    try:
        import asyncio
        result = await asyncio.to_thread(qmd_health_check)
        return QmdHealthResponse(
            healthy=result.get("healthy", False),
            version=result.get("version"),
            collections_count=result.get("collections_count"),
            collections=result.get("collections"),
            error=result.get("error")
        )
    except Exception as e:
        return QmdHealthResponse(healthy=False, error=str(e))

@app.post("/context/qmd/get", response_model=ContextGetResponse)
async def context_get(request: ContextGetRequest):
    """Get a single document by path or docid."""
    try:
        doc = qmd_get(request.path_or_docid, full=request.full)
        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found")
        return ContextGetResponse(
            path=doc.path,
            content=doc.content,
            doc_id=doc.doc_id,
            metadata=doc.metadata
        )
    except QmdError as e:
        raise HTTPException(status_code=400, detail=f"QMD get failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get document: {str(e)}")

@app.post("/context/qmd/multi-get", response_model=ContextMultiGetResponse)
async def context_multi_get(request: ContextMultiGetRequest):
    """Get multiple documents matching a glob pattern."""
    try:
        docs = qmd_multi_get(request.pattern, full=request.full)
        return ContextMultiGetResponse(
            documents=[
                ContextGetResponse(
                    path=doc.path,
                    content=doc.content,
                    doc_id=doc.doc_id,
                    metadata=doc.metadata
                )
                for doc in docs
            ]
        )
    except QmdError as e:
        raise HTTPException(status_code=400, detail=f"QMD multi-get failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get documents: {str(e)}")

@app.get("/context/qmd/collections", response_model=ContextCollectionsResponse)
async def context_collections():
    """List all QMD collections."""
    try:
        collections = qmd_list_collections()
        return ContextCollectionsResponse(
            collections=[
                ContextCollectionInfo(
                    name=c.name,
                    path=c.path,
                    document_count=c.document_count
                )
                for c in collections
            ]
        )
    except QmdError as e:
        raise HTTPException(status_code=400, detail=f"QMD collections failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to list collections: {str(e)}")

@app.post("/context/qmd/sync", response_model=ContextSyncResponse)
async def context_sync():
    """Sync filesystem context to QMD index and regenerate embeddings."""
    try:
        from context_fs import CONTEXT_ROOT
        collections_updated, documents_indexed = qmd_sync_fs_to_index(str(CONTEXT_ROOT))
        return ContextSyncResponse(
            success=True,
            collections_updated=collections_updated,
            documents_indexed=documents_indexed,
            message=f"Synced {documents_indexed} documents across {collections_updated} collections"
        )
    except QmdError as e:
        raise HTTPException(status_code=400, detail=f"QMD sync failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to sync context: {str(e)}")


@app.post("/api/reports", response_model=CreateReportResponse)
async def create_report(request: CreateReportRequest):
    qmd_stub = request.initial_qmd or default_qmd_skeleton(request.title)
    qmd_hash = compute_content_hash(qmd_stub)

    report_id = db.create_report(
        title=request.title,
        objective_id=request.objective_id,
        qmd_path="",
    )
    qmd_path = write_qmd(report_id, qmd_stub)
    db.set_report_qmd_path(report_id, qmd_path)
    db.update_report_qmd(report_id, qmd_hash)

    return CreateReportResponse(report_id=report_id, qmd_url=f"/api/reports/{report_id}/qmd")


@app.get("/api/reports")
async def list_reports(objective_id: Optional[str] = Query(default=None)):
    rows = db.list_reports(objective_id=objective_id)
    return {"reports": [_report_metadata_response(r).model_dump() for r in rows]}


@app.get("/api/reports/{report_id}", response_model=ReportMetadataResponse)
async def get_report(report_id: int):
    row = db.get_report(report_id)
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")
    return _report_metadata_response(row)


@app.get("/api/reports/{report_id}/qmd")
async def get_report_qmd(report_id: int):
    row = db.get_report(report_id)
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"report_id": report_id, "qmd": read_qmd(report_id)}


@app.put("/api/reports/{report_id}/qmd")
async def update_report_qmd(report_id: int, request: UpdateReportQmdRequest):
    row = db.get_report(report_id)
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")

    write_qmd(report_id, request.qmd)
    content_hash = compute_content_hash(request.qmd)
    db.update_report_qmd(report_id, content_hash)
    return {"report_id": report_id, "content_hash": content_hash}


@app.post("/api/reports/{report_id}/render", response_model=RenderReportResponse)
async def enqueue_report_render(report_id: int, request: RenderReportRequest):
    row = db.get_report(report_id)
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")

    qmd_text = read_qmd(report_id)
    if not qmd_text.strip():
        raise HTTPException(status_code=400, detail="Report QMD is empty")

    params = dict(request.params)
    if request.persona_id is not None:
        params["persona_id"] = request.persona_id
        db.update_report_status(report_id, status=row["status"], persona_id=request.persona_id)
    if row.get("objective_id"):
        params.setdefault("objective_id", row["objective_id"])

    content_hash = compute_content_hash(qmd_text)
    formats = [str(x) for x in (request.formats or ["html"])]
    if request.cache_ok and manifest_cache_hit(report_id, content_hash, params, formats):
        db.update_report_status(report_id, "success", error_message=None)
        return RenderReportResponse(report_id=report_id, status="success", cache_hit=True)

    job_id = db.enqueue_render_job(report_id, params=params, output_formats=formats)
    return RenderReportResponse(report_id=report_id, job_id=job_id, status="queued", cache_hit=False)


@app.get("/api/reports/{report_id}/output/html")
async def get_report_output_html(report_id: int):
    row = db.get_report(report_id)
    if not row or not row.get("last_output_html_path"):
        raise HTTPException(status_code=404, detail="HTML output not found")
    candidate = row["last_output_html_path"]
    _ensure_under_artifact_root(candidate)
    if not Path(candidate).exists():
        raise HTTPException(status_code=404, detail="HTML output not found")
    return FileResponse(candidate, media_type="text/html")


@app.get("/api/reports/{report_id}/output/pdf")
async def get_report_output_pdf(report_id: int):
    row = db.get_report(report_id)
    if not row or not row.get("last_output_pdf_path"):
        raise HTTPException(status_code=404, detail="PDF output not found")
    candidate = row["last_output_pdf_path"]
    _ensure_under_artifact_root(candidate)
    if not Path(candidate).exists():
        raise HTTPException(status_code=404, detail="PDF output not found")
    return FileResponse(candidate, media_type="application/pdf", filename=f"report_{report_id}.pdf")


@app.get("/api/reports/{report_id}/logs", response_model=ReportLogsResponse)
async def get_report_logs(report_id: int):
    row = db.get_report(report_id)
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")
    log_path = row.get("last_log_path")
    content = read_log_tail(log_path)
    return ReportLogsResponse(report_id=report_id, log_path=log_path, content=content)


@app.get("/api/objectives/{objective_id}/reports")
async def list_objective_reports(objective_id: str):
    return {"reports": db.list_reports_for_objective(objective_id)}


@app.post("/api/interviews", response_model=CreateInterviewResponse)
async def create_interview(request: CreateInterviewRequest):
    metadata = dict(request.metadata_json)
    if request.transcript_text:
        participant_id = _extract_participant_id(request.transcript_text)
        if participant_id:
            metadata["participant_id"] = participant_id

    interview_id = db.create_interview(
        scope=request.scope,
        transcript_text=request.transcript_text,
        transcript_path=request.transcript_path,
        metadata_json=metadata,
    )
    _write_interview_context(request.scope, request.transcript_path or "interview.txt", request.transcript_text)
    return CreateInterviewResponse(interview_id=interview_id)


@app.post("/api/interviews/import-texts", response_model=ImportInterviewTextsResponse)
async def import_interview_texts(request: ImportInterviewTextsRequest):
    folder = _resolve_interview_folder(request.folder)
    if not folder.exists() or not folder.is_dir():
        raise HTTPException(status_code=404, detail="Interview folder not found")

    glob_pattern = "**/*.txt" if request.recursive else "*.txt"
    files = sorted([p for p in folder.glob(glob_pattern) if p.is_file()])
    if not files:
        return ImportInterviewTextsResponse(imported_count=0, imported_files=[], skipped_count=0, skipped_files=[])

    imported_files = []
    skipped_files = []
    for txt_file in files:
        resolved_path = str(txt_file.resolve())
        existing = db.get_interview_by_scope_path(request.scope, resolved_path)
        if existing:
            skipped_files.append(resolved_path)
            continue

        text = txt_file.read_text(encoding="utf-8", errors="replace")
        participant_id = _extract_participant_id(text)
        db.create_interview(
            scope=request.scope,
            transcript_text=None,
            transcript_path=resolved_path,
            metadata_json={
                "source": "txt-import",
                "file_name": txt_file.name,
                "relative_path": str(txt_file.relative_to(folder)).replace("\\", "/"),
                "participant_id": participant_id,
            },
        )
        _write_interview_context(request.scope, resolved_path)
        imported_files.append(resolved_path)

    return ImportInterviewTextsResponse(
        imported_count=len(imported_files),
        imported_files=imported_files,
        skipped_count=len(skipped_files),
        skipped_files=skipped_files,
    )


@app.get("/api/interviews", response_model=InterviewListResponse)
async def list_interviews(scope_id: Optional[str] = Query(default=None)):
    if not scope_id:
        raise HTTPException(status_code=400, detail="scope_id is required")
    rows = db.get_interviews(scope_id)
    return InterviewListResponse(interviews=[_interview_row_to_response(r) for r in rows])


@app.post("/api/personas/from-interviews", response_model=PersonaFromInterviewsResponse)
async def create_or_update_persona_from_interviews(request: PersonaFromInterviewsRequest):
    interviews = db.get_interviews(request.scope_id, request.interview_ids)
    if not interviews:
        raise HTTPException(status_code=404, detail="No interviews found for scope")

    participant_id = _extract_participant_id_from_interviews(interviews)
    persona_name = request.persona_name or participant_id or "Unknown Persona"

    identity_key = _persona_identity_key(request.scope_id, persona_name, interviews)

    try:
        persona_payload, summary, fragments = await extract_persona_from_interviews(
            scope_id=request.scope_id,
            persona_name=persona_name,
            interviews=interviews,
        )
    except Exception as ex:
        raise HTTPException(status_code=400, detail=f"Persona extraction failed: {ex}") from ex

    existing_by_name = _find_persona_by_identity(request.scope_id, persona_name, identity_key=identity_key)

    if request.mode == "update":
        if not request.persona_id:
            raise HTTPException(status_code=400, detail="persona_id is required for update mode")
        existing = db.get_persona(request.persona_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Persona not found")
        merged_payload = merge_persona_payloads(existing.get("persona_json") or {}, persona_payload)
        merged_summary = build_persona_summary(PersonaPayload.model_validate(merged_payload))
        db.update_persona(
            request.persona_id,
            persona_json=merged_payload,
            last_summary=merged_summary,
            name=persona_name,
            identity_key=identity_key,
        )
        _write_persona_context(request.scope_id, persona_name, merged_payload, merged_summary, identity_key)
        save_persona_snapshot(request.persona_id, merged_payload, fragments)
        consolidated = _consolidate_persona_duplicates(request.scope_id, persona_name, identity_key, request.persona_id)
        return PersonaFromInterviewsResponse(persona_id=(consolidated["id"] if consolidated else request.persona_id))

    if existing_by_name:
        existing_versions = db.list_personas_by_scope_identity(request.scope_id, identity_key)
        if not existing_versions:
            existing_versions = db.list_personas_by_scope_name_normalized(request.scope_id, persona_name)
        max_version = max((p.get("version", 1) for p in existing_versions), default=0)
        new_version = max_version + 1
        persona_id = db.create_persona(
            name=persona_name,
            scope=request.scope_id,
            persona_json=persona_payload,
            last_summary=summary,
            identity_key=identity_key,
            version=new_version,
        )
        _write_persona_context(request.scope_id, persona_name, persona_payload, summary, identity_key)
        save_persona_snapshot(persona_id, persona_payload, fragments)
        return PersonaFromInterviewsResponse(persona_id=persona_id)

    persona_id = db.create_persona(
        name=persona_name,
        scope=request.scope_id,
        persona_json=persona_payload,
        last_summary=summary,
        identity_key=identity_key,
    )
    _write_persona_context(request.scope_id, persona_name, persona_payload, summary, identity_key)
    save_persona_snapshot(persona_id, persona_payload, fragments)
    return PersonaFromInterviewsResponse(persona_id=persona_id)


@app.post("/api/personas/extract-all", response_model=ExtractAllPersonasResponse)
async def extract_all_personas(request: ExtractAllPersonasRequest):
    from collections import defaultdict
    
    interviews = db.get_interviews(request.scope_id)
    if not interviews:
        raise HTTPException(status_code=404, detail="No interviews found for scope")
    
    by_participant: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    no_participant: List[Dict[str, Any]] = []
    
    for interview in interviews:
        pid = _extract_participant_id_from_interviews([interview])
        if pid:
            by_participant[pid].append(interview)
        else:
            no_participant.append(interview)
    
    extracted = []
    skipped = []
    
    for participant_id, participant_interviews in by_participant.items():
        identity_key = f"participant:{_canonical_identity(participant_id)}"
        existing = db.get_persona_by_scope_identity(request.scope_id, identity_key)
        
        if existing and request.extract_new_only:
            skipped.append({
                "participant_id": participant_id,
                "reason": "already_exists",
                "persona_id": existing["id"],
            })
            continue
        
        try:
            persona_payload, summary, fragments = await extract_persona_from_interviews(
                scope_id=request.scope_id,
                persona_name=participant_id,
                interviews=participant_interviews,
            )
        except Exception as ex:
            skipped.append({
                "participant_id": participant_id,
                "reason": f"extraction_failed: {ex}",
            })
            continue
        
        if existing:
            existing_versions = db.list_personas_by_scope_identity(request.scope_id, identity_key)
            max_version = max((p.get("version", 1) for p in existing_versions), default=0)
            new_version = max_version + 1
            persona_id = db.create_persona(
                name=participant_id,
                scope=request.scope_id,
                persona_json=persona_payload,
                last_summary=summary,
                identity_key=identity_key,
                version=new_version,
            )
        else:
            persona_id = db.create_persona(
                name=participant_id,
                scope=request.scope_id,
                persona_json=persona_payload,
                last_summary=summary,
                identity_key=identity_key,
            )
        
        _write_persona_context(request.scope_id, participant_id, persona_payload, summary, identity_key)
        save_persona_snapshot(persona_id, persona_payload, fragments)
        
        extracted.append({
            "participant_id": participant_id,
            "persona_id": persona_id,
            "interview_count": len(participant_interviews),
        })
    
    if no_participant:
        for interview in no_participant:
            skipped.append({
                "interview_id": interview["id"],
                "reason": "no_participant_id",
            })
    
    return ExtractAllPersonasResponse(extracted=extracted, skipped=skipped)


@app.put("/api/personas/{persona_id}", response_model=PersonaResponse)
async def update_persona(persona_id: int, request: UpdatePersonaRequest):
    existing = db.get_persona(persona_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Persona not found")

    if request.mode == "augment":
        next_payload = merge_persona_payloads(existing.get("persona_json") or {}, request.persona_json)
    else:
        next_payload = PersonaPayload.model_validate(request.persona_json).model_dump()

    next_name = request.name or existing["name"]
    next_summary = build_persona_summary(PersonaPayload.model_validate(next_payload))
    identity_key = existing.get("identity_key")
    db.update_persona(persona_id, persona_json=next_payload, last_summary=next_summary, name=next_name, identity_key=identity_key)
    _write_persona_context(existing["scope"], next_name, next_payload, next_summary, identity_key)
    save_persona_snapshot(persona_id, next_payload, [])

    consolidated = _consolidate_persona_duplicates(existing["scope"], next_name, identity_key or f"name:{_canonical_identity(existing['scope'])}:{_canonical_identity(next_name)}", persona_id)
    persona_id = int(consolidated["id"]) if consolidated else persona_id

    updated = db.get_persona(persona_id)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to load updated persona")
    return _persona_row_to_response(updated)



@app.post("/api/personas/bootstrap", response_model=PersonaBootstrapResponse)
async def bootstrap_persona(request: PersonaBootstrapRequest):
    scope_id = (request.scope_id or "default").strip() or "default"
    display_name = (request.display_name or "").strip() or "New User"

    base_payload = {
        "persona_id": _slugify(display_name),
        "scope_id": scope_id,
        "role": "unknown",
        "domain_expertise": {"biotech": "unknown", "stats": "unknown", "coding": "unknown"},
        "goals": [g.strip() for g in request.goals if isinstance(g, str) and g.strip()][:8],
        "constraints": {
            "time_sensitivity": "unknown",
            "compliance_posture": "unknown",
            "risk_tolerance": request.risk_tolerance or "unknown",
        },
        "preferences": {
            "output_format": request.output_format or "unknown",
            "citation_need": request.citation_need or "unknown",
            "verbosity": request.verbosity or "unknown",
        },
        "decision_style": request.decision_style or "unknown",
        "trust_profile": {"default_reliance": "unknown", "verification_habits": []},
        "taboo_or_redlines": [],
        "key_quotes": [],
        "evidence": {"support": []},
    }

    note = (request.profile_note or "").strip()
    if note:
        try:
            prompt = (
                "You are building a cold-start user persona from a short onboarding note. "
                "Return strict JSON with key 'persona' that matches the required persona schema and stays conservative where unknown.\n\n"
                f"Scope: {scope_id}\nName: {display_name}\n"
                f"Onboarding note:\n{note}\n"
            )
            llm_resp = await ollama.generate_json(prompt, max_retries=1, temperature=0.1, top_p=0.9)
            incoming = llm_resp.get("persona") if isinstance(llm_resp, dict) else llm_resp
            if isinstance(incoming, dict):
                base_payload = merge_persona_payloads(base_payload, incoming)
        except Exception:
            pass

    validated = PersonaPayload.model_validate(base_payload)
    payload = validated.model_dump()
    summary = build_persona_summary(validated)

    identity_key = f"name:{_canonical_identity(scope_id)}:{_canonical_identity(display_name)}"
    versions = db.list_personas_by_scope_identity(scope_id, identity_key)
    if not versions:
        versions = db.list_personas_by_scope_name_normalized(scope_id, display_name)
    max_version = max((p.get("version", 1) for p in versions), default=0)
    new_version = max_version + 1

    persona_id = db.create_persona(
        name=display_name,
        scope=scope_id,
        persona_json=payload,
        last_summary=summary,
        identity_key=identity_key,
        version=new_version,
    )
    _write_persona_context(scope_id, display_name, payload, summary, identity_key)
    save_persona_snapshot(persona_id, payload, [])

    seeded_events = 0
    for q in request.seed_queries[:10]:
        qn = (q or "").strip()
        if not qn:
            continue
        await log_event_safe("query_submitted", {"query": qn, "persona_id": persona_id, "cold_start_seed": True})
        seeded_events += 1

    for fb in request.seed_feedback[:10]:
        fn = (fb or "").strip()
        if not fn:
            continue
        db.create_feedback(
            persona_id=persona_id,
            objective_id=None,
            query=None,
            response_text=None,
            rating=3,
            feedback_text=fn,
            metadata={"source": "cold_start_bootstrap"},
        )
        await log_event_safe("explicit_feedback", {
            "persona_id": persona_id,
            "rating": 3,
            "feedback_text": fn,
            "metadata": {"source": "cold_start_bootstrap"},
        })
        seeded_events += 1

    return PersonaBootstrapResponse(persona_id=persona_id, name=display_name, version=new_version, seeded_events=seeded_events)

@app.get("/api/personas/templates", response_model=PersonaTemplateListResponse)
async def list_persona_starter_templates():
    templates = [PersonaTemplateSummary(**t) for t in list_persona_templates()]
    return PersonaTemplateListResponse(templates=templates)


@app.post("/api/personas/from-template", response_model=CreatePersonaFromTemplateResponse)
async def create_persona_from_template(request: CreatePersonaFromTemplateRequest):
    scope_id = (request.scope_id or "default").strip() or "default"
    template = get_persona_template(request.template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    display_name = (request.custom_name or "").strip() or str(template.get("name") or "Starter Persona")
    identity_key = f"template:{request.template_id}:{_canonical_identity(scope_id)}:{_canonical_identity(display_name)}"

    existing = db.get_persona_by_scope_identity(scope_id, identity_key)
    if existing:
        return CreatePersonaFromTemplateResponse(
            persona_id=int(existing["id"]),
            name=existing["name"],
            version=int(existing.get("version") or 1),
            created=False,
        )

    base_payload = dict(template.get("payload") or {})
    base_payload["persona_id"] = _slugify(display_name)
    base_payload["scope_id"] = scope_id

    validated = PersonaPayload.model_validate(base_payload)
    payload = validated.model_dump()
    summary = build_persona_summary(validated)

    versions = db.list_personas_by_scope_identity(scope_id, identity_key)
    max_version = max((p.get("version", 1) for p in versions), default=0)
    new_version = max_version + 1

    persona_id = db.create_persona(
        name=display_name,
        scope=scope_id,
        persona_json=payload,
        last_summary=summary,
        identity_key=identity_key,
        version=new_version,
    )

    _write_persona_context(scope_id, display_name, payload, summary, identity_key)
    save_persona_snapshot(persona_id, payload, [])

    await log_event_safe(
        "persona_template_selected",
        {
            "persona_id": persona_id,
            "template_id": request.template_id,
            "scope_id": scope_id,
        },
    )

    for q in (template.get("seed_queries") or [])[:5]:
        qn = str(q or "").strip()
        if not qn:
            continue
        await log_event_safe("query_submitted", {"query": qn, "persona_id": persona_id, "template_seed": True})

    return CreatePersonaFromTemplateResponse(
        persona_id=persona_id,
        name=display_name,
        version=new_version,
        created=True,
    )

@app.post("/api/personas/reset-to-starters", response_model=ResetPersonasResponse)
async def reset_personas_to_starters(request: ResetPersonasRequest):
    scope_id = (request.scope_id or "default").strip() or "default"
    seeded = _seed_starter_personas(scope_id, reset=True)
    return ResetPersonasResponse(
        scope_id=scope_id,
        removed_count=int(seeded.get("removed_count") or 0),
        created_persona_ids=[int(x) for x in (seeded.get("created_ids") or [])],
    )


@app.post("/api/personas/import-markdown", response_model=ImportPersonaMarkdownResponse)
async def import_persona_markdown(request: ImportPersonaMarkdownRequest):
    scope_id = (request.scope_id or "default").strip() or "default"
    markdown = (request.markdown or "").strip()
    if not markdown:
        raise HTTPException(status_code=400, detail="markdown content is required")

    inferred_name = _extract_markdown_title(markdown) or "Custom Persona"
    name = (request.name or "").strip() or inferred_name

    base_payload = {
        "persona_id": _slugify(name),
        "scope_id": scope_id,
        "role": "unknown",
        "domain_expertise": {"biotech": "unknown", "stats": "unknown", "coding": "unknown"},
        "goals": [],
        "constraints": {"time_sensitivity": "unknown", "compliance_posture": "unknown", "risk_tolerance": "unknown"},
        "preferences": {"output_format": "unknown", "citation_need": "unknown", "verbosity": "unknown"},
        "decision_style": "unknown",
        "trust_profile": {"default_reliance": "unknown", "verification_habits": []},
        "taboo_or_redlines": [],
        "key_quotes": [],
        "evidence": {"support": []},
    }

    try:
        prompt = (
            "Extract a user persona from this markdown note. "
            "Return strict JSON with key 'persona' matching the schema. "
            "If unknown, keep conservative 'unknown' values.\n\n"
            f"Scope: {scope_id}\n"
            f"Name: {name}\n"
            f"Markdown:\n{markdown}\n"
        )
        llm_resp = await ollama.generate_json(prompt, max_retries=1, temperature=0.1, top_p=0.9)
        incoming = llm_resp.get("persona") if isinstance(llm_resp, dict) else llm_resp
        if isinstance(incoming, dict):
            base_payload = merge_persona_payloads(base_payload, incoming)
    except Exception:
        pass

    validated = PersonaPayload.model_validate(base_payload)
    payload = validated.model_dump()
    summary = build_persona_summary(validated)

    identity_key = f"custom:{_canonical_identity(scope_id)}:{_canonical_identity(name)}"
    existing = db.get_persona_by_scope_identity(scope_id, identity_key)
    if existing:
        db.update_persona(int(existing["id"]), persona_json=payload, last_summary=summary, name=name, identity_key=identity_key)
        updated = db.get_persona(int(existing["id"]))
        if not updated:
            raise HTTPException(status_code=500, detail="Failed to update persona")
        _write_persona_context(scope_id, name, payload, summary, identity_key)
        save_persona_snapshot(int(updated["id"]), payload, [])
        return ImportPersonaMarkdownResponse(
            persona_id=int(updated["id"]),
            name=str(updated["name"]),
            version=int(updated.get("version") or 1),
            created=False,
        )

    persona_id = db.create_persona(
        name=name,
        scope=scope_id,
        persona_json=payload,
        last_summary=summary,
        identity_key=identity_key,
        version=1,
    )
    _write_persona_context(scope_id, name, payload, summary, identity_key)
    save_persona_snapshot(persona_id, payload, [])

    return ImportPersonaMarkdownResponse(persona_id=persona_id, name=name, version=1, created=True)

@app.get("/api/personas/{persona_id}", response_model=PersonaResponse)
async def get_persona(persona_id: int):
    row = db.get_persona(persona_id)
    if not row:
        raise HTTPException(status_code=404, detail="Persona not found")
    return _persona_row_to_response(row)


@app.get("/api/personas", response_model=PersonaListResponse)
async def list_personas(scope_id: Optional[str] = Query(default=None), project_id: Optional[int] = Query(default=None)):
    rows = db.list_personas(scope=scope_id, project_id=project_id)
    return PersonaListResponse(personas=[_persona_row_to_response(r) for r in rows])



@app.get("/api/personas/{persona_id}/display-name")
async def get_persona_display_name(persona_id: int, refresh: bool = Query(default=False)):
    persona = db.get_persona(persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    if not refresh and persona_id in _persona_display_name_cache:
        cached = _persona_display_name_cache[persona_id]
        return {"persona_id": persona_id, **cached, "source": "cache"}

    naming = await _persona_name_with_llm(persona)
    source = "llm" if naming.get("display_name") and naming.get("display_name") != _persona_name_fallback(persona) else "fallback"
    _persona_display_name_cache[persona_id] = naming
    return {"persona_id": persona_id, **naming, "source": source}


@app.get("/api/personas/display-names")
async def get_persona_display_names(scope_id: Optional[str] = Query(default=None), refresh: bool = Query(default=False)):
    personas = db.list_personas(scope=scope_id)
    result: Dict[int, Dict[str, str]] = {}
    for row in personas:
        pid = int(row["id"])
        if not refresh and pid in _persona_display_name_cache:
            result[pid] = {**_persona_display_name_cache[pid], "source": "cache"}
            continue
        naming = await _persona_name_with_llm(row)
        _persona_display_name_cache[pid] = naming
        source = "llm" if naming.get("display_name") and naming.get("display_name") != _persona_name_fallback(row) else "fallback"
        result[pid] = {**naming, "source": source}

    return {"display_names": result}


@app.get("/api/persona-display-names")
async def get_persona_display_names_alias(scope_id: Optional[str] = Query(default=None), refresh: bool = Query(default=False)):
    return await get_persona_display_names(scope_id=scope_id, refresh=refresh)

@app.post("/api/reports/{report_id}/generate-skeleton")
async def generate_report_skeleton(report_id: int, persona_id: Optional[int] = None, objective_id: Optional[str] = None):
    row = db.get_report(report_id)
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")

    persona_block = _persona_header(persona_id).strip()
    prompt = _assemble_prompt(
        system_instruction="Generate Quarto Markdown only. No explanations. Keep deterministic and concise.",
        persona_id=persona_id,
        task_context=(
            "Create a starter QMD with sections: assumptions, evidence table, analysis, decision. "
            "Include YAML params objective_id, persona_id, dataset_refs and one Python chunk that loads dataset refs. "
            f"objective_id={objective_id or row.get('objective_id')}."
        ),
    )
    generated = await ollama.generate(prompt, temperature=0.2)
    qmd = generated.strip()
    if qmd.startswith("```"):
        qmd = qmd.split("\n", 1)[1]
        if qmd.endswith("```"):
            qmd = qmd[:-3]

    if "---" not in qmd[:20]:
        qmd = default_qmd_skeleton(row["title"]) + "\n\n" + qmd
    if persona_block and "persona_id" not in qmd:
        qmd = qmd.replace("dataset_refs", "persona_id: null\n  dataset_refs", 1)

    write_qmd(report_id, qmd)
    db.update_report_qmd(report_id, compute_content_hash(qmd))
    return {"report_id": report_id, "updated": True}

async def log_event_safe(event_type: str, payload: dict):
    """Safely log an event without failing the main operation."""
    try:
        db.log_event(LogEventRequest(event_type=event_type, payload=payload))
    except Exception:
        # Don't let logging failures break the main functionality
        pass


@app.on_event("startup")
async def _start_background_persona_refactor():
    global _persona_refactor_task

    try:
        db.mark_incomplete_execution_runs_failed("Server restarted before the execution run finished.")
    except Exception:
        pass

    # Ensure starter personas exist for biotech use-case when instance is clean.
    try:
        _seed_starter_personas("default", reset=False)
    except Exception:
        pass

    interval = int(os.getenv("PERSONA_REFACTOR_INTERVAL_SEC", "0"))
    if interval <= 0:
        return
    _persona_refactor_task = asyncio.create_task(_persona_refactor_loop(interval))


@app.on_event("shutdown")
async def _stop_background_persona_refactor():
    global _persona_refactor_task
    for task in list(_project_execution_tasks.values()):
        task.cancel()
    _project_execution_tasks.clear()
    if _persona_refactor_task is None:
        return
    _persona_refactor_task.cancel()
    try:
        await _persona_refactor_task
    except Exception:
        pass
    _persona_refactor_task = None

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
