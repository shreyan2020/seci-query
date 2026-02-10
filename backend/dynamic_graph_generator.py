"""
Dynamic Graph Generator - Creates LLM-powered task causal graphs on-the-fly
No more fixed templates - every graph is unique to the query and user
"""

import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import httpx
from ollama_client import OllamaClient


class NodeType(str, Enum):
    INTENT = "intent"
    DECISION = "decision"
    ACTION = "action"
    OUTPUT = "output"
    VERIFICATION = "verification"


class EdgeType(str, Enum):
    REQUIRES = "requires"
    ENABLES = "enables"
    PRODUCES = "produces"
    VALIDATES = "validates"
    ALTERNATIVE = "alternative"


@dataclass
class DynamicNode:
    """A dynamically generated node"""
    id: str
    node_type: NodeType
    label: str
    description: str
    tool_suggestion: Optional[str] = None
    validation_criteria: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DynamicEdge:
    """A dynamically generated edge"""
    source: str
    target: str
    edge_type: EdgeType
    condition: Optional[str] = None


@dataclass
class DynamicCausalGraph:
    """A completely dynamic task causal graph"""
    query: str
    user_id: str
    nodes: List[DynamicNode]
    edges: List[DynamicEdge]
    uncertainty_score: float
    strategy: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_execution_plan(self) -> List[Dict[str, Any]]:
        """Convert to ordered execution steps"""
        # Topological sort based on edges
        in_degree = {node.id: 0 for node in self.nodes}
        adj = {node.id: [] for node in self.nodes}
        
        for edge in self.edges:
            if edge.edge_type in [EdgeType.REQUIRES, EdgeType.ENABLES]:
                adj[edge.source].append(edge.target)
                in_degree[edge.target] += 1
        
        # Find starting nodes
        ready = [node_id for node_id, deg in in_degree.items() if deg == 0]
        order = []
        
        while ready:
            node_id = ready.pop(0)
            order.append(node_id)
            for neighbor in adj[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    ready.append(neighbor)
        
        # Map back to nodes
        node_map = {node.id: node for node in self.nodes}
        return [
            {
                "step": i + 1,
                "node_id": node_id,
                "type": node_map[node_id].node_type.value,
                "label": node_map[node_id].label,
                "description": node_map[node_id].description,
                "tool": node_map[node_id].tool_suggestion,
                "validation": node_map[node_id].validation_criteria
            }
            for i, node_id in enumerate(order)
            if node_id in node_map
        ]
    
    def to_mermaid(self) -> str:
        """Convert to Mermaid diagram"""
        lines = ["flowchart TD"]
        
        # Add nodes
        for node in self.nodes:
            style_class = node.node_type.value
            safe_id = node.id.replace("-", "_")
            lines.append(f'    {safe_id}["{node.label}"]::{style_class}')
        
        # Add edges
        for edge in self.edges:
            source = edge.source.replace("-", "_")
            target = edge.target.replace("-", "_")
            label = edge.edge_type.value
            if edge.condition:
                label += f" ({edge.condition})"
            lines.append(f'    {source} -->|{label}| {target}')
        
        # Add styles
        lines.extend([
            "    classDef intent fill:#e1f5ff,stroke:#01579b,stroke-width:2px",
            "    classDef decision fill:#fff9c4,stroke:#f57f17,stroke-width:2px",
            "    classDef action fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px",
            "    classDef output fill:#f3e5f5,stroke:#6a1b9a,stroke-width:2px",
            "    classDef verification fill:#fff3e0,stroke:#e65100,stroke-width:2px"
        ])
        
        return "\n".join(lines)


class DynamicGraphGenerator:
    """
    Generates task causal graphs dynamically using LLM
    No templates - every graph is unique to the query and user
    """
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "qwen2.5:7b"):
        self.base_url = base_url
        self.model = model
        self.llm = OllamaClient(base_url=base_url, model=model)

    async def generate_graph(
        self,
        query: str,
        user_id: str,
        context: Optional[str] = None,
        user_history: Optional[List[Dict[str, Any]]] = None,
        uncertainty_score: float = 0.0
    ) -> DynamicCausalGraph:
        """
        Generate a completely dynamic causal graph for a query.
        """
        personalization = ""
        if user_history:
            recent_queries = [h.get("query", "") for h in user_history[-5:]]
            personalization = f"User recent queries: {recent_queries}"

        complexity = "simple" if uncertainty_score < 0.3 else "moderate" if uncertainty_score < 0.6 else "complex"

        prompt = f"""Generate a task causal graph for this query.

Query: "{query}"
{context and f'Context: {context}' or ''}
{personalization}
Complexity: {complexity}
Uncertainty score: {uncertainty_score}

Return JSON:
{{
  "nodes": [
    {{
      "id": "node_id",
      "type": "intent|decision|action|output|verification",
      "label": "Short label",
      "description": "What this step does",
      "tool_suggestion": "Optional tool",
      "validation_criteria": ["Check 1", "Check 2"],
      "parameters": {{}}
    }}
  ],
  "edges": [
    {{
      "source": "node_id",
      "target": "node_id",
      "type": "requires|enables|produces|validates",
      "condition": null
    }}
  ],
  "strategy": "direct|disambiguate",
  "reasoning": "Why this structure was chosen"
}}

Requirements:
- Include at least one intent node
- Include verification nodes where applicable
- Use clear dependencies between steps
"""

        graph_data = await self.llm.generate_json(prompt)

        nodes = [
            DynamicNode(
                id=n["id"],
                node_type=NodeType(n["type"]),
                label=n["label"],
                description=n["description"],
                tool_suggestion=n.get("tool_suggestion"),
                validation_criteria=n.get("validation_criteria", []),
                parameters=n.get("parameters", {})
            )
            for n in graph_data.get("nodes", [])
        ]

        edges = [
            DynamicEdge(
                source=e["source"],
                target=e["target"],
                edge_type=EdgeType(e["type"]),
                condition=e.get("condition")
            )
            for e in graph_data.get("edges", [])
        ]

        return DynamicCausalGraph(
            query=query,
            user_id=user_id,
            nodes=nodes,
            edges=edges,
            uncertainty_score=uncertainty_score,
            strategy=graph_data.get("strategy", "direct"),
            metadata={
                "reasoning": graph_data.get("reasoning", ""),
                "complexity": complexity,
                "node_count": len(nodes),
                "edge_count": len(edges)
            }
        )
    
    async def generate_graph_for_objective(
        self,
        query: str,
        objective: Dict[str, Any],
        user_id: str,
        context: Optional[str] = None,
        uncertainty_score: float = 0.0
    ) -> DynamicCausalGraph:
        """
        Generate a workflow graph for a SPECIFIC selected objective.
        This is called AFTER the user selects an objective from the clusters.
        """
        
        prompt = f"""Generate a detailed workflow graph for this specific objective.

Query: "{query}"
Selected Objective: {objective.get('title', 'Unknown')}
Objective Definition: {objective.get('definition', '')}
Objective Signals: {objective.get('signals', [])}

Create a complete execution workflow with:
- Specific steps needed to achieve this objective
- Tools to use at each step
- Validation checkpoints
- Decision points if alternatives exist

Return JSON:
{{
    "intent": {{
        "id": "intent",
        "label": "Clear intent statement",
        "description": "What we're trying to achieve"
    }},
    "nodes": [
        {{
            "id": "step_1",
            "type": "intent|decision|action|output|verification",
            "label": "Step name",
            "description": "What this step does in detail",
            "tool_suggestion": "Specific tool/API to use",
            "validation_criteria": ["Check 1", "Check 2"],
            "parameters": {{}}
        }}
    ],
    "edges": [
        {{
            "source": "step_1",
            "target": "step_2",
            "type": "requires|enables|produces|validates",
            "condition": null
        }}
    ],
    "reasoning": "Why this workflow structure was chosen"
}}

Requirements:
- Be specific to the objective selected
- Include actual tool names where relevant
- Add verification steps for quality control
- Show dependencies between steps"""

        graph_data = await self.llm.generate_json(prompt)

        nodes = [
            DynamicNode(
                id=n["id"],
                node_type=NodeType(n["type"]),
                label=n["label"],
                description=n["description"],
                tool_suggestion=n.get("tool_suggestion"),
                validation_criteria=n.get("validation_criteria", []),
                parameters=n.get("parameters", {})
            )
            for n in graph_data.get("nodes", [])
        ]

        edges = [
            DynamicEdge(
                source=e["source"],
                target=e["target"],
                edge_type=EdgeType(e["type"]),
                condition=e.get("condition")
            )
            for e in graph_data.get("edges", [])
        ]

        return DynamicCausalGraph(
            query=query,
            user_id=user_id,
            nodes=nodes,
            edges=edges,
            uncertainty_score=uncertainty_score,
            strategy="direct",
            metadata={
                "reasoning": graph_data.get("reasoning", ""),
                "objective_id": objective.get("id"),
                "objective_title": objective.get("title"),
                "node_count": len(nodes),
                "edge_count": len(edges)
            }
        )


# Global instance
dynamic_graph_generator = DynamicGraphGenerator()
