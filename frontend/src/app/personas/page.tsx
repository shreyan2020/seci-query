'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';

interface Persona {
  id: number;
  name: string;
  scope: string;
  project_id?: number | null;
  identity_key?: string | null;
  version: number;
  last_summary: string;
  persona_json: Record<string, unknown>;
}
interface ProjectOption {
  id: number;
  name: string;
  scope_id: string;
  end_product: string;
}
interface PersonaChangeLogItem {
  source_persona_id: number;
  new_persona_id: number;
  created_at: string;
  changes: string[];
  reasons: string[];
  supporting_events: Record<string, number>;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function classNames(...xs: Array<string | false | null | undefined>) {
  return xs.filter(Boolean).join(' ');
}

function prettyName(raw: string) {
  return raw.replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim();
}

function isStarterPersona(p: Persona) {
  const key = (p.identity_key || '').toLowerCase();
  return key.startsWith('starter:') || key.startsWith('template:');
}

function isProjectPersona(p: Persona) {
  return p.project_id !== null && p.project_id !== undefined;
}

export default function PersonasPage() {
  const [scopeId, setScopeId] = useState('default');
  const [projects, setProjects] = useState<ProjectOption[]>([]);
  const [projectIdFilter, setProjectIdFilter] = useState<number | ''>('');
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [selected, setSelected] = useState<Persona | null>(null);
  const [changeLog, setChangeLog] = useState<PersonaChangeLogItem[]>([]);

  const [status, setStatus] = useState<{ type: 'info' | 'success' | 'error'; message: string } | null>(null);
  const [resetting, setResetting] = useState(false);

  const [uploadName, setUploadName] = useState('');
  const [uploadContent, setUploadContent] = useState('');
  const [uploading, setUploading] = useState(false);

  const [editorJson, setEditorJson] = useState('');
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    const url = projectIdFilter === ''
      ? `${API_BASE}/api/personas?scope_id=${encodeURIComponent(scopeId)}`
      : `${API_BASE}/api/personas?project_id=${projectIdFilter}`;
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) {
      setPersonas([]);
      setSelected(null);
      return;
    }
    const data = await res.json();
    const rows = (data.personas || []) as Persona[];
    setPersonas(rows);
    setSelected((prev) => {
      if (!prev) return rows[0] || null;
      return rows.find((p) => p.id === prev.id) || rows[0] || null;
    });
  }, [scopeId, projectIdFilter]);

  const loadProjects = useCallback(async () => {
    const res = await fetch(`${API_BASE}/api/projects`, { cache: 'no-store' });
    if (!res.ok) {
      setProjects([]);
      return;
    }
    const data = await res.json();
    setProjects(data.projects || []);
  }, []);

  const loadChangeLog = useCallback(async (personaId: number) => {
    const res = await fetch(`${API_BASE}/api/personas/${personaId}/change-log?limit=8`, { cache: 'no-store' });
    if (!res.ok) {
      setChangeLog([]);
      return;
    }
    const data = await res.json();
    setChangeLog(data.items || []);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    loadProjects().catch(() => {});
  }, [loadProjects]);

  useEffect(() => {
    if (projectIdFilter === '') return;
    const active = projects.find((project) => project.id === Number(projectIdFilter));
    if (active?.scope_id) {
      setScopeId(active.scope_id);
    }
  }, [projectIdFilter, projects]);

  useEffect(() => {
    if (!selected) {
      setEditorJson('');
      setChangeLog([]);
      return;
    }
    setEditorJson(JSON.stringify(selected.persona_json || {}, null, 2));
    loadChangeLog(selected.id);
  }, [selected, loadChangeLog]);

  const starterCount = useMemo(() => personas.filter(isStarterPersona).length, [personas]);
  const projectCount = useMemo(() => personas.filter(isProjectPersona).length, [personas]);
  const customCount = useMemo(() => personas.filter((p) => !isStarterPersona(p) && !isProjectPersona(p)).length, [personas]);
  const activeProject = projectIdFilter === '' ? null : projects.find((project) => project.id === Number(projectIdFilter)) || null;

  const handleResetToStarters = async () => {
    if (projectIdFilter !== '') {
      setStatus({ type: 'error', message: 'Project personas are managed per project. Switch back to default scope to reset starter personas.' });
      return;
    }
    setResetting(true);
    setStatus({ type: 'info', message: 'Resetting personas to biotech starters...' });
    try {
      const res = await fetch(`${API_BASE}/api/personas/reset-to-starters`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scope_id: scopeId }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to reset personas');
      }
      const data = await res.json();
      setStatus({ type: 'success', message: `Reset complete. Removed ${data.removed_count} persona(s), seeded ${data.created_persona_ids?.length || 0} starter persona(s).` });
      setSelected(null);
      await load();
    } catch (err) {
      setStatus({ type: 'error', message: err instanceof Error ? err.message : 'Failed to reset personas' });
    } finally {
      setResetting(false);
    }
  };

  const handlePickMdFile = async (file: File) => {
    const text = await file.text();
    setUploadContent(text);
    if (!uploadName.trim()) {
      const base = file.name.replace(/\.md$/i, '').replace(/[_-]+/g, ' ').trim();
      setUploadName(base);
    }
  };

  const handleImportMarkdown = async () => {
    if (projectIdFilter !== '') {
      setStatus({ type: 'error', message: 'Markdown import is currently available for default scope personas only.' });
      return;
    }
    if (!uploadContent.trim()) {
      setStatus({ type: 'error', message: 'Please select an .md file first.' });
      return;
    }
    setUploading(true);
    setStatus({ type: 'info', message: 'Importing custom persona from markdown...' });
    try {
      const res = await fetch(`${API_BASE}/api/personas/import-markdown`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scope_id: scopeId,
          name: uploadName || undefined,
          markdown: uploadContent,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to import markdown persona');
      }
      const data = await res.json();
      setStatus({ type: 'success', message: data.created ? `Created custom persona ${data.name} (v${data.version}).` : `Updated custom persona ${data.name} to v${data.version}.` });
      setUploadContent('');
      await load();
      const picked = personas.find((p) => p.id === data.persona_id);
      if (picked) setSelected(picked);
    } catch (err) {
      setStatus({ type: 'error', message: err instanceof Error ? err.message : 'Failed to import markdown persona' });
    } finally {
      setUploading(false);
    }
  };

  const handleSavePersona = async () => {
    if (!selected) return;
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(editorJson);
    } catch {
      setStatus({ type: 'error', message: 'Invalid JSON in editor.' });
      return;
    }

    setSaving(true);
    setStatus({ type: 'info', message: 'Saving persona updates...' });
    try {
      const res = await fetch(`${API_BASE}/api/personas/${selected.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: selected.name,
          persona_json: parsed,
          mode: 'replace',
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to save persona');
      }
      setStatus({ type: 'success', message: 'Persona updated.' });
      await load();
    } catch (err) {
      setStatus({ type: 'error', message: err instanceof Error ? err.message : 'Failed to save persona' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_15%_0%,#dbeafe_0%,#f8fafc_45%,#eef2ff_100%)] p-6">
      <div className="mx-auto max-w-7xl space-y-5">
        <div className="flex items-center justify-between">
          <Link href="/" className="text-sm text-slate-600 hover:text-slate-900">Back</Link>
        </div>

        <section className="rounded-3xl border border-slate-200 bg-white/90 p-5 shadow-sm">
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Persona Studio (Biotech)</h1>
          <p className="mt-1 text-sm text-slate-600">
            Inspect default personas or open a specific project to see the personas generated and stored for that biotech program.
          </p>

          {status && (
            <div className={classNames(
              'mt-4 rounded-xl border px-3 py-2 text-sm',
              status.type === 'success' && 'border-emerald-200 bg-emerald-50 text-emerald-800',
              status.type === 'error' && 'border-rose-200 bg-rose-50 text-rose-800',
              status.type === 'info' && 'border-sky-200 bg-sky-50 text-sky-800'
            )}>
              {status.message}
            </div>
          )}

          <div className="mt-4 grid gap-3 lg:grid-cols-3">
            <div className="rounded-2xl border border-indigo-200 bg-indigo-50 p-3">
              <div className="text-xs font-semibold uppercase tracking-wide text-indigo-900">Project Or Scope</div>
              <select
                value={projectIdFilter}
                onChange={(e) => setProjectIdFilter(e.target.value === '' ? '' : Number(e.target.value))}
                className="mt-2 w-full rounded-xl border border-indigo-200 bg-white px-3 py-2 text-sm"
              >
                <option value="">Default personas</option>
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </select>

              {projectIdFilter === '' ? (
                <>
                  <input
                    value={scopeId}
                    onChange={(e) => setScopeId(e.target.value)}
                    className="mt-2 w-full rounded-xl border border-indigo-200 bg-white px-3 py-2 text-sm"
                  />
                  <button
                    onClick={handleResetToStarters}
                    disabled={resetting}
                    className="mt-2 w-full rounded-xl border border-indigo-300 bg-white px-3 py-2 text-sm font-semibold text-indigo-900 disabled:opacity-50"
                  >
                    {resetting ? 'Resetting...' : 'Reset To Starter Personas'}
                  </button>
                </>
              ) : (
                <div className="mt-2 rounded-xl border border-indigo-200 bg-white p-3 text-sm text-indigo-950">
                  <div className="font-semibold">{activeProject?.name || 'Project'}</div>
                  <div className="mt-1 text-xs text-indigo-800">{activeProject?.end_product || 'No project details loaded.'}</div>
                  <div className="mt-2 text-[11px] uppercase tracking-wide text-indigo-700">Stored scope</div>
                  <div className="mt-1 text-xs text-indigo-900">{scopeId}</div>
                </div>
              )}
            </div>

            <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-3 lg:col-span-2">
              <div className="text-xs font-semibold uppercase tracking-wide text-emerald-900">Upload Custom Persona (.md)</div>
              <div className="mt-2 grid gap-2 md:grid-cols-[1fr_1fr_auto]">
                <input
                  value={uploadName}
                  onChange={(e) => setUploadName(e.target.value)}
                  placeholder="Custom persona name (optional)"
                  disabled={projectIdFilter !== ''}
                  className="rounded-xl border border-emerald-200 bg-white px-3 py-2 text-sm"
                />
                <input
                  type="file"
                  accept=".md,text/markdown"
                  disabled={projectIdFilter !== ''}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handlePickMdFile(file).catch(() => {});
                  }}
                  className="rounded-xl border border-emerald-200 bg-white px-3 py-2 text-sm"
                />
                <button
                  onClick={handleImportMarkdown}
                  disabled={uploading || projectIdFilter !== ''}
                  className="rounded-xl border border-emerald-300 bg-white px-3 py-2 text-sm font-semibold text-emerald-900 disabled:opacity-50"
                >
                  {uploading ? 'Importing...' : 'Import Persona'}
                </button>
              </div>
              <div className="mt-2 text-xs text-emerald-800">
                Starter personas: {starterCount} | Project personas: {projectCount} | Custom personas: {customCount}
              </div>
              {projectIdFilter !== '' && (
                <div className="mt-2 text-xs text-emerald-900">
                  Project personas are already stored with the selected project. You can inspect and edit them below.
                </div>
              )}
            </div>
          </div>
        </section>

        <section className="grid gap-4 lg:grid-cols-[320px_1fr]">
          <aside className="rounded-3xl border border-slate-200 bg-white/90 p-4 shadow-sm">
            <div className="mb-2 text-sm font-semibold text-slate-900">Personas</div>
            <div className="space-y-2">
              {personas.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setSelected(p)}
                  className={classNames(
                    'w-full rounded-xl border px-3 py-2 text-left text-xs transition',
                    selected?.id === p.id ? 'border-cyan-300 bg-cyan-50 text-cyan-900' : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                  )}
                >
                  <div className="font-semibold text-sm text-slate-900">{prettyName(p.name)}</div>
                  <div className="mt-1 flex items-center gap-2 text-[11px]">
                    <span>v{p.version}</span>
                    <span>ID {p.id}</span>
                    <span
                      className={classNames(
                        'rounded-full px-2 py-0.5',
                        isProjectPersona(p)
                          ? 'bg-sky-100 text-sky-900'
                          : isStarterPersona(p)
                            ? 'bg-indigo-100 text-indigo-900'
                            : 'bg-emerald-100 text-emerald-900'
                      )}
                    >
                      {isProjectPersona(p) ? 'Project' : isStarterPersona(p) ? 'Starter' : 'Custom'}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </aside>

          <main className="space-y-4">
            {!selected ? (
              <div className="rounded-3xl border border-slate-200 bg-white/90 p-8 text-sm text-slate-600 shadow-sm">Select a persona to inspect or edit.</div>
            ) : (
              <>
                <section className="rounded-3xl border border-slate-200 bg-white/90 p-5 shadow-sm">
                  <div className="text-xl font-semibold text-slate-900">{prettyName(selected.name)}</div>
                  <div className="mt-1 text-xs text-slate-600">Version v{selected.version} | Scope {selected.scope} | ID {selected.id}</div>
                  <div className="mt-3 text-sm text-slate-700">{selected.last_summary || 'No summary available yet.'}</div>
                </section>

                <section className="rounded-3xl border border-slate-200 bg-white/90 p-5 shadow-sm">
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-semibold text-slate-900">Persona JSON Editor</div>
                    <button
                      onClick={handleSavePersona}
                      disabled={saving}
                      className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-900 disabled:opacity-50"
                    >
                      {saving ? 'Saving...' : 'Save Updates'}
                    </button>
                  </div>
                  <textarea
                    value={editorJson}
                    onChange={(e) => setEditorJson(e.target.value)}
                    rows={18}
                    className="mt-2 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 font-mono text-xs text-slate-900"
                  />
                </section>

                <section className="rounded-3xl border border-slate-200 bg-white/90 p-5 shadow-sm">
                  <div className="text-sm font-semibold text-slate-900">Recent Learning Updates</div>
                  {changeLog.length === 0 ? (
                    <div className="mt-2 text-sm text-slate-600">No learning updates recorded yet.</div>
                  ) : (
                    <div className="mt-2 space-y-2">
                      {changeLog.map((item, idx) => (
                        <div key={`${item.new_persona_id}-${idx}`} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                          <div className="text-xs font-semibold text-slate-800">Update {idx + 1} | {item.created_at}</div>
                          <ul className="mt-1 list-disc pl-4 text-xs text-slate-700">
                            {(item.changes || []).slice(0, 4).map((c, i) => (
                              <li key={`${i}-${c}`}>{c}</li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                  )}
                </section>
              </>
            )}
          </main>
        </section>
      </div>
    </div>
  );
}
