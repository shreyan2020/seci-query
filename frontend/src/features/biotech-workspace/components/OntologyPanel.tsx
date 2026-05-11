import { useMemo } from 'react';

import type { OntologyPreviewResponse } from '@/features/biotech-workspace/types';
import { classNames } from '@/features/biotech-workspace/lib/utils';

interface OntologyPanelProps {
  preview: OntologyPreviewResponse | null;
  loading: boolean;
  status: string;
  onRefresh: () => void;
  onReviewNode: (nodeId: string, status: 'confirmed' | 'rejected') => void;
}

const nodeTone: Record<string, string> = {
  project: 'border-slate-300 bg-slate-50 text-slate-800',
  paper: 'border-sky-200 bg-sky-50 text-sky-900',
  concept: 'border-emerald-200 bg-emerald-50 text-emerald-900',
  gap: 'border-rose-200 bg-rose-50 text-rose-900',
  validation: 'border-violet-200 bg-violet-50 text-violet-900',
  proposal: 'border-amber-200 bg-amber-50 text-amber-900',
  tacit_memory: 'border-orange-200 bg-orange-50 text-orange-900',
  plan_step: 'border-indigo-200 bg-indigo-50 text-indigo-900',
};

const statusTone: Record<string, string> = {
  confirmed: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  rejected: 'border-rose-200 bg-rose-50 text-rose-800',
  edited: 'border-amber-200 bg-amber-50 text-amber-800',
  inferred: 'border-slate-200 bg-white text-slate-600',
};

function relationLabel(value: string) {
  return value.replace(/_/g, ' ');
}

export function OntologyPanel({ preview, loading, status, onRefresh, onReviewNode }: OntologyPanelProps) {
  const topNodes = preview?.nodes.slice(0, 18) || [];
  const topEdges = preview?.edges.slice(0, 10) || [];
  const augmentation = preview?.query_augmentation;
  const nodesById = useMemo(() => new Map((preview?.nodes || []).map((node) => [node.id, node])), [preview?.nodes]);
  const reviewCandidates = useMemo(
    () => (preview?.nodes || []).filter((node) => node.status === 'inferred' && ['concept', 'gap', 'validation', 'tacit_memory'].includes(node.type)).slice(0, 5),
    [preview?.nodes]
  );

  return (
    <section className="rounded-[1.4rem] border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">Ontology Layer</div>
          <div className="mt-1 text-lg font-semibold text-slate-950">Research entities, relations, and query expansion</div>
          <div className="mt-1 max-w-3xl text-sm leading-6 text-slate-700">
            The preview connects literature, experiment tracks, open gaps, plans, and tacit memory into a graph that can later steer search
            routing and answer synthesis.
          </div>
          <div className="mt-2 text-xs text-slate-500">{status}</div>
        </div>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="rounded-2xl bg-slate-950 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? 'Syncing...' : 'Sync ontology'}
        </button>
      </div>

      {preview ? (
        <div className="mt-4 space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-sm leading-6 text-slate-700">
            {preview.summary}
          </div>

          <div className="grid gap-3 lg:grid-cols-[1fr_0.85fr]">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
              <div className="flex items-center justify-between gap-3">
                <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Graph Nodes</div>
                <div className="text-xs text-slate-500">{preview.nodes.length} entities</div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {topNodes.map((node) => (
                  <span
                    key={node.id}
                    title={node.description || node.label}
                    className={classNames(
                      'rounded-full border px-2.5 py-1 text-xs font-medium',
                      node.status === 'rejected' ? 'border-rose-200 bg-rose-50 text-rose-800 line-through' : nodeTone[node.type] || 'border-slate-200 bg-white text-slate-700'
                    )}
                  >
                    {node.label}
                  </span>
                ))}
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
              <div className="flex items-center justify-between gap-3">
                <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Query Routing</div>
                <div className="text-xs text-slate-500">{preview.edges.length} relations</div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {(augmentation?.search_routing || []).map((route) => (
                  <span key={route} className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700">
                    {relationLabel(route)}
                  </span>
                ))}
              </div>
              <div className="mt-3 text-xs leading-5 text-slate-600">
                {(augmentation?.expanded_terms || []).slice(0, 12).join(', ') || 'No expansion terms yet.'}
              </div>
            </div>
          </div>

          {topEdges.length > 0 && (
            <div className="rounded-2xl border border-slate-200 bg-white p-3">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Relation Samples</div>
              <div className="mt-2 space-y-2">
                {topEdges.map((edge) => {
                  const source = nodesById.get(edge.source);
                  const target = nodesById.get(edge.target);
                  return (
                    <div key={edge.id} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-700">
                      <span className="font-semibold text-slate-900">{source?.label || edge.source}</span>
                      {' -> '}
                      {relationLabel(edge.relation)}
                      {' -> '}
                      <span className="font-semibold text-slate-900">{target?.label || edge.target}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {reviewCandidates.length > 0 && (
            <div className="rounded-2xl border border-slate-200 bg-white p-3">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Review Queue</div>
              <div className="mt-2 space-y-2">
                {reviewCandidates.map((node) => (
                  <div key={node.id} className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <div className="text-sm font-semibold text-slate-900">{node.label}</div>
                      <div className="mt-0.5 flex flex-wrap gap-1">
                        <span className={classNames('rounded-full border px-2 py-0.5 text-[11px] font-medium', statusTone[node.status])}>{node.status}</span>
                        <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-600">{node.type}</span>
                        <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-600">
                          {Math.round((node.confidence || 0) * 100)}%
                        </span>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => onReviewNode(node.id, 'confirmed')}
                        className="rounded-xl border border-emerald-200 bg-white px-3 py-1.5 text-xs font-semibold text-emerald-800 hover:bg-emerald-50"
                      >
                        Confirm
                      </button>
                      <button
                        onClick={() => onReviewNode(node.id, 'rejected')}
                        className="rounded-xl border border-rose-200 bg-white px-3 py-1.5 text-xs font-semibold text-rose-800 hover:bg-rose-50"
                      >
                        Reject
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {(augmentation?.tacit_context.length || 0) > 0 && (
            <div className="rounded-2xl border border-orange-200 bg-orange-50 p-3">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-orange-800">Tacit Knowledge Made Explicit</div>
              <div className="mt-2 space-y-1 text-sm leading-6 text-orange-950">
                {augmentation?.tacit_context.slice(0, 4).map((item) => <div key={item}>{item}</div>)}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="mt-4 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm leading-6 text-slate-600">
          No ontology preview yet. Refresh once there is a project, collaborator, and research context to map.
        </div>
      )}
    </section>
  );
}
