from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from typing import Optional
import os
from pathlib import Path

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
    PersonaFromInterviewsRequest, PersonaFromInterviewsResponse,
    PersonaResponse, PersonaListResponse
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
from persona_extractor import extract_persona_from_interviews, save_persona_snapshot
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
        source=row["source"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        version=row["version"],
        last_summary=row["last_summary"],
        persona_json=row["persona_json"],
    )

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
    interview_id = db.create_interview(
        scope=request.scope,
        transcript_text=request.transcript_text,
        transcript_path=request.transcript_path,
        metadata_json=request.metadata_json,
    )
    return CreateInterviewResponse(interview_id=interview_id)


@app.post("/api/personas/from-interviews", response_model=PersonaFromInterviewsResponse)
async def create_or_update_persona_from_interviews(request: PersonaFromInterviewsRequest):
    interviews = db.get_interviews(request.scope_id, request.interview_ids)
    if not interviews:
        raise HTTPException(status_code=404, detail="No interviews found for scope")

    try:
        persona_payload, summary, fragments = await extract_persona_from_interviews(
            scope_id=request.scope_id,
            persona_name=request.persona_name,
            interviews=interviews,
        )
    except Exception as ex:
        raise HTTPException(status_code=400, detail=f"Persona extraction failed: {ex}") from ex

    if request.mode == "update":
        if not request.persona_id:
            raise HTTPException(status_code=400, detail="persona_id is required for update mode")
        existing = db.get_persona(request.persona_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Persona not found")
        db.update_persona(request.persona_id, persona_json=persona_payload, last_summary=summary, name=request.persona_name)
        save_persona_snapshot(request.persona_id, persona_payload, fragments)
        return PersonaFromInterviewsResponse(persona_id=request.persona_id)

    persona_id = db.create_persona(
        name=request.persona_name,
        scope=request.scope_id,
        persona_json=persona_payload,
        last_summary=summary,
    )
    save_persona_snapshot(persona_id, persona_payload, fragments)
    return PersonaFromInterviewsResponse(persona_id=persona_id)


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
