import { ResearchWorkTemplateSection } from '@/features/biotech-workspace/components/ResearchWorkTemplateSection';
import type {
  AgenticPlan,
  ObjectiveCluster,
  PlanStep,
  ResearchFinding,
  ResearchWorkTemplate,
} from '@/features/biotech-workspace/types';
import { classNames, getModeVisualKey } from '@/features/biotech-workspace/lib/utils';

interface WorkingDraftSectionProps {
  selectedObjective: ObjectiveCluster | null;
  currentModeTitle: string;
  currentModeDescription: string;
  onChooseAnotherObjective: () => void;
  focusQuestion: string;
  researchWorkTemplate: ResearchWorkTemplate;
  onResearchWorkTemplateChange: (next: ResearchWorkTemplate) => void;
  onFetchLiterature: () => void;
  fetchingLiterature: boolean;
  literatureToolStatus?: string | null;
  literatureObjectiveLens?: string | null;
  literatureProcessingSummary?: string | null;
  literatureElicitationQuestions?: string[];
  literatureElicitationAnswers?: Record<string, string>;
  onLiteratureElicitationAnswerChange?: (question: string, value: string) => void;
  onCaptureLiteratureTacitAnswer?: (question: string) => void;
  onPreparePaperPdf?: (finding: ResearchFinding) => void;
  preparingPdfFindingId?: string | null;
  pdfAnnotationStatus?: string | null;
  reasoningNotes: string;
  onReasoningNotesChange: (value: string) => void;
  agenticPlan: AgenticPlan | null;
  selectedPlanStepId: string;
  onSelectPlanStep: (stepId: string) => void;
  onUpdatePlanStep: (stepId: string, patch: Partial<PlanStep>) => void;
  onGeneratePlan: () => void;
  loadingPlan: boolean;
}

export function WorkingDraftSection({
  selectedObjective,
  currentModeTitle,
  currentModeDescription,
  onChooseAnotherObjective,
  focusQuestion,
  researchWorkTemplate,
  onResearchWorkTemplateChange,
  onFetchLiterature,
  fetchingLiterature,
  literatureToolStatus,
  literatureObjectiveLens,
  literatureProcessingSummary,
  literatureElicitationQuestions,
  literatureElicitationAnswers,
  onLiteratureElicitationAnswerChange,
  onCaptureLiteratureTacitAnswer,
  onPreparePaperPdf,
  preparingPdfFindingId,
  pdfAnnotationStatus,
  reasoningNotes,
  onReasoningNotesChange,
  agenticPlan,
  selectedPlanStepId,
  onSelectPlanStep,
  onUpdatePlanStep,
  onGeneratePlan,
  loadingPlan,
}: WorkingDraftSectionProps) {
  const selectedPlanStep = agenticPlan?.steps.find((step) => step.id === selectedPlanStepId) || null;
  const modeKey = getModeVisualKey(currentModeTitle);
  const modeShellTone: Record<string, string> = {
    evidence: 'border-sky-300/80',
    data: 'border-indigo-300/80',
    experiment: 'border-emerald-300/80',
    process: 'border-cyan-300/80',
    economics: 'border-amber-300/80',
    sourcing: 'border-lime-300/80',
    recovery: 'border-fuchsia-300/80',
    general: 'border-slate-300/80',
  };
  const modeWash: Record<string, string> = {
    evidence:
      'bg-[radial-gradient(circle_at_top_left,_rgba(96,165,250,0.26),_transparent_34%),linear-gradient(180deg,rgba(239,246,255,0.92),rgba(248,250,252,0.96))]',
    data:
      'bg-[radial-gradient(circle_at_top_left,_rgba(99,102,241,0.24),_transparent_34%),repeating-linear-gradient(90deg,rgba(15,23,42,0.04)_0px,rgba(15,23,42,0.04)_1px,transparent_1px,transparent_24px),linear-gradient(180deg,rgba(238,242,255,0.92),rgba(248,250,252,0.96))]',
    experiment:
      'bg-[radial-gradient(circle_at_top_left,_rgba(16,185,129,0.24),_transparent_34%),linear-gradient(180deg,rgba(236,253,245,0.92),rgba(255,251,235,0.94))]',
    process:
      'bg-[radial-gradient(circle_at_top_left,_rgba(6,182,212,0.22),_transparent_34%),linear-gradient(180deg,rgba(236,254,255,0.92),rgba(248,250,252,0.96))]',
    economics:
      'bg-[radial-gradient(circle_at_top_left,_rgba(245,158,11,0.2),_transparent_34%),linear-gradient(180deg,rgba(255,251,235,0.92),rgba(248,250,252,0.96))]',
    sourcing:
      'bg-[radial-gradient(circle_at_top_left,_rgba(132,204,22,0.18),_transparent_34%),linear-gradient(180deg,rgba(247,254,231,0.92),rgba(248,250,252,0.96))]',
    recovery:
      'bg-[radial-gradient(circle_at_top_left,_rgba(217,70,239,0.18),_transparent_34%),linear-gradient(180deg,rgba(250,245,255,0.92),rgba(248,250,252,0.96))]',
    general: 'bg-[linear-gradient(180deg,rgba(248,250,252,0.94),rgba(248,250,252,0.98))]',
  };

  return (
    <section
      className={classNames(
        'relative overflow-hidden rounded-[1.9rem] border p-6 shadow-[0_30px_90px_-50px_rgba(15,23,42,0.45)] backdrop-blur transition-colors duration-700',
        modeShellTone[modeKey] || modeShellTone.general
      )}
    >
      <div className={classNames('absolute inset-0 transition-opacity duration-700', modeWash[modeKey] || modeWash.general)} />

      <div className="relative">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Step 4 / Mode Workspace</div>
            <div className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
              {selectedObjective ? currentModeTitle : 'Select a mode to open the workspace'}
            </div>
            <div className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              {selectedObjective
                ? currentModeDescription
                : 'Once a mode is selected on the left, this workspace switches into that setting and becomes the place to generate, inspect, and edit the next draft.'}
            </div>
          </div>

          {selectedObjective && (
            <div className="flex flex-wrap gap-3">
              <button
                onClick={onChooseAnotherObjective}
                className="rounded-2xl border border-slate-200 bg-white/90 px-4 py-3 text-sm font-semibold text-slate-900 transition hover:bg-white"
              >
                Choose another objective
              </button>
              <button
                onClick={onGeneratePlan}
                disabled={loadingPlan}
                className="rounded-2xl bg-slate-950 px-4 py-3 text-sm font-semibold text-white shadow-sm hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loadingPlan ? 'Drafting...' : 'Generate Mode Draft'}
              </button>
            </div>
          )}
        </div>
      </div>

      {!selectedObjective ? (
        <div className="relative mt-5 rounded-[1.5rem] border border-dashed border-slate-300 bg-white/75 p-8 text-center text-sm text-slate-600">
          Choose an objective mode to move the system into a dedicated setting. The draft workspace will then inherit that visual frame,
          that reasoning style, and that generation behavior.
        </div>
      ) : (
        <>
          <ResearchWorkTemplateSection
            focusQuestion={focusQuestion}
            workTemplate={researchWorkTemplate}
            onWorkTemplateChange={onResearchWorkTemplateChange}
            onFetchLiterature={onFetchLiterature}
            fetchingLiterature={fetchingLiterature}
            literatureToolStatus={literatureToolStatus}
            literatureObjectiveLens={literatureObjectiveLens}
            literatureProcessingSummary={literatureProcessingSummary}
            literatureElicitationQuestions={literatureElicitationQuestions}
            literatureElicitationAnswers={literatureElicitationAnswers}
            onLiteratureElicitationAnswerChange={onLiteratureElicitationAnswerChange}
            onCaptureLiteratureTacitAnswer={onCaptureLiteratureTacitAnswer}
            onPreparePaperPdf={onPreparePaperPdf}
            preparingPdfFindingId={preparingPdfFindingId}
            pdfAnnotationStatus={pdfAnnotationStatus}
          />

          <div className="relative mt-5 rounded-[1.5rem] border border-slate-200 bg-white/85 p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Reasoning And Synthesis</div>
            <div className="mt-1 text-sm text-slate-600">
              {agenticPlan
                ? 'Keep a running synthesis between generations, then edit the draft plan directly underneath.'
                : 'Use this as the freeform layer for anything that does not fit the structured template: comparison notes, caveats, or synthesis across sources.'}
            </div>
            <textarea
              value={reasoningNotes}
              onChange={(e) => onReasoningNotesChange(e.target.value)}
              rows={agenticPlan ? 6 : 7}
              className="mt-3 w-full rounded-[1.25rem] border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900"
              placeholder={
                agenticPlan
                  ? 'Capture the latest interpretation, open questions, or next hypotheses before the next generation.'
                  : 'Example: reported flavonoid work often improves precursor flux and cofactor balance, but product toxicity and pathway burden still look unresolved. Use this box for caveats, cross-links, or synthesis beyond the structured work template.'
              }
            />
          </div>

          {!agenticPlan ? (
            <div className="relative mt-5 rounded-[1.5rem] border border-dashed border-slate-300 bg-white/75 p-8 text-center text-sm text-slate-600">
              Generate a draft to inspect the proposed reasoning steps, evidence hooks, risks, and editable rationale.
            </div>
          ) : (
            <div className="relative mt-5 space-y-5">
              <div className="rounded-[1.5rem] border border-slate-200 bg-white/90 p-4">
                <div className="text-lg font-semibold text-slate-950">{agenticPlan.plan_title}</div>
                <div className="mt-2 text-sm text-slate-700">{agenticPlan.strategy_summary}</div>
                {agenticPlan.success_criteria.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {agenticPlan.success_criteria.map((criterion) => (
                      <span key={criterion} className="rounded-full border border-emerald-200 bg-white px-2 py-0.5 text-[11px] text-emerald-900">
                        {criterion}
                      </span>
                    ))}
                  </div>
                )}
                {agenticPlan.assumptions.length > 0 && (
                  <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 p-3">
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-amber-800">Assumptions</div>
                    <div className="mt-2 space-y-1 text-sm text-amber-900">
                      {agenticPlan.assumptions.map((assumption) => (
                        <div key={assumption}>{assumption}</div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div className="grid gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
                <div className="space-y-2">
                  {agenticPlan.steps.map((step, index) => {
                    const active = selectedPlanStepId === step.id;
                    return (
                      <button
                        key={step.id}
                        onClick={() => onSelectPlanStep(step.id)}
                        className={classNames(
                          'w-full rounded-[1.35rem] border p-4 text-left transition',
                          active ? 'border-slate-900 bg-slate-950 text-white' : 'border-slate-200 bg-white hover:bg-slate-50'
                        )}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className={classNames('text-[11px] font-semibold uppercase tracking-wide', active ? 'text-slate-300' : 'text-slate-500')}>
                              Step {index + 1}
                            </div>
                            <div className={classNames('mt-1 text-sm font-semibold', active ? 'text-white' : 'text-slate-950')}>{step.title}</div>
                          </div>
                          <span className={classNames('rounded-full px-2 py-0.5 text-[11px]', active ? 'bg-white/10 text-white' : 'bg-slate-100 text-slate-700')}>
                            {Math.round((step.confidence || 0) * 100)}%
                          </span>
                        </div>
                        <div className={classNames('mt-2 text-xs leading-5', active ? 'text-slate-200' : 'text-slate-600')}>{step.description}</div>
                      </button>
                    );
                  })}
                </div>

                <div className="rounded-[1.5rem] border border-slate-200 bg-white/85 p-4">
                  {!selectedPlanStep ? (
                    <div className="text-sm text-slate-600">Select a step to inspect and edit the rationale.</div>
                  ) : (
                    <div className="space-y-3">
                      <input
                        value={selectedPlanStep.title}
                        onChange={(e) => onUpdatePlanStep(selectedPlanStep.id, { title: e.target.value })}
                        className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-950"
                      />

                      <textarea
                        value={selectedPlanStep.description}
                        onChange={(e) => onUpdatePlanStep(selectedPlanStep.id, { description: e.target.value })}
                        rows={3}
                        className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                      />

                      <div className="rounded-2xl border border-violet-200 bg-violet-50 p-3">
                        <div className="text-[11px] font-semibold uppercase tracking-wide text-violet-800">Why this step exists</div>
                        <textarea
                          value={selectedPlanStep.why_this_step}
                          onChange={(e) => onUpdatePlanStep(selectedPlanStep.id, { why_this_step: e.target.value })}
                          rows={3}
                          className="mt-2 w-full rounded-2xl border border-violet-200 bg-white px-3 py-2 text-sm text-slate-900"
                        />
                      </div>

                      <div className="grid gap-3 md:grid-cols-2">
                        <div>
                          <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Project link</div>
                          <textarea
                            value={selectedPlanStep.objective_link}
                            onChange={(e) => onUpdatePlanStep(selectedPlanStep.id, { objective_link: e.target.value })}
                            rows={2}
                            className="mt-1 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                          />
                        </div>
                        <div>
                          <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Persona link</div>
                          <textarea
                            value={selectedPlanStep.persona_link}
                            onChange={(e) => onUpdatePlanStep(selectedPlanStep.id, { persona_link: e.target.value })}
                            rows={2}
                            className="mt-1 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                          />
                        </div>
                      </div>

                      <div>
                        <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Evidence or factual anchors</div>
                        <textarea
                          value={selectedPlanStep.evidence_facts.join('\n')}
                          onChange={(e) =>
                            onUpdatePlanStep(selectedPlanStep.id, {
                              evidence_facts: e.target.value
                                .split('\n')
                                .map((item) => item.trim())
                                .filter(Boolean),
                            })
                          }
                          rows={4}
                          className="mt-1 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                        />
                      </div>

                      <div>
                        <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Examples</div>
                        <textarea
                          value={selectedPlanStep.examples.join('\n')}
                          onChange={(e) =>
                            onUpdatePlanStep(selectedPlanStep.id, {
                              examples: e.target.value
                                .split('\n')
                                .map((item) => item.trim())
                                .filter(Boolean),
                            })
                          }
                          rows={3}
                          className="mt-1 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                        />
                      </div>

                      <div>
                        <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Expected outcome</div>
                        <textarea
                          value={selectedPlanStep.expected_outcome}
                          onChange={(e) => onUpdatePlanStep(selectedPlanStep.id, { expected_outcome: e.target.value })}
                          rows={3}
                          className="mt-1 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                        />
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {agenticPlan.risks.length > 0 && (
                <div className="rounded-[1.5rem] border border-rose-200 bg-rose-50 p-4">
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-rose-800">Risk Radar</div>
                  <div className="mt-3 grid gap-3 lg:grid-cols-2">
                    {agenticPlan.risks.map((risk, index) => (
                      <div key={`${risk.risk}-${index}`} className="rounded-2xl border border-rose-200 bg-white p-3">
                        <div className="text-sm font-semibold text-rose-950">{risk.risk}</div>
                        <div className="mt-1 text-sm text-slate-700">Mitigation: {risk.mitigation}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
}
