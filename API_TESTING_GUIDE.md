# API Testing Guide - SECI Query Explorer

## Quick Health Check

```bash
# Check if server is running
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "SECI Query Explorer API",
  "version": "2.1.0",
  "capabilities": ["uncertainty_gate", "task_causal_graphs", ...]
}
```

---

## 1. Basic Endpoints (v2.0)

### Initialize Session
```bash
curl -X POST http://localhost:8000/init \
  -H "Content-Type: application/json" \
  -d '{"source": "test"}'
```

**Response:**
```json
{
  "session_id": "uuid-here",
  "user_id": "user_xyz",
  "is_new_user": true
}
```

### Generate Objectives (Original)
```bash
curl -X POST http://localhost:8000/objectives \
  -H "Content-Type: application/json" \
  -H "X-User-Id: test_user" \
  -H "X-Session-Id: test_session" \
  -d '{
    "query": "Best way to learn Python",
    "k": 3
  }'
```

---

## 2. NEW: Advanced Endpoints (v2.1)

### Assess Uncertainty (NEW)
```bash
curl -X POST "http://localhost:8000/assess?query=Best%20CRISPR%20delivery" \
  -H "X-User-Id: test" \
  -H "X-Session-Id: test"
```

**Response:**
```json
{
  "uncertainty_assessment": {
    "score": 0.75,
    "level": "low",
    "need_disambiguation": true
  },
  "strategy": "disambiguate",
  "critical_questions": [
    {
      "question": "What tissue type?",
      "voi_score": 0.85,
      "importance": "critical"
    }
  ],
  "template": {
    "id": "biotech_delivery_selection",
    "name": "Gene Delivery Method Selection"
  }
}
```

### Smart Objectives with Conditional Disambiguation (NEW)
```bash
curl -X POST http://localhost:8000/objectives/smart \
  -H "Content-Type: application/json" \
  -H "X-User-Id: test" \
  -H "X-Session-Id: test" \
  -d '{
    "query": "Best CRISPR delivery methods for liver",
    "context": "Working with human hepatocytes",
    "k": 5
  }'
```

**Two Possible Responses:**

**A. Low Uncertainty → Direct Plan:**
```json
{
  "strategy": "direct",
  "objectives": [{
    "id": "direct_plan",
    "title": "Direct: Gene Delivery Analysis",
    "facet_questions": []
  }],
  "processing_metadata": {
    "execution_plan": [...]
  }
}
```

**B. High Uncertainty → Objective Clusters:**
```json
{
  "strategy": "disambiguate",
  "objectives": [...],
  "critical_questions": [...],
  "uncertainty_assessment": {
    "score": 0.75
  }
}
```

### List TCG Templates (NEW)
```bash
curl http://localhost:8000/templates
```

**Response:**
```json
{
  "templates": [
    {
      "id": "bioinformatics_differential_expression",
      "name": "Differential Expression Analysis",
      "domain": "bioinformatics",
      "slots": ["organism", "contrast", "alpha", "ont"]
    },
    {
      "id": "biotech_delivery_selection",
      "name": "Gene Delivery Method Selection",
      "domain": "biotech",
      "slots": ["tissue_type", "cargo_size", "delivery_mode"]
    }
  ]
}
```

---

## 3. Testing Scenarios

### Scenario 1: Low Uncertainty (Direct Plan)
```bash
curl -X POST http://localhost:8000/objectives/smart \
  -H "Content-Type: application/json" \
  -H "X-User-Id: test" \
  -d '{
    "query": "Run DESeq2 on human liver RNA-seq data with alpha 0.05",
    "k": 3
  }'
```

**Expected:** Returns execution plan, no questions

### Scenario 2: High Uncertainty (Disambiguate)
```bash
curl -X POST http://localhost:8000/objectives/smart \
  -H "Content-Type: application/json" \
  -H "X-User-Id: test" \
  -d '{
    "query": "Best delivery method",
    "k": 5
  }'
```

**Expected:** Returns objective clusters + critical questions

### Scenario 3: With Context
```bash
curl -X POST http://localhost:8000/objectives/smart \
  -H "Content-Type: application/json" \
  -H "X-User-Id: test" \
  -d '{
    "query": "Best CRISPR method",
    "context": "Human liver cells, 4kb payload, in vivo application",
    "k": 3
  }'
```

**Expected:** Lower uncertainty score, possibly direct plan

---

## 4. Complete Workflow Test

```bash
#!/bin/bash

echo "1. Checking health..."
curl -s http://localhost:8000/health | jq '.version'

echo -e "\n2. Testing uncertainty assessment..."
curl -s -X POST "http://localhost:8000/assess?query=Best%20method" \
  -H "X-User-Id: test" | jq '.uncertainty_assessment'

echo -e "\n3. Testing smart objectives (high uncertainty)..."
curl -s -X POST http://localhost:8000/objectives/smart \
  -H "Content-Type: application/json" \
  -H "X-User-Id: test" \
  -d '{"query": "Best CRISPR delivery", "k": 3}' | jq '.strategy'

echo -e "\n4. Testing smart objectives (low uncertainty)..."
curl -s -X POST http://localhost:8000/objectives/smart \
  -H "Content-Type: application/json" \
  -H "X-User-Id: test" \
  -d '{"query": "Run DESeq2 on human liver RNA-seq alpha 0.05", "k": 3}' | jq '.strategy'

echo -e "\n5. Listing templates..."
curl -s http://localhost:8000/templates | jq '.templates | length'

echo -e "\nDone!"
```

Save as `test_api.sh` and run:
```bash
bash test_api.sh
```

---

## 5. API Documentation

### Swagger UI
Open in browser: http://localhost:8000/docs

### OpenAPI Schema
```bash
curl http://localhost:8000/openapi.json
```

---

## 6. Common Issues

### "Connection refused"
```bash
# Backend not running, start it:
cd backend
python -c "import uvicorn; uvicorn.run('main:app', host='0.0.0.0', port=8000)"
```

### "500 Internal Server Error"
Check server logs:
```bash
cd backend
tail -f server.log
```

### "404 Not Found"
Make sure you're using the right endpoint:
- ✅ `/objectives/smart` (NEW in v2.1)
- ✅ `/assess` (NEW in v2.1)
- ✅ `/templates` (NEW in v2.1)
- ✅ `/objectives` (Original v2.0)

---

## 7. Python Test Script

```python
import requests
import json

BASE_URL = "http://localhost:8000"
HEADERS = {
    "X-User-Id": "test_user",
    "X-Session-Id": "test_session"
}

def test_health():
    """Test health endpoint"""
    r = requests.get(f"{BASE_URL}/health")
    print(f"Health: {r.json()['status']}")
    print(f"Version: {r.json()['version']}")
    return r.status_code == 200

def test_assess(query):
    """Test uncertainty assessment"""
    r = requests.post(
        f"{BASE_URL}/assess",
        params={"query": query},
        headers=HEADERS
    )
    data = r.json()
    print(f"\nQuery: {query}")
    print(f"Uncertainty Score: {data['uncertainty_assessment']['score']}")
    print(f"Strategy: {data['strategy']}")
    print(f"Template: {data['template']['name']}")
    return data

def test_smart_objectives(query, context=""):
    """Test smart objectives generation"""
    r = requests.post(
        f"{BASE_URL}/objectives/smart",
        json={"query": query, "context": context, "k": 3},
        headers=HEADERS
    )
    data = r.json()
    print(f"\nStrategy: {data.get('strategy')}")
    print(f"Objectives: {len(data.get('objectives', []))}")
    if data.get('processing_metadata', {}).get('execution_plan'):
        print(f"Execution Plan Steps: {len(data['processing_metadata']['execution_plan'])}")
    return data

# Run tests
if __name__ == "__main__":
    print("Testing SECI Query Explorer API\n")
    
    # Test 1: Health
    test_health()
    
    # Test 2: High uncertainty query
    print("\n--- High Uncertainty Query ---")
    test_assess("Best delivery method")
    
    # Test 3: Low uncertainty query
    print("\n--- Low Uncertainty Query ---")
    result = test_assess("Run DESeq2 on human liver RNA-seq alpha 0.05")
    
    # Test 4: Smart objectives
    print("\n--- Smart Objectives ---")
    test_smart_objectives("Best CRISPR method")
    
    print("\n✅ All tests completed!")
```

Run with:
```bash
python test_api.py
```

---

## 8. Response Examples

### High Uncertainty Response
```json
{
  "schema_version": "2.1.0",
  "objectives": [
    {
      "id": "obj_1",
      "title": "Viral Vector Approach",
      "confidence": "medium",
      "facet_questions": [
        "What tissue type are you targeting?",
        "What is the size of your genetic payload?"
      ]
    }
  ],
  "uncertainty_assessment": {
    "score": 0.75,
    "need_disambiguation": true
  },
  "strategy": "disambiguate",
  "critical_questions": [
    {
      "question": "What tissue type?",
      "voi_score": 0.85,
      "importance": "critical"
    }
  ]
}
```

### Low Uncertainty Response
```json
{
  "schema_version": "2.1.0",
  "objectives": [
    {
      "id": "direct_plan",
      "title": "Direct: Differential Expression Analysis",
      "facet_questions": []
    }
  ],
  "strategy": "direct",
  "processing_metadata": {
    "execution_plan": [
      {"step": 1, "action": "load_data"},
      {"step": 2, "action": "validate"},
      {"step": 3, "action": "DESeq2"}
    ]
  }
}
```

---

**Quick Test:**
```bash
curl -s http://localhost:8000/health | jq && \
curl -s "http://localhost:8000/assess?query=Best%20method" | jq '.uncertainty_assessment.score' && \
echo "✅ API is working!"
```