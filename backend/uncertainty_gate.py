"""
Uncertainty Gate - Information-aware controller
Decides whether to disambiguate based on uncertainty scoring
"""

import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class UncertaintySignal(str, Enum):
    """Types of uncertainty signals"""
    UNDERSPECIFICATION = "underspecification"  # Missing critical parameters
    AMBIGUITY = "ambiguity"  # Multiple valid interpretations
    ACTION_RISK = "action_risk"  # Expensive/irreversible actions
    NON_IDENTIFIABILITY = "non_identifiability"  # Multiple valid outputs


@dataclass
class UncertaintyFactor:
    """A specific uncertainty factor with score and reasoning"""
    signal_type: UncertaintySignal
    score: float  # 0.0 to 1.0
    reasons: List[str]
    missing_variables: List[str]
    severity: str  # "low", "medium", "high", "critical"


@dataclass
class UncertaintyAssessment:
    """Complete uncertainty assessment"""
    total_score: float  # 0.0 to 1.0
    need_disambiguation: bool
    factors: List[UncertaintyFactor]
    critical_missing: List[str]  # Variables that must be resolved
    recommended_missing: List[str]  # Variables that should be resolved
    can_proceed_directly: bool
    confidence_level: str  # "high", "medium", "low"


class UncertaintyGate:
    """
    Information-aware controller that decides whether to disambiguate
    """
    
    # Thresholds for disambiguation
    DISAMBIGUATION_THRESHOLD = 0.6
    HIGH_CONFIDENCE_THRESHOLD = 0.3
    
    # Critical keywords that indicate underspecification
    UNDERSPECIFICATION_PATTERNS = {
        "contrast": ["vs", "versus", "compared to", "difference between", "contrast"],
        "organism": ["mouse", "human", "rat", "zebrafish", "organism", "species", "cell line"],
        "ontology": ["GO", "KEGG", "pathway", "ontology", "enrichment"],
        "parameters": ["threshold", "cutoff", "p-value", "alpha", "FDR"],
        "data_type": ["RNA-seq", "microarray", "proteomics", "ChIP-seq", "ATAC-seq"],
    }
    
    # Ambiguity indicators
    AMBIGUITY_PATTERNS = [
        "best", "good", "optimal", "better", "recommended",
        "should I", "which", "what is the", "how to choose"
    ]
    
    # High-risk action keywords
    HIGH_RISK_ACTIONS = [
        "delete", "remove", "drop", "modify", "update", "change",
        "run", "execute", "submit", "deploy", "publish"
    ]
    
    def __init__(self):
        self.critical_variables = set()
        self.available_context = {}
    
    def assess_uncertainty(
        self, 
        query: str, 
        context: Optional[str] = None,
        available_artifacts: Optional[List[str]] = None
    ) -> UncertaintyAssessment:
        """
        Main entry point: assess uncertainty and decide on disambiguation
        """
        self.available_context = {
            "query": query,
            "context": context or "",
            "artifacts": available_artifacts or []
        }
        
        factors = []
        
        # Check each uncertainty signal
        underspec = self._check_underspecification(query, context)
        if underspec.score > 0:
            factors.append(underspec)
        
        ambiguity = self._check_ambiguity(query)
        if ambiguity.score > 0:
            factors.append(ambiguity)
        
        action_risk = self._check_action_risk(query)
        if action_risk.score > 0:
            factors.append(action_risk)
        
        non_ident = self._check_non_identifiability(query, context)
        if non_ident.score > 0:
            factors.append(non_ident)
        
        # Calculate total score (weighted sum)
        total_score = self._calculate_total_score(factors)
        
        # Determine decision
        need_disambiguation = total_score >= self.DISAMBIGUATION_THRESHOLD
        can_proceed = total_score < self.HIGH_CONFIDENCE_THRESHOLD or not need_disambiguation
        
        # Classify confidence
        if total_score < 0.3:
            confidence = "high"
        elif total_score < 0.6:
            confidence = "medium"
        else:
            confidence = "low"
        
        # Collect missing variables
        critical_missing = []
        recommended_missing = []
        
        for factor in factors:
            for var in factor.missing_variables:
                if factor.severity in ["high", "critical"]:
                    critical_missing.append(var)
                else:
                    recommended_missing.append(var)
        
        return UncertaintyAssessment(
            total_score=total_score,
            need_disambiguation=need_disambiguation,
            factors=factors,
            critical_missing=list(set(critical_missing)),
            recommended_missing=list(set(recommended_missing)),
            can_proceed_directly=can_proceed,
            confidence_level=confidence
        )
    
    def _check_underspecification(self, query: str, context: Optional[str]) -> UncertaintyFactor:
        """Check for missing critical parameters"""
        query_lower = query.lower()
        context_lower = (context or "").lower()
        
        reasons = []
        missing_vars = []
        score = 0.0
        
        for param, patterns in self.UNDERSPECIFICATION_PATTERNS.items():
            # Check if parameter is mentioned in query but not specified
            mentioned = any(p in query_lower for p in patterns)
            specified = any(p in context_lower for p in patterns) if context else False
            
            if mentioned and not specified:
                reasons.append(f"Parameter '{param}' referenced but not specified")
                missing_vars.append(param)
                score += 0.25
            elif param in ["contrast", "organism"] and not mentioned and not specified:
                # These are often implicit but critical
                if any(word in query_lower for word in ["differential", "expression", "enrichment", "pathway"]):
                    reasons.append(f"Critical parameter '{param}' not mentioned")
                    missing_vars.append(param)
                    score += 0.2
        
        # Check for vague quantities
        vague_patterns = ["some", "a few", "several", "many", "lots"]
        if any(p in query_lower for p in vague_patterns):
            reasons.append("Vague quantities specified")
            score += 0.15
        
        severity = "critical" if score > 0.5 else "high" if score > 0.3 else "medium"
        
        return UncertaintyFactor(
            signal_type=UncertaintySignal.UNDERSPECIFICATION,
            score=min(score, 1.0),
            reasons=reasons,
            missing_variables=missing_vars,
            severity=severity
        )
    
    def _check_ambiguity(self, query: str) -> UncertaintyFactor:
        """Check for ambiguous interpretations"""
        query_lower = query.lower()
        
        reasons = []
        missing_vars = []
        score = 0.0
        
        # Check for ambiguity keywords
        ambiguity_count = sum(1 for p in self.AMBIGUITY_PATTERNS if p in query_lower)
        if ambiguity_count > 0:
            reasons.append(f"Ambiguity keywords detected ({ambiguity_count})")
            score += 0.2 * ambiguity_count
        
        # Check for multiple possible criteria
        criteria_keywords = ["fast", "accurate", "cheap", "safe", "easy", "efficient"]
        criteria_found = [k for k in criteria_keywords if k in query_lower]
        if len(criteria_found) > 1:
            reasons.append(f"Multiple criteria mentioned: {', '.join(criteria_found)}")
            missing_vars.append("optimization_priority")
            score += 0.3
        
        # Check for "or" which often indicates ambiguity
        if " or " in query_lower:
            reasons.append("Alternative options mentioned ('or')")
            score += 0.15
        
        severity = "high" if score > 0.4 else "medium" if score > 0.2 else "low"
        
        return UncertaintyFactor(
            signal_type=UncertaintySignal.AMBIGUITY,
            score=min(score, 1.0),
            reasons=reasons,
            missing_variables=missing_vars,
            severity=severity
        )
    
    def _check_action_risk(self, query: str) -> UncertaintyFactor:
        """Check for expensive or irreversible actions"""
        query_lower = query.lower()
        
        reasons = []
        missing_vars = []
        score = 0.0
        
        # Check for high-risk actions
        risky_actions = [a for a in self.HIGH_RISK_ACTIONS if a in query_lower]
        if risky_actions:
            reasons.append(f"High-risk actions: {', '.join(risky_actions)}")
            score += 0.3 * len(risky_actions)
            missing_vars.append("confirmation_safety")
        
        # Check for irreversible operations
        irreversible = ["delete", "drop", "remove", "overwrite", "replace"]
        irreversible_found = [i for i in irreversible if i in query_lower]
        if irreversible_found:
            reasons.append(f"Potentially irreversible: {', '.join(irreversible_found)}")
            score += 0.4
            missing_vars.append("backup_confirmation")
        
        # Check for resource-intensive operations
        resource_keywords = ["run", "execute", "process", "analyze", "compute"]
        if any(k in query_lower for k in resource_keywords):
            # Check if scale is mentioned
            scale_words = ["all", "every", "large", "big", "massive"]
            if any(s in query_lower for s in scale_words):
                reasons.append("Large-scale operation without specified limits")
                score += 0.25
                missing_vars.append("resource_limits")
        
        severity = "critical" if score > 0.5 else "high" if score > 0.3 else "medium"
        
        return UncertaintyFactor(
            signal_type=UncertaintySignal.ACTION_RISK,
            score=min(score, 1.0),
            reasons=reasons,
            missing_variables=missing_vars,
            severity=severity
        )
    
    def _check_non_identifiability(self, query: str, context: Optional[str]) -> UncertaintyFactor:
        """Check if multiple valid outputs are possible"""
        query_lower = query.lower()
        
        reasons = []
        missing_vars = []
        score = 0.0
        
        # Check for open-ended questions
        open_ended = ["suggest", "recommend", "ideas", "options", "alternatives"]
        if any(o in query_lower for o in open_ended):
            reasons.append("Open-ended request for suggestions")
            score += 0.25
        
        # Check for subjective criteria
        subjective = ["better", "best", "preferred", "optimal", "good"]
        subjective_found = [s for s in subjective if s in query_lower]
        if subjective_found:
            reasons.append(f"Subjective criteria: {', '.join(subjective_found)}")
            score += 0.2
            missing_vars.append("evaluation_criteria")
        
        # Check for context-dependent answers
        if any(word in query_lower for word in ["depends", "depending", "context", "situation"]):
            reasons.append("Answer explicitly context-dependent")
            score += 0.3
        
        severity = "medium" if score > 0.3 else "low"
        
        return UncertaintyFactor(
            signal_type=UncertaintySignal.NON_IDENTIFIABILITY,
            score=min(score, 1.0),
            reasons=reasons,
            missing_variables=missing_vars,
            severity=severity
        )
    
    def _calculate_total_score(self, factors: List[UncertaintyFactor]) -> float:
        """Calculate weighted total uncertainty score"""
        if not factors:
            return 0.0
        
        # Weights for different signal types
        weights = {
            UncertaintySignal.UNDERSPECIFICATION: 1.0,
            UncertaintySignal.AMBIGUITY: 0.8,
            UncertaintySignal.ACTION_RISK: 1.2,  # Higher weight for risk
            UncertaintySignal.NON_IDENTIFIABILITY: 0.6
        }
        
        weighted_sum = sum(f.score * weights.get(f.signal_type, 1.0) for f in factors)
        max_possible = sum(weights.get(f.signal_type, 1.0) for f in factors)
        
        if max_possible == 0:
            return 0.0
        
        return min(weighted_sum / max_possible, 1.0)
    
    def get_decision_explanation(self, assessment: UncertaintyAssessment) -> str:
        """Generate human-readable explanation of the decision"""
        if assessment.need_disambiguation:
            return (
                f"High uncertainty detected (score: {assessment.total_score:.2f}). "
                f"{len(assessment.critical_missing)} critical variables missing. "
                "Disambiguation recommended."
            )
        elif assessment.confidence_level == "high":
            return (
                f"Low uncertainty (score: {assessment.total_score:.2f}). "
                "Proceeding directly with planning."
            )
        else:
            return (
                f"Medium uncertainty (score: {assessment.total_score:.2f}). "
                "Can proceed with caution."
            )


# Global instance
uncertainty_gate = UncertaintyGate()