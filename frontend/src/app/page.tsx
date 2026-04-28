'use client';

import React, { useState } from 'react';
import Link from 'next/link';

// API types - matching backend models
interface Objective {
  id: string;
  title: string;
  subtitle: string;
  definition: string;
  signals: string[];
  facet_questions: string[];
  exemplar_answer: string;
}

interface EvidenceItem {
  id: string;
  type: string;
  title: string;
  snippet: string;
  source_ref: string;
  score: number;
}

interface ObjectivesResponse {
  objectives: Objective[];
  global_questions: string[];
}

interface AugmentResponse {
  evidence_items: EvidenceItem[];
  augmented_answer?: string;
}

interface FinalizeResponse {
  final_answer: string;
  assumptions: string[];
  next_questions: string[];
}

interface PlanRisk {
  risk: string;
  mitigation: string;
}

interface PlanStep {
  id: string;
  title: string;
  description: string;
  why_this_step: string;
  objective_link: string;
  persona_link: string;
  evidence_facts: string[];
  examples: string[];
  dependencies: string[];
  expected_outcome: string;
  confidence: number;
}

interface AgenticPlan {
  plan_title: string;
  strategy_summary: string;
  success_criteria: string[];
  assumptions: string[];
  risks: PlanRisk[];
  steps: PlanStep[];
}

interface GeneratePlanResponse {
  plan: AgenticPlan;
}

interface PersonaItem {
  id: number;
  name: string;
  scope: string;
}

interface TacitMemoryItem {
  id: string;
  label: string;
  inference: string;
  evidence: string[];
  confidence: number;
  status: 'inferred' | 'confirmed' | 'rejected' | 'edited';
  reviewer_note?: string | null;
}

interface WorkspaceMemory {
  workspace_key: string;
  scope: string;
  explicit_state: Record<string, unknown>;
  tacit_state: TacitMemoryItem[];
  handoff_summary: string;
  updated_at?: string | null;
}

// API client
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function generateObjectives(query: string, context?: string, k: number = 5, personaId?: number): Promise<ObjectivesResponse> {
  const response = await fetch(`${API_BASE}/objectives`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, context, k, persona_id: personaId })
  });
  if (!response.ok) throw new Error('Failed to generate objectives');
  return response.json();
}

async function augmentWithContext(query: string, objectiveId: string, objectiveDefinition: string, contextBlob: string, personaId?: number): Promise<AugmentResponse> {
  const response = await fetch(`${API_BASE}/augment`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, objective_id: objectiveId, objective_definition: objectiveDefinition, context_blob: contextBlob, persona_id: personaId })
  });
  if (!response.ok) throw new Error('Failed to augment with context');
  return response.json();
}

async function finalizeAnswer(query: string, objective: Objective, answers: Record<string, string>, contextBlob?: string, evidenceItems?: EvidenceItem[], personaId?: number): Promise<FinalizeResponse> {
  const response = await fetch(`${API_BASE}/finalize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, objective, answers, context_blob: contextBlob, evidence_items: evidenceItems, persona_id: personaId })
  });
  if (!response.ok) throw new Error('Failed to finalize answer');
  return response.json();
}

async function generateAgenticPlan(
  query: string,
  objective: Objective,
  personaId: number,
  facetAnswers: Record<string, string>,
  contextBlob?: string
): Promise<GeneratePlanResponse> {
  const response = await fetch(`${API_BASE}/api/plans/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      objective,
      persona_id: personaId,
      facet_answers: facetAnswers,
      context_blob: contextBlob,
    }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to generate agentic plan');
  }
  return response.json();
}

async function saveWorkspaceMemory(workspaceKey: string, payload: {
  scope: string;
  explicit_state: Record<string, unknown>;
  tacit_state: TacitMemoryItem[];
  handoff_summary: string;
}): Promise<{ memory: WorkspaceMemory | null }> {
  const response = await fetch(`${API_BASE}/api/workspace-memory/${encodeURIComponent(workspaceKey)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error('Failed to save workspace memory');
  return response.json();
}

async function getWorkspaceMemory(workspaceKey: string): Promise<{ memory: WorkspaceMemory | null }> {
  const response = await fetch(`${API_BASE}/api/workspace-memory/${encodeURIComponent(workspaceKey)}`, { cache: 'no-store' });
  if (!response.ok) throw new Error('Failed to load workspace memory');
  return response.json();
}

async function inferWorkspaceMemory(payload: {
  workspace_key: string;
  scope: string;
  explicit_state: Record<string, unknown>;
  existing_tacit_state: TacitMemoryItem[];
}): Promise<{ tacit_state: TacitMemoryItem[]; handoff_summary: string }> {
  const response = await fetch(`${API_BASE}/api/workspace-memory/infer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error('Failed to infer workspace memory');
  return response.json();
}

// Original UI components and styling patterns
function classNames(...xs: Array<string | false | null | undefined>) {
  return xs.filter(Boolean).join(' ');
}

function Pill({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full border border-neutral-200 bg-neutral-50 px-2 py-0.5 text-xs text-neutral-700">
      {children}
    </span>
  );
}

function SectionTitle({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-3">
      <div className="text-sm font-semibold text-neutral-900">{title}</div>
      {subtitle ? <div className="text-xs text-neutral-600">{subtitle}</div> : null}
    </div>
  );
}

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center py-8">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-neutral-900"></div>
    </div>
  );
}

function WorkspaceMemoryPanel({
  workspaceKey,
  memoryStatus,
  tacitState,
  handoffSummary,
  onInfer,
  onUpdateTacitItem,
  inferring,
}: {
  workspaceKey: string;
  memoryStatus: string;
  tacitState: TacitMemoryItem[];
  handoffSummary: string;
  onInfer: () => void;
  onUpdateTacitItem: (id: string, patch: Partial<TacitMemoryItem>) => void;
  inferring: boolean;
}) {
  return (
    <div className="rounded-2xl border border-amber-200 bg-gradient-to-br from-amber-50 via-white to-stone-50 p-4 shadow-sm">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="text-sm font-semibold text-neutral-900">Workspace Memory</div>
          <div className="mt-1 text-xs leading-5 text-neutral-600">
            Central state for explicit selections and reviewable tacit knowledge. This is the layer future handoff and onboarding flows should use.
          </div>
          <div className="mt-1 text-[11px] text-neutral-500">Key: {workspaceKey} · {memoryStatus}</div>
        </div>
        <button
          onClick={onInfer}
          disabled={inferring}
          className="rounded-xl bg-amber-900 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-amber-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {inferring ? 'Inferring...' : 'Infer tacit state'}
        </button>
      </div>

      {handoffSummary && (
        <div className="mt-3 rounded-xl border border-amber-200 bg-white/80 p-3">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-amber-800">Handoff summary</div>
          <div className="mt-1 text-sm leading-6 text-neutral-800">{handoffSummary}</div>
        </div>
      )}

      <div className="mt-3 space-y-2">
        {tacitState.length === 0 ? (
          <div className="rounded-xl border border-dashed border-amber-200 bg-white/65 p-3 text-sm text-neutral-600">
            No tacit memory items yet. Run inference after selecting an objective, collaborator, or adding answers/context.
          </div>
        ) : (
          tacitState.map((item) => (
            <div key={item.id} className="rounded-xl border border-amber-100 bg-white p-3">
              <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                <div>
                  <div className="text-sm font-semibold text-neutral-900">{item.label}</div>
                  <div className="mt-1 text-sm leading-6 text-neutral-700">{item.inference}</div>
                  {item.evidence.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {item.evidence.slice(0, 4).map((signal, index) => (
                        <span key={`${item.id}-${index}`} className="rounded-full border border-neutral-200 bg-neutral-50 px-2 py-0.5 text-[11px] text-neutral-600">
                          {signal}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <select
                  value={item.status}
                  onChange={(e) => onUpdateTacitItem(item.id, { status: e.target.value as TacitMemoryItem['status'] })}
                  className="rounded-lg border border-neutral-200 bg-white px-2 py-1 text-xs text-neutral-800"
                >
                  <option value="inferred">Inferred</option>
                  <option value="confirmed">Confirmed</option>
                  <option value="edited">Edited</option>
                  <option value="rejected">Rejected</option>
                </select>
              </div>
              <textarea
                value={item.reviewer_note || ''}
                onChange={(e) => onUpdateTacitItem(item.id, { reviewer_note: e.target.value, status: item.status === 'inferred' ? 'edited' : item.status })}
                rows={2}
                className="mt-2 w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs text-neutral-900"
                placeholder="Reviewer note: correct, nuance, or reject this inferred tacit knowledge..."
              />
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default function SECIQueryExplorer() {
  // State
  const [query, setQuery] = useState('best breakfast options');
  const [contextBlob, setContextBlob] = useState('');
  const [objectives, setObjectives] = useState<Objective[]>([]);
  const [globalQuestions, setGlobalQuestions] = useState<string[]>([]);
  const [selectedObjective, setSelectedObjective] = useState<Objective | null>(null);
  const [facetAnswers, setFacetAnswers] = useState<Record<string, string>>({});
  const [evidenceItems, setEvidenceItems] = useState<EvidenceItem[]>([]);
  const [augmentedAnswer, setAugmentedAnswer] = useState<string>('');
  const [finalAnswer, setFinalAnswer] = useState<FinalizeResponse | null>(null);
  const [agenticPlan, setAgenticPlan] = useState<AgenticPlan | null>(null);
  const [selectedPlanStepId, setSelectedPlanStepId] = useState<string>('');
  const [personas, setPersonas] = useState<PersonaItem[]>([]);
  const [personaId, setPersonaId] = useState<number | ''>('');
  const [tacitState, setTacitState] = useState<TacitMemoryItem[]>([]);
  const [handoffSummary, setHandoffSummary] = useState('');
  const [memoryStatus, setMemoryStatus] = useState('not saved yet');
  const [inferringMemory, setInferringMemory] = useState(false);
  
  // Loading states
  const [loadingObjectives, setLoadingObjectives] = useState(false);
  const [loadingAugment, setLoadingAugment] = useState(false);
  const [loadingFinalize, setLoadingFinalize] = useState(false);
  const [loadingPlan, setLoadingPlan] = useState(false);

  const selectedPersona = personaId === '' ? null : personas.find((persona) => persona.id === Number(personaId)) || null;
  const workspaceKey = React.useMemo(() => {
    const normalized = query.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 90);
    return normalized || 'untitled-workspace';
  }, [query]);
  const explicitWorkspaceState = React.useMemo<Record<string, unknown>>(() => ({
    query,
    context_blob: contextBlob,
    persona_id: personaId === '' ? null : Number(personaId),
    persona: selectedPersona?.name || null,
    objectives,
    selected_objective: selectedObjective,
    facet_answers: facetAnswers,
    evidence_items: evidenceItems,
    augmented_answer: augmentedAnswer,
    final_answer: finalAnswer,
    agentic_plan: agenticPlan,
    selected_plan_step_id: selectedPlanStepId,
  }), [
    query,
    contextBlob,
    personaId,
    selectedPersona?.name,
    objectives,
    selectedObjective,
    facetAnswers,
    evidenceItems,
    augmentedAnswer,
    finalAnswer,
    agenticPlan,
    selectedPlanStepId,
  ]);

  // Generate objectives
  const handleGenerateObjectives = async () => {
    setLoadingObjectives(true);
    try {
      const response = await generateObjectives(query, contextBlob || undefined, 5, personaId === '' ? undefined : Number(personaId));
      setObjectives(response.objectives);
      setGlobalQuestions(response.global_questions);
      setSelectedObjective(null);
      setFacetAnswers({});
      setEvidenceItems([]);
      setAugmentedAnswer('');
      setFinalAnswer(null);
      setAgenticPlan(null);
      setSelectedPlanStepId('');
    } catch (error) {
      console.error('Error generating objectives:', error);
      alert('Failed to generate objectives. Please check if the backend is running.');
    } finally {
      setLoadingObjectives(false);
    }
  };

  // Select objective
  const handleSelectObjective = (objective: Objective) => {
    setSelectedObjective(objective);
    setFacetAnswers({});
    setEvidenceItems([]);
    setAugmentedAnswer('');
    setFinalAnswer(null);
    setAgenticPlan(null);
    setSelectedPlanStepId('');
  };

  const handleGeneratePlan = async () => {
    if (!selectedObjective) return;
    if (personaId === '') {
      alert('Select a persona before generating a plan.');
      return;
    }

    setLoadingPlan(true);
    try {
      const response = await generateAgenticPlan(
        query,
        selectedObjective,
        Number(personaId),
        facetAnswers,
        contextBlob || undefined
      );
      setAgenticPlan(response.plan);
      if (response.plan.steps.length > 0) {
        setSelectedPlanStepId(response.plan.steps[0].id);
      }
    } catch (error) {
      console.error('Error generating plan:', error);
      alert(error instanceof Error ? error.message : 'Failed to generate plan');
    } finally {
      setLoadingPlan(false);
    }
  };

  const updatePlanStep = (stepId: string, patch: Partial<PlanStep>) => {
    setAgenticPlan((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        steps: prev.steps.map((s) => (s.id === stepId ? { ...s, ...patch } : s)),
      };
    });
  };

  // Augment with context
  const handleAugmentWithContext = async () => {
    if (!selectedObjective || !contextBlob) return;
    
    setLoadingAugment(true);
    try {
      const response = await augmentWithContext(
        query,
        selectedObjective.id,
        selectedObjective.definition,
        contextBlob,
        personaId === '' ? undefined : Number(personaId)
      );
      setEvidenceItems(response.evidence_items);
      setAugmentedAnswer(response.augmented_answer || '');
    } catch (error) {
      console.error('Error augmenting with context:', error);
      alert('Failed to augment with context.');
    } finally {
      setLoadingAugment(false);
    }
  };

  // Finalize answer
  const handleFinalizeAnswer = async () => {
    if (!selectedObjective) return;
    
    setLoadingFinalize(true);
    try {
      const response = await finalizeAnswer(
        query, 
        selectedObjective, 
        facetAnswers, 
        contextBlob || undefined, 
        evidenceItems.length > 0 ? evidenceItems : undefined,
        personaId === '' ? undefined : Number(personaId)
      );
      setFinalAnswer(response);
    } catch (error) {
      console.error('Error finalizing answer:', error);
      alert('Failed to finalize answer.');
    } finally {
      setLoadingFinalize(false);
    }
  };

  // Reset
  const handleReset = () => {
    setObjectives([]);
    setGlobalQuestions([]);
    setSelectedObjective(null);
    setFacetAnswers({});
    setEvidenceItems([]);
    setAugmentedAnswer('');
    setFinalAnswer(null);
    setContextBlob('');
    setAgenticPlan(null);
    setSelectedPlanStepId('');
    setTacitState([]);
    setHandoffSummary('');
  };

  const updateTacitItem = (id: string, patch: Partial<TacitMemoryItem>) => {
    setTacitState((prev) => prev.map((item) => (item.id === id ? { ...item, ...patch } : item)));
  };

  const handleInferWorkspaceMemory = async () => {
    setInferringMemory(true);
    try {
      const response = await inferWorkspaceMemory({
        workspace_key: workspaceKey,
        scope: 'seci-query-explorer',
        explicit_state: explicitWorkspaceState,
        existing_tacit_state: tacitState,
      });
      setTacitState(response.tacit_state || []);
      setHandoffSummary(response.handoff_summary || '');
      setMemoryStatus('tacit state inferred; saving...');
    } catch (error) {
      console.error('Error inferring workspace memory:', error);
      alert(error instanceof Error ? error.message : 'Failed to infer workspace memory');
    } finally {
      setInferringMemory(false);
    }
  };

  React.useEffect(() => {
    const load = async () => {
      const res = await fetch(`${API_BASE}/api/personas`, { cache: 'no-store' });
      if (!res.ok) return;
      const data = await res.json();
      setPersonas(data.personas || []);
    };
    load();
  }, []);

  React.useEffect(() => {
    let cancelled = false;
    const loadMemory = async () => {
      try {
        const response = await getWorkspaceMemory(workspaceKey);
        if (cancelled) return;
        if (response.memory) {
          setTacitState(response.memory.tacit_state || []);
          setHandoffSummary(response.memory.handoff_summary || '');
          setMemoryStatus(`loaded memory${response.memory.updated_at ? ` from ${new Date(response.memory.updated_at).toLocaleString()}` : ''}`);
        } else {
          setTacitState([]);
          setHandoffSummary('');
          setMemoryStatus('new memory record');
        }
      } catch {
        if (!cancelled) setMemoryStatus('memory load unavailable');
      }
    };
    loadMemory();
    return () => {
      cancelled = true;
    };
  }, [workspaceKey]);

  React.useEffect(() => {
    const timer = window.setTimeout(async () => {
      try {
        const response = await saveWorkspaceMemory(workspaceKey, {
          scope: 'seci-query-explorer',
          explicit_state: explicitWorkspaceState,
          tacit_state: tacitState,
          handoff_summary: handoffSummary,
        });
        const updatedAt = response.memory?.updated_at;
        setMemoryStatus(`saved${updatedAt ? ` at ${new Date(updatedAt).toLocaleTimeString()}` : ''}`);
      } catch {
        setMemoryStatus('save failed; changes are local');
      }
    }, 900);
    return () => window.clearTimeout(timer);
  }, [workspaceKey, explicitWorkspaceState, tacitState, handoffSummary]);

  // Calculate objective stats (like original topicStats)
  const objectiveStats = objectives.reduce((acc, obj) => {
    // For display purposes, we'll count signals as a proxy for "candidates"
    acc[obj.id] = obj.signals.length;
    return acc;
  }, {} as Record<string, number>);

  // Order objectives by signal count (like original topicCardOrder)
  const objectiveCardOrder = [...objectives].sort((a, b) => b.signals.length - a.signals.length);

  // Filter objectives (for now, just show all)
  const filteredObjectives = objectives;

  // Synthesize preview (like original synthesizedPreview)
  const synthesizedPreview = selectedObjective ? [
    `Interpretation: ${selectedObjective.subtitle}`,
    `Definition: ${selectedObjective.definition}`,
    `Common signals: ${selectedObjective.signals.slice(0, 5).join(', ')}`,
    `Facet questions: ${selectedObjective.facet_questions.length}`,
  ].join('\n') : null;

  const selectedPlanStep = agenticPlan?.steps.find((step) => step.id === selectedPlanStepId) || null;

  return (
    <div className="min-h-screen bg-neutral-50 p-6">
      <div className="mx-auto max-w-6xl space-y-6">
        {/* Header - using original styling */}
        <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm">
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div>
              <div className="text-lg font-semibold text-neutral-900">
                Underspecified Query Topic Explorer (SECI-PoC)
              </div>
              <div className="text-sm text-neutral-600">
                Type a query → generate diverse objective clusters → select objective → clarify with facet questions → augment with context → synthesize final answer.
              </div>
            </div>

            <div className="flex gap-2">
              <Link
                href="/reports"
                className="rounded-xl border border-neutral-200 bg-white px-4 py-2 text-sm font-semibold text-neutral-900 hover:bg-neutral-50"
              >
                Reports
              </Link>
              <Link
                href="/personas"
                className="rounded-xl border border-neutral-200 bg-white px-4 py-2 text-sm font-semibold text-neutral-900 hover:bg-neutral-50"
              >
                Personas
              </Link>
              <button
                onClick={handleGenerateObjectives}
                disabled={loadingObjectives || !query.trim()}
                className="rounded-xl bg-neutral-900 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-neutral-800 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loadingObjectives ? 'Generating...' : 'Generate objectives'}
              </button>
              <button
                onClick={handleReset}
                className="rounded-xl border border-neutral-200 bg-white px-4 py-2 text-sm font-semibold text-neutral-900 hover:bg-neutral-50"
              >
                Reset
              </button>
            </div>
          </div>

          {/* Query input */}
          <div className="mt-5 grid gap-3 md:grid-cols-12 md:items-center">
            <div className="md:col-span-8">
              <label className="mb-1 block text-xs font-medium text-neutral-700">User query</label>
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g., best breakfast options"
                className="w-full rounded-xl border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-900 outline-none ring-0 focus:border-neutral-300"
              />
              <div className="mt-1 text-xs text-neutral-500">
                SECI PoC: objectives generated via LLM, facet questions for clarification, context augmentation available.
              </div>
            </div>
            <div className="md:col-span-4">
              <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-3">
                <div className="text-xs font-medium text-neutral-700">Status</div>
                <div className="mt-1 text-sm text-neutral-900">
                  {objectives.length > 0 ? (
                    <>
                      Objectives: <span className="font-semibold">{objectives.length}</span> · Facet Questions:{' '}
                      <span className="font-semibold">{selectedObjective?.facet_questions.length || 0}</span>
                    </>
                  ) : (
                    'No objectives generated.'
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Context blob input */}
          <div className="mt-3">
            <label className="mb-1 block text-xs font-medium text-neutral-700">Persona (optional)</label>
            <select
              value={personaId}
              onChange={(e) => setPersonaId(e.target.value === '' ? '' : Number(e.target.value))}
              className="mb-3 w-full rounded-xl border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-900 outline-none ring-0 focus:border-neutral-300"
            >
              <option value="">None</option>
              {personas.map((p) => (
                <option key={p.id} value={p.id}>{p.name} ({p.scope})</option>
              ))}
            </select>
            <label className="mb-1 block text-xs font-medium text-neutral-700">Context evidence (optional)</label>
            <textarea
              value={contextBlob}
              onChange={(e) => setContextBlob(e.target.value)}
              placeholder="Paste relevant context, papers, data, or notes here..."
              rows={4}
              className="w-full rounded-xl border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-900 outline-none ring-0 focus:border-neutral-300"
            />
          </div>
        </div>

        <WorkspaceMemoryPanel
          workspaceKey={workspaceKey}
          memoryStatus={memoryStatus}
          tacitState={tacitState}
          handoffSummary={handoffSummary}
          onInfer={handleInferWorkspaceMemory}
          onUpdateTacitItem={updateTacitItem}
          inferring={inferringMemory}
        />

        {/* Main grid - using original layout */}
        <div className="grid gap-6 lg:grid-cols-12">
          {/* Left: Objectives */}
          <div className="lg:col-span-5">
            <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
              <SectionTitle title="Objective clusters" subtitle="Click one to explore and clarify" />

              {loadingObjectives ? (
                <LoadingSpinner />
              ) : objectives.length === 0 ? (
                <div className="text-center py-8 text-sm text-neutral-600">
                  Generate objectives to see clusters
                </div>
              ) : (
                <div className="grid gap-3">
                  {objectiveCardOrder.map((obj) => {
                    const count = objectiveStats[obj.id] ?? 0;
                    const active = selectedObjective?.id === obj.id;
                    const disabled = !objectives.length || count === 0;

                    return (
                      <button
                        key={obj.id}
                        disabled={disabled}
                        onClick={() => handleSelectObjective(obj)}
                        className={classNames(
                          'rounded-2xl border p-4 text-left transition',
                          disabled
                            ? 'cursor-not-allowed border-neutral-200 bg-neutral-50 opacity-60'
                            : active
                            ? 'border-neutral-900 bg-neutral-50'
                            : 'border-neutral-200 bg-white hover:bg-neutral-50'
                        )}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="text-sm font-semibold text-neutral-900">{obj.title}</div>
                            <div className="mt-1 text-xs text-neutral-600">{obj.subtitle}</div>
                          </div>
                          <div className="flex flex-col items-end gap-2">
                            <Pill>{count} signals</Pill>
                            {active ? <Pill>Selected</Pill> : null}
                          </div>
                        </div>

                        <div className="mt-3 flex flex-wrap gap-2">
                          {obj.signals.slice(0, 4).map((signal) => (
                            <Pill key={signal}>{signal}</Pill>
                          ))}
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Right: Details */}
          <div className="lg:col-span-7">
            <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
              <SectionTitle
                title={selectedObjective ? `Unroll: ${selectedObjective.title}` : 'Select an objective to unroll'}
                subtitle={
                  selectedObjective
                    ? 'View the objective definition, facet questions, and synthesize final answer.'
                    : objectives.length > 0
                    ? 'Objectives are ready. Choose one on the left.'
                    : 'Generate objectives first.'
                }
              />

              {/* Roll-up panel */}
              <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="text-sm font-semibold text-neutral-900">Rolled-up interpretation</div>
                  {selectedObjective ? (
                    <button
                      onClick={() => setSelectedObjective(null)}
                      className="rounded-xl border border-neutral-200 bg-white px-3 py-1.5 text-xs font-semibold text-neutral-900 hover:bg-neutral-50"
                    >
                      Clear selection
                    </button>
                  ) : null}
                </div>
                <div className="mt-2 whitespace-pre-wrap text-sm text-neutral-800">
                  {synthesizedPreview ?? (
                    <span className="text-neutral-600">
                      Pick an objective to see its rolled-up interpretation.
                    </span>
                  )}
                </div>
              </div>

              {/* Facet questions */}
              {selectedObjective && (
                <div className="mt-4">
                  <div className="text-sm font-semibold text-neutral-900">Facet clarifying questions</div>
                  <div className="mt-2 grid gap-2">
                    {selectedObjective.facet_questions.map((question, index) => (
                      <div key={index} className="rounded-xl border border-neutral-200 bg-white p-3 text-sm text-neutral-800">
                        {question}
                      </div>
                    ))}
                  </div>
                  
                  {/* Interactive facet answers */}
                  <div className="mt-3">
                    <div className="text-xs font-medium text-neutral-700 mb-2">Your answers:</div>
                    {selectedObjective.facet_questions.map((question, index) => (
                      <div key={index} className="mb-2">
                        <input
                          type="text"
                          placeholder={`Answer: ${question}`}
                          value={facetAnswers[question] || ''}
                          onChange={(e) => setFacetAnswers(prev => ({ ...prev, [question]: e.target.value }))}
                          className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-900 outline-none ring-0 focus:border-neutral-300"
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Agentic plan */}
              {selectedObjective && (
                <div className="mt-4 rounded-2xl border border-sky-200 bg-gradient-to-br from-sky-50 via-white to-cyan-50 p-4">
                  <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                    <div>
                      <div className="text-sm font-semibold text-slate-900">Agentic Plan Visualizer</div>
                      <div className="text-xs text-slate-600">
                        Build an objective-aligned plan with persona-specific rationale, facts, and editable steps.
                      </div>
                    </div>
                    <button
                      onClick={handleGeneratePlan}
                      disabled={loadingPlan || personaId === ''}
                      className="rounded-xl bg-slate-900 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {loadingPlan ? 'Planning...' : 'Generate Plan'}
                    </button>
                  </div>

                  {personaId === '' && (
                    <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                      Select a persona to generate a plan tailored to user behavior and decision style.
                    </div>
                  )}

                  {agenticPlan && (
                    <div className="mt-4 space-y-4">
                      <div className="rounded-xl border border-slate-200 bg-white p-3">
                        <div className="text-sm font-semibold text-slate-900">{agenticPlan.plan_title}</div>
                        <div className="mt-1 text-xs text-slate-700">{agenticPlan.strategy_summary}</div>
                        {agenticPlan.success_criteria.length > 0 && (
                          <div className="mt-2 flex flex-wrap gap-2">
                            {agenticPlan.success_criteria.map((criterion, idx) => (
                              <span key={`${criterion}-${idx}`} className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[11px] text-emerald-800">
                                {criterion}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>

                      <div className="grid gap-3 lg:grid-cols-2">
                        <div className="space-y-2">
                          {agenticPlan.steps.map((step, index) => {
                            const active = selectedPlanStepId === step.id;
                            return (
                              <button
                                key={step.id}
                                onClick={() => setSelectedPlanStepId(step.id)}
                                className={classNames(
                                  'w-full rounded-xl border p-3 text-left transition',
                                  active
                                    ? 'border-sky-400 bg-sky-50 shadow-sm'
                                    : 'border-slate-200 bg-white hover:bg-slate-50'
                                )}
                              >
                                <div className="flex items-start justify-between gap-2">
                                  <div>
                                    <div className="text-[11px] font-semibold uppercase tracking-wide text-sky-700">Step {index + 1}</div>
                                    <div className="text-sm font-semibold text-slate-900">{step.title}</div>
                                  </div>
                                  <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] text-slate-700">
                                    {Math.round((step.confidence || 0) * 100)}%
                                  </span>
                                </div>
                                <div className="mt-1 line-clamp-2 text-xs text-slate-700">{step.description}</div>
                                {step.dependencies.length > 0 && (
                                  <div className="mt-2 flex flex-wrap gap-1">
                                    {step.dependencies.map((dep) => (
                                      <span key={dep} className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-700">
                                        depends on {dep}
                                      </span>
                                    ))}
                                  </div>
                                )}
                              </button>
                            );
                          })}
                        </div>

                        <div className="rounded-xl border border-slate-200 bg-white p-3">
                          {!selectedPlanStep ? (
                            <div className="text-xs text-slate-600">Pick a step to inspect and edit rationale.</div>
                          ) : (
                            <div className="space-y-2">
                              <input
                                value={selectedPlanStep.title}
                                onChange={(e) => updatePlanStep(selectedPlanStep.id, { title: e.target.value })}
                                className="w-full rounded-lg border border-slate-200 px-2 py-1.5 text-sm font-semibold text-slate-900"
                              />
                              <textarea
                                value={selectedPlanStep.description}
                                onChange={(e) => updatePlanStep(selectedPlanStep.id, { description: e.target.value })}
                                rows={3}
                                className="w-full rounded-lg border border-slate-200 px-2 py-1.5 text-xs text-slate-800"
                              />
                              <div className="rounded-lg border border-violet-200 bg-violet-50 p-2">
                                <div className="text-[11px] font-semibold uppercase tracking-wide text-violet-800">Why this step was chosen</div>
                                <textarea
                                  value={selectedPlanStep.why_this_step}
                                  onChange={(e) => updatePlanStep(selectedPlanStep.id, { why_this_step: e.target.value })}
                                  rows={3}
                                  className="mt-1 w-full rounded-lg border border-violet-200 bg-white px-2 py-1.5 text-xs text-slate-800"
                                />
                              </div>
                              <div className="grid gap-2 md:grid-cols-2">
                                <div>
                                  <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Objective link</div>
                                  <textarea
                                    value={selectedPlanStep.objective_link}
                                    onChange={(e) => updatePlanStep(selectedPlanStep.id, { objective_link: e.target.value })}
                                    rows={2}
                                    className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-1.5 text-xs text-slate-800"
                                  />
                                </div>
                                <div>
                                  <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Persona link</div>
                                  <textarea
                                    value={selectedPlanStep.persona_link}
                                    onChange={(e) => updatePlanStep(selectedPlanStep.id, { persona_link: e.target.value })}
                                    rows={2}
                                    className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-1.5 text-xs text-slate-800"
                                  />
                                </div>
                              </div>
                              <div>
                                <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Evidence / facts (one per line)</div>
                                <textarea
                                  value={selectedPlanStep.evidence_facts.join('\n')}
                                  onChange={(e) =>
                                    updatePlanStep(selectedPlanStep.id, {
                                      evidence_facts: e.target.value.split('\n').map((x) => x.trim()).filter(Boolean),
                                    })
                                  }
                                  rows={3}
                                  className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-1.5 text-xs text-slate-800"
                                />
                              </div>
                              <div>
                                <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Examples (one per line)</div>
                                <textarea
                                  value={selectedPlanStep.examples.join('\n')}
                                  onChange={(e) =>
                                    updatePlanStep(selectedPlanStep.id, {
                                      examples: e.target.value.split('\n').map((x) => x.trim()).filter(Boolean),
                                    })
                                  }
                                  rows={3}
                                  className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-1.5 text-xs text-slate-800"
                                />
                              </div>
                              <div>
                                <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Expected outcome</div>
                                <textarea
                                  value={selectedPlanStep.expected_outcome}
                                  onChange={(e) => updatePlanStep(selectedPlanStep.id, { expected_outcome: e.target.value })}
                                  rows={2}
                                  className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-1.5 text-xs text-slate-800"
                                />
                              </div>
                            </div>
                          )}
                        </div>
                      </div>

                      {agenticPlan.risks.length > 0 && (
                        <div className="rounded-xl border border-rose-200 bg-rose-50 p-3">
                          <div className="text-xs font-semibold uppercase tracking-wide text-rose-800">Risk radar</div>
                          <div className="mt-2 space-y-2">
                            {agenticPlan.risks.map((r, idx) => (
                              <div key={`${r.risk}-${idx}`} className="rounded-lg border border-rose-200 bg-white p-2">
                                <div className="text-xs font-semibold text-rose-900">{r.risk}</div>
                                <div className="text-xs text-slate-700">Mitigation: {r.mitigation}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Context augmentation */}
              {selectedObjective && contextBlob && (
                <div className="mt-4">
                  <button
                    onClick={handleAugmentWithContext}
                    disabled={loadingAugment}
                    className="w-full rounded-xl border border-neutral-200 bg-white px-4 py-3 text-sm font-semibold text-neutral-900 hover:bg-neutral-50 disabled:opacity-50"
                  >
                    {loadingAugment ? 'Augmenting...' : 'Augment with context'}
                  </button>
                </div>
              )}

              {/* Evidence items */}
              {evidenceItems.length > 0 && (
                <div className="mt-4">
                  <div className="text-sm font-semibold text-neutral-900">Extracted evidence</div>
                  <div className="mt-2 space-y-2">
                    {evidenceItems.map((evidence) => (
                      <div key={evidence.id} className="rounded-xl border border-neutral-200 bg-neutral-50 p-3">
                        <div className="text-xs font-medium text-neutral-700">{evidence.title}</div>
                        <div className="mt-1 text-sm text-neutral-800">{evidence.snippet}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Exemplar/Augmented answer preview */}
              {selectedObjective && (
                <div className="mt-4">
                  <div className="text-sm font-semibold text-neutral-900">Answer preview</div>
                  <div className="mt-2 rounded-xl border border-neutral-200 bg-neutral-50 p-3">
                    <div className="text-sm text-neutral-800">
                      {augmentedAnswer || selectedObjective.exemplar_answer}
                    </div>
                  </div>
                </div>
              )}

              {/* Finalize button */}
              {selectedObjective && (
                <div className="mt-4">
                  <button
                    onClick={handleFinalizeAnswer}
                    disabled={loadingFinalize}
                    className="w-full rounded-xl bg-neutral-900 px-4 py-3 text-sm font-semibold text-white shadow-sm hover:bg-neutral-800 disabled:opacity-50"
                  >
                    {loadingFinalize ? 'Finalizing...' : 'Generate final answer'}
                  </button>
                </div>
              )}

              {/* Final answer */}
              {finalAnswer && (
                <div className="mt-4">
                  <div className="text-sm font-semibold text-neutral-900">Final answer</div>
                  <div className="mt-2 rounded-xl border border-neutral-200 bg-neutral-50 p-4">
                    <div className="text-sm text-neutral-900 mb-3">{finalAnswer.final_answer}</div>
                    
                    {finalAnswer.assumptions.length > 0 && (
                      <div className="mt-3">
                        <div className="text-xs font-medium text-neutral-700">Assumptions</div>
                        <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-neutral-600">
                          {finalAnswer.assumptions.map((assumption, index) => (
                            <li key={index}>{assumption}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {finalAnswer.next_questions.length > 0 && (
                      <div className="mt-3">
                        <div className="text-xs font-medium text-neutral-700">Next questions</div>
                        <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-neutral-600">
                          {finalAnswer.next_questions.map((question, index) => (
                            <li key={index}>{question}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Global questions */}
        {globalQuestions.length > 0 && (
          <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
            <SectionTitle title="Global clarifying questions" subtitle="Cross-cutting questions for any objective" />
            <div className="grid gap-2 md:grid-cols-2">
              {globalQuestions.map((question, index) => (
                <div key={index} className="rounded-xl border border-neutral-200 bg-neutral-50 p-3 text-sm text-neutral-800">
                  {question}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Footer: next step */}
        <div className="rounded-2xl border border-neutral-200 bg-white p-4">
          <div className="text-sm font-semibold text-neutral-900">SECI Framework Implementation</div>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-neutral-700">
            <li>Socialization: Generate multiple objective hypotheses via LLM</li>
            <li>Externalization: Render objectives + facet questions explicitly in UI</li>
            <li>Combination: Augment selected objective with external evidence (context blob)</li>
            <li>Internalization: Store selected objective + answers to reuse as prior (SQLite)</li>
          </ul>
        </div>

        {/* Minimal note */}
        <div className="text-xs text-neutral-500">
          SECI PoC uses LLM-generated objectives and facet questions. Swap in your embedding-based clusters by mapping each objective to a cluster id, then render clusters dynamically.
        </div>
      </div>
    </div>
  );
}
