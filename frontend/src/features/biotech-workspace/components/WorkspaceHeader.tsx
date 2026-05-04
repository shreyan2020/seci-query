import Link from 'next/link';

import type { StatusState } from '@/features/biotech-workspace/types';
import { classNames } from '@/features/biotech-workspace/lib/utils';

interface WorkspaceHeaderProps {
  selectedProject: boolean;
  onReturnToLanding: () => void;
  onOpenMemory?: () => void;
  journeyHref?: string;
  memoryItemCount?: number;
  status: StatusState | null;
}

export function WorkspaceHeader({ selectedProject, onReturnToLanding, onOpenMemory, journeyHref, memoryItemCount = 0, status }: WorkspaceHeaderProps) {
  return (
    <section className="rounded-none border border-emerald-200/70 bg-white/90 p-6 shadow-[0_24px_70px_-45px_rgba(15,23,42,0.45)] backdrop-blur">
      <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
        <div className="max-w-3xl">
          <div className="inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.28em] text-emerald-900">
            Biotech Program Workspace
          </div>
          <h1 className="mt-4 text-3xl font-semibold tracking-tight text-slate-950 md:text-4xl">Biotech project workspace</h1>
        </div>

        <div className="flex flex-wrap gap-2">
          {selectedProject && (
            <>
              {onOpenMemory && (
                <button
                  onClick={onOpenMemory}
                  className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-2 text-sm font-semibold text-amber-950 hover:bg-amber-100"
                >
                  Workspace Memory{memoryItemCount > 0 ? ` (${memoryItemCount})` : ''}
                </button>
              )}
              {journeyHref && (
                <Link
                  href={journeyHref}
                  className="rounded-2xl border border-cyan-200 bg-cyan-50 px-4 py-2 text-sm font-semibold text-cyan-950 hover:bg-cyan-100"
                >
                  User Journey
                </Link>
              )}
              <button
                onClick={onReturnToLanding}
                className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-900 hover:bg-emerald-100"
              >
                All Projects
              </button>
            </>
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
