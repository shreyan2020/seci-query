import httpx
import json
from typing import Optional, Dict, Any, List
from models import (
    AugmentResponse, EvidenceItem, FinalizeResponse,
    QueryType, EnhancedObjective, QueryRefinement, UncertaintyMarker,
    ProgressiveDisclosure, Claim, GroundingReport, ActionItem,
    ConfidenceLevel, SourceQuality, EvidenceType
)

class OllamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434", model: str = "qwen2.5:7b"):
        self.base_url = base_url
        self.model = model
    
    async def generate(self, prompt: str, temperature: float = 0.7, top_p: float = 0.9) -> str:
        """Generate text from Ollama model."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
                "num_predict": 2000  # Limit token generation for speed
            }
        }
        
        timeout = httpx.Timeout(20.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
    
    async def generate_json(self, prompt: str, max_retries: int = 2) -> Dict[str, Any]:
        """Generate and parse JSON from Ollama with retry logic."""
        initial_prompt = (
            f"{prompt}\n\n"
            "Return ONLY valid JSON. No markdown. No trailing commas. "
            "No comments. Use double quotes for all keys and strings."
        )
        response_text = ""
        
        for attempt in range(max_retries + 1):
            if attempt == 0:
                response_text = await self.generate(initial_prompt, temperature=0.2, top_p=0.8)
            else:
                retry_prompt = (
                    f"{initial_prompt}\n\n"
                    f"Fix JSON errors. Return a single JSON object only. "
                    f"Previous: {response_text[:200]}"
                )
                response_text = await self.generate(retry_prompt, temperature=0.1, top_p=0.7)
            
            try:
                json_part = response_text.strip()
                
                if "```json" in json_part:
                    json_part = json_part.split("```json")[1].split("```")[0].strip()
                elif "```" in json_part:
                    json_part = json_part.split("```")[1].split("```")[0].strip()
                
                if not json_part.startswith(('{', '[')):
                    start_idx = min(
                        (json_part.find('{') if json_part.find('{') != -1 else len(json_part)),
                        (json_part.find('[') if json_part.find('[') != -1 else len(json_part))
                    )
                    if start_idx < len(json_part):
                        json_part = json_part[start_idx:]
                
                if json_part.startswith('{'):
                    brace_count = 0
                    for i, char in enumerate(json_part):
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_part = json_part[:i+1]
                                break
                
                return json.loads(json_part)
            except json.JSONDecodeError as e:
                print(f"DEBUG: JSON parse error: {e}")
                if attempt == max_retries:
                    raise ValueError(f"Failed to parse JSON: {e}")
                continue
        
        raise ValueError("Unexpected error")
    
    def get_objectives_prompt(
        self, 
        query: str, 
        query_type: QueryType,
        context: Optional[str] = None, 
        k: int = 5,
        missing_inputs: Optional[List[str]] = None
    ) -> str:
        """Generate optimized, fast prompts for objective generation."""
        context_part = f"Context: {context}\n" if context else ""
        
        return f"""You are an expert at interpreting user queries. Generate {k} distinct objectives.

{context_part}Query: "{query}"
Type: {query_type.value}

Return valid JSON only:
{{
    "objectives": [
        {{
            "id": "obj_1",
            "title": "2-4 words",
            "subtitle": "what this means",
            "definition": "2-3 lines",
            "signals": ["keyword1", "keyword2"],
            "facet_questions": ["question1", "question2"],
            "when_this_objective_is_wrong": "1 line",
            "confidence": "medium",
            "is_speculative": false,
            "summary": {{"tldr": "1 line", "key_tradeoffs": ["tradeoff"], "next_actions": ["action"]}}
        }}
    ],
    "global_questions": ["question1", "question2"],
    "query_refinements": [
        {{"refined_query": "improved query", "what_changed": "brief", "why_it_helps": "benefit", "confidence": "medium"}}
    ]
}}

Be fast and concise."""
    
    def get_augment_prompt(
        self, 
        query: str, 
        objective_id: str, 
        objective_definition: str, 
        context_blob: str
    ) -> str:
        """Generate the prompt for evidence augmentation - simplified."""
        return f"""Extract evidence from context for this query.

Query: "{query}"
Objective: {objective_id}
Definition: "{objective_definition}"

Context:
""" + context_blob + """

Extract 3-5 evidence items. Each item:
- id: ev_1, ev_2, etc.
- snippet: relevant excerpt
- source_quality: primary/review/secondary/anecdotal
- score: 0.0-1.0

Return JSON: {"evidence_items": [...], "need_external_sources": true/false}

Be fast and concise."""

    def get_finalize_prompt(
        self, 
        query: str, 
        objective: EnhancedObjective, 
        answers: Dict[str, str],
        evidence_items: Optional[List[EvidenceItem]] = None
    ) -> str:
        """Generate the prompt for final answer synthesis - simplified."""
        evidence_text = ""
        if evidence_items:
            evidence_text = "\nEvidence:\n" + "\n".join([f"- {e.snippet[:100]}" for e in evidence_items[:3]])
        
        facet_text = "\n".join([f"{q}: {a}" for q, a in answers.items()])
        
        return f"""Generate a concise final answer.

Query: "{query}"
Objective: {objective.title}

User answers:
{facet_text}{evidence_text}

Return JSON:
{{
    "final_answer": "concise answer (3-5 sentences)",
    "progressive_disclosure": {{
        "tldr": "1 sentence summary",
        "key_tradeoffs": ["tradeoff1", "tradeoff2"],
        "next_actions": ["action1", "action2"]
    }},
    "assumptions": ["assumption1"],
    "next_questions": ["followup1", "followup2"]
}}

Be fast and concise. 200 words max."""

# Global Ollama client
ollama = OllamaClient()
