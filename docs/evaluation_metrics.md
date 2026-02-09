# SECI Query Explorer - Evaluation & Metrics

## Overview

This document outlines the evaluation framework for measuring improvements in the SECI Query Explorer system. Metrics are organized by the north-star goals: reduced cognitive load, knowledge creation, grounded results, and external knowledge integration.

---

## 1. Cognitive Load Metrics

### 1.1 Decision Speed
**Goal**: Users should decide faster with the new system

| Metric | Definition | Target | Measurement |
|--------|-----------|---------|-------------|
| Time to Select Objective | Seconds from objectives display to selection | < 30s | Frontend timing + backend logs |
| Time to Complete Workflow | Total time from query to final answer | < 3 min | Session tracking |
| Facet Questions Answered | Number of questions answered before finalize | 2-3 median | Response analysis |

### 1.2 Progressive Disclosure Effectiveness
**Goal**: Users should only see what they need

| Metric | Definition | Target | Measurement |
|--------|-----------|---------|-------------|
| TL;DR Usage Rate | % of users who don't expand details | > 60% | UI interaction tracking |
| Tradeoff Review Rate | % who view key tradeoffs | > 80% | Click tracking |
| Action Item Completion | % of recommended actions taken | > 40% | Follow-up tracking |

### 1.3 Cognitive Load Proxies
**Indirect indicators of reduced load**

- **Scroll Depth**: Less scrolling = better summarization
- **Re-selection Rate**: Lower = clearer initial objectives
- **Query Abandonment**: Lower = better guidance

---

## 2. Quality & Grounding Metrics

### 2.1 Evidence Coverage
**Goal**: Every claim should be traceable

| Metric | Definition | Target | Measurement |
|--------|-----------|---------|-------------|
| Claim Evidence Rate | % claims with supporting evidence | > 85% | Automated check |
| Assumption Explicitness | % assumptions clearly marked | 100% | Grounding report analysis |
| Source Quality Score | Average source_quality of evidence | > 3/5 | Evidence item analysis |

### 2.2 Uncertainty Handling
**Goal**: System should admit when unsure

| Metric | Definition | Target | Measurement |
|--------|-----------|---------|-------------|
| Speculative Objective Rate | % objectives marked speculative | 5-15% | Response analysis |
| Uncertainty Marker Presence | Queries with uncertainty markers | > 30% | Response analysis |
| Clarification Question Quality | Relevance to actual ambiguity | > 4/5 | Human evaluation |

### 2.3 Hallucination Detection
**Goal**: Minimize false claims

| Metric | Definition | Target | Measurement |
|--------|-----------|---------|-------------|
| Claim Verifiability | % claims that can be verified | > 90% | Spot audit |
| Evidence-Claim Alignment | Evidence actually supports claim | > 95% | Human evaluation |
| Contradiction Detection | System identifies conflicting info | > 80% | Test cases |

---

## 3. Knowledge Creation Metrics

### 3.1 Query Refinement
**Goal**: Help users ask better questions

| Metric | Definition | Target | Measurement |
|--------|-----------|---------|-------------|
| Refinement Click Rate | % users who view refinements | > 50% | UI tracking |
| Refinement Adoption | % who use a suggested refinement | > 20% | Query evolution |
| Query Improvement Score | Clarity improvement in rewrites | > 3/5 | Human evaluation |

### 3.2 Iterative Narrowing
**Goal**: Support progressive clarification

| Metric | Definition | Target | Measurement |
|--------|-----------|---------|-------------|
| Facet Utility Score | Questions actually clarify intent | > 4/5 | User feedback |
| Follow-up Query Usage | % who pursue suggested follow-ups | > 25% | Tracking |
| Intent Convergence | Similarity between initial and final objective | Track trend | Signature comparison |

---

## 4. Logging Schema

### 4.1 Event Types

```json
{
  "event_type": "objectives_generated",
  "timestamp": "2024-01-15T10:30:00Z",
  "session_id": "uuid",
  "query_signature": "hash",
  "payload": {
    "query": "user query text",
    "query_type": "ambiguity_preference",
    "query_type_confidence": 0.85,
    "has_context": true,
    "num_objectives": 5,
    "speculative_objectives": 1,
    "num_refinements": 3,
    "num_uncertainties": 2,
    "has_prior": false,
    "processing_time_ms": 2450
  }
}
```

```json
{
  "event_type": "objective_selected",
  "timestamp": "2024-01-15T10:30:15Z",
  "session_id": "uuid",
  "query_signature": "hash",
  "payload": {
    "objective_id": "obj_2",
    "selection_time_ms": 12000,
    "objective_confidence": "medium",
    "is_speculative": false
  }
}
```

```json
{
  "event_type": "context_augmented",
  "timestamp": "2024-01-15T10:31:00Z",
  "session_id": "uuid",
  "query_signature": "hash",
  "payload": {
    "objective_id": "obj_2",
    "evidence_count": 4,
    "claims_count": 6,
    "need_external_sources": false,
    "extraction_confidence": "high",
    "evidence_source_quality_avg": 4.2
  }
}
```

```json
{
  "event_type": "answer_finalized",
  "timestamp": "2024-01-15T10:32:00Z",
  "session_id": "uuid",
  "query_signature": "hash",
  "payload": {
    "objective_id": "obj_2",
    "has_evidence": true,
    "num_action_items": 3,
    "num_claims": 8,
    "num_follow_ups": 2,
    "overall_confidence": "medium",
    "assumptions_count": 2
  }
}
```

```json
{
  "event_type": "progressive_disclosure_interaction",
  "timestamp": "2024-01-15T10:32:10Z",
  "session_id": "uuid",
  "query_signature": "hash",
  "payload": {
    "interaction_type": "expand_details|view_tradeoffs|click_action|collapse",
    "element_id": "tldr|details|tradeoffs|action_1",
    "time_after_finalize_ms": 10000
  }
}
```

```json
{
  "event_type": "query_refinement_viewed",
  "timestamp": "2024-01-15T10:30:20Z",
  "session_id": "uuid",
  "query_signature": "hash",
  "payload": {
    "refinement_index": 0,
    "refinement_type": "specificity|scope|constraint"
  }
}
```

```json
{
  "event_type": "query_refinement_adopted",
  "timestamp": "2024-01-15T10:30:25Z",
  "session_id": "uuid",
  "query_signature": "hash",
  "payload": {
    "original_query": "what is best...",
    "refined_query": "what is best for...",
    "improvement_type": "added_context"
  }
}
```

### 4.2 User Feedback Events

```json
{
  "event_type": "user_feedback",
  "timestamp": "2024-01-15T10:35:00Z",
  "session_id": "uuid",
  "query_signature": "hash",
  "payload": {
    "feedback_type": "objective_relevance|answer_quality|grounding_satisfaction",
    "rating": 4,
    "comment": "optional text",
    "objective_id": "obj_2"
  }
}
```

---

## 5. Evaluation Test Sets

### 5.1 Query Classification Test Set

Create 100 representative queries across all types:

- 20 Ambiguity/Preference queries
- 20 Factual/Lookup queries
- 15 Planning/Protocol queries
- 15 Troubleshooting queries
- 15 Synthesis/Survey queries
- 15 Methodology queries

**Success Criteria**:
- Router accuracy > 85%
- Confidence calibrated (high confidence → high accuracy)

### 5.2 Grounding Test Set

Create 50 queries with known ground truth:

- 25 with sufficient context (should ground well)
- 25 with insufficient context (should ask for more)

**Success Criteria**:
- Evidence-backed claims > 90%
- Appropriate external source requests > 80%

### 5.3 Cognitive Load Test Set

Create 30 queries of varying complexity:

- 10 simple (1-2 facet questions sufficient)
- 10 medium (2-3 questions)
- 10 complex (3-4 questions or need refinement)

**Success Criteria**:
- Median completion time < 3 min for simple
- < 5 min for medium
- < 8 min for complex

---

## 6. A/B Testing Framework

### 6.1 Test Conditions

**Control (v1.0)**:
- Original prompts
- No query type routing
- No progressive disclosure
- Simple evidence extraction

**Treatment (v2.0)**:
- Type-specific prompts
- Full routing
- Progressive disclosure
- Grounded evidence

### 6.2 Success Metrics

| Metric | v1.0 Baseline | v2.0 Target | Minimum Improvement |
|--------|---------------|-------------|---------------------|
| Time to select objective | 45s | 30s | -33% |
| Query abandonment rate | 15% | 8% | -47% |
| User satisfaction (1-5) | 3.2 | 4.0 | +25% |
| Evidence-backed claims | 60% | 85% | +42% |

---

## 7. Dashboard Metrics

### 7.1 Real-time Monitoring

```
┌─────────────────────────────────────────────────────┐
│ SECI Query Explorer - Live Metrics                  │
├─────────────────────────────────────────────────────┤
│                                                      │
│ Queries (last hour): 127                            │
│ Avg processing time: 2.3s                           │
│ Completion rate: 78%                                │
│                                                      │
│ Query Type Distribution:                            │
│   Ambiguity: 42%  Factual: 23%  Planning: 18%      │
│   Troubleshoot: 10%  Synthesis: 5%  Method: 2%     │
│                                                      │
│ Quality Metrics:                                    │
│   Avg claim evidence rate: 87%                      │
│   Avg confidence calibration: 0.82                  │
│   User satisfaction: 4.1/5                          │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### 7.2 Alert Thresholds

- Processing time > 5s → Alert
- Error rate > 5% → Alert
- User satisfaction < 3.5 → Review
- Evidence rate < 80% → Investigate

---

## 8. Implementation Checklist

- [ ] Set up event logging infrastructure
- [ ] Implement frontend tracking for UI interactions
- [ ] Create test sets (classification, grounding, cognitive load)
- [ ] Build evaluation dashboard
- [ ] Set up A/B testing framework
- [ ] Define alert thresholds
- [ ] Schedule monthly metric reviews
- [ ] Create user feedback collection mechanism

---

## 9. Success Criteria Summary

### Minimum Viable Improvements

1. **Cognitive Load**: 25% faster objective selection
2. **Quality**: 80% of claims evidence-backed
3. **Grounding**: Explicit uncertainty markers on 30% of queries
4. **Knowledge Creation**: 20% refinement adoption rate

### Stretch Goals

1. **Cognitive Load**: 40% faster, < 2 min median completion
2. **Quality**: 90% claims evidence-backed
3. **Grounding**: 50% of queries have uncertainty markers
4. **Knowledge Creation**: 40% refinement adoption

---

## 10. Continuous Improvement

### Monthly Reviews

1. Analyze metric trends
2. Identify top failure modes
3. Review user feedback
4. Update prompt templates based on data
5. Expand test sets with new edge cases

### Quarterly Reviews

1. Re-evaluate query type taxonomy
2. Assess evidence source quality
3. Review grounding accuracy with spot audits
4. Update evaluation criteria based on learnings

---

**Document Version**: 1.0
**Last Updated**: 2024-01-15
**Owner**: Engineering Team
**Review Schedule**: Monthly