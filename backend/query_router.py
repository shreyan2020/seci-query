"""
Query Type Router - Classifies queries and routes to appropriate objective templates

This module provides intelligent routing of user queries into distinct types,
enabling domain-specific objective generation strategies.
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from models import QueryType
from ollama_client import OllamaClient


@dataclass
class RouterResult:
    """Result of query type classification."""
    query_type: QueryType
    confidence: float  # 0.0 - 1.0
    missing_inputs: List[str]
    recommended_workflow: str
    context_hints: Dict[str, Any]


class QueryTypeRouter:
    """Router that classifies queries and determines objective generation strategy."""
    
    def __init__(self, model: str = "qwen2.5:1.5b"):
        """Initialize the router with a small LLM for classification."""
        self.llm = OllamaClient(model=model)
    
    async def classify(self, query: str, context: Optional[str] = None) -> RouterResult:
        """
        Classify a query into a type using a small LLM.
        
        Args:
            query: The user's query string
            context: Optional context about the query
            
        Returns:
            RouterResult with classification and workflow recommendation
        """
        query_types = [qt.value for qt in QueryType]
        prompt = f"""Classify the user query into a single query type.

Query: "{query}"
{context and f'Context: {context}' or ''}

Return JSON:
{{
  "query_type": "one_of_{query_types}",
  "confidence": 0.0-1.0,
  "missing_inputs": ["short phrases"],
  "recommended_workflow": "short workflow name",
  "context_hints": {{"key": "value"}}
}}

Rules:
- Use exactly one query_type from the list above
- Be concise
- Confidence should reflect certainty
"""

        response_data = await self.llm.generate_json(prompt)
        raw_type = str(response_data.get("query_type", "")).strip().lower().replace(" ", "_")
        
        try:
            query_type = QueryType(raw_type)
        except ValueError as e:
            raise ValueError(f"Invalid query_type from LLM: {raw_type}") from e
        
        confidence = float(response_data.get("confidence", 0.5))
        missing_inputs = response_data.get("missing_inputs", []) or []
        recommended_workflow = response_data.get("recommended_workflow", "general")
        context_hints = response_data.get("context_hints", {}) or {}
        
        return RouterResult(
            query_type=query_type,
            confidence=confidence,
            missing_inputs=missing_inputs,
            recommended_workflow=recommended_workflow,
            context_hints=context_hints
        )
    
    def _determine_missing_inputs(
        self, 
        query_type: QueryType, 
        query: str, 
        context: Optional[str]
    ) -> List[str]:
        """Determine what inputs are missing for this query type."""
        missing = []
        query_lower = query.lower()
        
        if query_type == QueryType.AMBIGUITY_PREFERENCE:
            if not any(word in query_lower for word in ['for', 'to', 'when', 'in order to']):
                missing.append("Purpose or use case")
            if not context and 'constraint' not in query_lower:
                missing.append("Constraints (budget, time, resources)")
        
        elif query_type == QueryType.FACTUAL_LOOKUP:
            if 'level' not in query_lower and 'background' not in query_lower:
                missing.append("Target audience level (beginner/expert)")
        
        elif query_type == QueryType.PLANNING_PROTOCOL:
            if not context or 'timeline' not in context.lower():
                missing.append("Timeline or deadline")
            if not any(word in query_lower for word in ['scale', 'size', 'throughput']):
                missing.append("Scale requirements")
        
        elif query_type == QueryType.TROUBLESHOOTING:
            if 'error' not in query_lower and 'message' not in query_lower:
                missing.append("Error messages or logs")
            if 'tried' not in query_lower:
                missing.append("What you've already tried")
        
        elif query_type == QueryType.SYNTHESIS_SURVEY:
            if 'scope' not in query_lower and not context:
                missing.append("Scope (time period, field boundaries)")
        
        return missing
    


# Global router instance
router = QueryTypeRouter()
