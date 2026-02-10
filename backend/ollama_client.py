import httpx
import json
from typing import Optional, Dict, Any, List
from models import Objective, AugmentResponse, EvidenceItem, FinalizeResponse

class OllamaClient:
    def __init__(self, base_url: str = "http://ollama:11434", model: str = "qwen2.5:7b-instruct"):
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
                "top_p": top_p
            }
        }
        
        # Use longer timeout for LLM generation (5 minutes)
        timeout = httpx.Timeout(300.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
    
    async def generate_json(self, prompt: str, max_retries: int = 1) -> Dict[str, Any]:
        """Generate and parse JSON from Ollama with retry logic."""
        initial_prompt = f"{prompt}\n\nIMPORTANT: Return ONLY valid JSON. No markdown, no code blocks, no explanation."
        response_text = ""
        
        for attempt in range(max_retries + 1):
            if attempt == 0:
                response_text = await self.generate(initial_prompt)
            else:
                retry_prompt = f"{initial_prompt}\n\nYour previous output was invalid JSON. Please fix it and return ONLY valid JSON.\n\nPrevious invalid output:\n{response_text}"
                response_text = await self.generate(retry_prompt)
            
            try:
                # Try to extract JSON from response
                json_part = response_text.strip()
                
                # Remove markdown code blocks
                if "```json" in json_part:
                    json_part = json_part.split("```json")[1].split("```")[0].strip()
                elif "```" in json_part:
                    json_part = json_part.split("```")[1].split("```")[0].strip()
                
                # Try to find JSON object/array if wrapped in text
                if not json_part.startswith(('{', '[')):
                    # Find first { or [
                    start_idx = min(
                        (json_part.find('{') if json_part.find('{') != -1 else len(json_part)),
                        (json_part.find('[') if json_part.find('[') != -1 else len(json_part))
                    )
                    if start_idx < len(json_part):
                        json_part = json_part[start_idx:]
                
                # Try to find end of JSON if followed by text
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
                print(f"DEBUG: JSON parse error on attempt {attempt + 1}: {e}")
                print(f"DEBUG: Response text: {response_text[:500]}...")
                if attempt == max_retries:
                    raise ValueError(f"Failed to parse JSON after {max_retries + 1} attempts. Last error: {e}. Response: {response_text[:200]}")
                continue
        
        raise ValueError("Unexpected error in JSON generation")
    
    def get_objectives_prompt(self, query: str, context: Optional[str] = None, k: int = 5) -> str:
        """Generate the prompt for objective generation."""
        context_part = f"Context: {context}\n\n" if context else ""
        
        return f"""You are an expert at interpreting underspecified user queries.
{context_part}User query: "{query}"

Task:
Generate {k} distinct objectives that could represent different interpretations of what 'best' means.
For each objective, provide:
- id: obj_1..obj_{k}
- title: 2-5 words
- subtitle: what's user is trying to achieve
- definition: 2-4 lines describing the goal
- signals: 4-10 indicative keywords
- facet_questions: 2-4 clarifying questions
- exemplar_answer: 5-10 lines

Also provide 2-4 global questions broadly useful across objectives.

Return ONLY valid JSON with this structure:
{{
    "objectives": [
        {{
            "id": "obj_1",
            "title": "title here",
            "subtitle": "subtitle here",
            "definition": "definition here",
            "signals": ["signal1", "signal2"],
            "facet_questions": ["question1", "question2"],
            "exemplar_answer": "answer here"
        }}
    ],
    "global_questions": ["question1", "question2"]
}}

Return ONLY valid JSON. No markdown, no code blocks."""
    
    def get_augment_prompt(self, query: str, objective_id: str, objective_definition: str, context_blob: str) -> str:
        """Generate the prompt for evidence augmentation."""
        return f"""You are an expert at incorporating external evidence to improve answers based on specific objectives.

Query: "{query}"
Selected objective: {objective_id}
Objective definition: "{objective_definition}"

User context/evidence: "{context_blob}"

Your task:
1. Extract 3-7 evidence bullet points from the context that are most relevant to this objective
2. Rewrite or enhance an answer to incorporate this evidence
3. Return your response as valid JSON

Structure:
{{
    "evidence_items": [
        {{
            "id": "ev_1",
            "type": "note",
            "title": "short descriptive title",
            "snippet": "relevant excerpt from context",
            "source_ref": "user_context",
            "score": 1.0
        }}
    ],
    "augmented_answer": "updated answer using the evidence (or null if no context provided)"
}}

Return ONLY valid JSON. No markdown, no code blocks."""
    
    def get_finalize_prompt(self, query: str, objective: Objective, answers: Dict[str, str], 
                          evidence_items: Optional[List[EvidenceItem]] = None) -> str:
        """Generate the prompt for final answer synthesis."""
        evidence_text = ""
        if evidence_items:
            evidence_snippets = [item.snippet for item in evidence_items]
            evidence_text = f"\nEvidence to incorporate:\n" + "\n".join(f"- {snippet}" for snippet in evidence_snippets)
        
        facet_answers_text = "\n".join(f"- {question}: {answer}" for question, answer in answers.items())
        
        return f"""You are an expert at synthesizing comprehensive answers based on clarified objectives and user preferences.

Query: "{query}"
Selected objective: {objective.title} ({objective.subtitle})
Objective definition: "{objective.definition}"

User's answers to facet questions:
{facet_answers_text}{evidence_text}

Generate a final answer that:
1. Is consistent with the selected objective
2. Incorporates the user's specific answers to facet questions
3. Uses the evidence if provided
4. Clearly states any assumptions made
5. Suggests relevant follow-up questions

Return your response as valid JSON:
{{
    "final_answer": "comprehensive answer addressing the query",
    "assumptions": ["assumption1", "assumption2"],
    "next_questions": ["followup1", "followup2"]
}}

Return ONLY valid JSON. No markdown, no code blocks."""

# Global Ollama client
ollama = OllamaClient()