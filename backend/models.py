from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

# ============================================================================
# VERSIONING
# ============================================================================

CURRENT_SCHEMA_VERSION = "2.0.0"

# ============================================================================
# ENUMS
# ============================================================================

class QueryType(str, Enum):
    """Query type taxonomy for routing."""
    AMBIGUITY_PREFERENCE = "ambiguity_preference"
    FACTUAL_LOOKUP = "factual_lookup"
    SYNTHESIS_SURVEY = "synthesis_survey"
    PLANNING_PROTOCOL = "planning_protocol"
    TROUBLESHOOTING = "troubleshooting"
    OPEN_IDEATION = "open_ideation"
    METHODOLOGY = "methodology"
    DYNAMIC = "dynamic"  # For AI-generated query types

class EvidenceType(str, Enum):
    """Types of evidence sources."""
    USER_CONTEXT = "user_context"
    PAPER = "paper"
    DATABASE = "database"
    DOCUMENTATION = "documentation"
    INTERNAL = "internal"
    INFERRED = "inferred"

class ConfidenceLevel(str, Enum):
    """Confidence levels for claims and objectives."""
    HIGH = "high"      # Strong evidence or consensus
    MEDIUM = "medium"  # Some evidence or reasoning
    LOW = "low"        # Limited evidence, speculative
    UNCERTAIN = "uncertain"  # Cannot determine

class SourceQuality(str, Enum):
    """Quality assessment of evidence sources."""
    PRIMARY = "primary"      # Original research/data
    REVIEW = "review"        # Systematic review/meta-analysis
    SECONDARY = "secondary"  # Review article/textbook
    PREPRINT = "preprint"    # Unreviewed preprint
    ANECDOTAL = "anecdotal"  # Case report/experience
    UNKNOWN = "unknown"      # Unverified source

# ============================================================================
# PROGRESSIVE DISCLOSURE MODELS
# ============================================================================

class ProgressiveDisclosure(BaseModel):
    """
    Progressive disclosure schema for cognitive load reduction.
    Always includes summary, optionally includes deeper details.
    """
    tldr: str = Field(
        default="",
        description="1-2 line summary for quick scanning",
        max_length=200
    )
    key_tradeoffs: List[str] = Field(
        default_factory=list,
        description="Max 3 key tradeoffs to consider",
        max_length=3
    )
    next_actions: List[str] = Field(
        default_factory=list,
        description="Max 3 recommended next steps",
        max_length=3
    )
    details: Optional[str] = Field(
        None,
        description="Detailed explanation (optional expansion)"
    )
    glossary: Optional[Dict[str, str]] = Field(
        None,
        description="Optional term definitions"
    )

class ActionItem(BaseModel):
    """A single actionable item with priority and rationale."""
    action: str
    priority: str = Field(..., pattern="^(high|medium|low)$")
    rationale: str
    estimated_effort: Optional[str] = None

# ============================================================================
# GROUNDING MODELS
# ============================================================================

class EvidenceItem(BaseModel):
    """
    Enhanced evidence item with provenance and quality.
    """
    id: str
    type: EvidenceType
    title: str
    snippet: str
    source_ref: str
    source_quality: SourceQuality = SourceQuality.UNKNOWN
    retrieval_method: str = "provided"  # How we got this: provided, searched, inferred
    score: float = Field(..., ge=0.0, le=1.0)
    citation_key: Optional[str] = None  # For formal citations
    retrieval_date: Optional[datetime] = None

class Claim(BaseModel):
    """
    A claim with explicit grounding information.
    """
    claim_text: str
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    confidence: ConfidenceLevel
    is_assumption: bool = False
    reasoning: Optional[str] = None  # Why we think this
    counter_evidence: Optional[str] = None  # If there's conflicting info

class GroundingReport(BaseModel):
    """
    Complete grounding report for a response.
    """
    claims: List[Claim]
    evidence_summary: str
    overall_confidence: ConfidenceLevel
    missing_evidence: List[str]  # What we'd need to be more confident
    assumptions_made: List[str]  # Explicit assumptions

# ============================================================================
# QUERY REFINEMENT MODELS
# ============================================================================

class QueryRefinement(BaseModel):
    """
    A suggested refinement to the original query.
    """
    refined_query: str
    what_changed: Optional[str] = None  # Brief description of changes
    why_it_helps: Optional[str] = None  # Why this helps
    expected_benefit: Optional[str] = None
    confidence: str = "medium"

class UncertaintyMarker(BaseModel):
    """
    Marks something the system is uncertain about.
    """
    aspect: str  # What we're uncertain about
    uncertainty_type: str = "unknown"
    clarification_questions: List[str]  # Questions to resolve uncertainty
    fallback_recommendation: Optional[str] = None  # What to do if unresolved

# ============================================================================
# ENHANCED OBJECTIVE MODELS
# ============================================================================

class EnhancedObjective(BaseModel):
    """
    Enhanced objective with uncertainty markers and grounding.
    """
    id: str
    title: str
    subtitle: str
    definition: str
    signals: List[str]
    facet_questions: List[str]
    
    # Optional exemplar (removed from required fields)
    exemplar_answer: Optional[str] = Field(
        None,
        description="Optional example of a good answer"
    )
    
    # New fields for better grounding and uncertainty
    when_this_objective_is_wrong: Optional[str] = Field(
        None,
        description="1-2 lines on when this objective doesn't apply"
    )
    minimum_info_needed: List[str] = Field(
        default_factory=list,
        description="Minimum info needed to evaluate this objective"
    )
    expected_output_format: Optional[str] = Field(
        None,
        description="What form the answer should take (list, protocol, etc.)"
    )
    confidence: str = "medium"  # Simplified to string
    is_speculative: bool = False  # Marked if we're unsure about relevance
    rationale: Optional[str] = Field(
        None,
        description="Why this objective was generated"
    )
    
    # Progressive disclosure
    summary: ProgressiveDisclosure

class RouterInfo(BaseModel):
    """
    Information from the query router.
    """
    query_type: QueryType
    confidence: float = Field(..., ge=0.0, le=1.0)
    missing_inputs: List[str]
    recommended_workflow: str
    context_hints: Dict[str, Any]

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ObjectivesRequest(BaseModel):
    """Request for objective generation."""
    query: str
    context: Optional[str] = None
    k: int = Field(default=5, ge=2, le=8)
    schema_version: str = CURRENT_SCHEMA_VERSION
    previous_context: Optional[str] = None  # For continuous interaction
    iteration: int = Field(default=0, ge=0)  # Track refinement iterations


class RefineRequest(BaseModel):
    """Request for refining/continuing the conversation."""
    original_query: str
    current_objective_id: Optional[str] = None  # If user selected an objective
    user_feedback: str  # User's feedback or new query specification
    previous_objectives: List[EnhancedObjective] = Field(default_factory=list)
    previous_answers: Dict[str, str] = Field(default_factory=dict)
    action: str = Field(default="refine", pattern="^(refine|continue|explore|restart)$")
    schema_version: str = CURRENT_SCHEMA_VERSION

class ObjectivesResponse(BaseModel):
    """Response with enhanced objectives and metadata."""
    schema_version: str = CURRENT_SCHEMA_VERSION
    objectives: List[EnhancedObjective]
    global_questions: List[str]
    router_info: RouterInfo
    query_refinements: List[QueryRefinement]  # Suggested improvements to query
    uncertainty_markers: List[UncertaintyMarker]  # What we're unsure about
    progressive_summary: ProgressiveDisclosure  # Overall summary
    
    # Timing and metadata
    processing_metadata: Dict[str, Any] = Field(default_factory=dict)

class AugmentRequest(BaseModel):
    """Request for evidence augmentation."""
    query: str
    objective_id: str
    objective_definition: str
    context_blob: Optional[str] = None
    schema_version: str = CURRENT_SCHEMA_VERSION

class AugmentResponse(BaseModel):
    """Response with evidence extraction and synthesis."""
    schema_version: str = CURRENT_SCHEMA_VERSION
    evidence_items: List[EvidenceItem]
    grounded_claims: List[Claim]  # Claims extracted from evidence
    augmented_answer: Optional[str] = None
    grounding_report: Optional[GroundingReport] = None
    extraction_confidence: str = "medium"  # ConfidenceLevel as string
    need_external_sources: bool = False  # Flag if we need more sources
    recommended_sources: List[str] = Field(default_factory=list)  # What to search

class FinalizeRequest(BaseModel):
    """Request for final answer synthesis."""
    query: str
    objective: EnhancedObjective
    answers: Dict[str, str]
    context_blob: Optional[str] = None
    evidence_items: Optional[List[EvidenceItem]] = None
    schema_version: str = CURRENT_SCHEMA_VERSION

class FinalizeResponse(BaseModel):
    """Response with grounded final answer."""
    schema_version: str = CURRENT_SCHEMA_VERSION
    final_answer: str
    progressive_disclosure: Optional[ProgressiveDisclosure] = None
    grounding_report: Optional[GroundingReport] = None
    assumptions: List[str]
    next_questions: List[str]
    action_items: List[ActionItem]  # Concrete next steps
    claims: List[Claim]  # All claims with evidence mapping
    
    # Decision support
    decision_framework: Optional[str] = None  # If applicable
    
    # Refinement suggestions
    follow_up_queries: List[QueryRefinement]

class LogEventRequest(BaseModel):
    """Request for logging events."""
    event_type: str
    payload: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    session_id: Optional[str] = None
    query_signature: Optional[str] = None

class HealthCheckResponse(BaseModel):
    """Health check response with system status."""
    status: str
    service: str
    version: str = CURRENT_SCHEMA_VERSION
    capabilities: List[str] = Field(default_factory=list)