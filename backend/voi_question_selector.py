"""
VOI-Driven Question Selector
Only asks questions that affect downstream actions (Value of Information)
"""

from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass
from task_causal_graph import TaskCausalGraph, TCGNode, NodeType


@dataclass
class FacetQuestion:
    """A clarifying question with VOI metadata"""
    question: str
    variable_name: str
    importance: str  # "critical", "high", "medium", "low"
    affects_nodes: List[str]  # Which TCG nodes this affects
    voi_score: float  # Value of Information score 0.0-1.0
    can_infer: bool  # Can system infer from context?
    inference_source: Optional[str] = None
    asked: bool = False
    answer: Optional[str] = None


class VOIDrivenQuestionSelector:
    """
    Selects questions based on Value of Information
    Only asks if the answer would change downstream actions
    """
    
    def __init__(self, tcg: TaskCausalGraph):
        self.tcg = tcg
        self.questions: List[FacetQuestion] = []
        self.answered_vars: Dict[str, str] = {}
    
    def compute_voi_for_variable(
        self, 
        variable: str,
        affected_nodes: List[str]
    ) -> float:
        """
        Compute Value of Information for a variable
        Higher = more important to ask
        """
        voi = 0.0
        
        for node_id in affected_nodes:
            node = self.tcg.nodes.get(node_id)
            if not node:
                continue
            
            # Critical nodes (actions that can't proceed) get higher VOI
            if node.node_type == NodeType.ACTION:
                voi += 0.4
            
            # Decision nodes get high VOI (they branch the workflow)
            if node.node_type == NodeType.DECISION:
                voi += 0.5
            
            # Output nodes get medium VOI
            if node.node_type == NodeType.OUTPUT:
                voi += 0.3
        
        # Normalize by number of affected nodes
        if affected_nodes:
            voi = min(voi / len(affected_nodes) * 2, 1.0)
        
        return voi
    
    def identify_critical_questions(
        self,
        slot_variables: Dict[str, Any],
        context: Optional[str] = None
    ) -> List[FacetQuestion]:
        """
        Identify which slot variables need to be asked vs inferred
        """
        questions = []
        context_lower = (context or "").lower()
        
        for var_name, var_config in slot_variables.items():
            # Find which nodes this variable affects
            affected = self._find_affected_nodes(var_name)
            
            # Check if we can infer from context
            inferred_value = self._try_infer_from_context(var_name, context)
            can_infer = inferred_value is not None
            
            # Compute VOI
            voi = self.compute_voi_for_variable(var_name, affected)
            
            # Determine importance
            if len(affected) > 3 or any(
                self.tcg.nodes[n].node_type == NodeType.DECISION for n in affected
            ):
                importance = "critical"
            elif voi > 0.6:
                importance = "high"
            elif voi > 0.3:
                importance = "medium"
            else:
                importance = "low"
            
            # Only create question if:
            # 1. VOI is above threshold, OR
            # 2. It affects critical path and can't be inferred
            if voi > 0.2 or (importance == "critical" and not can_infer):
                question_text = self._generate_question_text(var_name, var_config)
                
                questions.append(FacetQuestion(
                    question=question_text,
                    variable_name=var_name,
                    importance=importance,
                    affects_nodes=affected,
                    voi_score=voi,
                    can_infer=can_infer,
                    inference_source=inferred_value if can_infer else None
                ))
        
        # Sort by VOI score (highest first)
        questions.sort(key=lambda q: q.voi_score, reverse=True)
        
        return questions
    
    def _find_affected_nodes(self, variable: str) -> List[str]:
        """Find all nodes affected by this variable"""
        affected = []
        
        for node_id, node in self.tcg.nodes.items():
            # Check if variable is mentioned in node's parameters or description
            node_text = f"{node.label} {node.description}"
            if variable.lower() in node_text.lower():
                affected.append(node_id)
            
            # Check in parameters
            if variable in node.parameters.get("slot_values", {}):
                affected.append(node_id)
        
        return list(set(affected))
    
    def _try_infer_from_context(self, variable: str, context: Optional[str]) -> Optional[str]:
        """Try to infer variable value from provided context"""
        if not context:
            return None
        
        context_lower = context.lower()
        
        # Organism inference
        if variable == "organism":
            organisms = {
                "human": ["human", "homo sapiens", "patient", "clinical"],
                "mouse": ["mouse", "mus musculus", "mice"],
                "rat": ["rat", "rattus"],
                "zebrafish": ["zebrafish", "danio"]
            }
            for org, keywords in organisms.items():
                if any(kw in context_lower for kw in keywords):
                    return org
        
        # Tissue inference
        if variable == "tissue_type":
            tissues = {
                "liver": ["liver", "hepatic"],
                "brain": ["brain", "neural", "cns"],
                "muscle": ["muscle", "myocyte"],
                "blood": ["blood", "hematopoietic"]
            }
            for tissue, keywords in tissues.items():
                if any(kw in context_lower for kw in keywords):
                    return tissue
        
        # Alpha/threshold inference
        if variable in ["alpha", "threshold"]:
            # Look for patterns like "p < 0.05" or "alpha = 0.01"
            import re
            patterns = [
                r'p\s*[<>=]\s*0\.(\d+)',
                r'alpha\s*=\s*0\.(\d+)',
                r'fdr\s*[<>=]\s*0\.(\d+)',
                r'threshold\s*:?\s*0?\.(\d+)'
            ]
            for pattern in patterns:
                match = re.search(pattern, context_lower)
                if match:
                    return f"0.{match.group(1)}"
        
        # Data type inference
        if variable == "data_type":
            types = {
                "RNA-seq": ["rna-seq", "rnaseq", "rna sequencing"],
                "microarray": ["microarray", "array"],
                "proteomics": ["proteomics", "mass spec", "ms data"],
                "ChIP-seq": ["chip-seq", "chipseq"]
            }
            for dtype, keywords in types.items():
                if any(kw in context_lower for kw in keywords):
                    return dtype
        
        return None
    
    def _generate_question_text(self, variable: str, config: Any) -> str:
        """Generate human-readable question for variable"""
        question_templates = {
            "organism": "What organism/species are you working with?",
            "contrast": "What is the comparison/contrast you want to analyze?",
            "alpha": "What significance threshold (alpha) should be used?",
            "ont": "Which ontology should be used for enrichment analysis?",
            "tissue_type": "What tissue or organ type are you targeting?",
            "cargo_size": "What is the size of your genetic payload?",
            "delivery_mode": "Are you planning in vivo (in patient) or ex vivo (in cells) delivery?",
            "safety_profile": "What safety constraints should be considered?",
            "domain": "What is your research domain?",
            "scope": "What is the scope of your analysis?",
            "depth": "How deep/detailed should the analysis be?"
        }
        
        return question_templates.get(variable, f"What is the value for {variable}?")
    
    def get_next_questions(self, n: int = 3) -> List[FacetQuestion]:
        """Get the next N most valuable questions to ask"""
        unanswered = [q for q in self.questions if not q.asked]
        return unanswered[:n]
    
    def record_answer(self, variable: str, answer: str):
        """Record an answer and update TCG"""
        self.answered_vars[variable] = answer
        
        # Mark question as answered
        for q in self.questions:
            if q.variable_name == variable:
                q.asked = True
                q.answer = answer
                break
        
        # Update affected nodes in TCG
        affected = self._find_affected_nodes(variable)
        for node_id in affected:
            if node_id in self.tcg.nodes:
                node = self.tcg.nodes[node_id]
                if "resolved_slots" not in node.parameters:
                    node.parameters["resolved_slots"] = {}
                node.parameters["resolved_slots"][variable] = answer
    
    def get_voi_summary(self) -> Dict[str, Any]:
        """Get summary of VOI analysis"""
        total_questions = len(self.questions)
        answered = sum(1 for q in self.questions if q.asked)
        inferred = sum(1 for q in self.questions if q.can_infer and not q.asked)
        critical = sum(1 for q in self.questions if q.importance == "critical")
        
        return {
            "total_questions": total_questions,
            "answered": answered,
            "inferred": inferred,
            "remaining": total_questions - answered,
            "critical_questions": critical,
            "avg_voi": sum(q.voi_score for q in self.questions) / total_questions if total_questions else 0,
            "questions_by_importance": {
                "critical": [q.question for q in self.questions if q.importance == "critical"],
                "high": [q.question for q in self.questions if q.importance == "high"],
                "medium": [q.question for q in self.questions if q.importance == "medium"]
            }
        }


class InformationAwareController:
    """
    Main controller that integrates Uncertainty Gate, TCG, and VOI
    Decides whether to disambiguate and what to ask
    """
    
    def __init__(self):
        from uncertainty_gate import UncertaintyGate
        from task_causal_graph import TCGTemplateLibrary
        
        self.uncertainty_gate = UncertaintyGate()
        self.tcg_library = TCGTemplateLibrary()
    
    async def process_query(
        self, 
        query: str, 
        context: Optional[str] = None,
        available_artifacts: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Main entry point: decide how to handle a query
        """
        # Step 1: Assess uncertainty
        uncertainty = self.uncertainty_gate.assess_uncertainty(
            query, context, available_artifacts
        )
        
        # Step 2: Select appropriate TCG template
        template_id = self.tcg_library.select_template_for_query(query, context)
        template_info = self.tcg_library.get_template(template_id)
        
        # Step 3: Determine strategy based on uncertainty
        if uncertainty.need_disambiguation:
            # High uncertainty - need objective clusters and clarifying questions
            strategy = "disambiguate"
            
            # Create preliminary TCG to identify critical questions
            tcg = self.tcg_library.instantiate_template(template_id, {})
            if tcg and template_info:
                voi_selector = VOIDrivenQuestionSelector(tcg)
                slots = template_info.get("slots", [])
                slot_vars = {slot: {} for slot in slots}
                critical_questions = voi_selector.identify_critical_questions(
                    slot_vars, context
                )
            else:
                critical_questions = []
            
            return {
                "strategy": strategy,
                "uncertainty_score": uncertainty.total_score,
                "confidence_level": uncertainty.confidence_level,
                "need_disambiguation": True,
                "reasons": [f.reasons for f in uncertainty.factors],
                "critical_missing": uncertainty.critical_missing,
                "recommended_missing": uncertainty.recommended_missing,
                "template_id": template_id,
                "template_name": template_info["name"],
                "critical_questions": [
                    {
                        "question": q.question,
                        "variable": q.variable_name,
                        "importance": q.importance,
                        "voi_score": q.voi_score,
                        "can_infer": q.can_infer,
                        "inferred_value": q.inference_source
                    }
                    for q in critical_questions[:5]  # Top 5
                ],
                "can_proceed_with_defaults": len(uncertainty.critical_missing) == 0
            }
        
        else:
            # Low uncertainty - can proceed directly with planning
            strategy = "plan_directly"
            
            # Try to instantiate template with inferred values
            slot_values = {}
            for slot in template_info["slots"]:
                # Try to infer from context
                inferred = self._try_infer_slot(slot, context)
                if inferred:
                    slot_values[slot] = inferred
            
            tcg = self.tcg_library.instantiate_template(template_id, slot_values)
            
            if tcg:
                # Validate and create execution plan
                is_valid, errors = tcg.validate()
                if is_valid:
                    execution_plan = tcg.to_execution_plan()
                else:
                    execution_plan = []
            else:
                execution_plan = []
            
            return {
                "strategy": strategy,
                "uncertainty_score": uncertainty.total_score,
                "confidence_level": uncertainty.confidence_level,
                "need_disambiguation": False,
                "template_id": template_id,
                "template_name": template_info["name"],
                "inferred_slots": slot_values,
                "execution_plan": execution_plan,
                "notes": uncertainty.get_decision_explanation(uncertainty)
            }
    
    def _try_infer_slot(self, slot: str, context: Optional[str]) -> Optional[str]:
        """Try to infer a slot value from context"""
        if not context:
            return None
        
        # Use same logic as VOI selector
        selector = VOIDrivenQuestionSelector(None)  # No TCG needed for this
        return selector._try_infer_from_context(slot, context)


# Global instance
info_controller = InformationAwareController()