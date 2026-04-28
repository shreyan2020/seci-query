from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal

class ObjectivesRequest(BaseModel):
    query: str
    context: Optional[str] = None
    k: int = 5
    persona_id: Optional[int] = None

class FacetQuestion(BaseModel):
    id: str
    text: str

class Objective(BaseModel):
    id: str
    title: str
    subtitle: str
    definition: str
    signals: List[str]
    facet_questions: List[str]
    exemplar_answer: str

class ObjectivesResponse(BaseModel):
    objectives: List[Objective]
    global_questions: List[str]

class AugmentRequest(BaseModel):
    query: str
    objective_id: str
    objective_definition: str
    context_blob: Optional[str] = None
    persona_id: Optional[int] = None

class EvidenceItem(BaseModel):
    id: str
    type: str
    title: str
    snippet: str
    source_ref: str
    score: float

class AugmentResponse(BaseModel):
    evidence_items: List[EvidenceItem]
    augmented_answer: Optional[str] = None

class FinalizeRequest(BaseModel):
    query: str
    objective: Objective
    answers: Dict[str, str]
    context_blob: Optional[str] = None
    evidence_items: Optional[List[EvidenceItem]] = None
    persona_id: Optional[int] = None

class FinalizeResponse(BaseModel):
    final_answer: str
    assumptions: List[str]
    next_questions: List[str]


class PlanStep(BaseModel):
    id: str
    title: str
    description: str
    why_this_step: str
    objective_link: str
    persona_link: str
    evidence_facts: List[str] = Field(default_factory=list)
    examples: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    expected_outcome: str
    confidence: float = 0.5


class PlanRisk(BaseModel):
    risk: str
    mitigation: str


class AgenticPlan(BaseModel):
    plan_title: str
    strategy_summary: str
    success_criteria: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    risks: List[PlanRisk] = Field(default_factory=list)
    steps: List[PlanStep] = Field(default_factory=list)


class GeneratePlanRequest(BaseModel):
    query: str
    objective: Objective
    persona_id: int
    facet_answers: Dict[str, str] = Field(default_factory=dict)
    context_blob: Optional[str] = None


class GeneratePlanResponse(BaseModel):
    plan: AgenticPlan


class TacitMemoryItem(BaseModel):
    id: str
    label: str
    inference: str
    evidence: List[str] = Field(default_factory=list)
    confidence: float = 0.5
    status: Literal["inferred", "confirmed", "rejected", "edited"] = "inferred"
    reviewer_note: Optional[str] = None


class WorkspaceMemory(BaseModel):
    workspace_key: str
    scope: str = "default"
    explicit_state: Dict[str, Any] = Field(default_factory=dict)
    tacit_state: List[TacitMemoryItem] = Field(default_factory=list)
    handoff_summary: str = ""
    updated_at: Optional[str] = None


class WorkspaceMemoryRequest(BaseModel):
    scope: str = "default"
    explicit_state: Dict[str, Any] = Field(default_factory=dict)
    tacit_state: List[TacitMemoryItem] = Field(default_factory=list)
    handoff_summary: str = ""


class WorkspaceMemoryResponse(BaseModel):
    memory: Optional[WorkspaceMemory] = None


class InferWorkspaceMemoryRequest(BaseModel):
    workspace_key: str
    scope: str = "default"
    explicit_state: Dict[str, Any] = Field(default_factory=dict)
    existing_tacit_state: List[TacitMemoryItem] = Field(default_factory=list)


class InferWorkspaceMemoryResponse(BaseModel):
    tacit_state: List[TacitMemoryItem] = Field(default_factory=list)
    handoff_summary: str = ""


class FeedbackRequest(BaseModel):
    persona_id: Optional[int] = None
    objective_id: Optional[str] = None
    query: Optional[str] = None
    response_text: Optional[str] = None
    rating: int = Field(ge=1, le=5)
    feedback_text: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FeedbackResponse(BaseModel):
    status: str


class PersonaRefactorItem(BaseModel):
    source_persona_id: int
    new_persona_id: int
    events_used: int
    version: int


class PersonaRefactorResponse(BaseModel):
    updated: List[PersonaRefactorItem]
    skipped: List[Dict[str, Any]] = Field(default_factory=list)

class LogEventRequest(BaseModel):
    event_type: str
    payload: Dict[str, Any]


class ContextListEntry(BaseModel):
    name: str
    path: str
    type: str
    size: int
    modified_at: str


class ContextListResponse(BaseModel):
    entries: List[ContextListEntry]


class ContextReadResponse(BaseModel):
    path: str
    content: str
    offset: int
    limit: int
    total_lines: int
    truncated: bool


class ContextWriteRequest(BaseModel):
    path: str
    content: str
    overwrite: bool = False


class ContextWriteResponse(BaseModel):
    path: str
    bytes_written: int


class ContextSearchRequest(BaseModel):
    query: str
    mode: str = "hybrid"  # hybrid | keyword | semantic
    collection: Optional[str] = None
    max_results: int = 10


class ContextSearchMatch(BaseModel):
    path: str
    line: int
    snippet: str
    score: Optional[float] = None
    doc_id: Optional[str] = None


class ContextSearchResponse(BaseModel):
    matches: List[ContextSearchMatch]


class ContextGetRequest(BaseModel):
    path_or_docid: str  # path like "socialization/notes.md" or docid like "#abc123"
    full: bool = True


class ContextGetResponse(BaseModel):
    path: str
    content: str
    doc_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ContextMultiGetRequest(BaseModel):
    pattern: str  # glob pattern like "socialization/*.md"
    full: bool = True


class ContextMultiGetResponse(BaseModel):
    documents: List[ContextGetResponse]


class ContextCollectionInfo(BaseModel):
    name: str
    path: str
    document_count: int


class ContextCollectionsResponse(BaseModel):
    collections: List[ContextCollectionInfo]


class ContextSyncResponse(BaseModel):
    success: bool
    collections_updated: int
    documents_indexed: int
    message: str


class QmdHealthResponse(BaseModel):
    healthy: bool
    version: Optional[str] = None
    collections_count: Optional[int] = None
    collections: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None


class ReportStatus(str):
    pass


class CreateReportRequest(BaseModel):
    title: str
    objective_id: Optional[str] = None
    initial_qmd: Optional[str] = None


class CreateReportResponse(BaseModel):
    report_id: int
    qmd_url: str


class ReportMetadataResponse(BaseModel):
    id: int
    title: str
    objective_id: Optional[str] = None
    persona_id: Optional[int] = None
    status: Literal["draft", "queued", "running", "success", "failed"]
    qmd_path: str
    last_output_html_path: Optional[str] = None
    last_output_pdf_path: Optional[str] = None
    last_render_at: Optional[str] = None
    last_manifest_path: Optional[str] = None
    last_log_path: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    updated_at: str


class UpdateReportQmdRequest(BaseModel):
    qmd: str


class RenderReportRequest(BaseModel):
    params: Dict[str, Any] = Field(default_factory=dict)
    formats: List[Literal["html", "pdf"]] = Field(default_factory=lambda: ["html"])
    cache_ok: bool = True
    persona_id: Optional[int] = None


class RenderReportResponse(BaseModel):
    report_id: int
    job_id: Optional[int] = None
    status: Literal["queued", "running", "success", "failed"]
    cache_hit: bool = False


class ReportLogsResponse(BaseModel):
    report_id: int
    log_path: Optional[str] = None
    content: str


class CreateInterviewRequest(BaseModel):
    scope: str
    transcript_text: Optional[str] = None
    transcript_path: Optional[str] = None
    metadata_json: Dict[str, Any] = Field(default_factory=dict)


class CreateInterviewResponse(BaseModel):
    interview_id: int


class ImportInterviewTextsRequest(BaseModel):
    scope: str
    folder: Optional[str] = None
    recursive: bool = True


class ImportInterviewTextsResponse(BaseModel):
    imported_count: int
    imported_files: List[str]
    skipped_count: int = 0
    skipped_files: List[str] = Field(default_factory=list)


class InterviewResponse(BaseModel):
    id: int
    scope: str
    transcript_path: Optional[str] = None
    transcript_text: Optional[str] = None
    created_at: str
    metadata_json: Dict[str, Any] = Field(default_factory=dict)


class InterviewListResponse(BaseModel):
    interviews: List[InterviewResponse]


class EvidenceReference(BaseModel):
    claim: str
    interview_id: int
    span_hint: Optional[str] = None


class KeyQuote(BaseModel):
    quote: str
    interview_id: int


class DomainExpertise(BaseModel):
    biotech: Optional[Literal["novice", "intermediate", "expert", "unknown"]] = "unknown"
    stats: Optional[Literal["novice", "intermediate", "expert", "unknown"]] = "unknown"
    coding: Optional[Literal["novice", "intermediate", "expert", "unknown"]] = "unknown"


class PersonaConstraints(BaseModel):
    time_sensitivity: Optional[Literal["low", "medium", "high", "unknown"]] = "unknown"
    compliance_posture: Optional[Literal["strict", "moderate", "flexible", "unknown"]] = "unknown"
    risk_tolerance: Optional[Literal["low", "medium", "high", "unknown"]] = "unknown"


class PersonaPreferences(BaseModel):
    output_format: Optional[Literal["steps", "table", "narrative", "mixed", "unknown"]] = "unknown"
    citation_need: Optional[Literal["low", "medium", "high", "unknown"]] = "unknown"
    verbosity: Optional[Literal["low", "medium", "high", "unknown"]] = "unknown"


class PersonaTrustProfile(BaseModel):
    default_reliance: Optional[Literal["low", "medium", "high", "unknown"]] = "unknown"
    verification_habits: List[str] = Field(default_factory=list)


class PersonaPayload(BaseModel):
    persona_id: str
    scope_id: str
    role: Optional[str] = "unknown"
    domain_expertise: DomainExpertise
    goals: List[str] = Field(default_factory=list)
    constraints: PersonaConstraints
    preferences: PersonaPreferences
    decision_style: Optional[Literal["exploratory", "confirmatory", "production", "unknown"]] = "unknown"
    trust_profile: PersonaTrustProfile
    taboo_or_redlines: List[str] = Field(default_factory=list)
    key_quotes: List[KeyQuote] = Field(default_factory=list, max_length=5)
    evidence: Dict[str, List[EvidenceReference]]
    workflow_stage: Optional[str] = "general"
    workflow_focus: List[str] = Field(default_factory=list)
    project_context: Dict[str, Any] = Field(default_factory=dict)


class PersonaFromInterviewsRequest(BaseModel):
    scope_id: str
    interview_ids: Optional[List[int]] = None
    persona_name: Optional[str] = None
    mode: Literal["create", "update"] = "create"
    persona_id: Optional[int] = None


class PersonaFromInterviewsResponse(BaseModel):
    persona_id: int


class ExtractAllPersonasRequest(BaseModel):
    scope_id: str
    extract_new_only: bool = True


class ExtractAllPersonasResponse(BaseModel):
    extracted: List[Dict[str, Any]]
    skipped: List[Dict[str, Any]]


class UpdatePersonaRequest(BaseModel):
    name: Optional[str] = None
    persona_json: Dict[str, Any]
    mode: Literal["augment", "replace"] = "augment"


class PersonaResponse(BaseModel):
    id: int
    name: str
    scope: str
    project_id: Optional[int] = None
    identity_key: Optional[str] = None
    source: str
    created_at: str
    updated_at: str
    version: int
    last_summary: str
    persona_json: Dict[str, Any]


class PersonaListResponse(BaseModel):
    personas: List[PersonaResponse]

class PersonaChangeLogItem(BaseModel):
    source_persona_id: int
    new_persona_id: int
    created_at: str
    changes: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    supporting_events: Dict[str, int] = Field(default_factory=dict)


class PersonaChangeLogResponse(BaseModel):
    persona_id: int
    items: List[PersonaChangeLogItem] = Field(default_factory=list)

class PersonaBootstrapRequest(BaseModel):
    scope_id: str = "default"
    display_name: Optional[str] = None
    profile_note: Optional[str] = None
    goals: List[str] = Field(default_factory=list)
    output_format: Optional[Literal["steps", "table", "narrative", "mixed", "unknown"]] = "unknown"
    citation_need: Optional[Literal["low", "medium", "high", "unknown"]] = "unknown"
    verbosity: Optional[Literal["low", "medium", "high", "unknown"]] = "unknown"
    risk_tolerance: Optional[Literal["low", "medium", "high", "unknown"]] = "unknown"
    decision_style: Optional[Literal["exploratory", "confirmatory", "production", "unknown"]] = "unknown"
    seed_queries: List[str] = Field(default_factory=list)
    seed_feedback: List[str] = Field(default_factory=list)


class PersonaBootstrapResponse(BaseModel):
    persona_id: int
    name: str
    version: int
    seeded_events: int = 0

class PersonaTemplateSummary(BaseModel):
    template_id: str
    name: str
    tagline: str
    description: str
    starter_goals: List[str] = Field(default_factory=list)


class PersonaTemplateListResponse(BaseModel):
    templates: List[PersonaTemplateSummary] = Field(default_factory=list)


class CreatePersonaFromTemplateRequest(BaseModel):
    scope_id: str = "default"
    template_id: str
    custom_name: Optional[str] = None


class CreatePersonaFromTemplateResponse(BaseModel):
    persona_id: int
    name: str
    version: int
    created: bool = True

class ResetPersonasRequest(BaseModel):
    scope_id: str = "default"


class ResetPersonasResponse(BaseModel):
    scope_id: str
    removed_count: int = 0
    created_persona_ids: List[int] = Field(default_factory=list)


class ImportPersonaMarkdownRequest(BaseModel):
    scope_id: str = "default"
    name: Optional[str] = None
    markdown: str


class ImportPersonaMarkdownResponse(BaseModel):
    persona_id: int
    name: str
    version: int
    created: bool = True


class ProjectWorkflowPersona(BaseModel):
    persona_id: int
    name: str
    role: str
    workflow_stage: str
    focus_area: str
    summary: str
    goals: List[str] = Field(default_factory=list)
    workflow_focus: List[str] = Field(default_factory=list)
    starter_questions: List[str] = Field(default_factory=list)
    version: int = 1


class CreateProjectRequest(BaseModel):
    name: str
    end_product: str
    target_host: Optional[str] = "Saccharomyces cerevisiae"
    project_goal: Optional[str] = None
    raw_material_focus: Optional[str] = None
    notes: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    scope_id: str
    end_product: str
    target_host: str
    project_goal: str
    raw_material_focus: Optional[str] = None
    notes: Optional[str] = None
    status: Literal["draft", "active", "archived"]
    created_at: str
    updated_at: str
    personas: List[ProjectWorkflowPersona] = Field(default_factory=list)


class ProjectListResponse(BaseModel):
    projects: List[ProjectResponse] = Field(default_factory=list)


class CreateProjectResponse(BaseModel):
    project: ProjectResponse
    created_persona_ids: List[int] = Field(default_factory=list)


class ResearchFinding(BaseModel):
    id: str
    citation: str = ""
    labels: List[str] = Field(default_factory=list)
    knowns: List[str] = Field(default_factory=list)
    unknowns: List[str] = Field(default_factory=list)
    relevance: str = ""


class ResearchGap(BaseModel):
    id: str
    theme: str = ""
    supporting_signals: List[str] = Field(default_factory=list)
    next_question: str = ""
    priority_note: str = ""


class JudgmentCall(BaseModel):
    id: str
    stance: str = ""
    rationale: str = ""
    implication: str = ""


class ValidationTrack(BaseModel):
    id: str
    target: str = ""
    method: str = ""
    questions: List[str] = Field(default_factory=list)
    success_signal: str = ""


class ProposalCandidate(BaseModel):
    id: str
    title: str = ""
    why_now: str = ""
    experiment_outline: str = ""
    readouts: List[str] = Field(default_factory=list)


class ResearchWorkTemplate(BaseModel):
    initial_query: str = ""
    literature_findings: List[ResearchFinding] = Field(default_factory=list)
    common_gaps: List[ResearchGap] = Field(default_factory=list)
    judgment_calls: List[JudgmentCall] = Field(default_factory=list)
    validation_tracks: List[ValidationTrack] = Field(default_factory=list)
    proposal_candidates: List[ProposalCandidate] = Field(default_factory=list)
    synthesis_memo: str = ""


class FetchProjectLiteratureRequest(BaseModel):
    persona_id: int
    query: str
    objective_id: Optional[str] = None
    objective_title: Optional[str] = None
    objective_definition: Optional[str] = None
    objective_signals: List[str] = Field(default_factory=list)
    project_goal: Optional[str] = None
    project_end_product: Optional[str] = None
    project_target_host: Optional[str] = None
    clarifying_answers: Dict[str, str] = Field(default_factory=dict)
    objective_answers: Dict[str, str] = Field(default_factory=dict)
    global_question_answers: Dict[str, str] = Field(default_factory=dict)
    reasoning_notes: Optional[str] = None
    work_template: Optional[ResearchWorkTemplate] = None
    max_results: int = 5
    existing_citations: List[str] = Field(default_factory=list)


class LiteratureToolTrace(BaseModel):
    tool_name: str
    query: str
    result_count: int
    status: Literal["success", "error"] = "success"
    error_message: Optional[str] = None


class FetchProjectLiteratureResponse(BaseModel):
    findings: List[ResearchFinding] = Field(default_factory=list)
    tool_trace: LiteratureToolTrace
    objective_lens: Optional[str] = None
    processing_summary: str = ""
    elicitation_questions: List[str] = Field(default_factory=list)


class GenerateProjectPlanRequest(BaseModel):
    persona_id: int
    focus_question: Optional[str] = None
    notes: Optional[str] = None
    clarifying_answers: Dict[str, str] = Field(default_factory=dict)
    reasoning_notes: Optional[str] = None
    work_template: Optional[ResearchWorkTemplate] = None


class ProjectWorkspaceState(BaseModel):
    project_id: int
    persona_id: int
    focus_question: Optional[str] = None
    clarifying_answers: Dict[str, str] = Field(default_factory=dict)
    reasoning_notes: Optional[str] = None
    work_template: Optional[ResearchWorkTemplate] = None
    plan: Optional[AgenticPlan] = None
    selected_step_id: Optional[str] = None
    updated_at: Optional[str] = None


class ProjectWorkspaceRequest(BaseModel):
    focus_question: Optional[str] = None
    clarifying_answers: Dict[str, str] = Field(default_factory=dict)
    reasoning_notes: Optional[str] = None
    work_template: Optional[ResearchWorkTemplate] = None
    plan: Optional[AgenticPlan] = None
    selected_step_id: Optional[str] = None


class ProjectWorkspaceResponse(BaseModel):
    state: Optional[ProjectWorkspaceState] = None


class StartProjectExecutionRequest(BaseModel):
    persona_id: int
    focus_question: Optional[str] = None
    notes: Optional[str] = None
    clarifying_answers: Dict[str, str] = Field(default_factory=dict)
    reasoning_notes: Optional[str] = None
    work_template: Optional[ResearchWorkTemplate] = None
    objective_id: Optional[str] = None
    objective_title: Optional[str] = None
    objective_definition: Optional[str] = None
    objective_signals: List[str] = Field(default_factory=list)


class ProjectExecutionEvent(BaseModel):
    id: int
    run_id: int
    event_type: str
    stage_key: Optional[str] = None
    title: str = ""
    detail: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: str


class ProjectExecutionRun(BaseModel):
    id: int
    project_id: int
    persona_id: int
    run_kind: str = "agentic_execution"
    status: Literal["queued", "running", "completed", "failed"] = "queued"
    objective_id: Optional[str] = None
    mode_label: Optional[str] = None
    focus_question: Optional[str] = None
    current_stage: Optional[str] = None
    summary: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    final_work_template: Optional[ResearchWorkTemplate] = None
    final_plan: Optional[AgenticPlan] = None


class ProjectExecutionRunResponse(BaseModel):
    run: Optional[ProjectExecutionRun] = None
    events: List[ProjectExecutionEvent] = Field(default_factory=list)
