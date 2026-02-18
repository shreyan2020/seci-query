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

// API client
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function generateObjectives(query: string, context?: string, k: number = 5): Promise<ObjectivesResponse> {
  const response = await fetch(`${API_BASE}/objectives`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, context, k })
  });
  if (!response.ok) throw new Error('Failed to generate objectives');
  return response.json();
}

async function augmentWithContext(query: string, objectiveId: string, objectiveDefinition: string, contextBlob: string): Promise<AugmentResponse> {
  const response = await fetch(`${API_BASE}/augment`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, objective_id: objectiveId, objective_definition: objectiveDefinition, context_blob: contextBlob })
  });
  if (!response.ok) throw new Error('Failed to augment with context');
  return response.json();
}

async function finalizeAnswer(query: string, objective: Objective, answers: Record<string, string>, contextBlob?: string, evidenceItems?: EvidenceItem[]): Promise<FinalizeResponse> {
  const response = await fetch(`${API_BASE}/finalize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, objective, answers, context_blob: contextBlob, evidence_items: evidenceItems })
  });
  if (!response.ok) throw new Error('Failed to finalize answer');
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
  
  // Loading states
  const [loadingObjectives, setLoadingObjectives] = useState(false);
  const [loadingAugment, setLoadingAugment] = useState(false);
  const [loadingFinalize, setLoadingFinalize] = useState(false);

  // Generate objectives
  const handleGenerateObjectives = async () => {
    setLoadingObjectives(true);
    try {
      const response = await generateObjectives(query, contextBlob || undefined);
      setObjectives(response.objectives);
      setGlobalQuestions(response.global_questions);
      setSelectedObjective(null);
      setFacetAnswers({});
      setEvidenceItems([]);
      setAugmentedAnswer('');
      setFinalAnswer(null);
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
  };

  // Augment with context
  const handleAugmentWithContext = async () => {
    if (!selectedObjective || !contextBlob) return;
    
    setLoadingAugment(true);
    try {
      const response = await augmentWithContext(query, selectedObjective.id, selectedObjective.definition, contextBlob);
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
        evidenceItems.length > 0 ? evidenceItems : undefined
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
  };

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