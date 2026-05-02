import type { ObjectiveCluster } from '@/features/biotech-workspace/types';
import { classNames, getModeVisualKey } from '@/features/biotech-workspace/lib/utils';

interface ObjectiveClusteringSectionProps {
  objectiveClusters: ObjectiveCluster[];
  selectedObjective: ObjectiveCluster | null;
  selectedObjectiveId: string;
  objectivePickerCollapsed: boolean;
  onSelectObjective: (objectiveId: string) => void;
  onGenerateModes: () => void;
  loadingObjectiveClusters: boolean;
  canGenerateModes: boolean;
  objectiveAnswers: Record<string, string>;
  onObjectiveAnswerChange: (question: string, value: string) => void;
  globalQuestions: string[];
  globalQuestionAnswers: Record<string, string>;
  onGlobalQuestionChange: (question: string, value: string) => void;
  onSetObjectivePickerCollapsed: (collapsed: boolean) => void;
  showManualObjectiveForm: boolean;
  manualObjective: {
    title: string;
    subtitle: string;
    definition: string;
    signals: string;
    facet_questions: string;
    exemplar_answer: string;
  };
  onToggleManualObjectiveForm: () => void;
  onManualObjectiveChange: (field: keyof ObjectiveClusteringSectionProps['manualObjective'], value: string) => void;
  onCreateManualObjective: () => void;
}

export function ObjectiveClusteringSection({
  objectiveClusters,
  selectedObjective,
  selectedObjectiveId,
  objectivePickerCollapsed,
  onSelectObjective,
  onGenerateModes,
  loadingObjectiveClusters,
  canGenerateModes,
  objectiveAnswers,
  onObjectiveAnswerChange,
  globalQuestions,
  globalQuestionAnswers,
  onGlobalQuestionChange,
  onSetObjectivePickerCollapsed,
  showManualObjectiveForm,
  manualObjective,
  onToggleManualObjectiveForm,
  onManualObjectiveChange,
  onCreateManualObjective,
}: ObjectiveClusteringSectionProps) {
  const modeCardTone = (label: string, active: boolean) => {
    const key = getModeVisualKey(label);
    const styles: Record<string, string> = {
      evidence: active ? 'border-sky-400 bg-sky-50' : 'border-sky-200 bg-sky-50/60',
      data: active ? 'border-indigo-400 bg-indigo-50' : 'border-indigo-200 bg-indigo-50/60',
      experiment: active ? 'border-emerald-400 bg-emerald-50' : 'border-emerald-200 bg-emerald-50/60',
      process: active ? 'border-cyan-400 bg-cyan-50' : 'border-cyan-200 bg-cyan-50/60',
      economics: active ? 'border-amber-400 bg-amber-50' : 'border-amber-200 bg-amber-50/60',
      sourcing: active ? 'border-lime-400 bg-lime-50' : 'border-lime-200 bg-lime-50/60',
      recovery: active ? 'border-fuchsia-400 bg-fuchsia-50' : 'border-fuchsia-200 bg-fuchsia-50/60',
      general: active ? 'border-slate-400 bg-slate-50' : 'border-slate-200 bg-slate-50/60',
    };
    return styles[key] || styles.general;
  };

  return (
    <section className="rounded-[1.75rem] border border-slate-200 bg-white/90 p-6 shadow-sm backdrop-blur">
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Step 4 / Objective Mode</div>
            <h3 className="mt-2 text-xl font-semibold text-slate-950">Choose the lens for the workspace</h3>
          </div>
          <button
            onClick={onGenerateModes}
            disabled={loadingObjectiveClusters || !canGenerateModes}
            className="rounded-2xl border border-slate-200 bg-slate-950 px-4 py-3 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loadingObjectiveClusters ? 'Generating Modes...' : objectiveClusters.length > 0 ? 'Refresh Objective Modes' : 'Generate Objective Modes'}
          </button>
        </div>
      </div>

      <div className="mt-5 rounded-[1.4rem] border border-dashed border-slate-300 bg-slate-50 p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Manual objective mode</div>
            <div className="mt-1 text-sm leading-6 text-slate-600">
              Add your own lens if the generated clusters miss the way this query should be handled.
            </div>
          </div>
          <button
            onClick={onToggleManualObjectiveForm}
            className="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-slate-50"
          >
            {showManualObjectiveForm ? 'Hide fields' : 'Add objective'}
          </button>
        </div>
        {showManualObjectiveForm && (
          <div className="mt-3 space-y-3">
            <div className="grid gap-3 lg:grid-cols-2">
              <input
                value={manualObjective.title}
                onChange={(event) => onManualObjectiveChange('title', event.target.value)}
                className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                placeholder="Title, e.g. Enzyme design validation"
              />
              <input
                value={manualObjective.subtitle}
                onChange={(event) => onManualObjectiveChange('subtitle', event.target.value)}
                className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                placeholder="Short subtitle"
              />
            </div>
            <textarea
              value={manualObjective.definition}
              onChange={(event) => onManualObjectiveChange('definition', event.target.value)}
              rows={3}
              className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
              placeholder="Define how this objective should condition the workspace"
            />
            <div className="grid gap-3 lg:grid-cols-3">
              <textarea
                value={manualObjective.signals}
                onChange={(event) => onManualObjectiveChange('signals', event.target.value)}
                rows={3}
                className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                placeholder="Signals, one per line"
              />
              <textarea
                value={manualObjective.facet_questions}
                onChange={(event) => onManualObjectiveChange('facet_questions', event.target.value)}
                rows={3}
                className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                placeholder="Refinement questions, one per line"
              />
              <textarea
                value={manualObjective.exemplar_answer}
                onChange={(event) => onManualObjectiveChange('exemplar_answer', event.target.value)}
                rows={3}
                className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                placeholder="What a good answer should look like"
              />
            </div>
            <div className="flex justify-end">
              <button
                onClick={onCreateManualObjective}
                disabled={!manualObjective.title.trim() || !manualObjective.definition.trim()}
                className="rounded-2xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Create objective
              </button>
            </div>
          </div>
        )}
      </div>

      {objectiveClusters.length === 0 ? (
        <div className="mt-5 rounded-[1.5rem] border border-dashed border-slate-300 bg-slate-50 p-6 text-sm text-slate-600">
          {canGenerateModes ? 'Generate objective modes from the current query.' : 'Choose a collaborator and query first.'}
        </div>
      ) : objectivePickerCollapsed && selectedObjective ? (
        <div className="mt-5 rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Selected Objective Mode</div>
              <div className="mt-2 text-lg font-semibold text-slate-950">{selectedObjective.title}</div>
              <div className="mt-1 text-sm text-slate-700">{selectedObjective.subtitle}</div>
              <div className="mt-3 text-sm leading-6 text-slate-600">{selectedObjective.definition}</div>
            </div>
            <button
              onClick={() => onSetObjectivePickerCollapsed(false)}
              className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-900 transition hover:bg-slate-50"
            >
              Choose another objective
            </button>
          </div>
          {selectedObjective.signals.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              {selectedObjective.signals.slice(0, 6).map((signal) => (
                <span key={signal} className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-700">
                  {signal}
                </span>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="mt-5 space-y-5">
          <div className="grid gap-3 xl:grid-cols-2">
            {objectiveClusters.map((objective) => {
              const active = selectedObjectiveId === objective.id;
              return (
                <button
                  key={objective.id}
                  onClick={() => {
                    onSelectObjective(objective.id);
                    onSetObjectivePickerCollapsed(true);
                  }}
                  className={classNames(
                    'rounded-[1.5rem] border p-4 text-left transition-all shadow-sm',
                    modeCardTone(objective.title, active),
                    active ? 'scale-[1.01]' : 'hover:-translate-y-0.5'
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-slate-950">{objective.title}</div>
                      <div className="mt-1 text-xs uppercase tracking-wide text-slate-500">{objective.id}</div>
                    </div>
                    {active && <span className="rounded-full bg-violet-100 px-2 py-0.5 text-[11px] font-semibold text-violet-900">Active</span>}
                  </div>
                  <div className="mt-2 text-sm text-slate-700">{objective.subtitle}</div>
                  <div className="mt-3 text-sm text-slate-600">{objective.definition}</div>
                  {objective.signals.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {objective.signals.slice(0, 6).map((signal) => (
                        <span key={signal} className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] text-slate-700">
                          {signal}
                        </span>
                      ))}
                    </div>
                  )}
                </button>
              );
            })}
          </div>

          {selectedObjective && (
            <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
              <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4">
                <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Active Mode</div>
                <div className="mt-2 text-lg font-semibold text-slate-950">{selectedObjective.title}</div>
                <div className="mt-1 text-sm text-slate-700">{selectedObjective.subtitle}</div>
                <div className="mt-3 text-sm leading-6 text-slate-700">{selectedObjective.definition}</div>
                <div className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
                  The next section is now framed by this mode. Continue downward to the workspace and start iterating inside that setting.
                </div>
                <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-3">
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Exemplar Answer Shape</div>
                  <div className="mt-2 text-sm text-slate-700">{selectedObjective.exemplar_answer}</div>
                </div>
              </div>

              <div className="space-y-4">
                <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4">
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Objective Refinement</div>
                  <div className="mt-2 space-y-3">
                    {selectedObjective.facet_questions.length === 0 ? (
                      <div className="text-sm text-slate-600">No follow-up questions were returned for this angle.</div>
                    ) : (
                      selectedObjective.facet_questions.map((question) => (
                        <div key={question} className="rounded-xl border border-slate-200 bg-white p-3">
                          <div className="text-sm text-slate-800">{question}</div>
                          <input
                            value={objectiveAnswers[question] || ''}
                            onChange={(e) => onObjectiveAnswerChange(question, e.target.value)}
                            className="mt-2 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900"
                            placeholder="Refine this objective angle"
                          />
                        </div>
                      ))
                    )}
                  </div>
                </div>

                {globalQuestions.length > 0 && (
                  <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4">
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Cross-Cutting Questions</div>
                    <div className="mt-2 space-y-3">
                      {globalQuestions.map((question) => (
                        <div key={question} className="rounded-xl border border-slate-200 bg-white p-3">
                          <div className="text-sm text-slate-800">{question}</div>
                          <input
                            value={globalQuestionAnswers[question] || ''}
                            onChange={(e) => onGlobalQuestionChange(question, e.target.value)}
                            className="mt-2 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900"
                            placeholder="Add a cross-cutting constraint or preference"
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
