import httpx
import inspect
import json
import os
from typing import Optional, Dict, Any, List, Callable
from models import Objective, EvidenceItem

class OllamaClient:
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = base_url or os.getenv("OLLAMA_URL") or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        top_p: float = 0.9,
        model: Optional[str] = None,
    ) -> str:
        """Generate text from Ollama model."""
        payload = {
            "model": model or self.model,
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
            active_model = model or self.model
            if response.status_code == 404 and active_model.endswith("-instruct"):
                fallback_model = active_model.replace("-instruct", "")
                payload["model"] = fallback_model
                response = await client.post(f"{self.base_url}/api/generate", json=payload)
                if response.is_success:
                    if model is None:
                        self.model = fallback_model
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
    
    async def generate_json(
        self,
        prompt: str,
        max_retries: int = 1,
        temperature: float = 0.7,
        top_p: float = 0.9,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate and parse JSON from Ollama with retry logic."""
        initial_prompt = f"{prompt}\n\nIMPORTANT: Return ONLY valid JSON. No markdown, no code blocks, no explanation."
        response_text = ""
        
        for attempt in range(max_retries + 1):
            if attempt == 0:
                response_text = await self.generate(
                    initial_prompt,
                    temperature=temperature,
                    top_p=top_p,
                    model=model,
                )
            else:
                retry_prompt = f"{initial_prompt}\n\nYour previous output was invalid JSON. Please fix it and return ONLY valid JSON.\n\nPrevious invalid output:\n{response_text}"
                response_text = await self.generate(
                    retry_prompt,
                    temperature=temperature,
                    top_p=top_p,
                    model=model,
                )
            
            try:
                return self._extract_json(response_text)
            except json.JSONDecodeError as e:
                print(f"DEBUG: JSON parse error on attempt {attempt + 1}: {e}")
                print(f"DEBUG: Response text: {response_text[:500]}...")
                if attempt == max_retries:
                    raise ValueError(f"Failed to parse JSON after {max_retries + 1} attempts. Last error: {e}. Response: {response_text[:200]}") from e
                continue
        
        raise ValueError("Unexpected error in JSON generation")

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
        top_p: float = 0.9,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
            },
        }
        if tools:
            payload["tools"] = tools

        timeout = httpx.Timeout(300.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            return response.json()

    async def run_tool_loop(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tools: List[Dict[str, Any]],
        tool_handlers: Dict[str, Callable[..., Any]],
        model: Optional[str] = None,
        max_rounds: int = 4,
        temperature: float = 0.2,
        top_p: float = 0.9,
    ) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []
        if system_prompt.strip():
            messages.append({"role": "system", "content": system_prompt.strip()})
        messages.append({"role": "user", "content": user_prompt.strip()})

        for _ in range(max_rounds):
            response = await self.chat(
                messages=messages,
                tools=tools,
                temperature=temperature,
                top_p=top_p,
                model=model,
            )
            message = response.get("message") or {}
            assistant_message = {
                "role": "assistant",
                "content": message.get("content") or "",
            }
            if message.get("thinking"):
                assistant_message["thinking"] = message.get("thinking")
            if message.get("tool_calls"):
                assistant_message["tool_calls"] = message.get("tool_calls")
            messages.append(assistant_message)

            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                break

            for call in tool_calls:
                function = call.get("function") or {}
                name = str(function.get("name") or "").strip()
                raw_arguments = function.get("arguments") or {}
                if isinstance(raw_arguments, str):
                    try:
                        raw_arguments = json.loads(raw_arguments)
                    except json.JSONDecodeError:
                        raw_arguments = {}
                handler = tool_handlers.get(name)
                if not handler:
                    result: Any = {"error": f"unknown_tool:{name}"}
                else:
                    try:
                        if inspect.iscoroutinefunction(handler):
                            result = await handler(**raw_arguments)
                        else:
                            result = handler(**raw_arguments)
                    except Exception as exc:
                        result = {"error": str(exc)}
                messages.append(
                    {
                        "role": "tool",
                        "tool_name": name,
                        "content": json.dumps(result),
                    }
                )

        return messages

    def collect_tool_messages(self, messages: List[Dict[str, Any]]) -> str:
        chunks: List[str] = []
        for message in messages:
            if message.get("role") != "tool":
                continue
            name = str(message.get("tool_name") or "tool").strip()
            content = str(message.get("content") or "").strip()
            if not content:
                continue
            chunks.append(f"Tool {name} result:\n{content}")
        return "\n\n".join(chunks)

    async def ollama_generate(
        self,
        prompt: str,
        temperature: float = 0.2,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        schema_hint = ""
        if json_schema is not None:
            schema_hint = f"\nJSON Schema hint:\n{json.dumps(json_schema)}"
        full_prompt = (
            f"{prompt}{schema_hint}\n\n"
            "Return ONLY valid JSON. No prose."
        )
        text = await self.generate(full_prompt, temperature=temperature)
        return self._extract_json(text)

    def _extract_json(self, response_text: str) -> Dict[str, Any]:
        json_part = response_text.strip()
        if "```json" in json_part:
            json_part = json_part.split("```json")[1].split("```")[0].strip()
        elif "```" in json_part:
            json_part = json_part.split("```")[1].split("```")[0].strip()

        if not json_part.startswith(("{", "[")):
            start_idx = min(
                (json_part.find("{") if json_part.find("{") != -1 else len(json_part)),
                (json_part.find("[") if json_part.find("[") != -1 else len(json_part)),
            )
            if start_idx < len(json_part):
                json_part = json_part[start_idx:]

        if json_part.startswith("{"):
            brace_count = 0
            for i, char in enumerate(json_part):
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        json_part = json_part[: i + 1]
                        break

        parsed = json.loads(json_part)
        if not isinstance(parsed, dict):
            raise json.JSONDecodeError("Expected JSON object", json_part, 0)
        return parsed
    
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
            evidence_text = "\nEvidence to incorporate:\n" + "\n".join(f"- {snippet}" for snippet in evidence_snippets)
        
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

    def get_agentic_plan_prompt(
        self,
        query: str,
        objective: Objective,
        persona_summary: str,
        facet_answers: Dict[str, str],
        context_blob: Optional[str] = None,
    ) -> str:
        facet_block = "\n".join(f"- {k}: {v}" for k, v in facet_answers.items()) if facet_answers else "- none"
        context_block = context_blob.strip() if context_blob else "none"

        return f"""You are an elite planning agent. Build an actionable, evidence-aware execution plan.

User query: "{query}"
Selected objective cluster:
- id: {objective.id}
- title: {objective.title}
- subtitle: {objective.subtitle}
- definition: {objective.definition}
- signals: {", ".join(objective.signals)}

Persona summary:
{persona_summary}

Facet answers:
{facet_block}

Additional context:
{context_block}

Planning requirements:
1) Produce a concrete multi-step plan (5-9 steps) that serves the selected objective.
2) Explain WHY each step was chosen and how it maps to objective + persona.
3) Include examples or factual anchors per step.
4) Include dependencies, expected outcomes, and confidence (0..1) for each step.
5) Include risks + mitigations and measurable success criteria.
6) Keep text concise but specific.

Return ONLY valid JSON using this exact shape:
{{
  "plan": {{
    "plan_title": "string",
    "strategy_summary": "string",
    "success_criteria": ["string"],
    "assumptions": ["string"],
    "risks": [{{"risk": "string", "mitigation": "string"}}],
    "steps": [
      {{
        "id": "step_1",
        "title": "string",
        "description": "string",
        "why_this_step": "string",
        "objective_link": "string",
        "persona_link": "string",
        "evidence_facts": ["string"],
        "examples": ["string"],
        "dependencies": ["step_1"],
        "source_refs": ["S1 or citation/source id"],
        "gap_refs": ["gap id or gap theme"],
        "judgment_refs": ["judgment id or stance"],
        "validation_refs": ["validation id, target, method, or tool result"],
        "expected_outcome": "string",
        "confidence": 0.75
      }}
    ]
  }}
}}

Return ONLY valid JSON. No markdown, no code blocks."""

    def get_project_persona_generation_prompt(self, project: Dict[str, Any]) -> str:
        return f"""You are designing a product-specific biotech project team.

Project brief:
- name: {project.get("name")}
- end_product: {project.get("end_product")}
- target_host: {project.get("target_host")}
- project_goal: {project.get("project_goal")}
- raw_material_focus: {project.get("raw_material_focus") or "none"}
- notes: {project.get("notes") or "none"}

Task:
Generate 4 to 6 distinct personas tailored to THIS product program. They should collectively cover the full workflow,
including raw materials or sourcing, strain/pathway design, upstream process, downstream recovery, and economics or program gating.
Make the personas product-specific when the brief suggests a specialized concern. For example, if the product implies precursor,
toxicity, extraction, purification, or formulation issues, reflect that in the persona names and focus areas.
Include one persona that is explicitly strong at literature, benchmark, or evidence synthesis so the team can answer questions
about successful strategies, examples, latest improvement options, and open technical challenges.

Allowed workflow_stage values:
- feedstock
- strain_engineering
- upstream_process
- downstream_processing
- economics
- regulatory_quality
- analytics

Enum rules:
- domain_expertise values must be one of: novice, intermediate, expert, unknown
- time_sensitivity, risk_tolerance, citation_need, verbosity must be one of: low, medium, high, unknown
- compliance_posture must be one of: flexible, moderate, strict, unknown
- output_format must be one of: steps, table, narrative, mixed, unknown
- decision_style must be one of: exploratory, confirmatory, production, unknown
- default_reliance must be one of: low, medium, high, unknown

Return ONLY valid JSON with this exact structure:
{{
  "personas": [
    {{
      "name": "string",
      "workflow_stage": "feedstock",
      "focus_area": "string",
      "starter_questions": ["string", "string"],
      "role": "string",
      "domain_expertise": {{"biotech": "expert", "stats": "intermediate", "coding": "unknown"}},
      "goals": ["string", "string", "string"],
      "constraints": {{"time_sensitivity": "medium", "compliance_posture": "moderate", "risk_tolerance": "medium"}},
      "preferences": {{"output_format": "mixed", "citation_need": "medium", "verbosity": "medium"}},
      "decision_style": "production",
      "trust_profile": {{"default_reliance": "medium", "verification_habits": ["string", "string"]}},
      "taboo_or_redlines": ["string"],
      "workflow_focus": ["string", "string", "string"]
    }}
  ]
}}

Requirements:
1) Every persona must have a concrete name, not a generic label like Persona 1.
2) Keep the team tightly tied to the product brief.
3) Use short, operational focus areas and starter questions.
4) Ensure the set of personas covers the full workflow without near-duplicates.
5) At least one persona should use workflow_stage="analytics" and focus on literature or benchmark reasoning.

Return ONLY valid JSON. No markdown, no code blocks."""

    def get_project_plan_prompt(
        self,
        project: Dict[str, Any],
        persona_summary: str,
        focus_question: Optional[str] = None,
        notes: Optional[str] = None,
        clarifying_answers: Optional[Dict[str, str]] = None,
        reasoning_notes: Optional[str] = None,
        work_template_summary: Optional[str] = None,
    ) -> str:
        focus = focus_question.strip() if focus_question else "Build the highest-leverage next-step workflow for this program."
        note_block = notes.strip() if notes else "none"
        answer_block = (
            "\n".join(f"- {question}: {answer}" for question, answer in (clarifying_answers or {}).items() if str(answer or "").strip())
            or "none"
        )
        reasoning_block = reasoning_notes.strip() if reasoning_notes else "none"
        work_template_block = work_template_summary.strip() if work_template_summary else "none"

        return f"""You are an elite biotech collaboration agent. Build an editable, concrete working draft.

Project:
- name: {project.get("name")}
- end_product: {project.get("end_product")}
- target_host: {project.get("target_host")}
- project_goal: {project.get("project_goal")}
- raw_material_focus: {project.get("raw_material_focus") or "none"}
- notes: {project.get("notes") or "none"}

Selected planning focus:
{focus}

Persona summary:
{persona_summary}

Clarifying answers:
{answer_block}

Current user reasoning or synthesis:
{reasoning_block}

Structured research work template:
{work_template_block}

Project context and constraints:
{note_block}

Planning requirements:
1) Let the working question determine scope. Do NOT force the full biotech workflow if the question is narrower.
2) Use the persona as a collaborator lens, not a reason to inject unrelated sections.
3) Only include raw materials, sourcing, or cost analysis if the question explicitly asks for it, the project context highlights it, or it is a true blocking dependency.
4) If the working question is about literature, benchmarks, examples, latest improvement options, or open questions, produce an evidence-synthesis draft:
   - scope the search/problem framing
   - identify comparison axes
   - extract successful strategies and benchmark examples
   - map bottlenecks, open questions, and future improvement options
   - convert those findings into next experiments or decisions
5) If the working question is about an experiment plan, focus on hypotheses, interventions, measurements, controls, and decision gates.
6) If the working question is about process or scale-up, focus on operating variables, DOE structure, and transition criteria.
7) Make each step actionable for a biotech program team, not generic advice.
8) Include factual anchors, examples, dependencies, expected outcomes, and confidence (0..1).
9) Include risks, mitigations, and measurable success criteria.
10) Surface assumptions explicitly, especially where data is missing.
11) If a structured research work template is provided, preserve its logic:
   - keep the known vs unknown split visible
   - honor explicit exclusions or boundary conditions from the user
   - translate validation tracks into decision-useful experiments or analyses
   - carry promising proposal seeds forward instead of restarting from zero
12) When the template references analog compounds, neighboring conditions, or transferable examples, state the generalization assumptions explicitly.
13) Make traceability explicit. For every step, include the paper/source refs, gap refs, user judgment refs, and validation refs that justify the step. If a ref is unavailable, leave that array empty rather than inventing a source.

Return ONLY valid JSON using this exact shape:
{{
  "plan": {{
    "plan_title": "string",
    "strategy_summary": "string",
    "success_criteria": ["string"],
    "assumptions": ["string"],
    "risks": [{{"risk": "string", "mitigation": "string"}}],
    "steps": [
      {{
        "id": "step_1",
        "title": "string",
        "description": "string",
        "why_this_step": "string",
        "objective_link": "string",
        "persona_link": "string",
        "evidence_facts": ["string"],
        "examples": ["string"],
        "dependencies": ["step_1"],
        "source_refs": ["S1 or citation/source id"],
        "gap_refs": ["gap id or gap theme"],
        "judgment_refs": ["judgment id or stance"],
        "validation_refs": ["validation id, target, method, or tool result"],
        "expected_outcome": "string",
        "confidence": 0.75
      }}
    ]
  }}
}}

Return ONLY valid JSON. No markdown, no code blocks."""

    def get_persona_refactor_prompt(
        self,
        current_persona_json: Dict[str, Any],
        current_summary: str,
        interaction_events: List[Dict[str, Any]],
    ) -> str:
        compact_events = json.dumps(interaction_events[:200])
        return f"""You are a persona-learning agent.

Task: infer how the user actually behaves from interaction telemetry and explicit feedback,
then output an updated persona JSON following the exact schema below.

Current persona summary:
{current_summary}

Current persona JSON:
{json.dumps(current_persona_json)}

Interaction events (clicks, searches, objective choices, answers, feedback):
{compact_events}

Rules:
1) Prefer explicit feedback over implicit behavior.
2) Update only fields supported by event evidence.
3) Keep unknown when weak evidence.
4) Maintain consistency and provenance-friendly claims.

Return ONLY valid JSON in this shape:
{{
  "persona": {{
    "persona_id": "string",
    "scope_id": "string",
    "role": "string|unknown",
    "domain_expertise": {{"biotech": "novice|intermediate|expert|unknown", "stats": "novice|intermediate|expert|unknown", "coding": "novice|intermediate|expert|unknown"}},
    "goals": ["string"],
    "constraints": {{"time_sensitivity": "low|medium|high|unknown", "compliance_posture": "strict|moderate|flexible|unknown", "risk_tolerance": "low|medium|high|unknown"}},
    "preferences": {{"output_format": "steps|table|narrative|mixed|unknown", "citation_need": "low|medium|high|unknown", "verbosity": "low|medium|high|unknown"}},
    "decision_style": "exploratory|confirmatory|production|unknown",
    "trust_profile": {{"default_reliance": "low|medium|high|unknown", "verification_habits": ["string"]}},
    "taboo_or_redlines": ["string"],
    "key_quotes": [{{"quote": "string", "interview_id": 0}}],
    "evidence": {{"support": [{{"claim": "string", "interview_id": 0, "span_hint": "event"}}]}}
  }},
  "learning_summary": "string"
}}

Return JSON only."""

# Global Ollama client
ollama = OllamaClient()
