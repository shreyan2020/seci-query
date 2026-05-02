import type { AgenticPlan, ObjectiveCluster, Project, ProjectPersona } from '@/features/biotech-workspace/types';
import { classNames, humanize, stageTone } from '@/features/biotech-workspace/lib/utils';

interface WorkflowStateSidebarProps {
  selectedProject: Project;
  focusQuestion: string;
  selectedPersona: ProjectPersona | null;
  selectedObjective: ObjectiveCluster | null;
  agenticPlan: AgenticPlan | null;
  workspaceStatusMessage: string;
  onEditQuestion: () => void;
  onChangeCollaborator: () => void;
  onChangeObjective: () => void;
  onOpenDraft: () => void;
}

function SidebarRow({
  label,
  value,
  detail,
  actionLabel,
  onAction,
  active,
}: {
  label: string;
  value: string;
  detail?: string;
  actionLabel: string;
  onAction: () => void;
  active: boolean;
}) {
  return (
    <div className={classNames('border-t border-slate-200 px-4 py-4', active ? 'bg-white' : 'bg-slate-50/70')}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">{label}</div>
          <div className="mt-1 line-clamp-2 text-sm font-semibold leading-5 text-slate-950">{value}</div>
        </div>
        <button
          onClick={onAction}
          className="shrink-0 rounded-xl border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700 transition hover:bg-slate-50"
        >
          {actionLabel}
        </button>
      </div>
      {detail && <div className="mt-2 line-clamp-3 text-xs leading-5 text-slate-600">{detail}</div>}
    </div>
  );
}

export function WorkflowStateSidebar({
  selectedProject,
  focusQuestion,
  selectedPersona,
  selectedObjective,
  agenticPlan,
  workspaceStatusMessage,
  onEditQuestion,
  onChangeCollaborator,
  onChangeObjective,
  onOpenDraft,
}: WorkflowStateSidebarProps) {
  return (
    <aside className="rounded-none border border-slate-200 bg-white/95 shadow-[18px_0_70px_-55px_rgba(15,23,42,0.65)] backdrop-blur xl:sticky xl:top-3 xl:max-h-[calc(100vh-1.5rem)] xl:overflow-y-auto">
      <div className="border-b border-slate-200 p-4">
        <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Project Console</div>
        <div className="mt-2 text-lg font-semibold text-slate-950">{selectedProject.name}</div>
        <div className="mt-2 text-xs leading-5 text-slate-500">{workspaceStatusMessage}</div>
      </div>

      <div className="grid grid-cols-2 gap-2 border-b border-slate-200 bg-slate-50/80 p-3">
        {['Projects', 'Queries', 'Papers', 'Drafts'].map((item) => (
          <div key={item} className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-center text-[11px] font-semibold text-slate-700">
            {item}
          </div>
        ))}
      </div>

      <SidebarRow
        label="Question"
        value={focusQuestion.trim() || selectedProject.project_goal || 'No working question yet'}
        actionLabel="Edit"
        onAction={onEditQuestion}
        active={Boolean(focusQuestion.trim())}
      />

      <div className={classNames('border-t border-slate-200 px-4 py-4', selectedPersona ? 'bg-white' : 'bg-slate-50/70')}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">Collaborator</div>
            <div className="mt-1 line-clamp-2 text-sm font-semibold leading-5 text-slate-950">
              {selectedPersona?.name || 'Not selected'}
            </div>
          </div>
          <button
            onClick={onChangeCollaborator}
            className="shrink-0 rounded-xl border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            Change
          </button>
        </div>
        {selectedPersona && (
          <div className="mt-3 space-y-2">
            <span className={classNames('inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide', stageTone(selectedPersona.workflow_stage))}>
              {humanize(selectedPersona.workflow_stage)}
            </span>
            <div className="line-clamp-3 text-xs leading-5 text-slate-600">{selectedPersona.focus_area}</div>
          </div>
        )}
      </div>

      <SidebarRow
        label="Objective Mode"
        value={selectedObjective?.title || 'Not selected'}
        detail={selectedObjective?.subtitle}
        actionLabel={selectedObjective ? 'Change' : 'Open'}
        onAction={onChangeObjective}
        active={Boolean(selectedObjective)}
      />

      <SidebarRow
        label="Draft"
        value={agenticPlan?.plan_title || 'No generated draft yet'}
        detail={agenticPlan ? `${agenticPlan.steps.length} editable steps` : 'Generate a draft after selecting an objective mode.'}
        actionLabel="Open"
        onAction={onOpenDraft}
        active={Boolean(agenticPlan)}
      />
    </aside>
  );
}
