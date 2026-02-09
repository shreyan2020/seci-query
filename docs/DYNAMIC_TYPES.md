# Dynamic Type Generation & Smart Context Detection

## Overview

Implemented a dynamic type generation system that creates custom query types on-the-fly using lightweight 1B parameter models, with automatic context detection and user prompting.

---

## Key Features

### 1. Dynamic Type Generation (No Hardcoded Types)

**Before:** 6 hardcoded query types (ambiguity_preference, factual_lookup, etc.)
**After:** AI generates custom types for each query

**How it works:**
1. User enters query: "Best CRISPR delivery methods for liver targeting"
2. Lightweight 1B model (qwen2.5:1.5b) analyzes the query
3. Generates custom type:
   ```json
   {
     "name": "Therapeutic Delivery Method Selection",
     "description": "Comparing delivery mechanisms for gene therapy",
     "characteristics": ["clinical application", "tissue-specific", "efficiency focused"],
     "complexity": "high",
     "estimated_time_seconds": 45
   }
   ```
4. Full 7B model then generates objectives tailored to this specific type

**Benefits:**
- Types match the actual query domain
- Not constrained to 6 categories
- More relevant objectives
- Better user experience

---

### 2. Automatic Context Detection

**Intelligent Analysis:**
```python
# Analyzes query and detects what's missing:
missing_context = [
  {
    "type": "tissue_type",
    "description": "Specific organ or tissue being targeted",
    "importance": "required",
    "why": "Different tissues require different delivery methods",
    "example": "liver, muscle, retina, brain"
  },
  {
    "type": "cargo_size",
    "description": "Size of genetic payload",
    "importance": "recommended", 
    "why": "AAV has packaging limits",
    "example": "small sgRNA vs large transgene"
  }
]
```

**Detected Context Types:**
- Domain (biology, clinical, chemistry)
- Scope (specific organ, cell type)
- Constraints (budget, timeline, regulations)
- Audience (researcher, clinician, patient)
- Timeline (urgency, milestones)
- Data sources (papers, datasets, experiments)

---

### 3. Smart User Prompting

**Before:** User blindly clicks "Generate"
**After:** System asks for missing context first

**Flow:**
```
1. User enters: "Best CRISPR delivery methods"
2. System analyzes → Detects missing: tissue type, cargo size
3. Shows prompt:
   
   ⚠️ Additional Context Recommended
   
   [Required for accurate results]
   • Specific organ or tissue being targeted
     Different tissues require different delivery methods
     Example: liver, muscle, retina, brain
   
   [Recommended for better results]  
   • Size of genetic payload
     AAV has packaging limits
     Example: small sgRNA vs large transgene
   
   [Proceed Anyway] [Add Context First]
4. User can add context or proceed
```

---

## Implementation

### New Backend Components

**1. `dynamic_type_generator.py`**
- `DynamicTypeGenerator` class
- Uses qwen2.5:1.5b for fast analysis (30s timeout)
- Uses qwen2.5:7b for objective generation
- Methods:
  - `analyze_query()` - Determines query characteristics
  - `check_context_sufficiency()` - Identifies gaps
  - `generate_context_prompt()` - Creates helpful prompts
  - `generate_dynamic_objectives()` - Creates custom objectives

**2. New API Endpoints:**

```python
POST /analyze
# Analyzes query, detects missing context
# Returns: query type, missing requirements, can_proceed

POST /objectives/dynamic  
# Generates objectives with dynamic typing
# Returns: objectives, dynamic_type_info
```

**3. Frontend Updates:**

```typescript
// New flow:
1. User clicks "Explore"
2. Frontend calls POST /analyze
3. If missing context:
   - Shows context requirements panel
   - Lists each missing item with importance
   - Shows examples
   - "Proceed Anyway" or "Add Context" buttons
4. When ready, calls POST /objectives/dynamic
5. Shows dynamic type in UI
6. Displays custom-generated objectives
```

---

## Usage Example

### Scenario: Biotech Research

**Query:** "Best method for delivering CRISPR to liver cells"

**Step 1 - Analysis:**
```json
{
  "query_type": {
    "name": "Tissue-Specific Gene Delivery",
    "description": "Selecting optimal delivery vectors for hepatic gene editing",
    "characteristics": ["clinical", "tissue-specific", "vector selection"],
    "complexity": "high",
    "estimated_time_seconds": 45
  },
  "missing_context": [
    {
      "type": "cargo_size",
      "importance": "required",
      "description": "Size of CRISPR components",
      "why": "AAV has ~4.7kb limit"
    },
    {
      "type": "delivery_mode", 
      "importance": "recommended",
      "description": "In vivo vs ex vivo",
      "why": "Different requirements for each"
    }
  ]
}
```

**Step 2 - Context Prompt:**
System shows:
- "What are you delivering? (sgRNA, Cas9, repair template?)"
- "In vivo (patient) or ex vivo (cells)?"

**Step 3 - Dynamic Objectives:**
```
1. Viral Vector Selection (AAV serotypes)
2. Non-viral Nanoparticle Approaches  
3. Ex Vivo Cell Editing Protocol
4. Clinical Trial Evidence Review
5. Regulatory Considerations
```

**All tailored to hepatic CRISPR delivery specifically!**

---

## Technical Architecture

### Two-Stage Processing

**Stage 1: Analysis (Fast - 1.5B model)**
- Timeout: 30 seconds
- Purpose: Understand query, detect context gaps
- Output: Query type, missing requirements

**Stage 2: Generation (Quality - 7B model)**
- Timeout: 60 seconds
- Purpose: Generate objectives based on custom type
- Output: Tailored objectives

### Context Detection Algorithm

```python
# 1. LLM analyzes query
analysis = await lightweight_llm.analyze(query)

# 2. Check what context was provided
provided_signals = extract_context_signals(context_text)

# 3. Compare required vs provided
missing = []
for req in analysis.missing_context:
    if not any(req.type in signal for signal in provided_signals):
        missing.append(req)

# 4. Generate helpful prompt
if missing:
    prompt = generate_user_prompt(missing)
```

---

## Benefits

✅ **No Hardcoded Types** - Every query gets custom analysis
✅ **Smart Context Detection** - System knows what's missing
✅ **User-Friendly Prompts** - Clear explanations with examples
✅ **Better Objectives** - Tailored to actual query domain
✅ **Professional Interface** - No gimmicks, clear workflow
✅ **Two-Stage Processing** - Fast analysis, quality generation
✅ **Exploration History** - Full tree of queries visible

---

## Files Modified

1. ✅ `backend/dynamic_type_generator.py` - New file (150+ lines)
2. ✅ `backend/main.py` - Added /analyze and /objectives/dynamic endpoints
3. ✅ `backend/models.py` - Added QueryType.DYNAMIC
4. ✅ `frontend/src/app/page.tsx` - Complete redesign for dynamic flow

---

## To Run

```bash
# Restart backend to pick up new endpoints
cd backend
python -c "import uvicorn; uvicorn.run('main:app', host='0.0.0.0', port=8000)"

# Start frontend
cd frontend
npm run dev
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/analyze` | POST | Analyze query, detect missing context |
| `/objectives/dynamic` | POST | Generate objectives with dynamic types |
| `/objectives` | POST | Original endpoint (still works) |
| `/augment` | POST | Add context to objective |
| `/finalize` | POST | Generate final answer |

---

**Status:** ✅ Complete
**Version:** 2.1 (Dynamic Types)
**Last Updated:** 2026-02-08