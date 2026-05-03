'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';

import { fetchProjectJourney } from '@/features/biotech-workspace/lib/api';
import { classNames } from '@/features/biotech-workspace/lib/utils';
import type { ProjectJourneyResponse } from '@/features/biotech-workspace/types';

function statLabel(value: number, label: string) {
  return `${value} ${label}${value === 1 ? '' : 's'}`;
}

function formatTime(value: string) {
  if (!value) return 'Unknown time';
  const date = new Date(value.endsWith('Z') ? value : `${value}Z`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export default function ProjectJourneyPage() {
  const searchParams = useSearchParams();
  const projectIdRaw = searchParams.get('projectId') || '';
  const projectId = Number(projectIdRaw);
  const [journey, setJourney] = useState<ProjectJourneyResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectIdRaw || !Number.isFinite(projectId)) {
      setJourney(null);
      setError('Open a project journey from the workspace so the page knows which project to summarize.');
      return;
    }
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetchProjectJourney(projectId);
        if (!cancelled) setJourney(response);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load journey');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load().catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [projectIdRaw, projectId]);

  const latestEvent = useMemo(() => journey?.events[journey.events.length - 1] || null, [journey?.events]);

  if (loading) {
    return <main className="min-h-screen bg-slate-950 p-8 text-white">Loading project journey...</main>;
  }

  if (error || !journey) {
    return (
      <main className="min-h-screen bg-slate-950 p-8 text-white">
        <div className="mx-auto max-w-3xl rounded-3xl border border-white/10 bg-white/8 p-8">
          <div className="text-sm font-semibold uppercase tracking-[0.28em] text-amber-200">Project Journey</div>
          <h1 className="mt-4 text-3xl font-semibold">No journey loaded</h1>
          <p className="mt-3 text-slate-300">{error}</p>
          <Link className="mt-6 inline-flex rounded-2xl bg-white px-4 py-2 text-sm font-semibold text-slate-950" href="/">
            Back to workspace
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,#164e63_0,#0f172a_34%,#020617_100%)] p-4 text-white md:p-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <section className="overflow-hidden rounded-[2rem] border border-white/10 bg-white/10 p-6 shadow-2xl backdrop-blur md:p-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.32em] text-cyan-200">User Journey Snapshot</div>
              <h1 className="mt-4 max-w-4xl text-4xl font-semibold tracking-tight md:text-5xl">{journey.project.name}</h1>
              <p className="mt-4 max-w-3xl text-base leading-7 text-slate-200">
                This page summarizes the exploration paths inside the project: queries, collaborators, objective modes, literature work,
                judgments, and draft/proposal activity. Use it as the map back into experiments you may want to revise or extend.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Link
                href={`/?projectId=${journey.project.id}`}
                className="rounded-2xl border border-white/15 bg-white px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-50"
              >
                Back to project
              </Link>
              <Link
                href="/"
                className="rounded-2xl border border-white/15 bg-white/10 px-4 py-2 text-sm font-semibold text-white hover:bg-white/15"
              >
                All projects
              </Link>
            </div>
          </div>

          <div className="mt-8 grid gap-3 md:grid-cols-3 xl:grid-cols-6">
            {[
              statLabel(journey.summary.total_queries, 'query'),
              statLabel(journey.summary.explored_collaborators, 'collaborator'),
              statLabel(journey.summary.explored_objectives, 'objective'),
              statLabel(journey.summary.literature_findings, 'literature item'),
              statLabel(journey.summary.judgment_calls, 'judgment'),
              statLabel(journey.summary.proposal_candidates, 'proposal seed'),
            ].map((item) => (
              <div key={item} className="rounded-3xl border border-white/10 bg-white/10 p-4">
                <div className="text-xl font-semibold">{item.split(' ')[0]}</div>
                <div className="mt-1 text-xs uppercase tracking-[0.2em] text-slate-300">{item.split(' ').slice(1).join(' ')}</div>
              </div>
            ))}
          </div>
        </section>

        <div className="grid gap-6 xl:grid-cols-[1.6fr_0.9fr]">
          <section className="space-y-4">
            {journey.paths.length === 0 ? (
              <div className="rounded-[2rem] border border-white/10 bg-white/10 p-8 text-slate-200">
                No query paths yet. Create a query in the workspace and this page will become the exploration map.
              </div>
            ) : (
              journey.paths.map((path, index) => {
                const reopenHref = `/?projectId=${journey.project.id}${path.selected_persona_id ? `&personaId=${path.selected_persona_id}` : ''}&queryId=${path.query_id}`;
                return (
                  <article key={path.id} className="rounded-[2rem] border border-white/10 bg-white/[0.93] p-5 text-slate-950 shadow-xl">
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                      <div>
                        <div className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-700">Exploration {index + 1}</div>
                        <h2 className="mt-2 text-2xl font-semibold">{path.query_title || 'Untitled query'}</h2>
                        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{path.query}</p>
                      </div>
                      <Link
                        href={reopenHref}
                        className="shrink-0 rounded-2xl bg-slate-950 px-4 py-2 text-center text-sm font-semibold text-white hover:bg-cyan-950"
                      >
                        Reopen path
                      </Link>
                    </div>

                    <div className="mt-5 grid gap-3 md:grid-cols-2">
                      <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
                        <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Collaborator</div>
                        <div className="mt-2 font-semibold">{path.selected_persona_name || 'Not selected yet'}</div>
                      </div>
                      <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
                        <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Objective Mode</div>
                        <div className="mt-2 font-semibold">{path.selected_objective_title || 'Not selected yet'}</div>
                      </div>
                    </div>

                    <p className="mt-5 rounded-3xl border border-cyan-100 bg-cyan-50 p-4 text-sm leading-6 text-cyan-950">{path.summary}</p>

                    <div className="mt-4 flex flex-wrap gap-2">
                      {[
                        `${path.literature_count} literature`,
                        `${path.judgment_count} judgments`,
                        `${path.gap_count} gaps`,
                        `${path.proposal_count} proposals`,
                        `${path.plan_step_count} plan steps`,
                      ].map((label) => (
                        <span key={label} className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-700">
                          {label}
                        </span>
                      ))}
                    </div>

                    <div className="mt-5 rounded-3xl border border-amber-100 bg-amber-50 p-4 text-sm text-amber-950">
                      <span className="font-semibold">Suggested next move:</span> {path.next_action_hint}
                    </div>

                    {path.recent_events.length > 0 && (
                      <div className="mt-5 space-y-2">
                        <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Recent trail</div>
                        {path.recent_events.map((event) => (
                          <div key={event.id} className="flex gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm">
                            <div className="mt-1 h-2 w-2 rounded-full bg-cyan-500" />
                            <div>
                              <div className="font-semibold">{event.title}</div>
                              <div className="text-xs text-slate-500">{formatTime(event.timestamp)}</div>
                              {event.detail && <div className="mt-1 text-slate-600">{event.detail}</div>}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </article>
                );
              })
            )}
          </section>

          <aside className="space-y-4 xl:sticky xl:top-6 xl:self-start">
            <div className="rounded-[2rem] border border-white/10 bg-white/10 p-5 backdrop-blur">
              <div className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-200">Project Frame</div>
              <dl className="mt-4 space-y-4 text-sm">
                <div>
                  <dt className="text-slate-400">Goal</dt>
                  <dd className="mt-1 text-slate-100">{journey.project.project_goal || 'Not set'}</dd>
                </div>
                <div>
                  <dt className="text-slate-400">End product</dt>
                  <dd className="mt-1 text-slate-100">{journey.project.end_product}</dd>
                </div>
                <div>
                  <dt className="text-slate-400">Target host</dt>
                  <dd className="mt-1 text-slate-100">{journey.project.target_host}</dd>
                </div>
                {latestEvent && (
                  <div>
                    <dt className="text-slate-400">Latest event</dt>
                    <dd className="mt-1 text-slate-100">{latestEvent.title}</dd>
                    <dd className="mt-1 text-xs text-slate-400">{formatTime(latestEvent.timestamp)}</dd>
                  </div>
                )}
              </dl>
            </div>

            <div className="rounded-[2rem] border border-white/10 bg-white/10 p-5 backdrop-blur">
              <div className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-200">Chronological Events</div>
              <div className="mt-4 max-h-[36rem] space-y-3 overflow-auto pr-1">
                {journey.events.length === 0 ? (
                  <div className="text-sm text-slate-300">No project events logged yet.</div>
                ) : (
                  journey.events
                    .slice()
                    .reverse()
                    .map((event) => (
                      <div key={event.id} className={classNames('rounded-2xl border border-white/10 bg-white/10 p-3 text-sm')}>
                        <div className="font-semibold text-white">{event.title}</div>
                        <div className="mt-1 text-xs text-slate-400">{formatTime(event.timestamp)}</div>
                        {event.detail && <div className="mt-2 text-slate-300">{event.detail}</div>}
                      </div>
                    ))
                )}
              </div>
            </div>
          </aside>
        </div>
      </div>
    </main>
  );
}
