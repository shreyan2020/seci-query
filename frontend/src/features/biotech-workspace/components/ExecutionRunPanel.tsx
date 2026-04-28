import type { ProjectExecutionEvent, ProjectExecutionRun } from '@/features/biotech-workspace/types';
import { classNames, humanize } from '@/features/biotech-workspace/lib/utils';

interface ExecutionRunPanelProps {
  executionRun: ProjectExecutionRun | null;
  executionEvents: ProjectExecutionEvent[];
  startingExecution: boolean;
  onStartExecution: () => void;
  onRefreshExecution: () => void;
}

function statusTone(status: ProjectExecutionRun['status'] | 'idle') {
  switch (status) {
    case 'running':
      return 'border-sky-300 bg-sky-50 text-sky-900';
    case 'queued':
      return 'border-amber-300 bg-amber-50 text-amber-900';
    case 'completed':
      return 'border-emerald-300 bg-emerald-50 text-emerald-900';
    case 'failed':
      return 'border-rose-300 bg-rose-50 text-rose-900';
    default:
      return 'border-slate-300 bg-slate-50 text-slate-900';
  }
}

function payloadPreview(payload: Record<string, unknown>) {
  const textItems = Object.values(payload).flatMap((value) => {
    if (typeof value === 'string') return [value];
    if (Array.isArray(value)) {
      return value.filter((item): item is string => typeof item === 'string');
    }
    return [];
  });
  return textItems
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 4);
}

export function ExecutionRunPanel({
  executionRun,
  executionEvents,
  startingExecution,
  onStartExecution,
  onRefreshExecution,
}: ExecutionRunPanelProps) {
  const status = executionRun?.status || 'idle';
  const live = executionRun?.status === 'queued' || executionRun?.status === 'running';

  return (
    <div className="relative mt-5 rounded-[1.5rem] border border-slate-200 bg-white/88 p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Agentic Execution</div>
          <div className="mt-1 text-sm text-slate-600">
            Run the workspace as a staged execution flow so the system actively processes the template, emits intermediate reasoning,
            and refreshes the draft when it finishes.
          </div>
        </div>
        <div className="flex flex-wrap gap-3">
          <div className={classNames('rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-wide', statusTone(status))}>
            {status === 'idle' ? 'Idle' : humanize(status)}
          </div>
          <button
            onClick={onRefreshExecution}
            className="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-slate-50"
          >
            Refresh
          </button>
          <button
            onClick={onStartExecution}
            disabled={startingExecution || live}
            className="rounded-2xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {startingExecution ? 'Starting...' : live ? 'Execution Running' : 'Run Agentic Execution'}
          </button>
        </div>
      </div>

      {!executionRun ? (
        <div className="mt-4 rounded-2xl border border-dashed border-slate-300 bg-slate-50/80 p-4 text-sm text-slate-600">
          No execution run yet. Start one to see the agent work through scope framing, evidence synthesis, validation design, and
          proposal drafting.
        </div>
      ) : (
        <>
          <div className="mt-4 grid gap-3 lg:grid-cols-[1.05fr_0.95fr]">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Run Summary</div>
              <div className="mt-2 text-sm text-slate-800">
                {executionRun.summary || 'The run is using the current workspace and will attach a summary once later stages complete.'}
              </div>
              <div className="mt-3 grid gap-2 text-xs text-slate-500 sm:grid-cols-2">
                <div>Run ID: {executionRun.id}</div>
                <div>Current stage: {executionRun.current_stage ? humanize(executionRun.current_stage) : 'Not started'}</div>
                <div>Created: {new Date(executionRun.created_at).toLocaleString()}</div>
                <div>Updated: {new Date(executionRun.updated_at).toLocaleString()}</div>
              </div>
              {executionRun.error_message && (
                <div className="mt-3 rounded-2xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900">{executionRun.error_message}</div>
              )}
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Applied Output</div>
              <div className="mt-2 text-sm text-slate-700">
                {executionRun.final_plan
                  ? `${executionRun.final_plan.plan_title} with ${executionRun.final_plan.steps.length} steps was applied back into the workspace.`
                  : 'The final plan will appear here once the run completes.'}
              </div>
              {executionRun.final_work_template && (
                <div className="mt-3 grid gap-2 text-xs text-slate-600 sm:grid-cols-2">
                  <div>Findings: {executionRun.final_work_template.literature_findings.length}</div>
                  <div>Gaps: {executionRun.final_work_template.common_gaps.length}</div>
                  <div>Validation tracks: {executionRun.final_work_template.validation_tracks.length}</div>
                  <div>Proposal candidates: {executionRun.final_work_template.proposal_candidates.length}</div>
                </div>
              )}
            </div>
          </div>

          <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Execution Timeline</div>
            <div className="mt-3 space-y-3">
              {executionEvents.length === 0 ? (
                <div className="text-sm text-slate-600">Events will appear here as the agent works through the run.</div>
              ) : (
                executionEvents.map((event) => {
                  const preview = payloadPreview(event.payload);
                  return (
                    <div key={event.id} className="rounded-2xl border border-slate-200 bg-white p-3">
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <div className="text-sm font-semibold text-slate-950">{event.title || humanize(event.event_type)}</div>
                          <div className="mt-1 text-sm text-slate-700">{event.detail}</div>
                        </div>
                        <div className="text-xs text-slate-500">{new Date(event.created_at).toLocaleTimeString()}</div>
                      </div>
                      {preview.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {preview.map((item) => (
                            <span key={item} className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] text-slate-700">
                              {item}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
