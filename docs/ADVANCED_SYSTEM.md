# Advanced Information-Aware System v2.1

## Overview

Implemented a sophisticated uncertainty-driven system with Task Causal Graphs and Value of Information (VOI) driven questioning. Objective clusters are now **conditional** - only shown when uncertainty is high.

---

## Architecture: Two Layers

### Layer 1: Information-Aware Controller
**Uncertainty Gate** decides whether to disambiguate

### Layer 2: Task Causal Graph (TCG)
Planning substrate with explicit dependencies

---

## 1. Uncertainty Gate

### Signals Detected

**A. Underspecification** (Missing critical parameters)
- organism, contrast, ontology, parameters
- data_type, thresholds

**B. Ambiguity** (Multiple valid interpretations)
- "best", "optimal", "better" keywords
- Multiple criteria mentioned
- Alternative options ("or")

**C. Action Risk** (Expensive/irreversible)
- delete, remove, modify operations
- Large-scale processing
- Resource-intensive tasks

**D. Non-identifiability** (Multiple valid outputs)
- Open-ended requests
- Subjective criteria
- Context-dependent answers

### Scoring

```python
# Weighted scoring
underspecification: 1.0x
ambiguity: 0.8x
action_risk: 1.2x  # Higher weight
non_identifiability: 0.6x

# Thresholds
DISAMBIGUATION_THRESHOLD = 0.6
HIGH_CONFIDENCE_THRESHOLD = 0.3
```

### Decision

```json
{
  "total_score": 0.75,
  "need_disambiguation": true,
  "confidence_level": "low",
  "can_proceed_directly": false,
  "factors": [
    {
      "signal_type": "underspecification",
      "score": 0.6,
      "reasons": ["Missing organism", "Missing contrast"],
      "severity": "critical"
    }
  ],
  "critical_missing": ["organism", "contrast"],
  "recommended_missing": ["alpha_threshold"]
}
```

---

## 2. Task Causal Graph (TCG)

### Node Types

- **INTENT**: User's goal
- **DECISION**: Decision variables (affects workflow)
- **ACTION**: Executable tools/commands
- **ARTIFACT**: Intermediate outputs
- **OBSERVATION**: Evidence/inputs
- **OUTPUT**: Final results

### Templates

**Bioinformatics DE Analysis:**
```
intent → load_data → validate → DESeq2 → deg_list → filter → 
filtered_degs → map_ids → gene_ids → enrichGO → enrichment → 
simplify → simplified → report
```

**Gene Delivery Selection:**
```
intent → define_criteria → [viral_options, nonviral_options] → 
[viral_comparison, nonviral_comparison] → safety_check → 
efficacy_check → tradeoff_analysis → recommendation
```

### Dependency Types

- **DEPENDS_ON**: Cannot execute without
- **PRODUCES**: Generates output
- **REQUIRES**: Needs as input
- **ENABLES**: Makes possible

### Verification

```python
# Validates graph invariants
valid, errors = tcg.validate()

# Checks:
- No cycles
- No missing nodes
- No isolated nodes
- All dependencies exist
```

---

## 3. VOI-Driven Question Selection

### Only Ask If:

1. **Affects high-probability path**
2. **Changes downstream actions materially**
3. **Cannot be inferred from context**

### VOI Score Calculation

```python
voi = 0.0
for affected_node in affected_nodes:
    if node.type == ACTION: voi += 0.4
    if node.type == DECISION: voi += 0.5  # Higher
    if node.type == OUTPUT: voi += 0.3

voi = min(voi / len(nodes) * 2, 1.0)
```

### Smart Inference

```python
# Try to infer from context before asking
organism: Detect "human", "mouse", "rat", etc.
tissue: Detect "liver", "brain", "muscle", etc.
alpha: Detect "p < 0.05", "alpha = 0.01"
data_type: Detect "RNA-seq", "microarray", etc.
```

### Question Ranking

```json
{
  "question": "What organism are you working with?",
  "variable": "organism",
  "importance": "critical",
  "voi_score": 0.85,
  "can_infer": true,
  "inferred_value": "human",
  "affects_nodes": ["load_data", "map_ids", "enrich"]
}
```

---

## 4. Conditional Disambiguation

### Scenario A: Low Uncertainty (< 0.3)

**System Response:**
```json
{
  "strategy": "plan_directly",
  "uncertainty_score": 0.15,
  "confidence": "high",
  "objectives": [
    {
      "id": "direct_plan",
      "title": "Direct: Differential Expression Analysis",
      "facet_questions": [],  // NO QUESTIONS
    }
  ],
  "execution_plan": [
    {"step": 1, "action": "load_data"},
    {"step": 2, "action": "validate"},
    {"step": 3, "action": "DESeq2"},
    // ...
  ]
}
```

**User Sees:** Direct execution plan, no objective clusters

### Scenario B: High Uncertainty (> 0.6)

**System Response:**
```json
{
  "strategy": "disambiguate",
  "uncertainty_score": 0.75,
  "confidence": "low",
  "objectives": [
    // Multiple approaches shown
    {"title": "Viral Vector Approach", ...},
    {"title": "Non-viral Nanoparticles", ...},
    {"title": "In Vivo vs Ex Vivo", ...}
  ],
  "critical_questions": [
    "What tissue type? (affects 4 downstream steps)",
    "What cargo size? (affects vector selection)",
  ]
}
```

**User Sees:** Objective clusters + critical questions

---

## 5. API Endpoints

### New Endpoints

```
POST /assess
  → Uncertainty assessment + decision
  
POST /objectives/smart
  → Conditional generation based on uncertainty
  
GET /templates
  → List TCG templates
```

### Example Flow

**Step 1: Assess Uncertainty**
```bash
curl -X POST /assess \
  -d '{"query": "Best CRISPR delivery"}'
```

**Response:**
```json
{
  "uncertainty_assessment": {
    "score": 0.72,
    "need_disambiguation": true
  },
  "strategy": "disambiguate",
  "critical_questions": [
    {
      "question": "What tissue type?",
      "voi_score": 0.85,
      "affects": ["vector_selection", "dosage"]
    }
  ],
  "template": {
    "id": "biotech_delivery_selection",
    "name": "Gene Delivery Method Selection"
  }
}
```

**Step 2: Generate Smart Objectives**
```bash
curl -X POST /objectives/smart \
  -d '{"query": "Best CRISPR delivery", "k": 5}'
```

**If uncertainty HIGH:**
- Returns objective clusters
- Includes critical questions
- Suggests context additions

**If uncertainty LOW:**
- Returns direct execution plan
- No questions needed
- Faster response

---

## 6. Benefits vs Simple Prompting

| Aspect | Simple Prompting | Information-Aware System |
|--------|------------------|-------------------------|
| **Uncertainty** | Vibes | Measured (0-1 score) |
| **Disambiguation** | Always | Conditional |
| **Questions** | All asked | Only high-VOI |
| **Planning** | Ad-hoc | Structured (TCG) |
| **Dependencies** | Implicit | Explicit (graph) |
| **Verification** | None | Graph invariants |
| **Context Use** | Manual | Automatic inference |

---

## 7. Files Created

1. ✅ `uncertainty_gate.py` - Uncertainty scoring (150+ lines)
2. ✅ `task_causal_graph.py` - TCG templates (300+ lines)
3. ✅ `voi_question_selector.py` - VOI + integration (250+ lines)
4. ✅ Updated `main.py` - New endpoints integrated

---

## 8. Key Innovation

**Objective clusters are NOT the default UI.**

They are a **fallback mechanism** triggered only when:
- Uncertainty score > 0.6
- Critical variables missing
- Multiple valid interpretations exist

This prevents "always ask questions" failure mode.

---

## 9. Testing Examples

### Low Uncertainty (Direct Plan)
```
Query: "Run DESeq2 on human liver RNA-seq data, alpha 0.05"
→ Score: 0.15
→ Strategy: plan_directly
→ Returns: Execution plan
```

### High Uncertainty (Disambiguate)
```
Query: "Best delivery method"
→ Score: 0.78
→ Strategy: disambiguate
→ Returns: 5 objectives + critical questions
```

### Medium Uncertainty (Proceed with Caution)
```
Query: "Analyze my RNA-seq data"
→ Score: 0.45
→ Strategy: proceed (with recommendations)
→ Returns: Plan + optional questions
```

---

**Status:** ✅ Complete
**Version:** 2.1.0
**Components:** Uncertainty Gate, TCG, VOI Selector, Smart Generator