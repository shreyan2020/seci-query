from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from typing import Optional, List, Dict, Any
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
    GeneratePlanRequest, GeneratePlanResponse, AgenticPlan,
    InferWorkspaceMemoryRequest, InferWorkspaceMemoryResponse,
    UpdatePersonaRequest,
    TacitMemoryItem, WorkspaceMemory, WorkspaceMemoryRequest, WorkspaceMemoryResponse,
    PersonaResponse, PersonaListResponse,
    PersonaPayload,
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

app = FastAPI(title="SECI Query Explorer API", version="1.0.0")

ensure_context_root()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
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
        identity_key=row.get("identity_key"),
        source=row["source"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        version=row["version"],
        last_summary=row["last_summary"],
        persona_json=row["persona_json"],
    )


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

@app.post("/objectives", response_model=ObjectivesResponse)
async def generate_objectives(request: ObjectivesRequest):
    """Generate objective clusters for an underspecified query."""
    try:
        # Check for existing prior
        query_sig = db.query_signature(request.query)
        prior = db.get_prior(query_sig)
        
        # Generate prompt and get response
        prompt = _assemble_prompt(
            system_instruction="Follow safety and formatting policy. Return strict JSON only.",
            persona_id=request.persona_id,
            task_context=ollama.get_objectives_prompt(request.query, request.context, request.k),
        )
        print(f"DEBUG: Generated prompt length: {len(prompt)} chars")
        
        response_data = await ollama.generate_json(prompt)
        print(f"DEBUG: Raw response type: {type(response_data)}")
        print(f"DEBUG: Response keys: {list(response_data.keys()) if response_data else 'None'}")
        
        # Convert to proper objects
        objectives = [Objective(**obj) for obj in response_data.get("objectives", [])]
        global_questions = response_data.get("global_questions", [])
        
        print(f"DEBUG: Parsed {len(objectives)} objectives and {len(global_questions)} global questions")
        
        # Log event
        await log_event_safe("objectives_generated", {
            "query": request.query,
            "has_context": bool(request.context),
            "num_objectives": len(objectives),
            "has_prior": prior is not None
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
        "selected_objective",
        "facet_answers",
        "evidence_items",
        "augmented_answer",
        "final_answer",
        "agentic_plan",
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
    answers = state.get("facet_answers") or {}
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
                inference="The user's facet answers should be treated as project constraints or preferences until revised.",
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


@app.get("/api/personas/{persona_id}", response_model=PersonaResponse)
async def get_persona(persona_id: int):
    row = db.get_persona(persona_id)
    if not row:
        raise HTTPException(status_code=404, detail="Persona not found")
    return _persona_row_to_response(row)


@app.get("/api/personas", response_model=PersonaListResponse)
async def list_personas(scope_id: Optional[str] = Query(default=None)):
    rows = db.list_personas(scope=scope_id)
    return PersonaListResponse(personas=[_persona_row_to_response(r) for r in rows])


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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
