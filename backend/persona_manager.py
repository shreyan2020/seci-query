from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
from database import db

@dataclass
class UserPersona:
    """Represents a user's behavioral and preference profile."""
    user_id: str
    
    # Preferences
    preferred_query_types: List[str] = field(default_factory=list)
    preferred_objective_types: List[str] = field(default_factory=list)
    preferred_depth_level: str = "detailed"  # brief, detailed, comprehensive
    
    # Behavioral patterns
    avg_time_to_objective_selection: float = 0.0
    avg_facet_questions_answered: float = 0.0
    frequently_used_signals: List[str] = field(default_factory=list)
    commonly_selected_objectives: Dict[str, int] = field(default_factory=dict)
    
    # Domain knowledge
    domain_expertise: Dict[str, str] = field(default_factory=dict)  # domain: level
    frequently_asked_domains: List[str] = field(default_factory=list)
    
    # Constraints and preferences
    typical_constraints: Dict[str, int] = field(default_factory=dict)
    preferred_evidence_sources: List[str] = field(default_factory=list)
    
    # Query patterns
    query_complexity_trend: str = "stable"  # increasing, decreasing, stable
    common_query_patterns: List[str] = field(default_factory=list)
    
    # Performance metrics
    satisfaction_scores: List[int] = field(default_factory=list)
    success_rate: float = 0.0
    
    # Metadata
    last_query_at: Optional[datetime] = None
    total_queries: int = 0


class PersonaManager:
    """Manages user personas and provides query optimization based on persona data."""
    
    def __init__(self):
        self.db = db
    
    def get_persona(self, user_id: str) -> UserPersona:
        """Get or create user persona."""
        persona_data = self.db.get_or_create_persona(user_id)
        
        return UserPersona(
            user_id=user_id,
            preferred_query_types=persona_data.get('preferred_query_types', []),
            preferred_objective_types=persona_data.get('preferred_objective_types', []),
            preferred_depth_level=persona_data.get('preferred_depth_level', 'detailed'),
            avg_time_to_objective_selection=persona_data.get('avg_time_to_objective_selection', 0.0),
            avg_facet_questions_answered=persona_data.get('avg_facet_questions_answered', 0.0),
            frequently_used_signals=persona_data.get('frequently_used_signals', []),
            commonly_selected_objectives=persona_data.get('commonly_selected_objectives', {}),
            domain_expertise=persona_data.get('domain_expertise', {}),
            frequently_asked_domains=persona_data.get('frequently_asked_domains', []),
            typical_constraints=persona_data.get('typical_constraints', {}),
            preferred_evidence_sources=persona_data.get('preferred_evidence_sources', []),
            query_complexity_trend=persona_data.get('query_complexity_trend', 'stable'),
            common_query_patterns=persona_data.get('common_query_patterns', []),
            satisfaction_scores=persona_data.get('satisfaction_scores', []),
            success_rate=persona_data.get('success_rate', 0.0),
            last_query_at=persona_data.get('last_query_at'),
            total_queries=persona_data.get('total_queries', 0)
        )
    
    def update_persona_from_interaction(self, user_id: str, interaction_data: Dict[str, Any]):
        """Update persona based on a new interaction."""
        persona = self.get_persona(user_id)
        
        # Update query type preferences
        query_type = interaction_data.get('query_type')
        if query_type:
            if query_type not in persona.preferred_query_types:
                persona.preferred_query_types.append(query_type)
            # Keep only top 5 most frequent
            persona.preferred_query_types = persona.preferred_query_types[:5]
        
        # Update objective preferences
        objective_id = interaction_data.get('selected_objective_id')
        if objective_id:
            persona.commonly_selected_objectives[objective_id] = \
                persona.commonly_selected_objectives.get(objective_id, 0) + 1
        
        # Update signals
        signals = interaction_data.get('signals', [])
        for signal in signals:
            if signal not in persona.frequently_used_signals:
                persona.frequently_used_signals.append(signal)
        persona.frequently_used_signals = persona.frequently_used_signals[:10]  # Keep top 10
        
        # Update domain expertise based on query content
        query_text = interaction_data.get('query_text', '')
        detected_domains = self._detect_domains(query_text)
        for domain in detected_domains:
            if domain not in persona.frequently_asked_domains:
                persona.frequently_asked_domains.append(domain)
        persona.frequently_asked_domains = persona.frequently_asked_domains[:10]
        
        # Update constraints
        constraints = interaction_data.get('constraints', [])
        for constraint in constraints:
            persona.typical_constraints[constraint] = \
                persona.typical_constraints.get(constraint, 0) + 1
        
        # Update satisfaction scores
        satisfaction = interaction_data.get('user_satisfaction')
        if satisfaction:
            persona.satisfaction_scores.append(satisfaction)
            persona.satisfaction_scores = persona.satisfaction_scores[-20:]  # Keep last 20
        
        # Update metadata
        persona.total_queries += 1
        persona.last_query_at = datetime.now()
        
        # Recalculate averages periodically
        if persona.total_queries % 5 == 0:
            self._recalculate_averages(persona, user_id)
        
        # Save updated persona
        self._save_persona(user_id, persona)
    
    def _detect_domains(self, query_text: str) -> List[str]:
        """Detect domains mentioned in query text."""
        query_lower = query_text.lower()
        domains = []
        
        domain_keywords = {
            'biology': ['cell', 'protein', 'gene', 'dna', 'rna', 'organism', 'biological'],
            'chemistry': ['reaction', 'compound', 'molecule', 'synthesis', 'chemical'],
            'computational': ['algorithm', 'code', 'software', 'programming', 'computational'],
            'clinical': ['patient', 'diagnosis', 'treatment', 'trial', 'clinical'],
            'engineering': ['system', 'device', 'component', 'prototype', 'engineering'],
            'data_science': ['data', 'analysis', 'machine learning', 'ml', 'statistics'],
            'medicine': ['disease', 'symptom', 'therapy', 'medical', 'health'],
            'physics': ['quantum', 'mechanics', 'particle', 'physics'],
            'economics': ['market', 'economic', 'financial', 'price', 'cost-benefit']
        }
        
        for domain, keywords in domain_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                domains.append(domain)
        
        return domains
    
    def _recalculate_averages(self, persona: UserPersona, user_id: str):
        """Recalculate behavioral averages from database."""
        patterns = self.db.analyze_user_patterns(user_id)
        
        persona.avg_time_to_objective_selection = patterns.get('avg_time_to_selection_seconds', 0.0) or 0.0
        persona.avg_facet_questions_answered = patterns.get('avg_facet_questions_answered', 0.0) or 0.0
        persona.success_rate = patterns.get('success_rate', 0.0) or 0.0
    
    def _save_persona(self, user_id: str, persona: UserPersona):
        """Save persona to database."""
        updates = {
            'preferred_query_types': persona.preferred_query_types,
            'preferred_objective_types': persona.preferred_objective_types,
            'preferred_depth_level': persona.preferred_depth_level,
            'avg_time_to_objective_selection': persona.avg_time_to_objective_selection,
            'avg_facet_questions_answered': persona.avg_facet_questions_answered,
            'frequently_used_signals': persona.frequently_used_signals,
            'commonly_selected_objectives': persona.commonly_selected_objectives,
            'domain_expertise': persona.domain_expertise,
            'frequently_asked_domains': persona.frequently_asked_domains,
            'typical_constraints': persona.typical_constraints,
            'preferred_evidence_sources': persona.preferred_evidence_sources,
            'query_complexity_trend': persona.query_complexity_trend,
            'common_query_patterns': persona.common_query_patterns,
            'satisfaction_scores': persona.satisfaction_scores,
            'success_rate': persona.success_rate,
            'last_query_at': datetime.now().isoformat()
        }
        
        self.db.update_persona(user_id, updates)
    
    def get_optimization_hints(self, user_id: str, current_query: str, query_type: str) -> Dict[str, Any]:
        """
        Generate optimization hints for a query based on user persona.
        
        Returns hints that can be used to:
        1. Reorder or filter objectives
        2. Adjust prompt parameters
        3. Pre-select likely facets
        4. Recommend evidence sources
        """
        persona = self.get_persona(user_id)
        hints = {
            'reorder_objectives': False,
            'objective_priority_weights': {},
            'suggested_facets': [],
            'recommended_evidence_sources': [],
            'adjust_complexity': False,
            'complexity_level': 'normal',
            'preemptive_context': []
        }
        
        # If user has preferred query types, prioritize matching objectives
        if persona.preferred_query_types and query_type in persona.preferred_query_types:
            hints['reorder_objectives'] = True
            # Boost objectives that align with user's typical selections
            for obj_id, count in persona.commonly_selected_objectives.items():
                hints['objective_priority_weights'][obj_id] = min(count * 0.1, 0.5)
        
        # If user consistently selects certain objective characteristics
        if persona.preferred_objective_types:
            hints['objective_characteristics'] = persona.preferred_objective_types
        
        # Suggest evidence sources user prefers
        if persona.preferred_evidence_sources:
            hints['recommended_evidence_sources'] = persona.preferred_evidence_sources
        
        # Adjust complexity based on user's history
        if persona.avg_facet_questions_answered and persona.avg_facet_questions_answered > 0:
            if persona.avg_facet_questions_answered < 2:
                hints['adjust_complexity'] = True
                hints['complexity_level'] = 'simple'
            elif persona.avg_facet_questions_answered > 4:
                hints['adjust_complexity'] = True
                hints['complexity_level'] = 'complex'
        
        # Add typical constraints user mentions
        if persona.typical_constraints:
            top_constraints = sorted(
                persona.typical_constraints.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:3]
            hints['preemptive_context'].extend([c[0] for c in top_constraints])
        
        # Add domain context
        if persona.frequently_asked_domains:
            hints['user_domains'] = persona.frequently_asked_domains[:3]
        
        return hints
    
    def get_persona_summary(self, user_id: str) -> str:
        """Generate a human-readable summary of the user persona."""
        persona = self.get_persona(user_id)
        stats = self.db.get_user_statistics(user_id)
        
        summary_parts = [
            f"User Profile: {user_id}",
            f"Total Queries: {stats['total_queries']}",
            f"Completion Rate: {stats['completion_rate']:.1f}%",
            f"Avg Satisfaction: {stats['avg_satisfaction']:.1f}/5" if stats['avg_satisfaction'] else "No ratings yet",
            "",
            "Preferences:",
            f"  - Preferred query types: {', '.join(persona.preferred_query_types) if persona.preferred_query_types else 'Not established'}",
            f"  - Depth level: {persona.preferred_depth_level}",
            f"  - Typical constraints: {', '.join(list(persona.typical_constraints.keys())[:3]) if persona.typical_constraints else 'None identified'}",
            "",
            "Behavioral Patterns:",
            f"  - Avg time to select objective: {persona.avg_time_to_objective_selection:.1f}s" if persona.avg_time_to_objective_selection else "  - Not enough data",
            f"  - Avg facet questions answered: {persona.avg_facet_questions_answered:.1f}",
            f"  - Success rate: {persona.success_rate*100:.1f}%",
            "",
            "Domains:",
            f"  {', '.join(persona.frequently_asked_domains[:5]) if persona.frequently_asked_domains else 'Not established'}"
        ]
        
        return '\n'.join(summary_parts)
    
    def suggest_personalized_improvements(self, user_id: str) -> List[Dict[str, str]]:
        """Suggest improvements based on persona analysis."""
        persona = self.get_persona(user_id)
        suggestions = []
        
        # If success rate is low
        if persona.success_rate < 0.5 and persona.total_queries > 5:
            suggestions.append({
                'type': 'workflow',
                'issue': 'Low completion rate',
                'suggestion': 'Consider simplifying objectives or providing more context upfront',
                'priority': 'high'
            })
        
        # If satisfaction scores are declining
        if len(persona.satisfaction_scores) >= 5:
            recent_avg = sum(persona.satisfaction_scores[-3:]) / 3
            older_avg = sum(persona.satisfaction_scores[-6:-3]) / 3
            if recent_avg < older_avg - 0.5:
                suggestions.append({
                    'type': 'quality',
                    'issue': 'Declining satisfaction',
                    'suggestion': 'Recent answers may not be meeting expectations. Review evidence quality.',
                    'priority': 'high'
                })
        
        # If user has very specific constraints pattern
        if len(persona.typical_constraints) > 5:
            suggestions.append({
                'type': 'context',
                'issue': 'Many recurring constraints',
                'suggestion': 'User mentions constraints frequently. Add constraint checklist to query form.',
                'priority': 'medium'
            })
        
        # If user typically takes long to select objectives
        if persona.avg_time_to_objective_selection > 60:
            suggestions.append({
                'type': 'objectives',
                'issue': 'Slow objective selection',
                'suggestion': 'Objectives may be unclear. Improve TL;DRs and reduce cognitive load.',
                'priority': 'medium'
            })
        
        return suggestions


# Global persona manager instance
persona_manager = PersonaManager()