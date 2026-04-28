import Link from 'next/link';

import type { StatusState } from '@/features/biotech-workspace/types';
import { classNames } from '@/features/biotech-workspace/lib/utils';

interface WorkspaceHeaderProps {
  selectedProject: boolean;
  onReturnToLanding: () => void;
  status: StatusState | null;
}

export function WorkspaceHeader({ selectedProject, onReturnToLanding, status }: WorkspaceHeaderProps) {
  return (
    <section className="rounded-[2rem] border border-emerald-200/70 bg-white/90 p-6 shadow-[0_30px_90px_-40px_rgba(15,23,42,0.45)] backdrop-blur">
      <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
        <div className="max-w-3xl">
          <div className="inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.28em] text-emerald-900">
            Biotech Program Workspace
          </div>
          <h1 className="mt-4 text-3xl font-semibold tracking-tight text-slate-950 md:text-4xl">Biotech project workspace</h1>
          <p className="mt-3 text-sm leading-6 text-slate-600 md:text-base">
            Start with the project goal, write the working question you actually want answered, and let the system surface the
            collaborators that fit that question. From there, capture structured literature-to-proposal reasoning before generating a
            draft that can stay literature-first, experiment-first, or broader depending on what you ask.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          {selectedProject && (
            <button
              onClick={onReturnToLanding}
              className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-900 hover:bg-emerald-100"
            >
              All Projects
            </button>
          )}
          <Link
            href="/personas"
            className="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-slate-50"
          >
            Persona Studio
          </Link>
          <Link
            href="/reports"
            className="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-slate-50"
          >
            Reports
          </Link>
        </div>
      </div>

      {status && (
        <div
          className={classNames(
            'mt-5 rounded-2xl border px-4 py-3 text-sm',
            status.type === 'success' && 'border-emerald-200 bg-emerald-50 text-emerald-900',
            status.type === 'error' && 'border-rose-200 bg-rose-50 text-rose-900',
            status.type === 'info' && 'border-sky-200 bg-sky-50 text-sky-900'
          )}
        >
          {status.message}
        </div>
      )}
    </section>
  );
}
