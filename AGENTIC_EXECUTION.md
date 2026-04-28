# Agentic Execution Notes

## What this branch adds

This branch extends the biotech workspace beyond static draft generation.

The new execution layer:

- starts an execution run from the current project, persona, objective mode, and workspace state
- processes the run through staged reasoning steps
- persists execution runs and timeline events in SQLite
- applies the enriched work template and refreshed plan back into the workspace
- shows run progress in the frontend with polling
- pre-fills some manual-heavy fields such as citation rows and boundary/judgment suggestions

## Why this shape

The code is intentionally split into:

- a persisted run/event contract
- a backend execution runtime
- a frontend execution timeline

That separation lets us swap the execution engine later without changing the UI contract.

## Recommended next library

The strongest next-step library fit is `PydanticAI`.

Why:

- the backend already uses FastAPI and Pydantic heavily
- the app depends on structured JSON outputs more than free-form agent chat
- the current local model path is Ollama, which PydanticAI supports
- the project will likely benefit from multi-agent handoffs and graph-style control later
- PydanticAI also has official UI streaming and durable-execution paths if the workflow becomes longer-running

## Suggested adoption path

1. Keep the current persisted run/event API as the stable app contract.
2. Replace stage internals in `backend/agent_execution.py` with PydanticAI agents.
3. Move polling to streaming once the event protocol is ready.
4. Add durable execution only after the workflow genuinely needs resume/retry across restarts.

## Current runtime behavior

The first version runs these stages:

1. tool-assisted enrichment
2. scope framing
3. evidence and gap synthesis
4. validation design
5. proposal drafting
6. final plan synthesis

## Tool support

The execution runtime can now use tools with local Ollama models where the selected model supports tool calling.

Current tools:

- `search_pubmed`
- `read_local_pdf`

There is also a dedicated literature-fetch endpoint for testing and for reducing manual entry before the full execution run:

- `POST /api/projects/{project_id}/literature`

This endpoint returns citation-ready `findings`, a `tool_trace` object, and an objective-conditioned processing layer:

- `objective_lens`: how the selected objective cluster conditioned the read
- `processing_summary`: what was fetched, how it was interpreted, and what still depends on user judgment
- `elicitation_questions`: prompts for transferability, feasibility, boundary conditions, and evidence priority

The frontend shows this processing layer above the literature table. Users can answer the elicitation prompts and capture those answers as `judgment_calls`, so tacit project knowledge becomes part of the saved work template instead of staying in the user's head.

The trace is the easiest way to confirm the tool path actually ran.

Before PubMed is called, the search layer now reformulates natural-language research questions into compact PubMed-style queries. The reformulation can use:

- the user's initial literature question
- project goal, product, and host
- selected objective title, definition, and signals
- clarifying answers, reasoning notes, and structured work-template content

This matters because PubMed often returns zero records for a full paragraph question, while a compact query such as `flavonoids yeast microbial production improvement synthesis` returns relevant papers.

## Workspace memory

The app now has a central workspace memory layer intended to support current state saving and future handoff/onboarding.

Backend contract:

- `GET /api/workspace-memory/{workspace_key}`
- `PUT /api/workspace-memory/{workspace_key}`
- `POST /api/workspace-memory/infer`

The memory record stores:

- `explicit_state`: selected objective, collaborator/persona, user answers, context, evidence, generated plans, and other visible UI state
- `tacit_state`: reviewable inferred assumptions, constraints, preferences, and handoff-relevant knowledge
- `handoff_summary`: a concise onboarding summary for future collaborators

Tacit items are intentionally reviewable. Each item has evidence, confidence, status (`inferred`, `confirmed`, `edited`, `rejected`), and an optional reviewer note. This prevents hidden LLM interpretation from silently becoming project truth.

The runtime also has a deterministic fallback path, so even if the local model does not call tools well, it can still:

- search PubMed from the active question
- ingest local PDFs when the notes contain explicit PDF file paths

This is meant to be the first usable execution layer, not the final orchestration system.
