from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class ObjectivesRequest(BaseModel):
    query: str
    context: Optional[str] = None
    k: int = 5

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

class FinalizeResponse(BaseModel):
    final_answer: str
    assumptions: List[str]
    next_questions: List[str]

class LogEventRequest(BaseModel):
    event_type: str
    payload: Dict[str, Any]