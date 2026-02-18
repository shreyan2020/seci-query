import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from models import PersonaPayload
from ollama_client import ollama

PERSONA_ROOT = Path(os.getenv("PERSONA_ROOT", "data/personas"))
MAX_TRANSCRIPT_CHARS = int(os.getenv("MAX_TRANSCRIPT_CHARS", "120000"))
CHUNK_SIZE = int(os.getenv("PERSONA_CHUNK_SIZE", "10000"))


def _schema_hint() -> str:
    return (
        "{"
        '"persona_id":"string",'
        '"scope_id":"string",'
        '"role":"string|unknown",'
        '"domain_expertise":{"biotech":"novice|intermediate|expert|unknown","stats":"novice|intermediate|expert|unknown","coding":"novice|intermediate|expert|unknown"},'
        '"goals":["string"],'
        '"constraints":{"time_sensitivity":"low|medium|high|unknown","compliance_posture":"strict|moderate|flexible|unknown","risk_tolerance":"low|medium|high|unknown"},'
        '"preferences":{"output_format":"steps|table|narrative|mixed|unknown","citation_need":"low|medium|high|unknown","verbosity":"low|medium|high|unknown"},'
        '"decision_style":"exploratory|confirmatory|production|unknown",'
        '"trust_profile":{"default_reliance":"low|medium|high|unknown","verification_habits":["string"]},'
        '"taboo_or_redlines":["string"],'
        '"key_quotes":[{"quote":"string","interview_id":1}],'
        '"evidence":{"support":[{"claim":"string","interview_id":1,"span_hint":"string"}]}'
        "}"
    )


def _compose_transcripts(interviews: List[Dict[str, Any]], max_chars: int) -> str:
    parts: List[str] = []
    used = 0
    for item in interviews:
        text = item.get("transcript_text") or ""
        if not text and item.get("transcript_path"):
            path = Path(item["transcript_path"])
            if path.exists() and path.is_file():
                text = path.read_text(encoding="utf-8", errors="replace")
        block = f"[interview_id={item['id']}]\n{text}\n"
        if used + len(block) > max_chars:
            remaining = max_chars - used
            if remaining <= 0:
                break
            block = block[:remaining]
        parts.append(block)
        used += len(block)
    return "\n".join(parts)


def _chunk_text(text: str, chunk_size: int) -> List[str]:
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    idx = 0
    while idx < len(text):
        chunks.append(text[idx : idx + chunk_size])
        idx += chunk_size
    return chunks


async def _extract_fragment(scope_id: str, persona_name: str, chunk: str, chunk_index: int) -> Dict[str, Any]:
    prompt = (
        "SYSTEM:\n"
        "You extract a user persona from interview transcripts. "
        "Output MUST be valid JSON matching the schema. Use only evidence from transcripts; if unknown, use 'unknown'.\n\n"
        "USER:\n"
        f"Schema: {_schema_hint()}\n"
        f"persona_id should be an internal slug and scope_id should be '{scope_id}'.\n"
        f"Persona name: {persona_name}\n"
        f"Transcript chunk index: {chunk_index}\n"
        "Transcripts:\n"
        f"{chunk}\n\n"
        "Return JSON only."
    )
    return await ollama.generate_json(prompt, max_retries=2)


async def _merge_fragments(scope_id: str, persona_name: str, fragments: List[Dict[str, Any]]) -> Dict[str, Any]:
    prompt = (
        "SYSTEM:\n"
        "Merge persona JSON fragments into one final persona JSON that matches schema exactly. "
        "Preserve evidence provenance via interview_id.\n\n"
        "USER:\n"
        f"Schema: {_schema_hint()}\n"
        f"scope_id must be '{scope_id}'.\n"
        f"Persona name: {persona_name}\n"
        "Fragments:\n"
        f"{json.dumps(fragments)}\n\n"
        "Return JSON only."
    )
    return await ollama.generate_json(prompt, max_retries=2)


def build_persona_summary(persona: PersonaPayload) -> str:
    goals = "; ".join(persona.goals[:3]) if persona.goals else "unknown goals"
    redlines = "; ".join(persona.taboo_or_redlines[:2]) if persona.taboo_or_redlines else "none"
    habits = "; ".join(persona.trust_profile.verification_habits[:2]) if persona.trust_profile.verification_habits else "none"
    summary = (
        f"Role: {persona.role}. "
        f"Expertise biotech/stats/coding: {persona.domain_expertise.biotech}/{persona.domain_expertise.stats}/{persona.domain_expertise.coding}. "
        f"Decision style: {persona.decision_style}. "
        f"Constraints: time={persona.constraints.time_sensitivity}, compliance={persona.constraints.compliance_posture}, risk={persona.constraints.risk_tolerance}. "
        f"Preferences: format={persona.preferences.output_format}, citations={persona.preferences.citation_need}, verbosity={persona.preferences.verbosity}. "
        f"Goals: {goals}. "
        f"Verification habits: {habits}. "
        f"Redlines: {redlines}."
    )
    return summary[:1200]


async def extract_persona_from_interviews(
    scope_id: str,
    persona_name: str,
    interviews: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], str, List[Dict[str, Any]]]:
    transcript_text = _compose_transcripts(interviews, MAX_TRANSCRIPT_CHARS)
    if not transcript_text.strip():
        raise ValueError("No interview transcript text available for extraction")

    chunks = _chunk_text(transcript_text, CHUNK_SIZE)
    fragments: List[Dict[str, Any]] = []
    for idx, chunk in enumerate(chunks):
        fragment = await _extract_fragment(scope_id, persona_name, chunk, idx)
        fragments.append(fragment)

    if len(fragments) == 1:
        merged = fragments[0]
    else:
        merged = await _merge_fragments(scope_id, persona_name, fragments)

    payload = PersonaPayload.model_validate(merged)
    summary = build_persona_summary(payload)
    return payload.model_dump(), summary, fragments


def save_persona_snapshot(persona_id: int, payload: Dict[str, Any], fragments: List[Dict[str, Any]]):
    PERSONA_ROOT.mkdir(parents=True, exist_ok=True)
    snapshot_path = PERSONA_ROOT / f"{persona_id}.json"
    snapshot_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    fragment_dir = PERSONA_ROOT / "fragments" / str(persona_id)
    fragment_dir.mkdir(parents=True, exist_ok=True)
    for idx, fragment in enumerate(fragments):
        (fragment_dir / f"fragment_{idx}.json").write_text(json.dumps(fragment, indent=2), encoding="utf-8")
