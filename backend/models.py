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
    identity_key: Optional[str] = None
    source: str
    created_at: str
    updated_at: str
    version: int
    last_summary: str
    persona_json: Dict[str, Any]


class PersonaListResponse(BaseModel):
    personas: List[PersonaResponse]
