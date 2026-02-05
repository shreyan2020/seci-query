from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Optional
import uuid

from models import (
    ObjectivesRequest, ObjectivesResponse, Objective,
    AugmentRequest, AugmentResponse, EvidenceItem,
    FinalizeRequest, FinalizeResponse, LogEventRequest
)
from ollama_client import ollama
from database import db

app = FastAPI(title="SECI Query Explorer API", version="1.0.0")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/objectives", response_model=ObjectivesResponse)
async def generate_objectives(request: ObjectivesRequest):
    """Generate objective clusters for an underspecified query."""
    try:
        # Check for existing prior
        query_sig = db.query_signature(request.query)
        prior = db.get_prior(query_sig)
        
        # Generate prompt and get response
        prompt = ollama.get_objectives_prompt(request.query, request.context, request.k)
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
        raise HTTPException(status_code=500, detail=f"Failed to generate objectives: {str(e)}")

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
        prompt = ollama.get_augment_prompt(
            request.query, 
            request.objective_id, 
            request.objective_definition, 
            request.context_blob
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
        raise HTTPException(status_code=500, detail=f"Failed to augment with context: {str(e)}")

@app.post("/finalize", response_model=FinalizeResponse)
async def finalize_answer(request: FinalizeRequest):
    """Generate final answer based on selected objective and user answers."""
    try:
        # Generate prompt and get response
        prompt = ollama.get_finalize_prompt(
            request.query,
            request.objective,
            request.answers,
            request.evidence_items
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
        raise HTTPException(status_code=500, detail=f"Failed to finalize answer: {str(e)}")

@app.post("/log_event")
async def log_event(request: LogEventRequest):
    """Log an event for internalization/prior building."""
    try:
        db.log_event(request)
        return {"status": "logged"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to log event: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "SECI Query Explorer API"}

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