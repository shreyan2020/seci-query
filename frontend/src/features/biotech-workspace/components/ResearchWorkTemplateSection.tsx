import { useEffect, useState } from 'react';
import type {
  JudgmentCall,
  ProposalCandidate,
  ResearchFinding,
  ResearchWorkTemplate,
  ValidationTrack,
} from '@/features/biotech-workspace/types';
import { classNames } from '@/features/biotech-workspace/lib/utils';

interface ResearchWorkTemplateSectionProps {
  workTemplate: ResearchWorkTemplate;
  onWorkTemplateChange: (next: ResearchWorkTemplate) => void;
  onFetchLiterature: () => void;
  fetchingLiterature: boolean;
  literatureToolStatus?: string | null;
  literatureObjectiveLens?: string | null;
  literatureProcessingSummary?: string | null;
  literatureElicitationQuestions?: string[];
  onPreparePaperPdf?: (finding: ResearchFinding) => void;
  preparingPdfFindingId?: string | null;
  pdfAnnotationStatus?: string | null;
  reviewComplete: boolean;
  onCompleteReview: () => void;
  onGeneratePlan: () => void;
  loadingPlan: boolean;
}

function makeId(prefix: string) {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function splitLines(value: string) {
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean);
}

function joinLines(values: string[]) {
  return values.join('\n');
}

function cardButtonClass(kind: 'primary' | 'secondary' = 'secondary') {
  return classNames(
    'rounded-2xl px-3 py-2 text-xs font-semibold transition',
    kind === 'primary'
      ? 'border border-slate-900 bg-slate-950 text-white hover:bg-slate-800'
      : 'border border-slate-200 bg-white text-slate-900 hover:bg-slate-50'
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  rows = 3,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  rows?: number;
}) {
  return (
    <label className="block">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">{label}</div>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={rows}
        className="mt-1 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
        placeholder={placeholder}
      />
    </label>
  );
}

function EmptyState({
  title,
  body,
  actionLabel,
  onAction,
}: {
  title: string;
  body: string;
  actionLabel: string;
  onAction: () => void;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-300 bg-white/75 p-4">
      <div className="text-sm font-semibold text-slate-900">{title}</div>
      <div className="mt-1 text-sm leading-6 text-slate-600">{body}</div>
      <button onClick={onAction} className={classNames(cardButtonClass(), 'mt-3')}>
        {actionLabel}
      </button>
    </div>
  );
}

function SectionHeader({
  eyebrow,
  title,
  description,
  actionLabel,
  onAction,
}: {
  eyebrow: string;
  title: string;
  description: string;
  actionLabel: string;
  onAction: () => void;
}) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div>
        <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">{eyebrow}</div>
        <div className="mt-1 text-base font-semibold text-slate-950">{title}</div>
        <div className="mt-1 text-sm leading-6 text-slate-600">{description}</div>
      </div>
      <button onClick={onAction} className={cardButtonClass()}>
        {actionLabel}
      </button>
    </div>
  );
}

export function ResearchWorkTemplateSection({
  workTemplate,
  onWorkTemplateChange,
  onFetchLiterature,
  fetchingLiterature,
  literatureToolStatus,
  literatureObjectiveLens,
  literatureProcessingSummary,
  literatureElicitationQuestions = [],
  onPreparePaperPdf,
  preparingPdfFindingId,
  pdfAnnotationStatus,
  reviewComplete,
  onCompleteReview,
  onGeneratePlan,
  loadingPlan,
}: ResearchWorkTemplateSectionProps) {
  const [activeFindingIndex, setActiveFindingIndex] = useState(0);
  const findingCount = workTemplate.literature_findings.length;
  const activeFinding = findingCount > 0 ? workTemplate.literature_findings[Math.min(activeFindingIndex, findingCount - 1)] : null;
  const activeJudgments = activeFinding?.judgment_calls || [];
  const activeValidationTracks = activeFinding?.validation_tracks || [];

  useEffect(() => {
    const lastIndex = Math.max(findingCount - 1, 0);
    if (activeFindingIndex > lastIndex) {
      setActiveFindingIndex(lastIndex);
    }
  }, [activeFindingIndex, findingCount]);

  const setInitialQuery = (value: string) => onWorkTemplateChange({ ...workTemplate, initial_query: value });
  const addLiteratureFinding = () => {
    const nextItem: ResearchFinding = {
      id: makeId('finding'),
      citation: '',
      labels: [],
      knowns: [],
      unknowns: [],
      relevance: '',
      source_ids: {},
      judgment_calls: [],
      validation_tracks: [],
      synthesis_memo: '',
    };
    onWorkTemplateChange({
      ...workTemplate,
      literature_findings: [...workTemplate.literature_findings, nextItem],
    });
    setActiveFindingIndex(workTemplate.literature_findings.length);
  };

  const updateLiteratureFinding = (id: string, patch: Partial<ResearchFinding>) => {
    onWorkTemplateChange({
      ...workTemplate,
      literature_findings: workTemplate.literature_findings.map((item) => (item.id === id ? { ...item, ...patch } : item)),
    });
  };

  const removeLiteratureFinding = (id: string) => {
    const removedIndex = workTemplate.literature_findings.findIndex((item) => item.id === id);
    const nextLength = Math.max(workTemplate.literature_findings.length - 1, 0);
    onWorkTemplateChange({
      ...workTemplate,
      literature_findings: workTemplate.literature_findings.filter((item) => item.id !== id),
    });
    setActiveFindingIndex(Math.min(Math.max(removedIndex, 0), Math.max(nextLength - 1, 0)));
  };

  const addJudgment = () => {
    if (!activeFinding) {
      return;
    }
    const nextItem: JudgmentCall = {
      id: makeId('judgment'),
      stance: '',
      rationale: '',
      implication: '',
    };
    updateLiteratureFinding(activeFinding.id, {
      judgment_calls: [...(activeFinding.judgment_calls || []), nextItem],
    });
  };

  const updateJudgment = (id: string, patch: Partial<JudgmentCall>) => {
    if (!activeFinding) {
      return;
    }
    updateLiteratureFinding(activeFinding.id, {
      judgment_calls: (activeFinding.judgment_calls || []).map((item) => (item.id === id ? { ...item, ...patch } : item)),
    });
  };

  const removeJudgment = (id: string) => {
    if (!activeFinding) {
      return;
    }
    updateLiteratureFinding(activeFinding.id, {
      judgment_calls: (activeFinding.judgment_calls || []).filter((item) => item.id !== id),
    });
  };

  const addValidationTrack = () => {
    if (!activeFinding) {
      return;
    }
    const nextItem: ValidationTrack = {
      id: makeId('validation'),
      target: '',
      method: '',
      questions: [],
      success_signal: '',
    };
    updateLiteratureFinding(activeFinding.id, {
      validation_tracks: [...(activeFinding.validation_tracks || []), nextItem],
    });
  };

  const updateValidationTrack = (id: string, patch: Partial<ValidationTrack>) => {
    if (!activeFinding) {
      return;
    }
    updateLiteratureFinding(activeFinding.id, {
      validation_tracks: (activeFinding.validation_tracks || []).map((item) => (item.id === id ? { ...item, ...patch } : item)),
    });
  };

  const removeValidationTrack = (id: string) => {
    if (!activeFinding) {
      return;
    }
    updateLiteratureFinding(activeFinding.id, {
      validation_tracks: (activeFinding.validation_tracks || []).filter((item) => item.id !== id),
    });
  };

  const addProposalCandidate = () => {
    const nextItem: ProposalCandidate = {
      id: makeId('proposal'),
      title: '',
      why_now: '',
      experiment_outline: '',
      readouts: [],
    };
    onWorkTemplateChange({
      ...workTemplate,
      proposal_candidates: [...workTemplate.proposal_candidates, nextItem],
    });
  };

  const updateProposalCandidate = (id: string, patch: Partial<ProposalCandidate>) => {
    onWorkTemplateChange({
      ...workTemplate,
      proposal_candidates: workTemplate.proposal_candidates.map((item) => (item.id === id ? { ...item, ...patch } : item)),
    });
  };

  const removeProposalCandidate = (id: string) => {
    onWorkTemplateChange({
      ...workTemplate,
      proposal_candidates: workTemplate.proposal_candidates.filter((item) => item.id !== id),
    });
  };

  return (
    <div className="relative mt-5 rounded-[1.5rem] border border-slate-200 bg-white/85 p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Research Work Template</div>
          <div className="mt-1 text-sm leading-6 text-slate-600">
            Capture literature findings, recurring gaps, your own decisions, validation ideas, and proposal seeds before generating the
            draft. This is the bridge between evidence gathering and experiment planning.
          </div>
        </div>
      </div>

      <div className="mt-4 rounded-[1.4rem] border border-slate-200 bg-slate-50 p-4">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Initial Query</div>
          <div className="mt-1 text-sm leading-6 text-slate-600">
            Store the literature-style question that translates the project goal into something the system can analyze.
          </div>
        </div>
        <textarea
          value={workTemplate.initial_query}
          onChange={(e) => setInitialQuery(e.target.value)}
          rows={4}
          className="mt-3 w-full rounded-[1.25rem] border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900"
          placeholder="Example: What are the key successful common strategies and examples in microbial flavonoid production? What are the latest improvement options and key challenges?"
        />
        <div className="mt-3 flex justify-end">
          <button onClick={onFetchLiterature} disabled={fetchingLiterature} className={cardButtonClass('primary')}>
            {fetchingLiterature ? 'Fetching...' : 'Fetch literature'}
          </button>
        </div>

        {literatureToolStatus && (
          <div className="mt-3 rounded-2xl border border-sky-200 bg-sky-50 px-3 py-2 text-xs font-medium text-sky-950">
            {literatureToolStatus}
          </div>
        )}

        {pdfAnnotationStatus && (
          <div className="mt-3 rounded-2xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-950">
            {pdfAnnotationStatus}
          </div>
        )}

        {(literatureProcessingSummary || literatureObjectiveLens) && (
          <div className="mt-3 rounded-[1.4rem] border border-sky-200 bg-[linear-gradient(135deg,rgba(239,246,255,0.98),rgba(240,253,250,0.9))] p-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wide text-sky-800">Literature Processing</div>
                <div className="mt-1 text-sm font-semibold text-slate-950">Objective-conditioned evidence review</div>
              </div>
              {literatureObjectiveLens && (
                <div className="max-w-xl rounded-2xl border border-white/80 bg-white/80 px-3 py-2 text-xs leading-5 text-slate-700 shadow-sm">
                  <span className="font-semibold text-slate-900">Lens:</span> {literatureObjectiveLens}
                </div>
              )}
            </div>

            {literatureProcessingSummary && (
              <div className="mt-3 rounded-2xl border border-white/80 bg-white/75 px-3 py-2 text-sm leading-6 text-slate-700">
                {literatureProcessingSummary}
              </div>
            )}

            {literatureElicitationQuestions.length > 0 && (
              <div className="mt-3 rounded-2xl border border-white/80 bg-white/70 px-3 py-2 text-xs leading-5 text-slate-600">
                Paper-specific judgment prompts are available inside each annotated PDF review panel.
              </div>
            )}
          </div>
        )}
      </div>

      <div className="mt-4">
        <section className="rounded-[1.6rem] border border-slate-200 bg-slate-50 p-5">
          <SectionHeader
            eyebrow="Evidence Library"
            title="Literature findings"
            description="Review one paper at a time, then capture your judgment, validation ideas, and memo for that specific source."
            actionLabel="Add finding"
            onAction={addLiteratureFinding}
          />
          <div className="mt-4 space-y-3">
            {workTemplate.literature_findings.length === 0 ? (
              <EmptyState
                title="No literature findings yet"
                body="Add a paper, review, benchmark example, or analogy source and separate what it already shows from what is still unknown."
                actionLabel="Add first finding"
                onAction={addLiteratureFinding}
              />
            ) : activeFinding ? (
              <>
                <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-slate-200 bg-white/80 px-3 py-2">
                  <button
                    onClick={() => setActiveFindingIndex((current) => Math.max(current - 1, 0))}
                    disabled={activeFindingIndex <= 0}
                    className={classNames(cardButtonClass(), 'disabled:cursor-not-allowed disabled:opacity-40')}
                  >
                    Previous
                  </button>
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                    Finding {Math.min(activeFindingIndex + 1, findingCount)} of {findingCount}
                  </div>
                  <button
                    onClick={() => setActiveFindingIndex((current) => Math.min(current + 1, findingCount - 1))}
                    disabled={activeFindingIndex >= findingCount - 1}
                    className={classNames(cardButtonClass(), 'disabled:cursor-not-allowed disabled:opacity-40')}
                  >
                    Next
                  </button>
                </div>

                <div key={`${activeFinding.id}-${activeFinding.citation || activeFindingIndex}`} className="rounded-[1.4rem] border border-slate-200 bg-white p-5">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-semibold text-slate-950">Finding {activeFindingIndex + 1}</div>
                    <div className="flex flex-wrap justify-end gap-2">
                      {onPreparePaperPdf && (
                        <button
                          onClick={() => onPreparePaperPdf(activeFinding)}
                          disabled={preparingPdfFindingId === activeFinding.id}
                          className={classNames(cardButtonClass(), 'disabled:cursor-not-allowed disabled:opacity-50')}
                        >
                          {preparingPdfFindingId === activeFinding.id ? 'Generating annotations...' : 'Review paper'}
                        </button>
                      )}
                      <button onClick={() => removeLiteratureFinding(activeFinding.id)} className={cardButtonClass()}>
                        Remove
                      </button>
                    </div>
                  </div>

                  <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 p-3">
                    <div className="line-clamp-2 text-sm font-semibold leading-6 text-slate-950">
                      {activeFinding.citation || 'Untitled literature source'}
                    </div>
                    <div className="mt-2 line-clamp-4 text-sm leading-6 text-slate-700">
                      {activeFinding.relevance ||
                        activeFinding.knowns[0] ||
                        'No summary captured yet. Open the paper review to inspect and annotate this source.'}
                    </div>
                    {activeFinding.labels.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {activeFinding.labels.slice(0, 6).map((label) => (
                          <span key={`${activeFinding.id}-${label}`} className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-700">
                            {label}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  <details className="mt-3 rounded-2xl border border-slate-200 bg-white p-3">
                    <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-slate-600">
                      Edit extracted fields
                    </summary>

                  <label className="mt-3 block">
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Citation Or Source</div>
                    <input
                      value={activeFinding.citation}
                      onChange={(e) => updateLiteratureFinding(activeFinding.id, { citation: e.target.value })}
                      className="mt-1 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                      placeholder="Example: Optimizing yeast for high-level production of kaempferol and quercetin, 2023, cited by 41"
                    />
                  </label>

                  <label className="mt-3 block">
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Labels Or Question Types</div>
                    <input
                      value={activeFinding.labels.join(', ')}
                      onChange={(e) => updateLiteratureFinding(activeFinding.id, { labels: splitLines(e.target.value.replace(/,\s*/g, '\n')) })}
                      className="mt-1 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                      placeholder="Example: enzyme engineering, process optimization, transfer question"
                    />
                  </label>

                  {activeFinding.source_ids && Object.values(activeFinding.source_ids).some(Boolean) && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {Object.entries(activeFinding.source_ids)
                        .filter(([, value]) => Boolean(value))
                        .map(([key, value]) => (
                          <span key={`${activeFinding.id}-${key}`} className="rounded-full border border-sky-200 bg-sky-50 px-2 py-0.5 text-[11px] font-semibold text-sky-900">
                            {key.toUpperCase()}: {value}
                          </span>
                        ))}
                    </div>
                  )}

                  <div className="mt-3 grid gap-3">
                    <Field
                      label="Knowns"
                      value={joinLines(activeFinding.knowns)}
                      onChange={(value) => updateLiteratureFinding(activeFinding.id, { knowns: splitLines(value) })}
                      placeholder="One known per line"
                      rows={4}
                    />
                    <Field
                      label="Unknowns Or Follow-up Questions"
                      value={joinLines(activeFinding.unknowns)}
                      onChange={(value) => updateLiteratureFinding(activeFinding.id, { unknowns: splitLines(value) })}
                      placeholder="One gap or question per line"
                      rows={4}
                    />
                  </div>

                  <Field
                    label="How this finding informs the project"
                    value={activeFinding.relevance}
                    onChange={(value) => updateLiteratureFinding(activeFinding.id, { relevance: value })}
                    placeholder="Explain why this source matters, what transfers, and where you remain uncertain."
                  />
                  </details>

                  <div className="mt-5 grid gap-4 xl:grid-cols-2">
                    <section className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Your View</div>
                          <div className="mt-1 text-sm font-semibold text-slate-950">Judgment for this source</div>
                          <div className="mt-1 text-sm leading-6 text-slate-600">
                            Capture what you believe, reject, or want to carry forward from this literature item.
                          </div>
                        </div>
                        <button onClick={addJudgment} className={cardButtonClass()}>
                          Add judgment
                        </button>
                      </div>

                      <div className="mt-4 space-y-3">
                        {activeJudgments.length === 0 ? (
                          <EmptyState
                            title="No judgments for this finding yet"
                            body="Add decisions like 'this result seems transferable', 'enzyme C needs independent validation', or 'this method is too expensive for our lab'."
                            actionLabel="Add first judgment"
                            onAction={addJudgment}
                          />
                        ) : (
                          activeJudgments.map((judgment, index) => (
                            <div key={judgment.id} className="rounded-[1.25rem] border border-slate-200 bg-white p-4">
                              <div className="flex items-center justify-between gap-3">
                                <div className="text-sm font-semibold text-slate-950">Judgment {index + 1}</div>
                                <button onClick={() => removeJudgment(judgment.id)} className={cardButtonClass()}>
                                  Remove
                                </button>
                              </div>

                              <Field
                                label="Stance"
                                value={judgment.stance}
                                onChange={(value) => updateJudgment(judgment.id, { stance: value })}
                                placeholder="Example: This result is close enough to my target compound to test transferability."
                              />

                              <Field
                                label="Rationale"
                                value={judgment.rationale}
                                onChange={(value) => updateJudgment(judgment.id, { rationale: value })}
                                placeholder="Why do you hold this view?"
                              />

                              <Field
                                label="Implication for the next plan"
                                value={judgment.implication}
                                onChange={(value) => updateJudgment(judgment.id, { implication: value })}
                                placeholder="Explain how this should shape analysis, experiments, or prioritization."
                              />
                            </div>
                          ))
                        )}
                      </div>
                    </section>

                    <section className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Validation Agenda</div>
                          <div className="mt-1 text-sm font-semibold text-slate-950">Validation for this source</div>
                          <div className="mt-1 text-sm leading-6 text-slate-600">
                            Add database checks, AI modeling, or theoretical analyses that should validate this paper's usefulness.
                          </div>
                        </div>
                        <button onClick={addValidationTrack} className={cardButtonClass()}>
                          Add validation
                        </button>
                      </div>

                      <div className="mt-4 space-y-3">
                        {activeValidationTracks.length === 0 ? (
                          <EmptyState
                            title="No validation tracks for this finding yet"
                            body="Add one if this source creates a claim, method, or transfer question that deserves independent checking."
                            actionLabel="Add first validation"
                            onAction={addValidationTrack}
                          />
                        ) : (
                          activeValidationTracks.map((track, index) => (
                            <div key={track.id} className="rounded-[1.25rem] border border-slate-200 bg-white p-4">
                              <div className="flex items-center justify-between gap-3">
                                <div className="text-sm font-semibold text-slate-950">Validation {index + 1}</div>
                                <button onClick={() => removeValidationTrack(track.id)} className={cardButtonClass()}>
                                  Remove
                                </button>
                              </div>

                              <Field
                                label="Target"
                                value={track.target}
                                onChange={(value) => updateValidationTrack(track.id, { target: value })}
                                placeholder="Example: transferability of result A to my target compound"
                              />

                              <Field
                                label="Method Or Tool Path"
                                value={track.method}
                                onChange={(value) => updateValidationTrack(track.id, { method: value })}
                                placeholder="Example: database query + AI structure modeling + comparative sequence analysis"
                              />

                              <Field
                                label="Questions to resolve"
                                value={joinLines(track.questions)}
                                onChange={(value) => updateValidationTrack(track.id, { questions: splitLines(value) })}
                                placeholder="One validation question per line"
                                rows={4}
                              />

                              <Field
                                label="Success signal"
                                value={track.success_signal}
                                onChange={(value) => updateValidationTrack(track.id, { success_signal: value })}
                                placeholder="What outcome would make this validation track decision-useful?"
                              />
                            </div>
                          ))
                        )}
                      </div>
                    </section>
                  </div>

                  <section className="mt-4 rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4">
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Finding Memo</div>
                    <div className="mt-1 text-sm leading-6 text-slate-600">
                      Summarize what this paper changes in your thinking before moving to the next literature item.
                    </div>
                    <textarea
                      value={activeFinding.synthesis_memo || ''}
                      onChange={(e) => updateLiteratureFinding(activeFinding.id, { synthesis_memo: e.target.value })}
                      rows={5}
                      className="mt-3 w-full rounded-[1.25rem] border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900"
                      placeholder="Example: This paper makes the transfer case plausible, but I still need enzyme activity data under my planned yeast condition."
                    />
                  </section>
                </div>
              </>
            ) : null}
          </div>
        </section>
      </div>

      {!reviewComplete && workTemplate.literature_findings.length > 0 && (
        <section className="mt-4 rounded-[1.4rem] border border-dashed border-slate-300 bg-white/80 p-5 text-center">
          <div className="text-sm font-semibold text-slate-950">Ready to move from literature review to proposal synthesis?</div>
          <div className="mx-auto mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Finish the source-by-source review when the current set of findings has enough judgments, validation ideas, and memos to guide
            the next planning step.
          </div>
          <button onClick={onCompleteReview} className={classNames(cardButtonClass('primary'), 'mt-4')}>
            Finish literature review
          </button>
        </section>
      )}

      {reviewComplete && (
      <section className="mt-4 rounded-[1.4rem] border border-slate-200 bg-slate-50 p-4">
        <SectionHeader
          eyebrow="Proposal Seeds"
          title="Candidate research proposals"
          description="Translate the reviewed paper notes into concrete proposal options. You can add your own or ask the system to draft from the insights."
          actionLabel="Add proposal"
          onAction={addProposalCandidate}
        />
        <div className="mt-3 flex flex-wrap gap-2">
          <button onClick={onGeneratePlan} disabled={loadingPlan} className={classNames(cardButtonClass('primary'), 'disabled:cursor-not-allowed disabled:opacity-50')}>
            {loadingPlan ? 'Generating...' : 'Generate draft from insights'}
          </button>
        </div>
        <div className="mt-4 space-y-3">
          {workTemplate.proposal_candidates.length === 0 ? (
            <EmptyState
              title="No proposal candidates yet"
              body="Add the first proposal idea you want the planner to mature, such as evaluating a promising literature result against your target compound."
              actionLabel="Add first proposal"
              onAction={addProposalCandidate}
            />
          ) : (
            workTemplate.proposal_candidates.map((proposal, index) => (
              <div key={proposal.id} className="rounded-[1.25rem] border border-slate-200 bg-white p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-semibold text-slate-950">Proposal {index + 1}</div>
                  <button onClick={() => removeProposalCandidate(proposal.id)} className={cardButtonClass()}>
                    Remove
                  </button>
                </div>

                <label className="mt-3 block">
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Proposal title</div>
                  <input
                    value={proposal.title}
                    onChange={(e) => updateProposalCandidate(proposal.id, { title: e.target.value })}
                    className="mt-1 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                    placeholder="Example: Evaluate whether result A generalizes from compound 1 to target compound 2"
                  />
                </label>

                <div className="mt-3 grid gap-3 lg:grid-cols-2">
                  <Field
                    label="Why now"
                    value={proposal.why_now}
                    onChange={(value) => updateProposalCandidate(proposal.id, { why_now: value })}
                    placeholder="Why is this proposal timely or decision-useful?"
                    rows={4}
                  />
                  <Field
                    label="Experiment outline"
                    value={proposal.experiment_outline}
                    onChange={(value) => updateProposalCandidate(proposal.id, { experiment_outline: value })}
                    placeholder="Describe the experiment shape, conditions, or comparison to run."
                    rows={4}
                  />
                </div>

                <Field
                  label="Readouts and measurements"
                  value={joinLines(proposal.readouts)}
                  onChange={(value) => updateProposalCandidate(proposal.id, { readouts: splitLines(value) })}
                  placeholder="One readout or measurement objective per line"
                  rows={4}
                />
              </div>
            ))
          )}
        </div>
      </section>
      )}
    </div>
  );
}
