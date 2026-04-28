import type {
  JudgmentCall,
  ProposalCandidate,
  ResearchFinding,
  ResearchGap,
  ResearchWorkTemplate,
  ValidationTrack,
} from '@/features/biotech-workspace/types';
import { classNames } from '@/features/biotech-workspace/lib/utils';

interface ResearchWorkTemplateSectionProps {
  focusQuestion: string;
  workTemplate: ResearchWorkTemplate;
  onWorkTemplateChange: (next: ResearchWorkTemplate) => void;
  onFetchLiterature: () => void;
  fetchingLiterature: boolean;
  literatureToolStatus?: string | null;
  literatureObjectiveLens?: string | null;
  literatureProcessingSummary?: string | null;
  literatureElicitationQuestions?: string[];
  literatureElicitationAnswers?: Record<string, string>;
  onLiteratureElicitationAnswerChange?: (question: string, value: string) => void;
  onCaptureLiteratureTacitAnswer?: (question: string) => void;
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
  focusQuestion,
  workTemplate,
  onWorkTemplateChange,
  onFetchLiterature,
  fetchingLiterature,
  literatureToolStatus,
  literatureObjectiveLens,
  literatureProcessingSummary,
  literatureElicitationQuestions = [],
  literatureElicitationAnswers = {},
  onLiteratureElicitationAnswerChange,
  onCaptureLiteratureTacitAnswer,
}: ResearchWorkTemplateSectionProps) {
  const setInitialQuery = (value: string) => onWorkTemplateChange({ ...workTemplate, initial_query: value });
  const setSynthesisMemo = (value: string) => onWorkTemplateChange({ ...workTemplate, synthesis_memo: value });

  const addLiteratureFinding = () => {
    const nextItem: ResearchFinding = {
      id: makeId('finding'),
      citation: '',
      labels: [],
      knowns: [],
      unknowns: [],
      relevance: '',
    };
    onWorkTemplateChange({
      ...workTemplate,
      literature_findings: [...workTemplate.literature_findings, nextItem],
    });
  };

  const updateLiteratureFinding = (id: string, patch: Partial<ResearchFinding>) => {
    onWorkTemplateChange({
      ...workTemplate,
      literature_findings: workTemplate.literature_findings.map((item) => (item.id === id ? { ...item, ...patch } : item)),
    });
  };

  const removeLiteratureFinding = (id: string) => {
    onWorkTemplateChange({
      ...workTemplate,
      literature_findings: workTemplate.literature_findings.filter((item) => item.id !== id),
    });
  };

  const addGap = () => {
    const nextItem: ResearchGap = {
      id: makeId('gap'),
      theme: '',
      supporting_signals: [],
      next_question: '',
      priority_note: '',
    };
    onWorkTemplateChange({ ...workTemplate, common_gaps: [...workTemplate.common_gaps, nextItem] });
  };

  const updateGap = (id: string, patch: Partial<ResearchGap>) => {
    onWorkTemplateChange({
      ...workTemplate,
      common_gaps: workTemplate.common_gaps.map((item) => (item.id === id ? { ...item, ...patch } : item)),
    });
  };

  const removeGap = (id: string) => {
    onWorkTemplateChange({
      ...workTemplate,
      common_gaps: workTemplate.common_gaps.filter((item) => item.id !== id),
    });
  };

  const addJudgment = () => {
    const nextItem: JudgmentCall = {
      id: makeId('judgment'),
      stance: '',
      rationale: '',
      implication: '',
    };
    onWorkTemplateChange({
      ...workTemplate,
      judgment_calls: [...workTemplate.judgment_calls, nextItem],
    });
  };

  const updateJudgment = (id: string, patch: Partial<JudgmentCall>) => {
    onWorkTemplateChange({
      ...workTemplate,
      judgment_calls: workTemplate.judgment_calls.map((item) => (item.id === id ? { ...item, ...patch } : item)),
    });
  };

  const removeJudgment = (id: string) => {
    onWorkTemplateChange({
      ...workTemplate,
      judgment_calls: workTemplate.judgment_calls.filter((item) => item.id !== id),
    });
  };

  const addValidationTrack = () => {
    const nextItem: ValidationTrack = {
      id: makeId('validation'),
      target: '',
      method: '',
      questions: [],
      success_signal: '',
    };
    onWorkTemplateChange({
      ...workTemplate,
      validation_tracks: [...workTemplate.validation_tracks, nextItem],
    });
  };

  const updateValidationTrack = (id: string, patch: Partial<ValidationTrack>) => {
    onWorkTemplateChange({
      ...workTemplate,
      validation_tracks: workTemplate.validation_tracks.map((item) => (item.id === id ? { ...item, ...patch } : item)),
    });
  };

  const removeValidationTrack = (id: string) => {
    onWorkTemplateChange({
      ...workTemplate,
      validation_tracks: workTemplate.validation_tracks.filter((item) => item.id !== id),
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
        <div className="flex flex-wrap gap-2">
          <button onClick={() => setInitialQuery(focusQuestion)} className={cardButtonClass()}>
            Use current question
          </button>
          <button onClick={onFetchLiterature} disabled={fetchingLiterature} className={cardButtonClass('primary')}>
            {fetchingLiterature ? 'Fetching...' : 'Fetch literature'}
          </button>
        </div>
      </div>

      {literatureToolStatus && (
        <div className="mt-3 rounded-2xl border border-sky-200 bg-sky-50 px-3 py-2 text-xs font-medium text-sky-950">
          {literatureToolStatus}
        </div>
      )}

      {(literatureProcessingSummary || literatureObjectiveLens || literatureElicitationQuestions.length > 0) && (
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
            <div className="mt-3 grid gap-3 xl:grid-cols-2">
              {literatureElicitationQuestions.map((question) => {
                const answer = literatureElicitationAnswers[question] || '';
                return (
                  <div key={question} className="rounded-2xl border border-sky-100 bg-white/85 p-3">
                    <div className="text-xs font-semibold uppercase tracking-wide text-sky-800">Tacit input needed</div>
                    <div className="mt-1 text-sm leading-6 text-slate-800">{question}</div>
                    <textarea
                      value={answer}
                      onChange={(e) => onLiteratureElicitationAnswerChange?.(question, e.target.value)}
                      rows={3}
                      className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                      placeholder="Add your transferability, feasibility, boundary-condition, or priority judgment..."
                    />
                    <button
                      onClick={() => onCaptureLiteratureTacitAnswer?.(question)}
                      disabled={!answer.trim()}
                      className={classNames(cardButtonClass(), 'mt-2 disabled:cursor-not-allowed disabled:opacity-50')}
                    >
                      Add as judgment call
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      <div className="mt-4 rounded-[1.4rem] border border-emerald-200 bg-emerald-50/70 p-4">
        <div className="text-[11px] font-semibold uppercase tracking-wide text-emerald-800">Template flow</div>
        <div className="mt-2 text-sm leading-6 text-emerald-950">
          Goal to initial query, then literature findings with knowns and unknowns, then recurring gap patterns, your judgment calls,
          validation or tool-use tracks, and finally proposal candidates.
        </div>
      </div>

      <div className="mt-4 rounded-[1.4rem] border border-slate-200 bg-slate-50 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Initial Query</div>
            <div className="mt-1 text-sm leading-6 text-slate-600">
              Store the literature-style question that translates the project goal into something the system can analyze.
            </div>
          </div>
          {focusQuestion.trim() && (
            <div className="max-w-sm rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600">
              Current working question: {focusQuestion}
            </div>
          )}
        </div>
        <textarea
          value={workTemplate.initial_query}
          onChange={(e) => setInitialQuery(e.target.value)}
          rows={4}
          className="mt-3 w-full rounded-[1.25rem] border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900"
          placeholder="Example: What are the key successful common strategies and examples in microbial flavonoid production? What are the latest improvement options and key challenges?"
        />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <section className="rounded-[1.4rem] border border-slate-200 bg-slate-50 p-4">
          <SectionHeader
            eyebrow="Evidence Library"
            title="Literature findings"
            description="Track the specific papers, examples, knowns, and open questions that should feed later decisions."
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
            ) : (
              workTemplate.literature_findings.map((finding, index) => (
                <div key={finding.id} className="rounded-[1.25rem] border border-slate-200 bg-white p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-semibold text-slate-950">Finding {index + 1}</div>
                    <button onClick={() => removeLiteratureFinding(finding.id)} className={cardButtonClass()}>
                      Remove
                    </button>
                  </div>

                  <label className="mt-3 block">
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Citation Or Source</div>
                    <input
                      value={finding.citation}
                      onChange={(e) => updateLiteratureFinding(finding.id, { citation: e.target.value })}
                      className="mt-1 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                      placeholder="Example: Optimizing yeast for high-level production of kaempferol and quercetin, 2023, cited by 41"
                    />
                  </label>

                  <label className="mt-3 block">
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Labels Or Question Types</div>
                    <input
                      value={finding.labels.join(', ')}
                      onChange={(e) => updateLiteratureFinding(finding.id, { labels: splitLines(e.target.value.replace(/,\s*/g, '\n')) })}
                      className="mt-1 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                      placeholder="Example: enzyme engineering, process optimization, transfer question"
                    />
                  </label>

                  <div className="mt-3 grid gap-3">
                    <Field
                      label="Knowns"
                      value={joinLines(finding.knowns)}
                      onChange={(value) => updateLiteratureFinding(finding.id, { knowns: splitLines(value) })}
                      placeholder="One known per line"
                      rows={4}
                    />
                    <Field
                      label="Unknowns Or Follow-up Questions"
                      value={joinLines(finding.unknowns)}
                      onChange={(value) => updateLiteratureFinding(finding.id, { unknowns: splitLines(value) })}
                      placeholder="One gap or question per line"
                      rows={4}
                    />
                  </div>

                  <Field
                    label="How this finding informs the project"
                    value={finding.relevance}
                    onChange={(value) => updateLiteratureFinding(finding.id, { relevance: value })}
                    placeholder="Explain why this source matters, what transfers, and where you remain uncertain."
                  />
                </div>
              ))
            )}
          </div>
        </section>

        <section className="rounded-[1.4rem] border border-slate-200 bg-slate-50 p-4">
          <SectionHeader
            eyebrow="Pattern Map"
            title="Recurring gaps and transfer questions"
            description="Group common research gaps so the planner sees patterns instead of isolated paper notes."
            actionLabel="Add gap theme"
            onAction={addGap}
          />
          <div className="mt-4 space-y-3">
            {workTemplate.common_gaps.length === 0 ? (
              <EmptyState
                title="No gap themes yet"
                body="Capture the recurring themes you want to zoom in on, such as AI enzyme design, synthetic biology tools, or transfer questions."
                actionLabel="Add first gap theme"
                onAction={addGap}
              />
            ) : (
              workTemplate.common_gaps.map((gap, index) => (
                <div key={gap.id} className="rounded-[1.25rem] border border-slate-200 bg-white p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-semibold text-slate-950">Gap theme {index + 1}</div>
                    <button onClick={() => removeGap(gap.id)} className={cardButtonClass()}>
                      Remove
                    </button>
                  </div>

                  <label className="mt-3 block">
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Theme</div>
                    <input
                      value={gap.theme}
                      onChange={(e) => updateGap(gap.id, { theme: e.target.value })}
                      className="mt-1 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                      placeholder="Example: Use of AI tools to improve key enzymes"
                    />
                  </label>

                  <Field
                    label="Supporting signals"
                    value={joinLines(gap.supporting_signals)}
                    onChange={(value) => updateGap(gap.id, { supporting_signals: splitLines(value) })}
                    placeholder="One recurring pattern or source hint per line"
                    rows={4}
                  />

                  <Field
                    label="Next research question"
                    value={gap.next_question}
                    onChange={(value) => updateGap(gap.id, { next_question: value })}
                    placeholder="What does this pattern imply for the current project?"
                  />

                  <Field
                    label="Priority note"
                    value={gap.priority_note}
                    onChange={(value) => updateGap(gap.id, { priority_note: value })}
                    placeholder="Explain why this deserves attention now."
                  />
                </div>
              ))
            )}
          </div>
        </section>

        <section className="rounded-[1.4rem] border border-slate-200 bg-slate-50 p-4">
          <SectionHeader
            eyebrow="Your View"
            title="Judgment calls and boundaries"
            description="Record what you agree with, what you want to validate, and what you explicitly do not want to pursue."
            actionLabel="Add judgment"
            onAction={addJudgment}
          />
          <div className="mt-4 space-y-3">
            {workTemplate.judgment_calls.length === 0 ? (
              <EmptyState
                title="No judgment calls yet"
                body="Add decisions like 'enzyme A and B are obvious priorities', 'method C is not feasible', or 'result A deserves extra attention'."
                actionLabel="Add first judgment"
                onAction={addJudgment}
              />
            ) : (
              workTemplate.judgment_calls.map((judgment, index) => (
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
                    placeholder="Example: Use methods A and B as standard, but exclude method C."
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

        <section className="rounded-[1.4rem] border border-slate-200 bg-slate-50 p-4">
          <SectionHeader
            eyebrow="Validation Agenda"
            title="Validation and tool-use tracks"
            description="Describe the independent analyses, database checks, AI workflows, or modeling tasks that should validate the literature view."
            actionLabel="Add validation track"
            onAction={addValidationTrack}
          />
          <div className="mt-4 space-y-3">
            {workTemplate.validation_tracks.length === 0 ? (
              <EmptyState
                title="No validation tracks yet"
                body="Add plans like database queries, AI-supported enzyme modeling, theoretical checks, or function-call style analyses."
                actionLabel="Add first validation track"
                onAction={addValidationTrack}
              />
            ) : (
              workTemplate.validation_tracks.map((track, index) => (
                <div key={track.id} className="rounded-[1.25rem] border border-slate-200 bg-white p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-semibold text-slate-950">Validation track {index + 1}</div>
                    <button onClick={() => removeValidationTrack(track.id)} className={cardButtonClass()}>
                      Remove
                    </button>
                  </div>

                  <Field
                    label="Target"
                    value={track.target}
                    onChange={(value) => updateValidationTrack(track.id, { target: value })}
                    placeholder="Example: FLS enzyme candidates or transferability of result A to target compound B"
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

      <section className="mt-4 rounded-[1.4rem] border border-slate-200 bg-slate-50 p-4">
        <SectionHeader
          eyebrow="Proposal Seeds"
          title="Candidate research proposals"
          description="Translate the evidence and your judgments into concrete proposal options that the planner can turn into experiments."
          actionLabel="Add proposal"
          onAction={addProposalCandidate}
        />
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

      <section className="mt-4 rounded-[1.4rem] border border-slate-200 bg-slate-50 p-4">
        <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Synthesis Memo</div>
        <div className="mt-1 text-sm leading-6 text-slate-600">
          Keep a short narrative summary of what the literature says, what you believe, what still needs validation, and what the next
          proposal should emphasize.
        </div>
        <textarea
          value={workTemplate.synthesis_memo}
          onChange={(e) => setSynthesisMemo(e.target.value)}
          rows={5}
          className="mt-3 w-full rounded-[1.25rem] border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900"
          placeholder="Example: AI-assisted enzyme improvement is promising, but the experiment plan needs explicit conditions, readouts, and generalization logic before we commit to a design campaign."
        />
      </section>
    </div>
  );
}
