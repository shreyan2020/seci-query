"""
Dynamic Type Generator - Generates custom query types and interpretations on-the-fly
Uses lightweight models for fast, query-specific type generation
"""

import httpx
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class DynamicQueryType:
    """A dynamically generated query type"""
    type_id: str
    type_name: str
    description: str
    key_characteristics: List[str]
    suggested_objective_count: int
    complexity_level: str  # simple, moderate, complex
    estimated_time_seconds: int
    required_context: List[str]
    optional_context: List[str]


@dataclass
class ContextRequirement:
    """Identified context requirement for a query"""
    requirement_type: str  # domain, scope, constraints, audience, timeline, data_sources
    description: str
    importance: str  # required, recommended, optional
    why_needed: str
    example_answer: str


class DynamicTypeGenerator:
    """
    Generates dynamic query types and identifies context requirements
    Uses lightweight LLM for fast analysis
    """
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "qwen2.5:1.5b"):
        self.base_url = base_url
        self.model = model
        self.analysis_model = "qwen2.5:1.5b"  # Use 1.5B for fast analysis
        self.generation_model = "qwen2.5:7b"  # Use 7B for objectives
    
    async def analyze_query(self, query: str, existing_context: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze query to determine:
        1. What type of query this is (dynamic)
        2. What context is missing
        3. What objectives would be most relevant
        
        Uses lightweight model for speed
        """
        prompt = f"""Analyze this query and identify its characteristics.

Query: "{query}"
{existing_context and f'Context: {existing_context}' or ''}

Return JSON analysis:
{{
    "query_type": {{
        "name": "short descriptive name",
        "description": "what type of query this is",
        "characteristics": ["char1", "char2"],
        "complexity": "simple|moderate|complex",
        "estimated_time_seconds": 15-60
    }},
    "missing_context": [
        {{
            "type": "domain|scope|constraints|audience|timeline|data_sources",
            "description": "what is needed",
            "importance": "required|recommended|optional",
            "why": "why this helps",
            "example": "example answer"
        }}
    ],
    "suggested_objectives_count": 3-7,
    "objective_categories": ["category1", "category2"],
    "user_expertise_inferred": "beginner|intermediate|expert"
}}

Be fast and concise."""

        payload = {
            "model": self.analysis_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 800
            }
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            
            try:
                # Extract JSON from response
                text = result.get("response", "")
                # Find JSON block
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0]
                
                return json.loads(text.strip())
            except Exception as e:
                print(f"Failed to parse analysis: {e}")
                # Return fallback analysis
                return self._fallback_analysis(query)
    
    def _fallback_analysis(self, query: str) -> Dict[str, Any]:
        """Fallback analysis if LLM fails"""
        return {
            "query_type": {
                "name": "General Research",
                "description": "Broad research query",
                "characteristics": ["open-ended", "exploratory"],
                "complexity": "moderate",
                "estimated_time_seconds": 30
            },
            "missing_context": [
                {
                    "type": "scope",
                    "description": "Specific domain or field",
                    "importance": "recommended",
                    "why": "Helps focus the objectives",
                    "example": "molecular biology, clinical research"
                }
            ],
            "suggested_objectives_count": 5,
            "objective_categories": ["general"],
            "user_expertise_inferred": "intermediate"
        }
    
    async def generate_dynamic_objectives(
        self, 
        query: str, 
        analysis: Dict[str, Any],
        context: Optional[str] = None,
        k: int = 5
    ) -> Dict[str, Any]:
        """
        Generate objectives based on dynamic type analysis
        Uses larger model for quality
        """
        query_type = analysis.get("query_type", {})
        categories = analysis.get("objective_categories", ["general"])
        expertise = analysis.get("user_expertise_inferred", "intermediate")
        
        prompt = f"""Generate {k} distinct analytical objectives for this query.

Query: "{query}"
Query Type: {query_type.get('name', 'Research')}
Description: {query_type.get('description', '')}
Categories: {', '.join(categories)}
User Level: {expertise}
{context and f'Context: {context}' or ''}

Generate objectives that cover different angles of this query. Each should represent a different approach or interpretation.

Return JSON:
{{
    "objectives": [
        {{
            "id": "obj_1",
            "title": "3-5 words",
            "subtitle": "one line description",
            "definition": "2-3 lines explaining this approach",
            "signals": ["keyword1", "keyword2"],
            "facet_questions": ["clarifying question 1", "question 2"],
            "confidence": "high|medium|low",
            "is_speculative": false,
            "summary": {{
                "tldr": "one line summary",
                "key_tradeoffs": ["tradeoff1"],
                "next_actions": ["action1"]
            }}
        }}
    ],
    "global_questions": ["cross-cutting question 1"],
    "query_refinements": [
        {{
            "refined_query": "more specific version",
            "why_it_helps": "benefit"
        }}
    ]
}}

Tailor to {expertise} level. Be specific to the query domain."""

        payload = {
            "model": self.generation_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 2000
            }
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            
            try:
                text = result.get("response", "")
                # Extract JSON
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0]
                
                data = json.loads(text.strip())
                
                # Add dynamic metadata
                data["dynamic_analysis"] = analysis
                data["query_type_info"] = query_type
                
                return data
            except Exception as e:
                print(f"Failed to parse objectives: {e}")
                return {
                    "objectives": [],
                    "global_questions": [],
                    "query_refinements": [],
                    "dynamic_analysis": analysis
                }
    
    async def check_context_sufficiency(
        self, 
        query: str, 
        analysis: Dict[str, Any],
        provided_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check if provided context is sufficient
        Return what's missing and recommendations
        """
        missing = analysis.get("missing_context", [])
        
        # Check what context was already provided
        provided_signals = []
        if provided_context:
            provided_signals = self._extract_context_signals(provided_context)
        
        # Determine what's still missing
        still_needed = []
        for req in missing:
            req_type = req.get("type", "")
            # Simple check - in real implementation could be more sophisticated
            if not any(req_type in signal.lower() for signal in provided_signals):
                still_needed.append(req)
        
        return {
            "is_sufficient": len(still_needed) == 0,
            "missing_requirements": still_needed,
            "provided_signals": provided_signals,
            "can_proceed": len(still_needed) == 0 or all(
                r.get("importance") != "required" for r in still_needed
            )
        }
    
    def _extract_context_signals(self, context: str) -> List[str]:
        """Extract what types of context are provided"""
        signals = []
        context_lower = context.lower()
        
        # Simple keyword matching
        if any(word in context_lower for word in ['paper', 'study', 'research', 'journal']):
            signals.append("research")
        if any(word in context_lower for word in ['data', 'dataset', 'results', 'experiment']):
            signals.append("data")
        if any(word in context_lower for word in ['biology', 'cell', 'gene', 'protein']):
            signals.append("biology")
        if any(word in context_lower for word in ['clinical', 'patient', 'trial', 'treatment']):
            signals.append("clinical")
        if any(word in context_lower for word in ['timeline', 'deadline', 'schedule']):
            signals.append("timeline")
        if any(word in context_lower for word in ['budget', 'cost', 'price', 'expensive']):
            signals.append("constraints")
            
        return signals
    
    async def generate_context_prompt(
        self, 
        query: str, 
        missing_requirements: List[Dict[str, Any]]
    ) -> str:
        """
        Generate a helpful prompt asking for missing context
        """
        required = [r for r in missing_requirements if r.get("importance") == "required"]
        recommended = [r for r in missing_requirements if r.get("importance") == "recommended"]
        
        prompt_parts = ["To provide the most relevant objectives, it would help to know:"]
        
        if required:
            prompt_parts.append("\n**Required for accurate results:**")
            for req in required:
                prompt_parts.append(f"• {req['description']}")
                prompt_parts.append(f"  Example: {req['example']}")
        
        if recommended:
            prompt_parts.append("\n**Recommended for better results:**")
            for req in recommended[:3]:  # Limit to top 3
                prompt_parts.append(f"• {req['description']} - {req['why']}")
        
        prompt_parts.append("\nYou can proceed without this, but the objectives may be less targeted.")
        
        return "\n".join(prompt_parts)


# Global instance
dynamic_generator = DynamicTypeGenerator()