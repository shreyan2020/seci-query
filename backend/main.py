from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Optional, Any
import uuid
import time
import json
from datetime import datetime

from models import (
    ObjectivesRequest, ObjectivesResponse, EnhancedObjective,
    AugmentRequest, AugmentResponse, EvidenceItem,
    FinalizeRequest, FinalizeResponse, LogEventRequest,
    RouterInfo, QueryType, ProgressiveDisclosure, 
    QueryRefinement, UncertaintyMarker, HealthCheckResponse,
    RefineRequest
)
from ollama_client import ollama
from database import db
from query_router import router
from persona_manager import persona_manager
from dynamic_type_generator import dynamic_generator
from uncertainty_gate import uncertainty_gate, UncertaintyAssessment
from task_causal_graph import tcg_library
from voi_question_selector import info_controller

app = FastAPI(
    title="SECI Query Explorer API", 
    version="2.0.0",
    description="Enhanced query exploration with grounding and progressive disclosure"
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/objectives", response_model=ObjectivesResponse)
async def generate_objectives(
    request: ObjectivesRequest,
    x_user_id: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None)
):
    """
    Generate enhanced objective clusters with grounding and uncertainty markers.
    
    New features:
    - Query type classification and routing
    - Type-specific objective generation
    - Uncertainty markers for unclear queries
    - Query refinement suggestions
    - Progressive disclosure for cognitive load reduction
    - User persona tracking and optimization
    """
    start_time = time.time()
    
    # Generate session ID if not provided
    session_id = x_session_id or str(uuid.uuid4())
    user_id = x_user_id or f"anonymous_{session_id[:8]}"
    
    # Ensure session exists
    db.create_session(session_id, user_id)
    
    # Initialize interaction tracking
    query_sig = db.query_signature(request.query)
    interaction_start_time = time.time()
    
    try:
        # Step 1: Classify query type
        router_result = router.classify(request.query, request.context)
        print(f"DEBUG: Query classified as {router_result.query_type.value} (confidence: {router_result.confidence:.2f})")
        
        # Step 2: Get user persona optimization hints
        persona_hints = persona_manager.get_optimization_hints(
            user_id, request.query, router_result.query_type.value
        )
        print(f"DEBUG: Persona hints: {persona_hints}")
        
        # Step 3: Check for existing prior
        prior = db.get_prior(query_sig)
        
        # Step 3: Generate type-specific prompt
        prompt = ollama.get_objectives_prompt(
            query=request.query,
            query_type=router_result.query_type,
            context=request.context,
            k=request.k,
            missing_inputs=router_result.missing_inputs
        )
        print(f"DEBUG: Generated {router_result.query_type.value} prompt, length: {len(prompt)} chars")
        
        # Step 4: Get LLM response
        response_data = await ollama.generate_json(prompt)
        print(f"DEBUG: LLM response received with {len(response_data.get('objectives', []))} objectives")
        
        # Step 5: Parse objectives with new fields
        objectives = []
        for obj_data in response_data.get("objectives", []):
            # Ensure summary exists
            if "summary" not in obj_data:
                obj_data["summary"] = {
                    "tldr": obj_data.get("subtitle", ""),
                    "key_tradeoffs": [],
                    "next_actions": []
                }
            
            # Ensure required new fields exist
            if "when_this_objective_is_wrong" not in obj_data:
                obj_data["when_this_objective_is_wrong"] = "Not specified"
            if "minimum_info_needed" not in obj_data:
                obj_data["minimum_info_needed"] = []
            if "expected_output_format" not in obj_data:
                obj_data["expected_output_format"] = "Explanation"
            if "rationale" not in obj_data:
                obj_data["rationale"] = "Generated based on query interpretation"
            
            objectives.append(EnhancedObjective(**obj_data))
        
        # Step 6: Parse query refinements
        query_refinements = [
            QueryRefinement(**ref) for ref in response_data.get("query_refinements", [])
        ]
        
        # Step 7: Parse uncertainty markers
        uncertainty_markers = [
            UncertaintyMarker(**um) for um in response_data.get("uncertainty_markers", [])
        ]
        
        # Step 8: Create progressive summary
        progressive_summary = ProgressiveDisclosure(
            tldr=f"Found {len(objectives)} ways to interpret your query",
            key_tradeoffs=[
                "Different objectives optimize for different criteria",
                "Some objectives may require additional context",
                "Consider your constraints when selecting"
            ],
            next_actions=[
                "Review objectives and select the best fit",
                "Answer facet questions to clarify intent",
                "Consider query refinements if none fit"
            ],
            details=None,
            glossary=None
        )
        
        # Step 9: Record query interaction and log event
        processing_time = time.time() - start_time
        
        # Store interaction data for persona tracking
        interaction_data = {
            'session_id': session_id,
            'user_id': user_id,
            'query_signature': query_sig,
            'query_text': request.query,
            'query_type': router_result.query_type.value,
            'query_type_confidence': router_result.confidence,
            'created_at': datetime.now().isoformat()
        }
        
        # Log comprehensive event
        await log_event_safe("objectives_generated", {
            "session_id": session_id,
            "user_id": user_id,
            "query": request.query,
            "query_type": router_result.query_type.value,
            "query_type_confidence": router_result.confidence,
            "has_context": bool(request.context),
            "num_objectives": len(objectives),
            "speculative_objectives": sum(1 for o in objectives if o.is_speculative),
            "num_refinements": len(query_refinements),
            "num_uncertainties": len(uncertainty_markers),
            "has_prior": prior is not None,
            "processing_time_ms": int(processing_time * 1000),
            "persona_hints_used": bool(persona_hints)
        })
        
        response = ObjectivesResponse(
            schema_version="2.0.0",
            objectives=objectives,
            global_questions=response_data.get("global_questions", []),
            router_info=RouterInfo(
                query_type=router_result.query_type,
                confidence=router_result.confidence,
                missing_inputs=router_result.missing_inputs,
                recommended_workflow=router_result.recommended_workflow,
                context_hints=router_result.context_hints
            ),
            query_refinements=query_refinements,
            uncertainty_markers=uncertainty_markers,
            progressive_summary=progressive_summary,
            processing_metadata={
                "processing_time_ms": int(processing_time * 1000),
                "prompt_length": len(prompt),
                "query_signature": query_sig,
                "session_id": session_id,
                "user_id": user_id
            }
        )
        
        # Update session stats
        db.increment_session_stats(session_id, 'total_queries')
        
        return response
        
    except Exception as e:
        import traceback
        print(f"DEBUG: Exception in generate_objectives: {str(e)}")
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to generate objectives: {str(e)}")

@app.post("/augment", response_model=AugmentResponse)
async def augment_with_context(request: AugmentRequest):
    """
    Augment selected objective with external context and grounding.
    
    New features:
    - Two-phase extraction (evidence then synthesis)
    - Explicit claim mapping
    - Grounding report with confidence
    - External source recommendations when needed
    """
    try:
        # No context provided - check if we need external sources
        if not request.context_blob:
            return AugmentResponse(
                schema_version="2.0.0",
                evidence_items=[],
                grounded_claims=[],
                augmented_answer=None,
                grounding_report=None,
                extraction_confidence="uncertain",
                need_external_sources=True,
                recommended_sources=[
                    "Consider providing relevant papers, documentation, or notes",
                    "Enable retrieval from academic databases if available"
                ]
            )
        
        # Generate prompt with grounding requirements
        prompt = ollama.get_augment_prompt(
            request.query, 
            request.objective_id, 
            request.objective_definition, 
            request.context_blob
        )
        
        response_data = await ollama.generate_json(prompt)
        
        # Parse enhanced evidence items
        evidence_items = []
        for item_data in response_data.get("evidence_items", []):
            # Set defaults for new fields
            if "source_quality" not in item_data:
                item_data["source_quality"] = "unknown"
            if "retrieval_method" not in item_data:
                item_data["retrieval_method"] = "provided"
            evidence_items.append(EvidenceItem(**item_data))
        
        # Parse grounded claims
        from models import Claim, GroundingReport
        grounded_claims = [
            Claim(**claim_data) for claim_data in response_data.get("grounded_claims", [])
        ]
        
        # Parse grounding report
        grounding_report_data = response_data.get("grounding_report", {})
        grounding_report = GroundingReport(
            claims=[Claim(**c) for c in grounding_report_data.get("claims", [])],
            evidence_summary=grounding_report_data.get("evidence_summary", ""),
            overall_confidence=grounding_report_data.get("overall_confidence", "uncertain"),
            missing_evidence=grounding_report_data.get("missing_evidence", []),
            assumptions_made=grounding_report_data.get("assumptions_made", [])
        ) if grounding_report_data else None
        
        # Log event with grounding metrics
        await log_event_safe("context_augmented", {
            "query": request.query,
            "objective_id": request.objective_id,
            "evidence_count": len(evidence_items),
            "claims_count": len(grounded_claims),
            "need_external_sources": response_data.get("need_external_sources", False),
            "extraction_confidence": response_data.get("extraction_confidence", "unknown")
        })
        
        return AugmentResponse(
            schema_version="2.0.0",
            evidence_items=evidence_items,
            grounded_claims=grounded_claims,
            augmented_answer=response_data.get("augmented_answer"),
            grounding_report=grounding_report,
            extraction_confidence=response_data.get("extraction_confidence", "medium"),
            need_external_sources=response_data.get("need_external_sources", False),
            recommended_sources=response_data.get("recommended_sources", [])
        )
        
    except Exception as e:
        import traceback
        print(f"DEBUG: Exception in augment: {str(e)}")
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to augment with context: {str(e)}")

@app.post("/finalize", response_model=FinalizeResponse)
async def finalize_answer(
    request: FinalizeRequest,
    x_user_id: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None)
):
    """
    Generate final answer with explicit grounding and progressive disclosure.
    
    New features:
    - Progressive disclosure (TL;DR, tradeoffs, actions)
    - Complete grounding report
    - Action items with priorities
    - Follow-up query suggestions
    - User persona tracking and optimization
    """
    try:
        user_id = x_user_id or "anonymous"
        session_id = x_session_id or "unknown"
        # Generate enhanced prompt
        prompt = ollama.get_finalize_prompt(
            request.query,
            request.objective,
            request.answers,
            request.evidence_items
        )
        
        response_data = await ollama.generate_json(prompt)
        
        # Parse progressive disclosure
        prog_disc_data = response_data.get("progressive_disclosure", {})
        from models import ProgressiveDisclosure
        progressive_disclosure = ProgressiveDisclosure(
            tldr=prog_disc_data.get("tldr", ""),
            key_tradeoffs=prog_disc_data.get("key_tradeoffs", []),
            next_actions=prog_disc_data.get("next_actions", []),
            details=prog_disc_data.get("details"),
            glossary=prog_disc_data.get("glossary")
        ) if prog_disc_data else None
        
        # Parse grounding report
        grounding_data = response_data.get("grounding_report", {})
        from models import GroundingReport, Claim
        grounding_report = GroundingReport(
            claims=[Claim(**c) for c in grounding_data.get("claims", [])],
            evidence_summary=grounding_data.get("evidence_summary", ""),
            overall_confidence=grounding_data.get("overall_confidence", "uncertain"),
            missing_evidence=grounding_data.get("missing_evidence", []),
            assumptions_made=grounding_data.get("assumptions_made", [])
        ) if grounding_data else None
        
        # Parse action items
        from models import ActionItem
        action_items = [
            ActionItem(**action_data) for action_data in response_data.get("action_items", [])
        ]
        
        # Parse claims
        claims = [Claim(**claim_data) for claim_data in response_data.get("claims", [])]
        
        # Parse follow-up queries
        follow_ups = [
            QueryRefinement(**ref_data) for ref_data in response_data.get("follow_up_queries", [])
        ]
        
        # Update prior
        query_sig = db.query_signature(request.query)
        db.update_prior(query_sig, request.objective.id, request.answers)
        
        # Record complete interaction for persona tracking
        interaction_data = {
            'session_id': session_id,
            'user_id': user_id,
            'query_signature': query_sig,
            'query_text': request.query,
            'selected_objective_id': request.objective.id,
            'selected_objective_confidence': request.objective.confidence,
            'is_speculative_selection': request.objective.is_speculative,
            'facet_answers': request.answers,
            'num_facet_questions_answered': len(request.answers),
            'evidence_count': len(request.evidence_items) if request.evidence_items else 0,
            'evidence_sources': [ev.source_ref for ev in request.evidence_items] if request.evidence_items else [],
            'final_answer': response_data.get("final_answer", ""),
            'assumptions_made': response_data.get("assumptions", []),
            'action_items': [item.action for item in action_items],
            'user_satisfaction': None,  # To be filled later via feedback endpoint
        }
        
        db.record_query_interaction(interaction_data)
        
        # Update user persona based on this interaction
        persona_manager.update_persona_from_interaction(user_id, {
            'query_type': request.objective.id.split('_')[0] if '_' in request.objective.id else 'unknown',
            'selected_objective_id': request.objective.id,
            'query_text': request.query,
            'constraints': list(request.answers.keys()),
            'user_satisfaction': None
        })
        
        # Update session stats
        db.increment_session_stats(session_id, 'total_answers_finalized')
        
        # Log comprehensive event
        await log_event_safe("answer_finalized", {
            "session_id": session_id,
            "user_id": user_id,
            "query": request.query,
            "objective_id": request.objective.id,
            "has_evidence": bool(request.evidence_items),
            "num_action_items": len(action_items),
            "num_claims": len(claims),
            "num_follow_ups": len(follow_ups),
            "overall_confidence": grounding_report.overall_confidence if grounding_report else "unknown"
        })
        
        return FinalizeResponse(
            schema_version="2.0.0",
            final_answer=response_data.get("final_answer", ""),
            progressive_disclosure=progressive_disclosure,
            grounding_report=grounding_report,
            assumptions=response_data.get("assumptions", []),
            next_questions=response_data.get("next_questions", []),
            action_items=action_items,
            claims=claims,
            follow_up_queries=follow_ups
        )
        
    except Exception as e:
        import traceback
        print(f"DEBUG: Exception in finalize: {str(e)}")
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to finalize answer: {str(e)}")

@app.post("/refine")
async def refine_query(
    request: RefineRequest,
    x_user_id: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None)
):
    """
    Refine or continue the query exploration with continuous interaction support.
    
    This endpoint allows users to:
    - Refine their query based on objectives shown
    - Continue exploring from where they left off
    - Explore alternative directions
    - Restart with a completely new query
    
    Supports continuous loop: generate -> refine -> continue -> refine -> etc.
    """
    try:
        user_id = x_user_id or "anonymous"
        session_id = x_session_id or str(uuid.uuid4())
        
        # Build context from previous interaction
        context_parts = []
        if request.previous_objectives:
            context_parts.append(f"Previous objectives considered: {len(request.previous_objectives)}")
        if request.current_objective_id:
            context_parts.append(f"User selected: {request.current_objective_id}")
        if request.previous_answers:
            context_parts.append(f"Previous answers: {json.dumps(request.previous_answers)}")
        
        previous_context = "\n".join(context_parts)
        
        # Create a new objectives request with accumulated context
        new_request = ObjectivesRequest(
            query=request.user_feedback if request.action != "restart" else request.user_feedback,
            context=previous_context if request.action != "restart" else None,
            k=5,
            schema_version="2.0.0",
            previous_context=previous_context,
            iteration=len(request.previous_objectives) // 5 + 1  # Rough iteration count
        )
        
        # Generate new objectives with context
        router_result = router.classify(new_request.query, new_request.context)
        prompt = ollama.get_objectives_prompt(
            query=new_request.query,
            query_type=router_result.query_type,
            context=new_request.context,
            k=new_request.k,
            missing_inputs=router_result.missing_inputs
        )
        
        response_data = await ollama.generate_json(prompt)
        
        # Parse objectives (simplified)
        objectives = []
        for obj_data in response_data.get("objectives", []):
            if "summary" not in obj_data:
                obj_data["summary"] = {
                    "tldr": obj_data.get("subtitle", ""),
                    "key_tradeoffs": [],
                    "next_actions": []
                }
            objectives.append(EnhancedObjective(**obj_data))
        
        # Parse refinements
        query_refinements = [
            QueryRefinement(**ref) for ref in response_data.get("query_refinements", [])
        ]
        
        # Parse uncertainty markers
        uncertainty_markers = [
            UncertaintyMarker(**um) for um in response_data.get("uncertainty_markers", [])
        ]
        
        # Create response with continuity info
        progressive_summary = ProgressiveDisclosure(
            tldr=f"Iteration {new_request.iteration}: Found {len(objectives)} refined objectives",
            key_tradeoffs=[
                "Building on previous exploration",
                "Refining direction based on feedback"
            ],
            next_actions=[
                "Select an objective to continue",
                "Provide more feedback to refine further",
                "Finalize if ready"
            ],
            details=None,
            glossary=None
        )
        
        # Log the refinement event
        await log_event_safe("query_refined", {
            "session_id": session_id,
            "user_id": user_id,
            "action": request.action,
            "original_query": request.original_query,
            "user_feedback": request.user_feedback,
            "num_previous_objectives": len(request.previous_objectives),
            "num_new_objectives": len(objectives),
            "iteration": new_request.iteration
        })
        
        return ObjectivesResponse(
            schema_version="2.0.0",
            objectives=objectives,
            global_questions=response_data.get("global_questions", []),
            router_info=RouterInfo(
                query_type=router_result.query_type,
                confidence=router_result.confidence,
                missing_inputs=router_result.missing_inputs,
                recommended_workflow=router_result.recommended_workflow,
                context_hints=router_result.context_hints
            ),
            query_refinements=query_refinements,
            uncertainty_markers=uncertainty_markers,
            progressive_summary=progressive_summary,
            processing_metadata={
                "iteration": new_request.iteration,
                "action": request.action,
                "previous_context_length": len(previous_context),
                "session_id": session_id,
                "user_id": user_id
            }
        )
        
    except Exception as e:
        import traceback
        print(f"DEBUG: Exception in refine: {str(e)}")
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to refine query: {str(e)}")

@app.post("/analyze")
async def analyze_query(
    query: str,
    context: Optional[str] = None,
    x_user_id: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None)
):
    """
    Analyze a query to determine:
    1. Dynamic query type (generated on-the-fly, not hardcoded)
    2. Missing context requirements
    3. Context sufficiency check
    
    This should be called BEFORE /objectives to check if more context is needed.
    """
    try:
        session_id = x_session_id or str(uuid.uuid4())
        user_id = x_user_id or f"anonymous_{session_id[:8]}"
        
        # Step 1: Analyze query dynamically
        analysis = await dynamic_generator.analyze_query(query, context)
        
        # Step 2: Check context sufficiency
        sufficiency = await dynamic_generator.check_context_sufficiency(
            query, analysis, context
        )
        
        # Step 3: Generate helpful prompt if context is missing
        context_prompt = None
        if not sufficiency["is_sufficient"] and sufficiency["missing_requirements"]:
            context_prompt = await dynamic_generator.generate_context_prompt(
                query, sufficiency["missing_requirements"]
            )
        
        # Log analysis
        await log_event_safe("query_analyzed", {
            "session_id": session_id,
            "user_id": user_id,
            "query": query,
            "query_type": analysis.get("query_type", {}).get("name"),
            "complexity": analysis.get("query_type", {}).get("complexity"),
            "missing_context_count": len(sufficiency["missing_requirements"]),
            "can_proceed": sufficiency["can_proceed"]
        })
        
        return {
            "schema_version": "2.0.0",
            "query": query,
            "analysis": analysis,
            "context_assessment": sufficiency,
            "context_prompt": context_prompt,
            "recommendation": {
                "should_proceed": sufficiency["can_proceed"],
                "reason": "Sufficient context" if sufficiency["is_sufficient"] else "Missing recommended context",
                "suggested_action": "proceed" if sufficiency["can_proceed"] else "provide_context"
            },
            "session_id": session_id,
            "user_id": user_id
        }
        
    except Exception as e:
        import traceback
        print(f"DEBUG: Exception in analyze: {str(e)}")
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze query: {str(e)}")

@app.post("/objectives/dynamic")
async def generate_dynamic_objectives(
    request: ObjectivesRequest,
    skip_analysis: bool = False,
    x_user_id: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None)
):
    """
    Generate objectives using DYNAMIC type generation.
    
    Instead of hardcoded query types (ambiguity_preference, factual_lookup, etc.),
    this endpoint:
    1. Analyzes the query to determine its unique characteristics
    2. Generates a custom query type specific to this query
    3. Creates objectives tailored to that dynamic type
    4. Identifies and requests missing context automatically
    
    Use this for more intelligent, query-specific objective generation.
    """
    start_time = time.time()
    
    session_id = x_session_id or str(uuid.uuid4())
    user_id = x_user_id or f"anonymous_{session_id[:8]}"
    
    try:
        # Step 1: Dynamic analysis (unless skipped)
        if not skip_analysis:
            analysis = await dynamic_generator.analyze_query(
                request.query, 
                request.context
            )
            
            # Check if we should prompt for more context
            sufficiency = await dynamic_generator.check_context_sufficiency(
                request.query, analysis, request.context
            )
            
            # If required context is missing, return early with prompt
            required_missing = [
                r for r in sufficiency["missing_requirements"] 
                if r.get("importance") == "required"
            ]
            
            if required_missing and not skip_analysis:
                context_prompt = await dynamic_generator.generate_context_prompt(
                    request.query, required_missing
                )
                
                return {
                    "schema_version": "2.0.0",
                    "status": "context_needed",
                    "message": "Additional context would help generate better objectives",
                    "context_prompt": context_prompt,
                    "missing_requirements": required_missing,
                    "can_proceed_without": True,  # Allow proceeding if user wants
                    "session_id": session_id,
                    "user_id": user_id
                }
        else:
            # Use basic analysis if skipping detailed analysis
            analysis = {
                "query_type": {
                    "name": "Dynamic Research",
                    "description": "Auto-generated query type",
                    "characteristics": ["dynamic"],
                    "complexity": "moderate",
                    "estimated_time_seconds": 30
                },
                "missing_context": [],
                "suggested_objectives_count": request.k,
                "objective_categories": ["general"],
                "user_expertise_inferred": "intermediate"
            }
        
        # Step 2: Generate dynamic objectives
        response_data = await dynamic_generator.generate_dynamic_objectives(
            query=request.query,
            analysis=analysis,
            context=request.context,
            k=request.k
        )
        
        # Step 3: Parse objectives
        objectives = []
        for obj_data in response_data.get("objectives", []):
            if "summary" not in obj_data:
                obj_data["summary"] = {
                    "tldr": obj_data.get("subtitle", ""),
                    "key_tradeoffs": [],
                    "next_actions": []
                }
            objectives.append(EnhancedObjective(**obj_data))
        
        # Step 4: Parse refinements and markers
        query_refinements = [
            QueryRefinement(**ref) for ref in response_data.get("query_refinements", [])
        ]
        
        uncertainty_markers = [
            UncertaintyMarker(**um) for um in response_data.get("uncertainty_markers", [])
        ]
        
        # Step 5: Create progressive summary
        query_type_info = response_data.get("query_type_info", {})
        progressive_summary = ProgressiveDisclosure(
            tldr=f"Dynamic analysis identified {len(objectives)} approaches for: {query_type_info.get('name', 'your query')}",
            key_tradeoffs=[
                "Different approaches suit different contexts",
                "Select the one closest to your needs",
                "You can refine or explore alternatives"
            ],
            next_actions=[
                "Select an objective to explore",
                "Answer clarifying questions",
                "Add context to improve results"
            ],
            details=None,
            glossary=None
        )
        
        processing_time = time.time() - start_time
        
        # Log event
        await log_event_safe("dynamic_objectives_generated", {
            "session_id": session_id,
            "user_id": user_id,
            "query": request.query,
            "dynamic_type": query_type_info.get("name"),
            "complexity": query_type_info.get("complexity"),
            "num_objectives": len(objectives),
            "processing_time_ms": int(processing_time * 1000)
        })
        
        return ObjectivesResponse(
            schema_version="2.0.0",
            objectives=objectives,
            global_questions=response_data.get("global_questions", []),
            router_info=RouterInfo(
                query_type=QueryType.DYNAMIC,
                confidence=0.85,
                missing_inputs=[],
                recommended_workflow="dynamic_exploration",
                context_hints={
                    "dynamic_type": query_type_info.get("name"),
                    "categories": analysis.get("objective_categories", []),
                    "estimated_time": query_type_info.get("estimated_time_seconds")
                }
            ),
            query_refinements=query_refinements,
            uncertainty_markers=uncertainty_markers,
            progressive_summary=progressive_summary,
            processing_metadata={
                "processing_time_ms": int(processing_time * 1000),
                "query_signature": db.query_signature(request.query),
                "dynamic_type": query_type_info.get("name"),
                "session_id": session_id,
                "user_id": user_id
            }
        )
        
    except Exception as e:
        import traceback
        print(f"DEBUG: Exception in dynamic objectives: {str(e)}")
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to generate dynamic objectives: {str(e)}")

@app.post("/assess")
async def assess_uncertainty(
    query: str,
    context: Optional[str] = None,
    x_user_id: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None)
):
    """
    ADVANCED: Information-aware uncertainty assessment.
    
    Uses the Uncertainty Gate to:
    1. Score uncertainty across multiple dimensions
    2. Detect underspecification, ambiguity, action risk
    3. Determine if disambiguation is needed
    4. Select appropriate TCG template
    
    Returns a decision on whether to disambiguate or proceed directly.
    """
    try:
        session_id = x_session_id or str(uuid.uuid4())
        user_id = x_user_id or f"anonymous_{session_id[:8]}"
        
        # Step 1: Run information-aware controller
        decision = await info_controller.process_query(query, context)
        
        # Step 2: Log assessment
        await log_event_safe("uncertainty_assessed", {
            "session_id": session_id,
            "user_id": user_id,
            "query": query,
            "uncertainty_score": decision["uncertainty_score"],
            "confidence_level": decision["confidence_level"],
            "strategy": decision["strategy"],
            "need_disambiguation": decision["need_disambiguation"]
        })
        
        return {
            "schema_version": "2.1.0",
            "query": query,
            "uncertainty_assessment": {
                "score": decision["uncertainty_score"],
                "level": decision["confidence_level"],
                "need_disambiguation": decision["need_disambiguation"]
            },
            "strategy": decision["strategy"],
            "template": {
                "id": decision["template_id"],
                "name": decision["template_name"]
            },
            "critical_questions": decision.get("critical_questions", []),
            "missing_context": {
                "critical": decision.get("critical_missing", []),
                "recommended": decision.get("recommended_missing", [])
            },
            "can_proceed": decision.get("can_proceed_with_defaults", True),
            "recommendation": {
                "action": "disambiguate" if decision["need_disambiguation"] else "proceed",
                "reason": decision.get("notes", "")
            },
            "session_id": session_id,
            "user_id": user_id
        }
        
    except Exception as e:
        import traceback
        print(f"DEBUG: Exception in assess: {str(e)}")
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to assess uncertainty: {str(e)}")

@app.post("/objectives/smart")
async def generate_smart_objectives(
    request: ObjectivesRequest,
    x_user_id: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None)
):
    """
    ADVANCED: Smart objective generation with conditional disambiguation.
    
    This endpoint intelligently decides:
    - If uncertainty is LOW: Skip objective clusters, return execution plan directly
    - If uncertainty is HIGH: Generate objective clusters + VOI-driven questions
    
    Uses the complete information-aware pipeline:
    1. Uncertainty Gate assessment
    2. Task Causal Graph template selection
    3. VOI-driven question selection (only ask what matters)
    4. Conditional objective generation
    """
    start_time = time.time()
    
    session_id = x_session_id or str(uuid.uuid4())
    user_id = x_user_id or f"anonymous_{session_id[:8]}"
    
    try:
        # Step 1: Assess uncertainty
        decision = await info_controller.process_query(
            request.query, 
            request.context
        )
        
        strategy = decision["strategy"]
        
        if strategy == "plan_directly":
            # LOW UNCERTAINTY: Skip disambiguation, return plan directly
            
            # Get or create objectives based on template
            execution_plan = decision.get("execution_plan", [])
            
            # Generate a single "objective" representing the direct approach
            direct_objective = EnhancedObjective(
                id="direct_plan",
                title=f"Direct: {decision['template_name']}",
                subtitle="Proceeding with execution plan",
                definition=f"Based on low uncertainty (score: {decision['uncertainty_score']:.2f}), "
                          f"proceeding directly with {decision['template_name']} workflow.",
                signals=["direct_execution", "low_uncertainty"],
                facet_questions=[],  # No questions needed
                confidence="high",
                is_speculative=False,
                summary=ProgressiveDisclosure(
                    tldr=f"Direct execution: {decision['template_name']}",
                    key_tradeoffs=["Faster execution", "No disambiguation needed"],
                    next_actions=["Review execution plan", "Proceed with workflow"],
                    details=None,
                    glossary=None
                ),
                exemplar_answer=None,
                when_this_objective_is_wrong=None,
                expected_output_format=None,
                rationale=None
            )
            
            processing_time = time.time() - start_time
            
            await log_event_safe("smart_objectives_direct", {
                "session_id": session_id,
                "user_id": user_id,
                "query": request.query,
                "uncertainty_score": decision["uncertainty_score"],
                "strategy": "direct",
                "template": decision["template_id"]
            })
            
            return ObjectivesResponse(
                schema_version="2.1.0",
                objectives=[direct_objective],
                global_questions=[],
                router_info=RouterInfo(
                    query_type=QueryType.DYNAMIC,
                    confidence=1.0 - decision["uncertainty_score"],
                    missing_inputs=[],
                    recommended_workflow="direct_execution",
                    context_hints={
                        "strategy": "direct",
                        "uncertainty_score": decision["uncertainty_score"],
                        "execution_plan_steps": len(execution_plan),
                        "template": decision["template_name"]
                    }
                ),
                query_refinements=[],
                uncertainty_markers=[],
                progressive_summary=ProgressiveDisclosure(
                    tldr=f"Low uncertainty detected. Proceeding directly with {decision['template_name']}.",
                    key_tradeoffs=["Fast execution", "Confidence: " + decision["confidence_level"]],
                    next_actions=["Review plan", "Execute workflow"],
                    details=None,
                    glossary=None
                ),
                processing_metadata={
                    "processing_time_ms": int(processing_time * 1000),
                    "strategy": "direct",
                    "uncertainty_score": decision["uncertainty_score"],
                    "template_id": decision["template_id"],
                    "execution_plan": execution_plan,
                    "session_id": session_id,
                    "user_id": user_id
                }
            )
        
        else:
            # HIGH UNCERTAINTY: Generate objective clusters + questions
            
            # Get critical questions from VOI analysis
            critical_questions = decision.get("critical_questions", [])
            
            # Generate objectives using dynamic generator
            response_data = await dynamic_generator.generate_dynamic_objectives(
                query=request.query,
                analysis={
                    "query_type": {
                        "name": decision["template_name"],
                        "description": "Auto-selected based on query",
                        "characteristics": ["uncertainty_driven"],
                        "complexity": "high",
                        "estimated_time_seconds": 45
                    },
                    "objective_categories": [decision["template_id"]],
                    "user_expertise_inferred": "intermediate"
                },
                context=request.context,
                k=request.k
            )
            
            # Parse objectives
            objectives = []
            for obj_data in response_data.get("objectives", []):
                if "summary" not in obj_data:
                    obj_data["summary"] = {
                        "tldr": obj_data.get("subtitle", ""),
                        "key_tradeoffs": [],
                        "next_actions": []
                    }
                objectives.append(EnhancedObjective(**obj_data))
            
            # Add VOI-driven questions as facet questions to first objective
            # This ensures the questions are prominently displayed
            if objectives and critical_questions:
                for i, obj in enumerate(objectives):
                    # Distribute questions across objectives
                    start_idx = i * 2
                    end_idx = start_idx + 2
                    obj_questions = critical_questions[start_idx:end_idx]
                    obj.facet_questions = [q["question"] for q in obj_questions]
            
            # Parse refinements
            query_refinements = [
                QueryRefinement(**ref) for ref in response_data.get("query_refinements", [])
            ]
            
            uncertainty_markers = [
                UncertaintyMarker(**um) for um in response_data.get("uncertainty_markers", [])
            ]
            
            processing_time = time.time() - start_time
            
            await log_event_safe("smart_objectives_disambiguate", {
                "session_id": session_id,
                "user_id": user_id,
                "query": request.query,
                "uncertainty_score": decision["uncertainty_score"],
                "strategy": "disambiguate",
                "num_objectives": len(objectives),
                "num_critical_questions": len(critical_questions)
            })
            
            return ObjectivesResponse(
                schema_version="2.1.0",
                objectives=objectives,
                global_questions=[q["question"] for q in critical_questions[:3]],
                router_info=RouterInfo(
                    query_type=QueryType.DYNAMIC,
                    confidence=1.0 - decision["uncertainty_score"],
                    missing_inputs=decision.get("critical_missing", []),
                    recommended_workflow="disambiguation_required",
                    context_hints={
                        "strategy": "disambiguate",
                        "uncertainty_score": decision["uncertainty_score"],
                        "template": decision["template_name"],
                        "critical_questions_count": len(critical_questions),
                        "reasons": decision.get("reasons", [])
                    }
                ),
                query_refinements=query_refinements,
                uncertainty_markers=uncertainty_markers,
                progressive_summary=ProgressiveDisclosure(
                    tldr=f"High uncertainty detected ({decision['uncertainty_score']:.2f}). "
                         f"{len(objectives)} approaches identified.",
                    key_tradeoffs=[
                        "Multiple valid interpretations",
                        "Additional context would help",
                        "Select the approach closest to your intent"
                    ],
                    next_actions=[
                        "Select an objective",
                        "Answer critical questions",
                        "Or provide more context"
                    ],
                    details=None,
                    glossary=None
                ),
                processing_metadata={
                    "processing_time_ms": int(processing_time * 1000),
                    "strategy": "disambiguate",
                    "uncertainty_score": decision["uncertainty_score"],
                    "critical_questions": critical_questions,
                    "template_id": decision["template_id"],
                    "session_id": session_id,
                    "user_id": user_id
                }
            )
        
    except Exception as e:
        import traceback
        print(f"DEBUG: Exception in smart objectives: {str(e)}")
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to generate smart objectives: {str(e)}")

@app.get("/templates")
async def list_tcg_templates(
    domain: Optional[str] = None
):
    """
    List available Task Causal Graph templates.
    
    Templates define workflow patterns for different domains
    (bioinformatics, biotech, general research, etc.)
    """
    try:
        templates = tcg_library.list_templates(domain)
        return {
            "schema_version": "2.1.0",
            "templates": templates,
            "count": len(templates)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list templates: {str(e)}")

@app.post("/log_event")
async def log_event(request: LogEventRequest):
    """Log an event for internalization/prior building."""
    try:
        db.log_event(request)
        return {"status": "logged", "schema_version": "2.0.0"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to log event: {str(e)}")

@app.post("/feedback")
async def submit_feedback(
    query_signature: str,
    rating: int,
    feedback_type: str = "general",
    comment: Optional[str] = None,
    x_user_id: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None)
):
    """
    Submit user feedback for a query to improve personalization.
    
    This feedback is used to update the user persona and improve future recommendations.
    """
    try:
        user_id = x_user_id or "anonymous"
        session_id = x_session_id or "unknown"
        
        # Store feedback
        feedback_data = {
            'session_id': session_id,
            'user_id': user_id,
            'query_signature': query_signature,
            'feedback_type': feedback_type,
            'rating': rating,
            'comment': comment
        }
        
        # Log event
        await log_event_safe("user_feedback", feedback_data)
        
        # Update persona with satisfaction score
        if rating > 0:
            persona_manager.update_persona_from_interaction(user_id, {
                'user_satisfaction': rating
            })
        
        return {
            "status": "feedback_recorded",
            "schema_version": "2.0.0",
            "message": "Thank you for your feedback! It helps us personalize future responses."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record feedback: {str(e)}")

@app.get("/persona/{user_id}")
async def get_user_persona(user_id: str):
    """
    Get the persona profile for a user.
    
    Returns a summary of the user's preferences, behavioral patterns, and interaction history.
    """
    try:
        persona = persona_manager.get_persona(user_id)
        stats = db.get_user_statistics(user_id)
        suggestions = persona_manager.suggest_personalized_improvements(user_id)
        
        return {
            "user_id": user_id,
            "schema_version": "2.0.0",
            "persona_summary": persona_manager.get_persona_summary(user_id),
            "statistics": stats,
            "improvement_suggestions": suggestions,
            "total_queries": persona.total_queries,
            "preferred_depth_level": persona.preferred_depth_level,
            "preferred_query_types": persona.preferred_query_types,
            "frequently_asked_domains": persona.frequently_asked_domains,
            "success_rate": persona.success_rate
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get persona: {str(e)}")

@app.get("/persona/{user_id}/history")
async def get_user_history(user_id: str, limit: int = 50):
    """
    Get recent query interaction history for a user.
    
    Useful for understanding the user's journey and query evolution.
    """
    try:
        history = db.get_user_interaction_history(user_id, limit)
        return {
            "user_id": user_id,
            "schema_version": "2.0.0",
            "total_interactions": len(history),
            "interactions": history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")

@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint with system capabilities."""
    return HealthCheckResponse(
        status="healthy",
        service="SECI Query Explorer API",
        version="2.1.0",
        capabilities=[
            "query_type_routing",
            "enhanced_objectives",
            "grounding_reports",
            "progressive_disclosure",
            "uncertainty_markers",
            "query_refinements",
            "user_persona_tracking",
            "interaction_history",
            "personalized_optimization",
            "continuous_interaction",
            "simple_user_identification",
            "uncertainty_gate",
            "task_causal_graphs",
            "voi_driven_questions",
            "conditional_disambiguation",
            "smart_objective_generation"
        ]
    )

@app.post("/init")
async def initialize_session(
    user_info: Optional[Dict[str, Any]] = None,
    x_user_id: Optional[str] = Header(None)
):
    """
    Initialize a new session with simple user identification.
    
    This endpoint creates a new session and optionally registers user info.
    No authentication required - just generates IDs for tracking.
    
    Frontend should call this on app load to get session/user IDs.
    """
    try:
        # Generate session ID
        session_id = str(uuid.uuid4())
        
        # Use provided user_id or generate one
        if x_user_id:
            user_id = x_user_id
        elif user_info and user_info.get('user_id'):
            user_id = user_info.get('user_id')
        else:
            # Generate anonymous user ID
            user_id = f"user_{uuid.uuid4().hex[:8]}"
        
        # Create session in database
        db.create_session(
            session_id=session_id,
            user_id=user_id,
            metadata=user_info or {}
        )
        
        # Get or create persona
        assert user_id is not None
        persona = persona_manager.get_persona(user_id)
        
        return {
            "status": "initialized",
            "schema_version": "2.0.0",
            "session_id": session_id,
            "user_id": user_id,
            "is_new_user": persona.total_queries == 0,
            "previous_queries_count": persona.total_queries,
            "message": "Session initialized. Use these IDs in request headers."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize: {str(e)}")

@app.post("/identify")
async def identify_user(
    user_info: Dict[str, Any],
    x_session_id: Optional[str] = Header(None)
):
    """
    Update user identification information.
    
    Allows users to provide name, email, or other identifying info
    without requiring authentication. Links to existing session.
    """
    try:
        session_id = x_session_id or str(uuid.uuid4())
        user_id = user_info.get('user_id') or f"user_{uuid.uuid4().hex[:8]}"
        
        # Update or create session with user info
        db.create_session(
            session_id=session_id,
            user_id=user_id,
            metadata=user_info
        )
        
        # Update persona with any useful info
        if 'preferences' in user_info and user_id:
            persona_manager.update_persona_from_interaction(user_id, {
                'preferences': user_info['preferences']
            })
        
        return {
            "status": "identified",
            "user_id": user_id,
            "session_id": session_id,
            "identified_fields": list(user_info.keys()),
            "message": "User identification updated."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to identify user: {str(e)}")

async def log_event_safe(event_type: str, payload: dict):
    """Safely log an event without failing the main operation."""
    try:
        db.log_event(LogEventRequest(event_type=event_type, payload=payload))
    except Exception as e:
        # Don't let logging failures break the main functionality
        print(f"WARNING: Failed to log event {event_type}: {e}")
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)