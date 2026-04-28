import type { TacitMemoryItem } from '@/features/biotech-workspace/types';
import { classNames } from '@/features/biotech-workspace/lib/utils';

interface WorkspaceMemoryPanelProps {
  workspaceKey: string;
  memoryStatus: string;
  tacitState: TacitMemoryItem[];
  handoffSummary: string;
  inferring: boolean;
  onInfer: () => void;
  onUpdateTacitItem: (id: string, patch: Partial<TacitMemoryItem>) => void;
}

export function WorkspaceMemoryPanel({
  workspaceKey,
  memoryStatus,
  tacitState,
  handoffSummary,
  inferring,
  onInfer,
  onUpdateTacitItem,
}: WorkspaceMemoryPanelProps) {
  return (
    <section className="rounded-[1.6rem] border border-amber-200 bg-[linear-gradient(135deg,rgba(255,251,235,0.96),rgba(255,255,255,0.9))] p-4 shadow-[0_24px_80px_-55px_rgba(120,53,15,0.55)]">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-amber-800">Workspace Memory</div>
          <div className="mt-1 text-lg font-semibold text-slate-950">Explicit state plus reviewable tacit knowledge</div>
          <div className="mt-1 max-w-3xl text-sm leading-6 text-slate-700">
            This is the durable handoff layer for the current project workspace. It saves visible selections and lets the system surface
            assumptions, constraints, preferences, and onboarding-relevant context for user review.
          </div>
          <div className="mt-2 text-xs text-slate-500">
            {workspaceKey} · {memoryStatus}
          </div>
        </div>
        <button
          onClick={onInfer}
          disabled={inferring}
          className="rounded-2xl bg-amber-950 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-amber-900 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {inferring ? 'Inferring...' : 'Infer tacit state'}
        </button>
      </div>

      {handoffSummary && (
        <div className="mt-4 rounded-2xl border border-amber-200 bg-white/80 p-3">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-amber-800">Handoff summary</div>
          <div className="mt-1 text-sm leading-6 text-slate-800">{handoffSummary}</div>
        </div>
      )}

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        {tacitState.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-amber-300 bg-white/60 p-4 text-sm leading-6 text-slate-600">
            No tacit memory items yet. Once the user selects a collaborator/objective or adds judgments, infer and review the hidden state
            here before it becomes project memory.
          </div>
        ) : (
          tacitState.map((item) => (
            <div
              key={item.id}
              className={classNames(
                'rounded-2xl border bg-white p-4',
                item.status === 'confirmed'
                  ? 'border-emerald-200'
                  : item.status === 'rejected'
                    ? 'border-rose-200 opacity-75'
                    : 'border-amber-100'
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-slate-950">{item.label}</div>
                  <div className="mt-1 text-sm leading-6 text-slate-700">{item.inference}</div>
                </div>
                <select
                  value={item.status}
                  onChange={(event) => onUpdateTacitItem(item.id, { status: event.target.value as TacitMemoryItem['status'] })}
                  className="rounded-xl border border-slate-200 bg-white px-2 py-1 text-xs text-slate-800"
                >
                  <option value="inferred">Inferred</option>
                  <option value="confirmed">Confirmed</option>
                  <option value="edited">Edited</option>
                  <option value="rejected">Rejected</option>
                </select>
              </div>

              {item.evidence.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {item.evidence.slice(0, 4).map((evidence, index) => (
                    <span key={`${item.id}-${index}`} className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] text-slate-600">
                      {evidence}
                    </span>
                  ))}
                </div>
              )}

              <div className="mt-2 text-[11px] font-medium text-slate-500">Confidence {Math.round((item.confidence || 0) * 100)}%</div>
              <textarea
                value={item.reviewer_note || ''}
                onChange={(event) =>
                  onUpdateTacitItem(item.id, {
                    reviewer_note: event.target.value,
                    status: item.status === 'inferred' ? 'edited' : item.status,
                  })
                }
                rows={2}
                className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                placeholder="Reviewer note: correct, nuance, or reject this inferred tacit knowledge..."
              />
            </div>
          ))
        )}
      </div>
    </section>
  );
}
