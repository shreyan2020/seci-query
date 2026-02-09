"""
Task Causal Graph (TCG) - Planning substrate with dependencies
Formalizes task workflows with explicit dependencies
"""

from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json


class NodeType(str, Enum):
    """Types of nodes in the task causal graph"""
    INTENT = "intent"  # User's goal
    DECISION = "decision"  # Decision variables
    ACTION = "action"  # Executable actions/tools
    ARTIFACT = "artifact"  # Intermediate outputs
    OBSERVATION = "observation"  # Evidence/inputs
    OUTPUT = "output"  # Final results


class EdgeType(str, Enum):
    """Types of edges/dependencies"""
    DEPENDS_ON = "depends_on"  # Cannot execute without
    PRODUCES = "produces"  # Generates output
    REQUIRES = "requires"  # Needs as input
    ENABLES = "enables"  # Makes possible


@dataclass
class TCGNode:
    """A node in the Task Causal Graph"""
    id: str
    node_type: NodeType
    label: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending, ready, running, completed, failed
    
    def is_ready(self, completed_nodes: Set[str]) -> bool:
        """Check if this node is ready to execute"""
        # Will be determined by edges in the graph
        return self.status == "pending"


@dataclass
class TCGEdge:
    """An edge representing dependency in the graph"""
    source: str
    target: str
    edge_type: EdgeType
    condition: Optional[str] = None  # Conditional dependency


@dataclass
class TaskCausalGraph:
    """A complete task causal graph"""
    id: str
    name: str
    description: str
    nodes: Dict[str, TCGNode]
    edges: List[TCGEdge]
    domain: str
    
    def get_dependencies(self, node_id: str) -> List[str]:
        """Get all nodes that must complete before this node"""
        deps = []
        for edge in self.edges:
            if edge.target == node_id and edge.edge_type in [EdgeType.DEPENDS_ON, EdgeType.REQUIRES]:
                deps.append(edge.source)
        return deps
    
    def get_enabled_by(self, node_id: str) -> List[str]:
        """Get all nodes enabled by completing this node"""
        enabled = []
        for edge in self.edges:
            if edge.source == node_id and edge.edge_type in [EdgeType.ENABLES, EdgeType.PRODUCES]:
                enabled.append(edge.target)
        return enabled
    
    def get_ready_nodes(self, completed: Set[str]) -> List[str]:
        """Get all nodes ready to execute"""
        ready = []
        for node_id, node in self.nodes.items():
            if node.status == "pending":
                deps = self.get_dependencies(node_id)
                if all(d in completed for d in deps):
                    ready.append(node_id)
        return ready
    
    def validate(self) -> Tuple[bool, List[str]]:
        """Validate graph invariants"""
        errors = []
        
        # Check for cycles
        visited = set()
        temp_mark = set()
        
        def has_cycle(node_id: str) -> bool:
            if node_id in temp_mark:
                return True
            if node_id in visited:
                return False
            
            temp_mark.add(node_id)
            for edge in self.edges:
                if edge.source == node_id:
                    if has_cycle(edge.target):
                        return True
            temp_mark.remove(node_id)
            visited.add(node_id)
            return False
        
        for node_id in self.nodes:
            if has_cycle(node_id):
                errors.append(f"Cycle detected involving node {node_id}")
        
        # Check for missing nodes
        for edge in self.edges:
            if edge.source not in self.nodes:
                errors.append(f"Edge references missing source: {edge.source}")
            if edge.target not in self.nodes:
                errors.append(f"Edge references missing target: {edge.target}")
        
        # Check for isolated nodes
        connected = set()
        for edge in self.edges:
            connected.add(edge.source)
            connected.add(edge.target)
        
        for node_id in self.nodes:
            if node_id not in connected and len(self.nodes) > 1:
                errors.append(f"Node {node_id} is isolated")
        
        return len(errors) == 0, errors
    
    def to_execution_plan(self) -> List[Dict[str, Any]]:
        """Convert to ordered execution plan"""
        plan = []
        completed = set()
        
        while len(completed) < len(self.nodes):
            ready = self.get_ready_nodes(completed)
            if not ready:
                break  # Deadlock or cycle
            
            for node_id in ready:
                node = self.nodes[node_id]
                plan.append({
                    "step": len(plan) + 1,
                    "node_id": node_id,
                    "type": node.node_type.value,
                    "label": node.label,
                    "description": node.description,
                    "parameters": node.parameters,
                    "dependencies": self.get_dependencies(node_id)
                })
                completed.add(node_id)
        
        return plan


class TCGTemplateLibrary:
    """Library of task causal graph templates for different domains"""
    
    TEMPLATES = {
        "bioinformatics_differential_expression": {
            "name": "Differential Expression Analysis",
            "description": "Complete workflow for DE analysis with enrichment",
            "domain": "bioinformatics",
            "slots": ["organism", "contrast", "alpha", "ont"],
            "graph": {
                "nodes": [
                    {"id": "intent", "type": "intent", "label": "Find differentially expressed genes", "description": "User wants to identify DE genes"},
                    {"id": "load_data", "type": "action", "label": "Load count matrix", "description": "Load expression data"},
                    {"id": "validate", "type": "action", "label": "Validate input", "description": "Check data quality and format"},
                    {"id": "deseq2", "type": "action", "label": "Run DESeq2", "description": "Differential expression analysis"},
                    {"id": "deg_list", "type": "artifact", "label": "DEG list", "description": "List of differentially expressed genes"},
                    {"id": "filter", "type": "action", "label": "Filter DEGs", "description": "Apply significance and fold change filters"},
                    {"id": "filtered_degs", "type": "artifact", "label": "Filtered DEGs", "description": "Significant DEGs only"},
                    {"id": "map_ids", "type": "action", "label": "Map gene IDs", "description": "Convert to appropriate ID format"},
                    {"id": "gene_ids", "type": "artifact", "label": "Mapped gene IDs", "description": "Genes in correct ID space"},
                    {"id": "enrich", "type": "action", "label": "Run enrichGO", "description": "Gene ontology enrichment analysis"},
                    {"id": "enrichment", "type": "artifact", "label": "Enrichment results", "description": "GO term enrichment table"},
                    {"id": "simplify", "type": "action", "label": "Simplify GO", "description": "Remove redundant GO terms"},
                    {"id": "simplified", "type": "artifact", "label": "Simplified GO", "description": "Non-redundant GO terms"},
                    {"id": "report", "type": "output", "label": "Final report", "description": "DE and enrichment summary"}
                ],
                "edges": [
                    {"source": "intent", "target": "load_data", "type": "enables"},
                    {"source": "load_data", "target": "validate", "type": "produces"},
                    {"source": "validate", "target": "deseq2", "type": "enables"},
                    {"source": "deseq2", "target": "deg_list", "type": "produces"},
                    {"source": "deg_list", "target": "filter", "type": "requires"},
                    {"source": "filter", "target": "filtered_degs", "type": "produces"},
                    {"source": "filtered_degs", "target": "map_ids", "type": "requires"},
                    {"source": "map_ids", "target": "gene_ids", "type": "produces"},
                    {"source": "gene_ids", "target": "enrich", "type": "requires"},
                    {"source": "enrich", "target": "enrichment", "type": "produces"},
                    {"source": "enrichment", "target": "simplify", "type": "requires"},
                    {"source": "simplify", "target": "simplified", "type": "produces"},
                    {"source": "simplified", "target": "report", "type": "enables"}
                ]
            }
        },
        
        "biotech_delivery_selection": {
            "name": "Gene Delivery Method Selection",
            "description": "Compare and select delivery methods for gene therapy",
            "domain": "biotech",
            "slots": ["tissue_type", "cargo_size", "delivery_mode", "safety_profile"],
            "graph": {
                "nodes": [
                    {"id": "intent", "type": "intent", "label": "Select delivery method", "description": "Choose optimal gene delivery approach"},
                    {"id": "define_criteria", "type": "decision", "label": "Define selection criteria", "description": "Based on tissue, cargo, and constraints"},
                    {"id": "viral_options", "type": "action", "label": "Evaluate viral vectors", "description": "AAV, lentivirus, adenovirus comparison"},
                    {"id": "nonviral_options", "type": "action", "label": "Evaluate non-viral", "description": "Nanoparticles, electroporation, etc."},
                    {"id": "viral_comparison", "type": "artifact", "label": "Viral comparison", "description": "Table of viral vector options"},
                    {"id": "nonviral_comparison", "type": "artifact", "label": "Non-viral comparison", "description": "Table of non-viral options"},
                    {"id": "safety_check", "type": "action", "label": "Safety assessment", "description": "Evaluate immunogenicity and risks"},
                    {"id": "efficacy_check", "type": "action", "label": "Efficacy assessment", "description": "Evaluate delivery efficiency"},
                    {"id": "tradeoff_analysis", "type": "action", "label": "Tradeoff analysis", "description": "Compare across all criteria"},
                    {"id": "recommendation", "type": "output", "label": "Method recommendation", "description": "Recommended delivery approach"}
                ],
                "edges": [
                    {"source": "intent", "target": "define_criteria", "type": "enables"},
                    {"source": "define_criteria", "target": "viral_options", "type": "enables"},
                    {"source": "define_criteria", "target": "nonviral_options", "type": "enables"},
                    {"source": "viral_options", "target": "viral_comparison", "type": "produces"},
                    {"source": "nonviral_options", "target": "nonviral_comparison", "type": "produces"},
                    {"source": "viral_comparison", "target": "safety_check", "type": "requires"},
                    {"source": "nonviral_comparison", "target": "safety_check", "type": "requires"},
                    {"source": "safety_check", "target": "efficacy_check", "type": "enables"},
                    {"source": "efficacy_check", "target": "tradeoff_analysis", "type": "enables"},
                    {"source": "tradeoff_analysis", "target": "recommendation", "type": "enables"}
                ]
            }
        },
        
        "general_research": {
            "name": "General Research Query",
            "description": "Flexible template for open research questions",
            "domain": "general",
            "slots": ["domain", "scope", "depth"],
            "graph": {
                "nodes": [
                    {"id": "intent", "type": "intent", "label": "Research question", "description": "User's research goal"},
                    {"id": "context_gather", "type": "action", "label": "Gather context", "description": "Collect relevant background"},
                    {"id": "define_approach", "type": "decision", "label": "Define approach", "description": "Choose analytical strategy"},
                    {"id": "search_literature", "type": "action", "label": "Literature search", "description": "Find relevant papers"},
                    {"id": "synthesize", "type": "action", "label": "Synthesize findings", "description": "Combine insights"},
                    {"id": "identify_gaps", "type": "action", "label": "Identify gaps", "description": "Find unanswered questions"},
                    {"id": "recommendations", "type": "output", "label": "Recommendations", "description": "Actionable next steps"}
                ],
                "edges": [
                    {"source": "intent", "target": "context_gather", "type": "enables"},
                    {"source": "context_gather", "target": "define_approach", "type": "enables"},
                    {"source": "define_approach", "target": "search_literature", "type": "enables"},
                    {"source": "search_literature", "target": "synthesize", "type": "produces"},
                    {"source": "synthesize", "target": "identify_gaps", "type": "enables"},
                    {"source": "identify_gaps", "target": "recommendations", "type": "enables"}
                ]
            }
        }
    }
    
    @classmethod
    def get_template(cls, template_id: str) -> Optional[Dict[str, Any]]:
        """Get a template by ID"""
        return cls.TEMPLATES.get(template_id)
    
    @classmethod
    def list_templates(cls, domain: Optional[str] = None) -> List[Dict[str, str]]:
        """List available templates, optionally filtered by domain"""
        templates = []
        for tid, template in cls.TEMPLATES.items():
            if domain is None or template["domain"] == domain:
                templates.append({
                    "id": tid,
                    "name": template["name"],
                    "description": template["description"],
                    "domain": template["domain"],
                    "slots": template["slots"]
                })
        return templates
    
    @classmethod
    def instantiate_template(
        cls, 
        template_id: str, 
        slot_values: Dict[str, Any]
    ) -> Optional[TaskCausalGraph]:
        """Create a concrete TCG from a template with slot values filled"""
        template = cls.get_template(template_id)
        if not template:
            return None
        
        graph_def = template["graph"]
        
        # Create nodes
        nodes = {}
        for node_def in graph_def["nodes"]:
            node_id = node_def["id"]
            # Replace slot values in labels and descriptions
            label = node_def["label"]
            description = node_def["description"]
            
            for slot, value in slot_values.items():
                placeholder = f"{{{slot}}}"
                label = label.replace(placeholder, str(value))
                description = description.replace(placeholder, str(value))
            
            nodes[node_id] = TCGNode(
                id=node_id,
                node_type=NodeType(node_def["type"]),
                label=label,
                description=description,
                parameters={"slot_values": slot_values}
            )
        
        # Create edges
        edges = []
        for edge_def in graph_def["edges"]:
            edges.append(TCGEdge(
                source=edge_def["source"],
                target=edge_def["target"],
                edge_type=EdgeType(edge_def["type"])
            ))
        
        return TaskCausalGraph(
            id=f"{template_id}_{hash(str(slot_values))}",
            name=template["name"],
            description=template["description"],
            nodes=nodes,
            edges=edges,
            domain=template["domain"]
        )
    
    @classmethod
    def select_template_for_query(cls, query: str, context: Optional[str] = None) -> str:
        """Select the most appropriate template for a query"""
        query_lower = query.lower()
        
        # Bioinformatics DE indicators
        de_indicators = ["differential expression", "deseq", "edger", "limma", "degs", "rna-seq"]
        if any(ind in query_lower for ind in de_indicators):
            return "bioinformatics_differential_expression"
        
        # Gene delivery indicators
        delivery_indicators = ["delivery", "vector", "aav", "lentivirus", "transduction", "transfection"]
        if any(ind in query_lower for ind in delivery_indicators):
            return "biotech_delivery_selection"
        
        # Default to general
        return "general_research"


# Global instances
tcg_library = TCGTemplateLibrary()