import type { RankedPersona } from '@/features/biotech-workspace/types';
import { classNames, humanize, stageTone } from '@/features/biotech-workspace/lib/utils';

interface CollaboratorGridProps {
  rankedPersonas: RankedPersona[];
  selectedPersonaId: number | '';
  onSelectPersona: (personaId: number) => void;
}

export function CollaboratorGrid({ rankedPersonas, selectedPersonaId, onSelectPersona }: CollaboratorGridProps) {
  return (
    <section className="rounded-[1.75rem] border border-slate-200 bg-white/90 p-6 shadow-sm backdrop-blur">
      <div>
        <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Recommended Collaborators</div>
        <div className="mt-1 text-sm text-slate-600">
          These collaborators stay attached to the project, but the working question changes who rises to the top. An experiment-plan
          question should rank differently from a literature review or a sourcing question.
        </div>
      </div>

      <div className="mt-4 grid gap-3 xl:grid-cols-3">
        {rankedPersonas.map(({ persona, score }) => {
          const active = selectedPersonaId === persona.persona_id;
          const recommended = score >= 3;
          return (
            <button
              key={persona.persona_id}
              onClick={() => onSelectPersona(persona.persona_id)}
              className={classNames(
                'rounded-[1.5rem] border p-4 text-left transition',
                active ? 'border-slate-900 bg-slate-950 text-white shadow-sm' : 'border-slate-200 bg-white hover:bg-slate-50'
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div
                    className={classNames(
                      'inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide',
                      active ? 'border-white/20 bg-white/10 text-white' : stageTone(persona.workflow_stage)
                    )}
                  >
                    {humanize(persona.workflow_stage)}
                  </div>
                  <div className={classNames('mt-3 text-base font-semibold', active ? 'text-white' : 'text-slate-950')}>
                    {persona.name}
                  </div>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <span className={classNames('rounded-full px-2 py-0.5 text-[11px]', active ? 'bg-white/10 text-white' : 'bg-slate-100 text-slate-700')}>
                    v{persona.version}
                  </span>
                  {recommended && (
                    <span
                      className={classNames(
                        'rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide',
                        active ? 'bg-emerald-400/20 text-emerald-100' : 'bg-emerald-100 text-emerald-900'
                      )}
                    >
                      Recommended
                    </span>
                  )}
                </div>
              </div>
              <div className={classNames('mt-2 text-sm', active ? 'text-slate-200' : 'text-slate-600')}>{persona.focus_area}</div>
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
