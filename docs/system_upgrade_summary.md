# SECI Query Explorer v2.0 - System Upgrade Summary

## Overview

This document summarizes the major architectural and design improvements implemented in SECI Query Explorer v2.0, transforming the system from simple prompt-based interactions to a human-in-the-loop reasoning system with explicit state management.

---

## 1. Architecture Changes

### 1.1 Before (v1.0)
```
Query → Single Prompt → Objectives → Augment → Finalize
        (one-size-fits-all)      (extracts snippets)
```

**Limitations**:
- Single prompt template for all query types
- No awareness of query context or domain
- Objectives only interpret "best"
- Evidence extraction without provenance
- No explicit uncertainty handling
- Stateless - no memory of user intent

### 1.2 After (v2.0)
```
Query → Router → Type-Specific Prompt → Enhanced Objectives
         ↓              ↓                      ↓
    Classification  Domain-Aware       Uncertainty Markers
    Confidence      Grounding          Query Refinements
    Missing Inputs  Progressive        Intent Priors
                    Disclosure
```

**Improvements**:
- Intelligent query type classification
- Type-specific objective generation
- Explicit uncertainty markers
- Progressive disclosure for cognitive load
- Grounding reports with evidence mapping
- Query refinement suggestions

---

## 2. Key Components

### 2.1 Query Type Router (`query_router.py`)

**Purpose**: Classify queries and route to appropriate objective generation strategies

**Taxonomy**:
- **Ambiguity/Preference** (best, good, ideal) - Original use case, enhanced
- **Factual/Lookup** (what is, how does) - Grounded explanations
- **Planning/Protocol** (design, setup) - Constraint satisfaction
- **Troubleshooting** (why, error) - Diagnostic paths
- **Synthesis/Survey** (compare, review) - Systematic comparison
- **Methodology** (method, technique) - Method selection

**Output**:
```python
RouterResult(
    query_type=QueryType.PLANNING_PROTOCOL,
    confidence=0.85,
    missing_inputs=["Timeline", "Scale requirements"],
    recommended_workflow="constraint_satisfaction",
    context_hints={"domain_keywords": ["biology"], ...}
)
```

**Benefits**:
- Domain-appropriate objectives
- Better missing context detection
- Confidence-calibrated routing

### 2.2 Enhanced Objective Model

**New Fields**:
- `when_this_objective_is_wrong` - When to discard
- `minimum_info_needed` - Requirements checklist
- `expected_output_format` - Answer format guidance
- `confidence` - System certainty level
- `is_speculative` - Mark uncertain objectives
- `rationale` - Why generated
- `summary` - Progressive disclosure

**Example Objective**:
```json
{
  "id": "obj_1",
  "title": "Fast Implementation",
  "subtitle": "Minimize time to first result",
  "definition": "Optimize for speed...",
  "signals": ["urgent", "deadline", "prototype"],
  "facet_questions": ["What's your timeline?"],
  "exemplar_answer": "For rapid prototyping...",
  "when_this_objective_is_wrong": "Don't use if quality is critical",
  "minimum_info_needed": ["Timeline", "Quality requirements"],
  "expected_output_format": "Step-by-step protocol",
  "confidence": "medium",
  "is_speculative": false,
  "rationale": "User mentioned 'asap' indicating urgency",
  "summary": {
    "tldr": "Quick implementation path",
    "key_tradeoffs": ["Speed vs thoroughness"],
    "next_actions": ["Define timeline", "List constraints"]
  }
}
```

### 2.3 Progressive Disclosure

**Purpose**: Reduce cognitive load by tiered information display

**Structure**:
```python
ProgressiveDisclosure(
    tldr="1-2 line summary",
    key_tradeoffs=["Max 3 critical tradeoffs"],
    next_actions=["Max 3 concrete steps"],
    details="Optional full explanation",
    glossary={"term": "definition"}
)
```

**UI Implications**:
- Always show TL;DR first
- Collapsible tradeoffs section
- Action items as buttons/CTAs
- Expandable details

### 2.4 Grounding & Evidence

**Enhanced Evidence Model**:
```python
EvidenceItem(
    id="ev_1",
    type="user_context",  # or paper, database, etc.
    title="User Notes",
    snippet="relevant excerpt",
    source_ref="user_context",
    source_quality="primary",  # primary, review, anecdotal...
    retrieval_method="provided",  # how we got it
    score=0.95,
    citation_key=None
)
```

**Grounding Report**:
```python
GroundingReport(
    claims=[
        Claim(
            claim_text="Specific claim",
            supporting_evidence_ids=["ev_1", "ev_2"],
            confidence="high",
            is_assumption=False,
            reasoning="Supported by..."
        )
    ],
    evidence_summary="Overall assessment",
    overall_confidence="medium",
    missing_evidence=["What would help"],
    assumptions_made=["Explicit assumptions"]
)
```

**Benefits**:
- Every claim traceable to evidence
- Clear uncertainty boundaries
- Explicit assumption marking

### 2.5 Query Refinements

**Purpose**: Help users ask better questions

**Structure**:
```python
QueryRefinement(
    refined_query="What is the best approach for X given Y?",
    what_changed="Added context Y",
    why_it_helps="Narrows scope to applicable solutions",
    expected_benefit="More relevant objectives",
    confidence="medium"
)
```

**Usage**:
- Suggest before objectives generated
- Offer as alternatives during review
- Enable one-click adoption

### 2.6 Uncertainty Markers

**Purpose**: Explicitly mark what the system is unsure about

**Structure**:
```python
UncertaintyMarker(
    aspect="Domain expertise needed",
    uncertainty_type="domain_knowledge",  # ambiguity, missing_context...
    clarification_questions=["Are you asking about X or Y?"],
    fallback_recommendation="If unclear, try..."
)
```

**Benefits**:
- Transparency about limitations
- Guided clarification
- Alternative paths when stuck

---

## 3. API Changes

### 3.1 Endpoint: POST /objectives

**v1.0 Request**:
```json
{
  "query": "What is the best way to learn Python?",
  "context": null,
  "k": 5
}
```

**v2.0 Request** (same structure, enhanced processing):
```json
{
  "query": "What is the best way to learn Python?",
  "context": null,
  "k": 5,
  "schema_version": "2.0.0"
}
```

**v2.0 Response** (major additions):
```json
{
  "schema_version": "2.0.0",
  "objectives": [...],  // EnhancedObjective with new fields
  "global_questions": [...],
  "router_info": {
    "query_type": "ambiguity_preference",
    "confidence": 0.92,
    "missing_inputs": ["Current skill level", "Learning goals"],
    "recommended_workflow": "preference_elicitation",
    "context_hints": {...}
  },
  "query_refinements": [
    {
      "refined_query": "What's the best way for a beginner to learn Python for data science?",
      "what_changed": "Added beginner level and domain",
      "why_it_helps": "Narrows to relevant resources",
      "expected_benefit": "More targeted recommendations",
      "confidence": "medium"
    }
  ],
  "uncertainty_markers": [
    {
      "aspect": "User's current programming background",
      "uncertainty_type": "missing_context",
      "clarification_questions": ["Have you programmed before?"],
      "fallback_recommendation": "Assume beginner-friendly path"
    }
  ],
  "progressive_summary": {
    "tldr": "Found 5 ways to approach learning Python",
    "key_tradeoffs": [...],
    "next_actions": [...]
  },
  "processing_metadata": {
    "processing_time_ms": 2450,
    "prompt_length": 1523,
    "query_signature": "abc123"
  }
}
```

### 3.2 Endpoint: POST /augment

**v2.0 Enhancements**:
- Two-phase extraction (evidence then synthesis)
- Grounded claims with evidence mapping
- External source recommendations
- Extraction confidence

**v2.0 Response**:
```json
{
  "schema_version": "2.0.0",
  "evidence_items": [...],  // With source_quality, retrieval_method
  "grounded_claims": [...],  // Claims with evidence links
  "augmented_answer": "...",
  "grounding_report": {
    "claims": [...],
    "evidence_summary": "...",
    "overall_confidence": "medium",
    "missing_evidence": [...],
    "assumptions_made": [...]
  },
  "extraction_confidence": "high",
  "need_external_sources": false,
  "recommended_sources": []
}
```

### 3.3 Endpoint: POST /finalize

**v2.0 Enhancements**:
- Progressive disclosure
- Complete grounding report
- Action items with priorities
- Follow-up query suggestions

**v2.0 Response**:
```json
{
  "schema_version": "2.0.0",
  "final_answer": "...",
  "progressive_disclosure": {
    "tldr": "...",
    "key_tradeoffs": [...],
    "next_actions": [...],
    "details": "..."
  },
  "grounding_report": {...},
  "assumptions": [...],
  "next_questions": [...],
  "action_items": [
    {
      "action": "Install Python 3.9+",
      "priority": "high",
      "rationale": "Required for all paths",
      "estimated_effort": "15 minutes"
    }
  ],
  "claims": [...],
  "follow_up_queries": [...]
}
```

---

## 4. Prompt Improvements

### 4.1 Type-Specific Prompts

Each query type now has a customized prompt that:
- Defines appropriate objective structures
- Requests domain-relevant facet questions
- Specifies expected output formats
- Encourages uncertainty marking

**Example: Planning Protocol Prompt**:
```
Task: Generate {k} distinct approaches to achieving this goal, 
considering different constraints and priorities.

For each objective, provide:
- title: The approach/strategy name
- subtitle: Primary constraint this optimizes for
- ...
- when_this_objective_is_wrong: "Don't use this when..."
- minimum_info_needed: Required resources, timeline

Focus on: Speed vs thoroughness tradeoffs, resource constraints, risk levels.
```

### 4.2 Prompt Constraints

All prompts now include:
- "When you are unsure, mark objective as speculative"
- "Return ONLY valid JSON"
- Explicit schema expectations
- Error handling guidance

### 4.3 Uncertainty Handling

Prompts explicitly request:
- Confidence levels for each objective
- Speculative marking when unsure
- Clarification questions for missing context
- Fallback recommendations

---

## 5. Database & Logging

### 5.1 Enhanced Event Logging

New events tracked:
- `objectives_generated` - With type, confidence, uncertainties
- `objective_selected` - With selection time and confidence
- `context_augmented` - With grounding metrics
- `answer_finalized` - With action items and follow-ups
- `progressive_disclosure_interaction` - UI engagement
- `query_refinement_viewed/adopted` - Refinement usage
- `user_feedback` - Satisfaction ratings

### 5.2 Query Signature Evolution

Now includes:
- Query type information
- Confidence scores
- Objective selections over time
- User intent priors

---

## 6. Frontend Implications

### 6.1 New UI Components Needed

1. **Query Type Indicator**
   - Show detected type
   - Display confidence
   - Allow manual override

2. **Progressive Disclosure Widget**
   - TL;DR card (always visible)
   - Expandable tradeoffs
   - Action item buttons
   - Collapsible details

3. **Uncertainty Banner**
   - Display when system is unsure
   - Show clarification questions
   - Offer query refinements

4. **Refinement Suggestions**
   - Show alternative query phrasings
   - One-click adoption
   - Explain benefits

5. **Grounding Panel**
   - Evidence visualization
   - Claim-evidence mapping
   - Assumption highlighting

6. **Action Items List**
   - Prioritized checklist
   - Effort estimates
   - Completion tracking

### 6.2 State Management

Track:
- Selected query type
- Current uncertainty markers
- Chosen refinements
- Progressive disclosure state
- Action item completion

### 6.3 Migration Guide

See `docs/frontend_migration_guide.md` for detailed migration instructions.

---

## 7. Evaluation Framework

### 7.1 Metrics by Goal

**Reduced Cognitive Load**:
- Time to select objective: Target < 30s
- Facet questions answered: Target 2-3 median
- TL;DR usage: Target > 60%

**Knowledge Creation**:
- Refinement adoption: Target > 20%
- Query improvement: Track clarity scores
- Follow-up usage: Target > 25%

**Grounded Results**:
- Evidence-backed claims: Target > 85%
- Assumption explicitness: Target 100%
- Uncertainty markers: Target > 30% of queries

### 7.2 Test Sets

- 100 queries for classification testing
- 50 queries for grounding validation
- 30 queries for cognitive load assessment

### 7.3 A/B Testing

Compare v1.0 vs v2.0 on:
- Completion rates
- User satisfaction
- Time to completion
- Evidence quality

See `docs/evaluation_metrics.md` for complete evaluation plan.

---

## 8. Benefits Summary

### 8.1 For Users

- **Faster decisions**: Progressive disclosure reduces reading
- **Better guidance**: Query refinements improve questions
- **More trust**: Grounding reports show evidence
- **Less confusion**: Uncertainty markers set expectations

### 8.2 For Developers

- **Extensible**: Easy to add new query types
- **Testable**: Clear metrics and evaluation criteria
- **Debuggable**: Rich logging and metadata
- **Maintainable**: Modular architecture

### 8.3 For the System

- **Smarter routing**: Type-specific processing
- **Better grounding**: Explicit evidence mapping
- **Continuous improvement**: Metrics-driven optimization
- **User learning**: Query priors over time

---

## 9. Implementation Status

✅ **Completed**:
- Query Type Router with 6-type taxonomy
- Enhanced models with grounding and disclosure
- Type-specific prompt templates
- Progressive disclosure schema
- Uncertainty markers
- Query refinements
- Comprehensive logging
- Evaluation framework

🚧 **Next Steps**:
- Frontend implementation
- A/B testing setup
- Retrieval system integration
- User feedback collection
- Performance optimization

---

## 10. Files Changed

### New Files
- `backend/query_router.py` - Query classification
- `docs/evaluation_metrics.md` - Evaluation framework
- `docs/system_upgrade_summary.md` - This document

### Modified Files
- `backend/models.py` - Enhanced schemas
- `backend/ollama_client.py` - Type-specific prompts
- `backend/main.py` - Integration and logging
- `backend/database.py` - Enhanced event logging

---

## 11. Non-Negotiable Constraints Met

✅ Progressive disclosure controls information density
✅ No ungrounded claims presented as facts
✅ Missing inputs requested before guessing
✅ JSON schemas stable and versioned
✅ Narrow, testable changes with acceptance criteria

---

**System Version**: 2.0.0
**Schema Version**: 2.0.0
**Last Updated**: 2024-01-15
**Status**: Backend Implementation Complete