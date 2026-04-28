import type { ProjectPersona, RankedPersona } from '@/features/biotech-workspace/types';
import { classNames, humanize, stageTone } from '@/features/biotech-workspace/lib/utils';

interface QueryAlignmentSectionProps {
  activeStep: 'collaborator' | 'query';
  focusQuestion: string;
  onFocusQuestionChange: (value: string) => void;
  rankedPersonas: RankedPersona[];
  selectedPersonaId: number | '';
  onSelectPersona: (personaId: number) => void;
  selectedPersona: ProjectPersona | null;
  topRecommendedPersona: ProjectPersona | null;
  clarifyingAnswers: Record<string, string>;
  onClarifyingAnswerChange: (question: string, value: string) => void;
  onSubmitQuery: () => void;
  submittingQuery: boolean;
}

function sentenceCase(value: string) {
  const normalized = humanize(value).replace(/\s+/g, ' ').trim();
  if (!normalized) return '';
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

function compactRoleLabel(role: string) {
  return sentenceCase(role).replace(/\b\w/g, (match, index) => (index === 0 ? match : match.toLowerCase()));
}

function buildPersonaHighlights(persona: ProjectPersona) {
  const leadGoal = persona.goals[0] || '';
  const supportGoal = persona.goals[1] || '';

  return [
    {
      label: 'Best for',
      value: persona.focus_area || persona.summary || 'General project support',
    },
    {
      label: 'Leads with',
      value: persona.workflow_focus.slice(0, 2).join(' and ') || 'Cross-functional workflow reasoning',
    },
    {
      label: 'Primary outcome',
      value: leadGoal || 'No primary outcome captured yet',
    },
    {
      label: 'Also watches',
      value: supportGoal || persona.workflow_focus[2] || 'Secondary tradeoffs and downstream implications',
    },
  ];
}

export function QueryAlignmentSection({
  activeStep,
  focusQuestion,
  onFocusQuestionChange,
  rankedPersonas,
  selectedPersonaId,
  onSelectPersona,
  selectedPersona,
  topRecommendedPersona,
  clarifyingAnswers,
  onClarifyingAnswerChange,
  onSubmitQuery,
  submittingQuery,
}: QueryAlignmentSectionProps) {
  if (activeStep === 'collaborator') {
    return (
      <section className="rounded-[1.75rem] border border-slate-200 bg-white/90 p-6 shadow-sm backdrop-blur">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Step 2 / Collaborator</div>
            <h3 className="mt-2 text-xl font-semibold text-slate-950">Choose who should frame the next move</h3>
          </div>
          <div className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-slate-700">
            {rankedPersonas.length} agents
          </div>
        </div>

        <div className="mt-5 grid gap-3 xl:grid-cols-2">
          {rankedPersonas.map(({ persona, score }) => {
            const active = selectedPersonaId === persona.persona_id;
            const recommended = score >= 3 || topRecommendedPersona?.persona_id === persona.persona_id;
            const highlights = buildPersonaHighlights(persona);
            return (
              <button
                key={persona.persona_id}
                onClick={() => onSelectPersona(persona.persona_id)}
                className={classNames(
                  'rounded-[1.4rem] border p-4 text-left transition-all',
                  active ? 'border-slate-900 bg-slate-950 text-white shadow-sm' : 'border-slate-200 bg-white hover:-translate-y-0.5 hover:bg-slate-50'
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-2">
                    <div
                      className={classNames(
                        'inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide',
                        active ? 'border-white/20 bg-white/10 text-white' : stageTone(persona.workflow_stage)
                      )}
                    >
                      {humanize(persona.workflow_stage)}
                    </div>
                    <div className={classNames('text-lg font-semibold', active ? 'text-white' : 'text-slate-950')}>{persona.name}</div>
                  </div>

                  {(recommended || active) && (
                    <span
                      className={classNames(
                        'rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide',
                        active ? 'bg-white/10 text-white' : 'bg-emerald-100 text-emerald-900'
                      )}
                    >
                      {active ? 'Selected' : 'Best Match'}
                    </span>
                  )}
                </div>

                <div className={classNames('mt-2 text-xs font-medium uppercase tracking-[0.18em]', active ? 'text-slate-300' : 'text-slate-500')}>
                  {compactRoleLabel(persona.role)}
                </div>
                <div className={classNames('mt-3 text-sm leading-6', active ? 'text-slate-100' : 'text-slate-700')}>{highlights[0].value}</div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {persona.workflow_focus.slice(0, 3).map((item) => (
                    <span
                      key={item}
                      className={classNames(
                        'rounded-full px-2 py-0.5 text-[11px]',
                        active ? 'bg-white/10 text-white' : 'border border-slate-200 bg-slate-50 text-slate-700'
                      )}
                    >
                      {item}
                    </span>
                  ))}
                </div>
              </button>
            );
          })}
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-[1.75rem] border border-slate-200 bg-white/90 p-6 shadow-sm backdrop-blur">
      <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-5">
        <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Step 3 / Working Query</div>
        <h3 className="mt-2 text-xl font-semibold text-slate-950">Write the question for this collaborator</h3>

        <textarea
          value={focusQuestion}
          onChange={(e) => onFocusQuestionChange(e.target.value)}
          rows={7}
          className="mt-4 w-full rounded-[1.25rem] border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900"
          placeholder="Example: What are the key successful common strategies and latest improvement options in microbial flavonoid production?"
        />

        {selectedPersona && selectedPersona.starter_questions.length > 0 && (
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            {selectedPersona.starter_questions.map((question) => (
              <div key={question} className="rounded-xl border border-slate-200 bg-white p-3">
                <div className="text-sm text-slate-800">{question}</div>
                <input
                  value={clarifyingAnswers[question] || ''}
                  onChange={(e) => onClarifyingAnswerChange(question, e.target.value)}
                  className="mt-2 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900"
                  placeholder="Answer, assumption, or boundary"
                />
              </div>
            ))}
          </div>
        )}

        <div className="mt-4 flex justify-end">
          <button
            onClick={onSubmitQuery}
            disabled={!focusQuestion.trim() || submittingQuery}
            className="rounded-2xl bg-slate-950 px-4 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submittingQuery ? 'Generating objective modes...' : 'Generate objective modes'}
          </button>
        </div>
      </div>
    </section>
  );
}
