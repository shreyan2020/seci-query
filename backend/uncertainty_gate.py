"""
Uncertainty Gate - LLM-driven information-aware controller.
Decides whether to disambiguate based on uncertainty scoring.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
from ollama_client import OllamaClient


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
    LLM-driven controller that decides whether to disambiguate.
    """

    def __init__(self, model: str = "qwen2.5:1.5b"):
        self.llm = OllamaClient(model=model)

    async def assess_uncertainty(
        self,
        query: str,
        context: Optional[str] = None,
        available_artifacts: Optional[List[str]] = None
    ) -> UncertaintyAssessment:
        """
        Use LLM to assess uncertainty across multiple dimensions.
        """
        prompt = f"""Assess uncertainty for this query.

Query: "{query}"
{context and f'Context: {context}' or ''}
{available_artifacts and f'Artifacts: {available_artifacts}' or ''}

Return JSON:
{{
  "total_score": 0.0-1.0,
  "need_disambiguation": true|false,
  "confidence_level": "high|medium|low",
  "factors": [
    {{
      "signal_type": "underspecification|ambiguity|action_risk|non_identifiability",
      "score": 0.0-1.0,
      "reasons": ["short reason"],
      "missing_variables": ["short phrase"],
      "severity": "low|medium|high|critical"
    }}
  ],
  "critical_missing": ["short phrase"],
  "recommended_missing": ["short phrase"],
  "can_proceed_directly": true|false
}}

Rules:
- Be conservative: only mark disambiguation true if it affects downstream actions.
- Keep scores calibrated.
"""

        data = await self.llm.generate_json(prompt)

        factors = []
        for f in data.get("factors", []):
            factors.append(
                UncertaintyFactor(
                    signal_type=UncertaintySignal(f.get("signal_type")),
                    score=float(f.get("score", 0.0)),
                    reasons=f.get("reasons", []),
                    missing_variables=f.get("missing_variables", []),
                    severity=f.get("severity", "low")
                )
            )

        return UncertaintyAssessment(
            total_score=float(data.get("total_score", 0.0)),
            need_disambiguation=bool(data.get("need_disambiguation", False)),
            factors=factors,
            critical_missing=data.get("critical_missing", []) or [],
            recommended_missing=data.get("recommended_missing", []) or [],
            can_proceed_directly=bool(data.get("can_proceed_directly", True)),
            confidence_level=str(data.get("confidence_level", "medium"))
        )
    
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
