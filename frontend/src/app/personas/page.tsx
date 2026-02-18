'use client';

import { useEffect, useState } from 'react';

interface Persona {
  id: number;
  name: string;
  scope: string;
  version: number;
  last_summary: string;
  persona_json: Record<string, unknown>;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function PersonasPage() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [scopeId, setScopeId] = useState('default');
  const [personaName, setPersonaName] = useState('Interview Persona');
  const [interviewIds, setInterviewIds] = useState('');
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<Persona | null>(null);

  const load = async () => {
    const res = await fetch(`${API_BASE}/api/personas`, { cache: 'no-store' });
    if (!res.ok) return;
    const data = await res.json();
    setPersonas(data.personas || []);
  };

  useEffect(() => {
    load();
  }, []);

  const createFromInterviews = async () => {
    setLoading(true);
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
          persona_name: personaName,
          mode: 'create',
        }),
      });
      if (!res.ok) throw new Error('Failed to create persona');
      await load();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-50 p-6">
      <div className="mx-auto max-w-6xl space-y-4">
        <div className="rounded-2xl border border-neutral-200 bg-white p-4 shadow-sm">
          <div className="text-lg font-semibold text-neutral-900">Personas</div>
          <div className="mt-3 grid gap-2 md:grid-cols-4">
            <input
              value={scopeId}
              onChange={(e) => setScopeId(e.target.value)}
              placeholder="scope_id"
              className="rounded-xl border border-neutral-200 px-3 py-2 text-sm"
            />
            <input
              value={personaName}
              onChange={(e) => setPersonaName(e.target.value)}
              placeholder="persona name"
              className="rounded-xl border border-neutral-200 px-3 py-2 text-sm"
            />
            <input
              value={interviewIds}
              onChange={(e) => setInterviewIds(e.target.value)}
              placeholder="interview ids: 1,2,3"
              className="rounded-xl border border-neutral-200 px-3 py-2 text-sm"
            />
            <button
              onClick={createFromInterviews}
              disabled={loading}
              className="rounded-xl bg-neutral-900 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
            >
              {loading ? 'Creating...' : 'Create from interviews'}
            </button>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border border-neutral-200 bg-white p-4 shadow-sm">
            <div className="mb-2 text-sm font-semibold text-neutral-900">Persona list</div>
            <div className="space-y-2">
              {personas.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setSelected(p)}
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
                <pre className="max-h-[600px] overflow-auto rounded-xl border border-neutral-200 bg-neutral-50 p-3 text-xs text-neutral-800">
                  {JSON.stringify(selected.persona_json, null, 2)}
                </pre>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
