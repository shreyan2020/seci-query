from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional


_TEMPLATES: List[Dict[str, Any]] = [
    {
        "template_id": "metabolic_hypothesis_scientist",
        "name": "Hypothesis-Driven Metabolic Scientist",
        "tagline": "Prefers mechanistic reasoning and clear experimental hypotheses.",
        "description": "Designed for users exploring pathway-level causality, intervention logic, and follow-up experiments.",
        "starter_goals": [
            "Identify likely pathway bottlenecks",
            "Compare intervention mechanisms",
            "Define next-step validation experiments",
        ],
        "seed_queries": [
            "Which metabolic pathways explain this phenotype shift?",
            "What is the strongest mechanistic hypothesis to test first?",
        ],
        "payload": {
            "role": "scientist",
            "domain_expertise": {"biotech": "expert", "stats": "intermediate", "coding": "intermediate"},
            "goals": [
                "Prioritize biologically plausible mechanisms",
                "Generate testable pathway hypotheses",
                "Balance novelty with reproducibility",
            ],
            "constraints": {"time_sensitivity": "medium", "compliance_posture": "moderate", "risk_tolerance": "medium"},
            "preferences": {"output_format": "mixed", "citation_need": "high", "verbosity": "high"},
            "decision_style": "exploratory",
            "trust_profile": {
                "default_reliance": "medium",
                "verification_habits": ["cross-check with pathway databases", "ask for evidence hierarchy"],
            },
            "taboo_or_redlines": [],
            "key_quotes": [],
            "evidence": {"support": []},
        },
    },
    {
        "template_id": "translational_decision_maker",
        "name": "Translational Decision Maker",
        "tagline": "Optimizes for practical choices under uncertainty.",
        "description": "For users who need ranked options, tradeoffs, and decision-ready recommendations in metabolic programs.",
        "starter_goals": [
            "Rank pathway intervention options",
            "Estimate feasibility and risk quickly",
            "Decide next action with confidence",
        ],
        "seed_queries": [
            "What are the top 3 intervention targets with best risk-reward?",
            "Which pathway strategy is most actionable this quarter?",
        ],
        "payload": {
            "role": "translational_lead",
            "domain_expertise": {"biotech": "intermediate", "stats": "intermediate", "coding": "novice"},
            "goals": [
                "Make fast and defensible go/no-go calls",
                "Focus on interventions with clear translational value",
                "Track uncertainty explicitly",
            ],
            "constraints": {"time_sensitivity": "high", "compliance_posture": "moderate", "risk_tolerance": "low"},
            "preferences": {"output_format": "steps", "citation_need": "medium", "verbosity": "medium"},
            "decision_style": "production",
            "trust_profile": {
                "default_reliance": "medium",
                "verification_habits": ["require short justification", "ask for confidence and caveats"],
            },
            "taboo_or_redlines": [],
            "key_quotes": [],
            "evidence": {"support": []},
        },
    },
    {
        "template_id": "bioinformatics_builder",
        "name": "Bioinformatics Workflow Builder",
        "tagline": "Wants reproducible analysis plans and implementation detail.",
        "description": "For users building metabolic analysis pipelines, feature engineering strategy, and QC-first workflows.",
        "starter_goals": [
            "Design robust computational workflow",
            "Reduce analysis ambiguity",
            "Capture reproducibility best practices",
        ],
        "seed_queries": [
            "What pipeline should I run for metabolic pathway enrichment?",
            "How should I structure QC and sensitivity checks?",
        ],
        "payload": {
            "role": "bioinformatics_engineer",
            "domain_expertise": {"biotech": "intermediate", "stats": "expert", "coding": "expert"},
            "goals": [
                "Build reproducible and scalable analysis flow",
                "Preserve statistical rigor in pathway interpretation",
                "Standardize reporting for team reuse",
            ],
            "constraints": {"time_sensitivity": "medium", "compliance_posture": "moderate", "risk_tolerance": "medium"},
            "preferences": {"output_format": "table", "citation_need": "high", "verbosity": "high"},
            "decision_style": "confirmatory",
            "trust_profile": {
                "default_reliance": "medium",
                "verification_habits": ["validate assumptions", "request alternative model checks"],
            },
            "taboo_or_redlines": [],
            "key_quotes": [],
            "evidence": {"support": []},
        },
    },
    {
        "template_id": "regulatory_safe_operator",
        "name": "Compliance-First Program Operator",
        "tagline": "Prioritizes traceability, safety, and conservative recommendations.",
        "description": "For users in regulated contexts where pathway claims must be tightly supported and auditable.",
        "starter_goals": [
            "Ensure recommendation traceability",
            "Minimize compliance risk",
            "Document assumptions and boundaries",
        ],
        "seed_queries": [
            "What pathway conclusion is safest to report right now?",
            "Where are compliance or evidence gaps in this interpretation?",
        ],
        "payload": {
            "role": "program_operator",
            "domain_expertise": {"biotech": "intermediate", "stats": "novice", "coding": "novice"},
            "goals": [
                "Avoid over-claiming in pathway interpretation",
                "Highlight evidence limitations early",
                "Keep decisions audit-friendly",
            ],
            "constraints": {"time_sensitivity": "medium", "compliance_posture": "strict", "risk_tolerance": "low"},
            "preferences": {"output_format": "narrative", "citation_need": "high", "verbosity": "medium"},
            "decision_style": "confirmatory",
            "trust_profile": {
                "default_reliance": "low",
                "verification_habits": ["require citations for key claims", "document uncertainty explicitly"],
            },
            "taboo_or_redlines": [],
            "key_quotes": [],
            "evidence": {"support": []},
        },
    },
]


def list_persona_templates() -> List[Dict[str, Any]]:
    return [
        {
            "template_id": row["template_id"],
            "name": row["name"],
            "tagline": row["tagline"],
            "description": row["description"],
            "starter_goals": list(row.get("starter_goals") or []),
        }
        for row in _TEMPLATES
    ]


def get_persona_template(template_id: str) -> Optional[Dict[str, Any]]:
    for row in _TEMPLATES:
        if row.get("template_id") == template_id:
            return deepcopy(row)
    return None
