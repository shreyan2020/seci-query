import type { ObjectiveFrame, ProjectPersona } from '@/features/biotech-workspace/types';
import { classNames, humanize, stageTone } from '@/features/biotech-workspace/lib/utils';

interface CollaboratorWorkspaceProps {
  selectedPersona: ProjectPersona;
  topRecommendedPersona: ProjectPersona | null;
  workspaceStatusMessage: string;
  clarifyingAnswers: Record<string, string>;
  onClarifyingAnswerChange: (question: string, value: string) => void;
  currentModeTitle: string;
  objectiveFrame: ObjectiveFrame;
  focusQuestion: string;
  onFocusQuestionChange: (value: string) => void;
  onClusterObjectives: () => void;
  loadingObjectiveClusters: boolean;
  onGeneratePlan: () => void;
  loadingPlan: boolean;
}

export function CollaboratorWorkspace({
  selectedPersona,
  topRecommendedPersona,
  workspaceStatusMessage,
  clarifyingAnswers,
  onClarifyingAnswerChange,
  currentModeTitle,
  objectiveFrame,
  focusQuestion,
  onFocusQuestionChange,
  onClusterObjectives,
  loadingObjectiveClusters,
  onGeneratePlan,
  loadingPlan,
}: CollaboratorWorkspaceProps) {
  return (
    <section className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
      <div className="rounded-[1.75rem] border border-slate-200 bg-white/90 p-5 shadow-sm backdrop-blur">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Active Collaborator</div>
            <div className="mt-2 text-xl font-semibold text-slate-950">{selectedPersona.name}</div>
          </div>
          <div className={classNames('rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-wide', stageTone(selectedPersona.workflow_stage))}>
            {humanize(selectedPersona.workflow_stage)}
          </div>
        </div>

        {topRecommendedPersona && topRecommendedPersona.persona_id !== selectedPersona.persona_id && (
          <div className="mt-3 rounded-2xl border border-violet-200 bg-violet-50 px-3 py-2 text-sm text-violet-900">
            Best fit for the current question: {topRecommendedPersona.name}. You can still work with {selectedPersona.name} if you want
            to push a different angle.
          </div>
        )}
        <div className="mt-2 text-xs text-slate-500">{workspaceStatusMessage}</div>

        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Primary Goals</div>
            <div className="mt-2 space-y-2">
              {selectedPersona.goals.length === 0 ? (
                <div className="text-sm text-slate-600">No persona goals yet.</div>
              ) : (
                selectedPersona.goals.map((goal) => (
                  <div key={goal} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800">
                    {goal}
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Prompted Inputs</div>
            <div className="mt-2 space-y-2">
              {selectedPersona.starter_questions.length === 0 ? (
                <div className="text-sm text-slate-600">No starter questions yet.</div>
              ) : (
                selectedPersona.starter_questions.map((question) => (
                  <div key={question} className="rounded-xl border border-slate-200 bg-white p-3">
                    <div className="text-sm text-slate-800">{question}</div>
                    <input
                      value={clarifyingAnswers[question] || ''}
                      onChange={(e) => onClarifyingAnswerChange(question, e.target.value)}
                      className="mt-2 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900"
                      placeholder="Capture an answer, assumption, or boundary"
                    />
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-[1.75rem] border border-slate-200 bg-white/90 p-5 shadow-sm backdrop-blur">
        <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Objective Or Working Question</div>
        <div className="mt-2 text-sm text-slate-600">
          This controls what kind of draft gets generated. It can be a literature synthesis question, an experiment plan, a bottleneck
          analysis, or a broader project question.
        </div>

        <div className="mt-3 rounded-2xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
          Current mode: {currentModeTitle}. {objectiveFrame.rawMaterialGuidance}
        </div>

        <textarea
          value={focusQuestion}
          onChange={(e) => onFocusQuestionChange(e.target.value)}
          rows={8}
          className="mt-4 w-full rounded-[1.5rem] border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900"
          placeholder="Example: What are the key successful common strategies and latest improvement options in microbial flavonoid production?"
        />

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <button
            onClick={onClusterObjectives}
            disabled={loadingObjectiveClusters}
            className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-900 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loadingObjectiveClusters ? 'Clustering...' : 'Cluster Objective Angles'}
          </button>
          <button
            onClick={onGeneratePlan}
            disabled={loadingPlan}
            className="rounded-2xl bg-slate-950 px-4 py-3 text-sm font-semibold text-white shadow-sm hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loadingPlan ? 'Drafting...' : `Generate ${objectiveFrame.draftLabel}`}
          </button>
        </div>
      </div>
    </section>
  );
}
