'use client';

import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';

interface Persona {
  id: number;
  name: string;
  scope: string;
  version: number;
  last_summary: string;
  persona_json: Record<string, unknown>;
}

interface InterviewItem {
  id: number;
  scope: string;
  transcript_path?: string | null;
  created_at: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function PersonasPage() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [scopeId, setScopeId] = useState('default');
  const [interviewIds, setInterviewIds] = useState('');
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<Persona | null>(null);
  const [folder, setFolder] = useState('');
  const [interviews, setInterviews] = useState<InterviewItem[]>([]);
  const [importing, setImporting] = useState(false);
  const [editableName, setEditableName] = useState('');
  const [editableJson, setEditableJson] = useState('');
  const [saveMode, setSaveMode] = useState<'augment' | 'replace'>('augment');
  const [saving, setSaving] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [status, setStatus] = useState<{ type: 'info' | 'success' | 'error'; message: string } | null>(null);

  const clearStatus = useCallback(() => setStatus(null), []);

  const load = async () => {
    const [personaRes, interviewRes] = await Promise.all([
      fetch(`${API_BASE}/api/personas`, { cache: 'no-store' }),
      fetch(`${API_BASE}/api/interviews?scope_id=${encodeURIComponent(scopeId)}`, { cache: 'no-store' }),
    ]);
    if (personaRes.ok) {
      const data = await personaRes.json();
      setPersonas(data.personas || []);
    }
    if (interviewRes.ok) {
      const data = await interviewRes.json();
      setInterviews(data.interviews || []);
    }
  };

  useEffect(() => {
    load();
  }, [scopeId]);

  useEffect(() => {
    if (status?.type === 'success') {
      const timer = setTimeout(clearStatus, 5000);
      return () => clearTimeout(timer);
    }
  }, [status, clearStatus]);

  const importTxtFiles = async () => {
    setImporting(true);
    setStatus({ type: 'info', message: 'Scanning for .txt files...' });
    try {
      const res = await fetch(`${API_BASE}/api/interviews/import-texts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scope: scopeId,
          folder: folder || undefined,
          recursive: true,
        }),
      });
      if (!res.ok) throw new Error('Failed to import txt files');
      const data = await res.json();
      setStatus({ 
        type: 'success', 
        message: `Imported ${data.imported_count} file(s), skipped ${data.skipped_count} existing.` 
      });
      await load();
    } catch {
      setStatus({ type: 'error', message: 'Failed to import txt files' });
    } finally {
      setImporting(false);
    }
  };

  const createFromInterviews = async () => {
    setLoading(true);
    setStatus({ type: 'info', message: 'Extracting persona from interviews...' });
    try {
      const ids = interviewIds
        .split(',')
        .map((x) => x.trim())
        .filter(Boolean)
        .map((x) => Number(x))
        .filter((x) => !Number.isNaN(x));

      const res = await fetch(`${API_BASE}/api/personas/from-interviews`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scope_id: scopeId,
          interview_ids: ids.length ? ids : undefined,
          mode: 'create',
        }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to create persona');
      }
      const data = await res.json();
      setStatus({ type: 'success', message: `Persona created successfully (ID: ${data.persona_id})` });
      await load();
    } catch (err) {
      setStatus({ type: 'error', message: err instanceof Error ? err.message : 'Failed to create persona' });
    } finally {
      setLoading(false);
    }
  };

  const extractAllPersonas = async () => {
    setExtracting(true);
    setStatus({ type: 'info', message: 'Extracting personas from all interviews...' });
    try {
      const res = await fetch(`${API_BASE}/api/personas/extract-all`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scope_id: scopeId,
          extract_new_only: true,
        }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to extract personas');
      }
      const data = await res.json();
      const extracted = data.extracted || [];
      const skipped = data.skipped || [];
      let msg = `Extracted ${extracted.length} persona(s)`;
      if (extracted.length > 0) {
        msg += `: ${extracted.map((e: { participant_id: string }) => e.participant_id).join(', ')}`;
      }
      if (skipped.length > 0) {
        msg += `. Skipped ${skipped.length} (already exist or no ID).`;
      }
      setStatus({ type: 'success', message: msg });
      await load();
    } catch (err) {
      setStatus({ type: 'error', message: err instanceof Error ? err.message : 'Failed to extract personas' });
    } finally {
      setExtracting(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-50 p-6">
      <div className="mx-auto max-w-6xl space-y-4">
        <Link href="/" className="inline-flex items-center gap-1 text-sm text-neutral-600 hover:text-neutral-900">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
            <path fillRule="evenodd" d="M17 10a.75.75 0 01-.75.75H5.612l4.158 3.958a.75.75 0 11-1.04 1.08l-5.5-5.25a.75.75 0 010-1.08l5.5-5.25a.75.75 0 111.04 1.08L5.612 9.25H16.25A.75.75 0 0117 10z" clipRule="evenodd" />
          </svg>
          Back to main
        </Link>
        {status && (
          <div
            className={`flex items-center justify-between gap-2 rounded-xl px-4 py-2 text-sm ${
              status.type === 'success'
                ? 'bg-green-50 text-green-800 border border-green-200'
                : status.type === 'error'
                ? 'bg-red-50 text-red-800 border border-red-200'
                : 'bg-blue-50 text-blue-800 border border-blue-200'
            }`}
          >
            <div className="flex items-center gap-2">
              {status.type === 'info' && (
                <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              )}
              {status.message}
            </div>
            <button onClick={clearStatus} className="text-current opacity-60 hover:opacity-100">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
              </svg>
            </button>
          </div>
        )}
        <div className="rounded-2xl border border-neutral-200 bg-white p-4 shadow-sm">
          <div className="text-lg font-semibold text-neutral-900">Personas</div>
          <div className="mt-3 grid gap-2 md:grid-cols-6">
            <input
              value={scopeId}
              onChange={(e) => setScopeId(e.target.value)}
              placeholder="scope_id"
              className="rounded-xl border border-neutral-200 px-3 py-2 text-sm"
            />
            <input
              value={folder}
              onChange={(e) => setFolder(e.target.value)}
              placeholder="txt folder under data/interviews"
              className="rounded-xl border border-neutral-200 px-3 py-2 text-sm"
            />
            <button
              onClick={importTxtFiles}
              disabled={importing}
              className="rounded-xl border border-neutral-200 bg-white px-3 py-2 text-sm font-semibold text-neutral-900 disabled:opacity-60"
            >
              {importing ? 'Importing...' : 'Import .txt'}
            </button>
            <button
              onClick={extractAllPersonas}
              disabled={extracting || interviews.length === 0}
              className="rounded-xl bg-neutral-900 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
            >
              {extracting ? 'Extracting...' : 'Extract All Personas'}
            </button>
            <input
              value={interviewIds}
              onChange={(e) => setInterviewIds(e.target.value)}
              placeholder="interview ids: 1,2,3 (optional)"
              className="rounded-xl border border-neutral-200 px-3 py-2 text-sm"
            />
            <button
              onClick={createFromInterviews}
              disabled={loading}
              className="rounded-xl border border-neutral-300 bg-white px-3 py-2 text-sm font-semibold text-neutral-700 disabled:opacity-60"
            >
              {loading ? 'Creating...' : 'Create Single'}
            </button>
          </div>
          <div className="mt-2 text-xs text-neutral-600">
            Drop transcript files in <span className="font-mono">backend/data/interviews</span> (or a subfolder).
            Interviews: <span className="font-semibold">{interviews.length}</span> · 
            Personas: <span className="font-semibold">{personas.length}</span>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border border-neutral-200 bg-white p-4 shadow-sm">
            <div className="mb-2 text-sm font-semibold text-neutral-900">Persona list</div>
            <div className="space-y-2">
              {personas.map((p) => (
                <button
                  key={p.id}
                  onClick={() => {
                    setSelected(p);
                    setEditableName(p.name);
                    setEditableJson(JSON.stringify(p.persona_json, null, 2));
                  }}
                  className="w-full rounded-xl border border-neutral-200 p-3 text-left text-sm hover:bg-neutral-50"
                >
                  <div className="font-semibold text-neutral-900">{p.name}</div>
                  <div className="text-xs text-neutral-600">
                    scope={p.scope} · version={p.version}
                  </div>
                  <div className="mt-1 line-clamp-2 text-xs text-neutral-700">{p.last_summary}</div>
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-neutral-200 bg-white p-4 shadow-sm">
            <div className="mb-2 text-sm font-semibold text-neutral-900">Persona viewer</div>
            {!selected ? (
              <div className="text-sm text-neutral-600">Select a persona from the list.</div>
            ) : (
              <>
                <div className="mb-2 text-xs text-neutral-700">{selected.last_summary}</div>
                <input
                  value={editableName}
                  onChange={(e) => setEditableName(e.target.value)}
                  className="mb-2 w-full rounded-xl border border-neutral-200 px-3 py-2 text-sm"
                />
                <textarea
                  value={editableJson}
                  onChange={(e) => setEditableJson(e.target.value)}
                  rows={20}
                  className="w-full rounded-xl border border-neutral-200 bg-neutral-50 p-3 font-mono text-xs text-neutral-800"
                />
                <div className="mt-2 flex items-center gap-2">
                  <select
                    value={saveMode}
                    onChange={(e) => setSaveMode(e.target.value as 'augment' | 'replace')}
                    className="rounded-xl border border-neutral-200 px-3 py-2 text-sm"
                  >
                    <option value="augment">Augment</option>
                    <option value="replace">Replace</option>
                  </select>
                  <button
                    onClick={async () => {
                      if (!selected) return;
                      setSaving(true);
                      try {
                        const parsed = JSON.parse(editableJson);
                        const res = await fetch(`${API_BASE}/api/personas/${selected.id}`, {
                          method: 'PUT',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({
                            name: editableName,
                            persona_json: parsed,
                            mode: saveMode,
                          }),
                        });
                        if (!res.ok) throw new Error('Failed to save persona');
                        const updated = await res.json();
                        setSelected(updated);
                        setEditableName(updated.name);
                        setEditableJson(JSON.stringify(updated.persona_json, null, 2));
                        await load();
                      } catch {
                        alert('Failed to save persona. Check JSON format and schema.');
                      } finally {
                        setSaving(false);
                      }
                    }}
                    disabled={saving}
                    className="rounded-xl bg-neutral-900 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
                  >
                    {saving ? 'Saving...' : 'Save Persona'}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
