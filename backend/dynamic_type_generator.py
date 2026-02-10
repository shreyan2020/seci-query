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
        from ollama_client import OllamaClient
        self.analysis_llm = OllamaClient(base_url=base_url, model=self.analysis_model)
        self.generation_llm = OllamaClient(base_url=base_url, model=self.generation_model)
    
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

        return await self.analysis_llm.generate_json(prompt)
    
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

        data = await self.generation_llm.generate_json(prompt)
        data["dynamic_analysis"] = analysis
        data["query_type_info"] = query_type
        return data
    
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
        prompt = f"""Assess if the provided context is sufficient for this query.

Query: "{query}"
Analysis: {json.dumps(analysis)}
Provided Context: {provided_context or ""}

Return JSON:
{{
  "is_sufficient": true|false,
  "missing_requirements": [{{"type": "...", "description": "...", "importance": "required|recommended|optional", "why": "...", "example": "..."}}],
  "can_proceed": true|false
}}

Rules:
- Only include truly missing context
- If missing required info, can_proceed should be false
"""

        return await self.analysis_llm.generate_json(prompt)
    
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
