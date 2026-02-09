"""
Query Type Router - Classifies queries and routes to appropriate objective templates

This module provides intelligent routing of user queries into distinct types,
enabling domain-specific objective generation strategies.
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import re
from models import QueryType


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
    
    # Keywords that indicate query types
    AMBIGUITY_KEYWORDS = [
        'best', 'good', 'ideal', 'better', 'optimize', 'choose', 'select',
        'recommend', 'top', 'preferred', 'effective', 'efficient', 'suitable',
        'appropriate', 'optimal', 'advisable', 'worthwhile'
    ]
    
    FACTUAL_KEYWORDS = [
        'what is', 'how does', 'explain', 'define', 'describe', 'what are',
        'how do', 'mechanism', 'process', 'function', 'difference between'
    ]
    
    SYNTHESIS_KEYWORDS = [
        'compare', 'contrast', 'difference', 'similarities', 'overview',
        'survey', 'review', 'literature', 'state of the art', 'landscape',
        'trends', 'evolution', 'comparison', 'versus', 'vs'
    ]
    
    PLANNING_KEYWORDS = [
        'design', 'plan', 'protocol', 'pipeline', 'workflow', 'setup',
        'configure', 'implement', 'build', 'create', 'develop', 'construct',
        'architecture', 'framework', 'structure'
    ]
    
    TROUBLESHOOTING_KEYWORDS = [
        'why', 'error', 'problem', 'issue', 'bug', 'fail', 'broken',
        'not working', 'troubleshoot', 'debug', 'fix', 'solve', 'resolve',
        'exception', 'crash', 'warning'
    ]
    
    IDEATION_KEYWORDS = [
        'generate', 'propose', 'hypothesize', 'ideas', 'suggestions',
        'brainstorm', 'possibilities', 'options', 'alternatives',
        'directions', 'approaches', 'strategies'
    ]
    
    METHODOLOGY_KEYWORDS = [
        'method', 'technique', 'approach', 'procedure', 'assay',
        'measurement', 'quantification', 'analysis', 'detection',
        'characterization', 'validation', 'statistical', 'experimental'
    ]
    
    def __init__(self):
        """Initialize the router with pattern matchers."""
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile regex patterns for keyword matching."""
        self.patterns = {
            QueryType.AMBIGUITY_PREFERENCE: re.compile(
                r'\b(' + '|'.join(map(re.escape, self.AMBIGUITY_KEYWORDS)) + r')\b',
                re.IGNORECASE
            ),
            QueryType.FACTUAL_LOOKUP: re.compile(
                r'\b(' + '|'.join(map(re.escape, self.FACTUAL_KEYWORDS)) + r')\b',
                re.IGNORECASE
            ),
            QueryType.SYNTHESIS_SURVEY: re.compile(
                r'\b(' + '|'.join(map(re.escape, self.SYNTHESIS_KEYWORDS)) + r')\b',
                re.IGNORECASE
            ),
            QueryType.PLANNING_PROTOCOL: re.compile(
                r'\b(' + '|'.join(map(re.escape, self.PLANNING_KEYWORDS)) + r')\b',
                re.IGNORECASE
            ),
            QueryType.TROUBLESHOOTING: re.compile(
                r'\b(' + '|'.join(map(re.escape, self.TROUBLESHOOTING_KEYWORDS)) + r')\b',
                re.IGNORECASE
            ),
            QueryType.OPEN_IDEATION: re.compile(
                r'\b(' + '|'.join(map(re.escape, self.IDEATION_KEYWORDS)) + r')\b',
                re.IGNORECASE
            ),
            QueryType.METHODOLOGY: re.compile(
                r'\b(' + '|'.join(map(re.escape, self.METHODOLOGY_KEYWORDS)) + r')\b',
                re.IGNORECASE
            ),
        }
    
    def classify(self, query: str, context: Optional[str] = None) -> RouterResult:
        """
        Classify a query into a type and return routing information.
        
        Args:
            query: The user's query string
            context: Optional context about the query
            
        Returns:
            RouterResult with classification and workflow recommendation
        """
        query_lower = query.lower()
        scores = {}
        
        # Calculate match scores for each type
        for query_type, pattern in self.patterns.items():
            matches = len(pattern.findall(query_lower))
            # Weight by keyword density and position
            score = min(matches * 0.3, 0.9)  # Cap at 0.9 to leave room for uncertainty
            scores[query_type] = score
        
        # Determine primary type and confidence
        if not scores or max(scores.values()) < 0.1:
            # Low confidence - default to ambiguity_preference or ideation
            primary_type = QueryType.AMBIGUITY_PREFERENCE
            confidence = 0.3
            missing_inputs = ["Please clarify what you're looking for"]
        else:
            primary_type = max(scores.items(), key=lambda x: x[1])[0]
            confidence = scores[primary_type]
            
            # Check for competing interpretations
            sorted_scores = sorted(scores.values(), reverse=True)
            if len(sorted_scores) > 1 and sorted_scores[0] - sorted_scores[1] < 0.2:
                confidence *= 0.8  # Reduce confidence if close runner-up
            
            missing_inputs = self._determine_missing_inputs(primary_type, query, context)
        
        workflow = self._get_recommended_workflow(primary_type)
        context_hints = self._extract_context_hints(query, primary_type)
        
        return RouterResult(
            query_type=primary_type,
            confidence=confidence,
            missing_inputs=missing_inputs,
            recommended_workflow=workflow,
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
    
    def _get_recommended_workflow(self, query_type: QueryType) -> str:
        """Get the recommended workflow for a query type."""
        workflows = {
            QueryType.AMBIGUITY_PREFERENCE: "preference_elicitation",
            QueryType.FACTUAL_LOOKUP: "grounded_explanation",
            QueryType.SYNTHESIS_SURVEY: "systematic_comparison",
            QueryType.PLANNING_PROTOCOL: "constraint_satisfaction",
            QueryType.TROUBLESHOOTING: "diagnostic_probe",
            QueryType.OPEN_IDEATION: "creative_expansion",
            QueryType.METHODOLOGY: "method_selection"
        }
        return workflows.get(query_type, "general")
    
    def _extract_context_hints(self, query: str, query_type: QueryType) -> Dict[str, Any]:
        """Extract hints from query for objective generation."""
        hints = {
            'domain_keywords': [],
            'urgency_indicators': [],
            'constraint_keywords': []
        }
        
        query_lower = query.lower()
        
        # Domain detection
        domain_patterns = {
            'biology': ['cell', 'protein', 'gene', 'dna', 'rna', 'organism'],
            'chemistry': ['reaction', 'compound', 'molecule', 'synthesis'],
            'computational': ['algorithm', 'code', 'software', 'programming'],
            'clinical': ['patient', 'diagnosis', 'treatment', 'trial'],
            'engineering': ['system', 'device', 'component', 'prototype']
        }
        
        for domain, keywords in domain_patterns.items():
            if any(kw in query_lower for kw in keywords):
                hints['domain_keywords'].append(domain)
        
        # Urgency detection
        if any(word in query_lower for word in ['urgent', 'asap', 'quickly', 'soon', 'deadline']):
            hints['urgency_indicators'].append('high')
        
        # Constraint detection
        constraint_patterns = ['budget', 'cost', 'price', 'expensive', 'cheap', 'time', 'hours', 'days']
        hints['constraint_keywords'] = [p for p in constraint_patterns if p in query_lower]
        
        return hints


# Global router instance
router = QueryTypeRouter()