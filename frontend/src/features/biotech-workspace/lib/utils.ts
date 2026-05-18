import type {
  ObjectiveCluster,
  ObjectiveFrame,
  Project,
  ProjectPersona,
  ResearchWorkTemplate,
} from '@/features/biotech-workspace/types';

export function classNames(...xs: Array<string | false | null | undefined>) {
  return xs.filter(Boolean).join(' ');
}

export function humanize(value: string) {
  return value.replace(/[_:-]+/g, ' ').replace(/\s+/g, ' ').trim();
}

export function defaultFocusQuestion(project: Project, persona?: ProjectPersona | null) {
  if (persona) {
    return '';
  }
  return '';
}

export function inferObjectiveFrame(objectiveText: string): ObjectiveFrame {
  const text = objectiveText.toLowerCase();

  if (/(literature|benchmark|examples|review|latest|papers|open questions|future|challenge)/.test(text)) {
    return {
      label: 'Evidence synthesis',
      description:
        'The draft should stay literature-first: benchmark reported strategies, compare examples, and turn open questions into next hypotheses.',
      draftLabel: 'Evidence Synthesis Draft',
      rawMaterialGuidance:
        'Only bring feedstock or raw materials in if the literature repeatedly flags precursor supply, carbon source, or sourcing cost as a real bottleneck.',
    };
  }

  if (/(data analysis|dataset|statistics|statistical|correlation|regression|omics|screening data|analy[sz]e data)/.test(text)) {
    return {
      label: 'Data analysis',
      description:
        'The draft should focus on interpreting datasets, comparing patterns, defining decision thresholds, and turning results into the next project choices.',
      draftLabel: 'Data Analysis Draft',
      rawMaterialGuidance:
        'Raw materials only matter here when feed, substrate, or sourcing variables are part of the dataset being interpreted.',
    };
  }

  if (/(experiment|strain|pathway|gene|construct|screen|assay|hypothesis)/.test(text)) {
    return {
      label: 'Experiment design',
      description:
        'The draft should prioritize hypotheses, constructs or edits, readouts, controls, and decision gates rather than full workflow coverage.',
      draftLabel: 'Experiment Plan Draft',
      rawMaterialGuidance:
        'Only include raw-material logic if substrate choice or precursor supply is part of the experimental hypothesis.',
    };
  }

  if (/(fermentation|media|bioreactor|culture|titer|yield|process|scale-up|doe)/.test(text)) {
    return {
      label: 'Process development',
      description: 'The draft should focus on operating conditions, DOE structure, and scale-up decision points.',
      draftLabel: 'Process Development Draft',
      rawMaterialGuidance:
        'Bring sourcing in only when feed composition, substrate quality, or cost materially changes process behavior.',
    };
  }

  if (/(purification|recovery|extraction|separation|downstream|isolation)/.test(text)) {
    return {
      label: 'Recovery strategy',
      description:
        'The draft should focus on extraction, separation, purity targets, and where upstream choices create downstream burden.',
      draftLabel: 'Recovery Strategy Draft',
      rawMaterialGuidance:
        'Only discuss raw materials if impurity profile or feed composition directly drives recovery complexity.',
    };
  }

  if (/(economics|tea|commercial|margin|cost|viability|scale)/.test(text)) {
    return {
      label: 'Economics and gating',
      description:
        'The draft should translate technical choices into cost drivers, milestone gates, and commercial feasibility questions.',
      draftLabel: 'Techno-Economic Draft',
      rawMaterialGuidance:
        'Raw materials should be a first-class topic here when they meaningfully affect COGS or scale assumptions.',
    };
  }

  if (/(feedstock|raw material|substrate|sourcing|supply|carbon source)/.test(text)) {
    return {
      label: 'Feedstock and sourcing',
      description:
        'The draft should focus on low-cost inputs, sourcing risk, and how feed choices constrain biology and process design.',
      draftLabel: 'Sourcing Strategy Draft',
      rawMaterialGuidance: 'Raw materials are central to this question and should be explicitly analyzed.',
    };
  }

  return {
    label: 'General project reasoning',
    description:
      'The draft can stay cross-functional, but it should still follow the working question instead of forcing every workflow stage.',
    draftLabel: 'Working Draft',
    rawMaterialGuidance:
      'Raw materials only need to enter when they change feasibility, economics, or the next scientific decision.',
  };
}

export function buildPlanningReasoningNotes(args: {
  reasoningNotes: string;
  selectedObjective: ObjectiveCluster | null;
  objectiveAnswers: Record<string, string>;
  globalQuestions: string[];
  globalQuestionAnswers: Record<string, string>;
}) {
  const sections: string[] = [];

  if (args.reasoningNotes.trim()) {
    sections.push(args.reasoningNotes.trim());
  }

  if (args.selectedObjective) {
    sections.push(
      [
        `Selected objective cluster: ${args.selectedObjective.title}`,
        args.selectedObjective.subtitle ? `Why this angle matters: ${args.selectedObjective.subtitle}` : '',
        args.selectedObjective.definition ? `Definition: ${args.selectedObjective.definition}` : '',
      ]
        .filter(Boolean)
        .join('\n')
    );
  }

  const answeredObjectiveQuestions = Object.entries(args.objectiveAnswers)
    .filter(([, answer]) => answer.trim())
    .map(([question, answer]) => `- ${question}: ${answer.trim()}`);
  if (answeredObjectiveQuestions.length > 0) {
    sections.push(`Objective refinement answers:\n${answeredObjectiveQuestions.join('\n')}`);
  }

  const answeredGlobalQuestions = args.globalQuestions
    .map((question) => ({ question, answer: args.globalQuestionAnswers[question] || '' }))
    .filter((item) => item.answer.trim())
    .map((item) => `- ${item.question}: ${item.answer.trim()}`);
  if (answeredGlobalQuestions.length > 0) {
    sections.push(`Cross-cutting considerations:\n${answeredGlobalQuestions.join('\n')}`);
  }

  return sections.filter(Boolean).join('\n\n');
}

export function createEmptyResearchWorkTemplate(initialQuery = ''): ResearchWorkTemplate {
  return {
    initial_query: initialQuery,
    literature_findings: [],
    common_gaps: [],
    judgment_calls: [],
    validation_tracks: [],
    proposal_candidates: [],
    synthesis_memo: '',
  };
}

export function scorePersonaForObjective(persona: ProjectPersona, objectiveText: string) {
  const text = objectiveText.toLowerCase();
  const haystack = [
    persona.workflow_stage,
    persona.focus_area,
    persona.summary,
    ...persona.goals,
    ...persona.workflow_focus,
  ]
    .join(' ')
    .toLowerCase();

  const keywordGroups: Record<string, string[]> = {
    feedstock: ['feedstock', 'raw material', 'substrate', 'sourcing', 'supply', 'carbon source', 'cost'],
    strain_engineering: ['experiment', 'engineering', 'pathway', 'gene', 'construct', 'biosynthesis', 'enzyme', 'strain'],
    upstream_process: ['fermentation', 'media', 'bioreactor', 'culture', 'titer', 'yield', 'upstream', 'doe'],
    downstream_processing: ['purification', 'recovery', 'extraction', 'separation', 'downstream', 'isolation'],
    economics: ['economics', 'cost', 'commercial', 'margin', 'tea', 'scale', 'viability'],
    analytics: [
      'literature',
      'benchmark',
      'examples',
      'strategies',
      'review',
      'latest',
      'papers',
      'challenges',
      'open questions',
      'data analysis',
      'dataset',
      'statistics',
      'omics',
      'correlation',
    ],
  };

  let score = 0;
  Object.entries(keywordGroups).forEach(([stage, keywords]) => {
    const stageWeight = stage === persona.workflow_stage ? 2 : 1;
    keywords.forEach((keyword) => {
      if (text.includes(keyword) && haystack.includes(keyword)) {
        score += stageWeight;
      }
    });
  });

  if (text.includes('draft experiment plan') && persona.workflow_stage === 'strain_engineering') score += 5;
  if (text.includes('draft experiment plan') && persona.workflow_stage === 'upstream_process') score += 4;
  if ((text.includes('literature') || text.includes('latest') || text.includes('examples')) && persona.workflow_stage === 'analytics') score += 6;
  return score;
}

export function stageTone(stage: string) {
  switch (stage) {
    case 'feedstock':
      return 'border-amber-300 bg-amber-50 text-amber-900';
    case 'strain_engineering':
      return 'border-emerald-300 bg-emerald-50 text-emerald-900';
    case 'upstream_process':
      return 'border-sky-300 bg-sky-50 text-sky-900';
    case 'downstream_processing':
      return 'border-fuchsia-300 bg-fuchsia-50 text-fuchsia-900';
    case 'economics':
      return 'border-slate-300 bg-slate-100 text-slate-900';
    case 'analytics':
      return 'border-violet-300 bg-violet-50 text-violet-900';
    case 'regulatory_quality':
      return 'border-rose-300 bg-rose-50 text-rose-900';
    default:
      return 'border-slate-300 bg-slate-50 text-slate-900';
  }
}

export function getModeVisualKey(modeLabel: string) {
  const label = modeLabel.toLowerCase();
  if (label.includes('evidence')) return 'evidence';
  if (label.includes('data analysis')) return 'data';
  if (label.includes('experiment')) return 'experiment';
  if (label.includes('process')) return 'process';
  if (label.includes('economics')) return 'economics';
  if (label.includes('feedstock') || label.includes('sourcing')) return 'sourcing';
  if (label.includes('recovery')) return 'recovery';
  return 'general';
}
