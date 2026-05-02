'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useMemo, useRef, useState } from 'react';

import { ModeBackdrop } from '@/features/biotech-workspace/components/ModeBackdrop';
import { ObjectiveClusteringSection } from '@/features/biotech-workspace/components/ObjectiveClusteringSection';
import { ProjectLandingShell } from '@/features/biotech-workspace/components/ProjectLandingShell';
import { ProjectOverview } from '@/features/biotech-workspace/components/ProjectOverview';
import { QueryAlignmentSection } from '@/features/biotech-workspace/components/QueryAlignmentSection';
import { WorkingDraftSection } from '@/features/biotech-workspace/components/WorkingDraftSection';
import { WorkspaceMemoryPanel } from '@/features/biotech-workspace/components/WorkspaceMemoryPanel';
import { WorkflowStateSidebar } from '@/features/biotech-workspace/components/WorkflowStateSidebar';
import { WorkspaceHeader } from '@/features/biotech-workspace/components/WorkspaceHeader';
import {
  API_BASE,
  clusterObjectives,
  createProject,
  createProjectCollaborator,
  createProjectQuery,
  deleteProject,
  fetchExecutionRun,
  fetchLatestExecutionRun,
  fetchProjectLiterature,
  fetchProjectQueries,
  fetchProjects,
  fetchWorkspaceMemory,
  fetchWorkspaceState,
  generateProjectPlan,
  inferWorkspaceMemory,
  preparePaperPdf,
  saveWorkspaceMemory,
  saveWorkspaceState,
  startExecutionRun,
  updateProjectQuery,
} from '@/features/biotech-workspace/lib/api';
import {
  buildPlanningReasoningNotes,
  classNames,
  createEmptyResearchWorkTemplate,
  defaultFocusQuestion,
  getModeVisualKey,
  inferObjectiveFrame,
  scorePersonaForObjective,
} from '@/features/biotech-workspace/lib/utils';
import type {
  AgenticPlan,
  JudgmentCall,
  ObjectiveCluster,
  PlanStep,
  ProjectExecutionEvent,
  ProjectExecutionRun,
  Project,
  ProjectFormState,
  ProjectQuerySession,
  ResearchFinding,
  ResearchWorkTemplate,
  StatusState,
  TacitMemoryItem,
} from '@/features/biotech-workspace/types';

type FlowStep = 'collaborator' | 'query' | 'objective' | 'workspace';
type DesktopOpenPathResult = { ok: boolean; error?: string };
type PdfViewerState = {
  findingId: string;
  title: string;
  url: string;
  annotatedPath?: string | null;
  insights: string[];
  questions: string[];
} | null;
type ManualCollaboratorForm = {
  name: string;
  role: string;
  workflow_stage: string;
  focus_area: string;
  workflow_focus: string;
  goals: string;
  starter_questions: string;
};
type ManualObjectiveForm = {
  title: string;
  subtitle: string;
  definition: string;
  signals: string;
  facet_questions: string;
  exemplar_answer: string;
};

function stableFindingKey(finding: ResearchFinding) {
  const ids = finding.source_ids || {};
  const sourceKey = ids.doi || ids.pmid || ids.pmcid || ids.pdf_url || finding.citation || finding.id;
  return sourceKey.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 80) || `finding_${Date.now()}`;
}

function uniqueFindingId(finding: ResearchFinding, existingIds: Set<string>, index: number) {
  const base = stableFindingKey(finding) || `finding_${index + 1}`;
  let candidate = `finding_${base}`;
  let suffix = 2;
  while (existingIds.has(candidate)) {
    candidate = `finding_${base}_${suffix}`;
    suffix += 1;
  }
  existingIds.add(candidate);
  return candidate;
}

const emptyManualCollaborator: ManualCollaboratorForm = {
  name: '',
  role: '',
  workflow_stage: 'analytics',
  focus_area: '',
  workflow_focus: '',
  goals: '',
  starter_questions: '',
};

const emptyManualObjective: ManualObjectiveForm = {
  title: '',
  subtitle: '',
  definition: '',
  signals: '',
  facet_questions: '',
  exemplar_answer: '',
};

declare global {
  interface Window {
    desktopApp?: {
      openPath?: (targetPath: string) => Promise<DesktopOpenPathResult>;
    };
  }
}

export default function BiotechProjectWorkspace() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const routeProjectIdRaw = searchParams.get('projectId') || '';
  const routePersonaIdRaw = searchParams.get('personaId') || '';
  const parsedRouteProjectId = Number(routeProjectIdRaw);
  const parsedRoutePersonaId = Number(routePersonaIdRaw);
  const routeProjectId = routeProjectIdRaw && Number.isFinite(parsedRouteProjectId) ? parsedRouteProjectId : '';
  const routePersonaId = routePersonaIdRaw && Number.isFinite(parsedRoutePersonaId) ? parsedRoutePersonaId : '';

  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<number | ''>('');
  const [selectedPersonaId, setSelectedPersonaId] = useState<number | ''>('');
  const [activeFlowStep, setActiveFlowStep] = useState<FlowStep>(routePersonaId !== '' ? 'query' : 'collaborator');
  const [focusQuestion, setFocusQuestion] = useState('');
  const [objectiveClusters, setObjectiveClusters] = useState<ObjectiveCluster[]>([]);
  const [selectedObjectiveId, setSelectedObjectiveId] = useState('');
  const [globalQuestions, setGlobalQuestions] = useState<string[]>([]);
  const [objectiveAnswers, setObjectiveAnswers] = useState<Record<string, string>>({});
  const [globalQuestionAnswers, setGlobalQuestionAnswers] = useState<Record<string, string>>({});
  const [clarifyingAnswers, setClarifyingAnswers] = useState<Record<string, string>>({});
  const [reasoningNotes, setReasoningNotes] = useState('');
  const [researchWorkTemplate, setResearchWorkTemplate] = useState<ResearchWorkTemplate>(createEmptyResearchWorkTemplate());
  const [agenticPlan, setAgenticPlan] = useState<AgenticPlan | null>(null);
  const [executionRun, setExecutionRun] = useState<ProjectExecutionRun | null>(null);
  const [executionEvents, setExecutionEvents] = useState<ProjectExecutionEvent[]>([]);
  const [selectedPlanStepId, setSelectedPlanStepId] = useState('');
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [creatingProject, setCreatingProject] = useState(false);
  const [deletingProjectId, setDeletingProjectId] = useState<number | null>(null);
  const [loadingObjectiveClusters, setLoadingObjectiveClusters] = useState(false);
  const [loadingPlan, setLoadingPlan] = useState(false);
  const [startingExecution, setStartingExecution] = useState(false);
  const [fetchingLiterature, setFetchingLiterature] = useState(false);
  const [literatureToolStatus, setLiteratureToolStatus] = useState<string | null>(null);
  const [literatureObjectiveLens, setLiteratureObjectiveLens] = useState<string | null>(null);
  const [literatureProcessingSummary, setLiteratureProcessingSummary] = useState<string | null>(null);
  const [literatureElicitationQuestions, setLiteratureElicitationQuestions] = useState<string[]>([]);
  const [literatureElicitationAnswers, setLiteratureElicitationAnswers] = useState<Record<string, string>>({});
  const [preparingPdfFindingId, setPreparingPdfFindingId] = useState<string | null>(null);
  const [pdfAnnotationStatus, setPdfAnnotationStatus] = useState<string | null>(null);
  const [pdfViewer, setPdfViewer] = useState<PdfViewerState>(null);
  const [memoryDrawerOpen, setMemoryDrawerOpen] = useState(false);
  const [projectQueries, setProjectQueries] = useState<ProjectQuerySession[]>([]);
  const [activeQueryId, setActiveQueryId] = useState<number | ''>('');
  const [newQueryText, setNewQueryText] = useState('');
  const [showNewQueryForm, setShowNewQueryForm] = useState(false);
  const [creatingQuery, setCreatingQuery] = useState(false);
  const [creatingManualCollaborator, setCreatingManualCollaborator] = useState(false);
  const [manualCollaborator, setManualCollaborator] = useState<ManualCollaboratorForm>(emptyManualCollaborator);
  const [showManualCollaboratorForm, setShowManualCollaboratorForm] = useState(false);
  const [showManualObjectiveForm, setShowManualObjectiveForm] = useState(false);
  const [manualObjective, setManualObjective] = useState<ManualObjectiveForm>(emptyManualObjective);
  const [loadingWorkspace, setLoadingWorkspace] = useState(false);
  const [collaboratorPickerCollapsed, setCollaboratorPickerCollapsed] = useState(false);
  const [objectivePickerCollapsed, setObjectivePickerCollapsed] = useState(false);
  const [workspaceReadyForSave, setWorkspaceReadyForSave] = useState(false);
  const [workspaceSaveState, setWorkspaceSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [workspaceUpdatedAt, setWorkspaceUpdatedAt] = useState<string | null>(null);
  const [tacitState, setTacitState] = useState<TacitMemoryItem[]>([]);
  const [handoffSummary, setHandoffSummary] = useState('');
  const [memoryStatus, setMemoryStatus] = useState('not saved yet');
  const [inferringMemory, setInferringMemory] = useState(false);
  const [status, setStatus] = useState<StatusState | null>(null);
  const querySectionRef = useRef<HTMLDivElement | null>(null);
  const objectiveSectionRef = useRef<HTMLDivElement | null>(null);
  const draftSectionRef = useRef<HTMLDivElement | null>(null);
  const [form, setForm] = useState<ProjectFormState>({
    name: '',
    end_product: '',
    target_host: 'Saccharomyces cerevisiae',
    project_goal: '',
    raw_material_focus: '',
    notes: '',
  });

  const selectedProject =
    selectedProjectId === '' ? null : projects.find((project) => project.id === Number(selectedProjectId)) || null;
  const selectedPersona =
    selectedProject && selectedPersonaId !== ''
      ? selectedProject.personas.find((persona) => persona.persona_id === Number(selectedPersonaId)) || null
      : null;
  const selectedObjective = objectiveClusters.find((objective) => objective.id === selectedObjectiveId) || null;
  const pdfViewerFinding = pdfViewer
    ? researchWorkTemplate.literature_findings.find((finding) => finding.id === pdfViewer.findingId) || null
    : null;
  const workingQuestionText = focusQuestion.trim() || selectedProject?.project_goal || '';
  const selectedObjectiveLens = selectedObjective
    ? [selectedObjective.title, selectedObjective.definition, ...selectedObjective.signals].join(' ')
    : '';
  const activeObjectiveFrame = selectedObjective ? inferObjectiveFrame(selectedObjectiveLens) : null;
  const currentModeTitle = selectedObjective ? selectedObjective.title : 'Neutral workspace';
  const currentModeDescription = selectedObjective
    ? selectedObjective.definition
    : 'Choose an objective mode after aligning the query with a collaborator. The selected mode becomes the active workspace setting.';
  const modeVisualKey = selectedObjective ? getModeVisualKey(selectedObjective.title) : 'general';
  const rankedPersonas = selectedProject
    ? [...selectedProject.personas]
        .map((persona) => ({ persona, score: scorePersonaForObjective(persona, workingQuestionText) }))
        .sort((a, b) => b.score - a.score || a.persona.name.localeCompare(b.persona.name))
    : [];
  const topRecommendedPersona = rankedPersonas[0]?.persona || null;
  const workspaceMemoryKey = useMemo(() => {
    const parts = [
      selectedProject?.scope_id || (selectedProject ? `project-${selectedProject.id}` : 'no-project'),
      activeQueryId === '' ? 'no-query' : `query-${activeQueryId}`,
      selectedPersonaId === '' ? 'no-persona' : `persona-${selectedPersonaId}`,
    ];
    return parts.join('__').toLowerCase().replace(/[^a-z0-9_-]+/g, '-');
  }, [selectedProject?.id, selectedProject?.scope_id, activeQueryId, selectedPersonaId]);
  const explicitWorkspaceState = useMemo<Record<string, unknown>>(
    () => ({
      selected_project: selectedProject,
      persona_id: selectedPersonaId === '' ? null : Number(selectedPersonaId),
      persona: selectedPersona?.name || null,
      query: focusQuestion,
      selected_objective: selectedObjective,
      clarifying_answers: clarifyingAnswers,
      objective_answers: objectiveAnswers,
      global_question_answers: globalQuestionAnswers,
      reasoning_notes: reasoningNotes,
      research_work_template: researchWorkTemplate,
      literature_processing: {
        objective_lens: literatureObjectiveLens,
        processing_summary: literatureProcessingSummary,
        elicitation_questions: literatureElicitationQuestions,
        elicitation_answers: literatureElicitationAnswers,
      },
      agentic_plan: agenticPlan,
      selected_plan_step_id: selectedPlanStepId,
      execution_run: executionRun,
    }),
    [
      selectedProject,
      selectedPersonaId,
      selectedPersona?.name,
      focusQuestion,
      selectedObjective,
      clarifyingAnswers,
      objectiveAnswers,
      globalQuestionAnswers,
      reasoningNotes,
      researchWorkTemplate,
      literatureObjectiveLens,
      literatureProcessingSummary,
      literatureElicitationQuestions,
      literatureElicitationAnswers,
      agenticPlan,
      selectedPlanStepId,
      executionRun,
    ]
  );
  const workspaceDigest = useMemo(() => {
    const findingNotes = researchWorkTemplate.literature_findings
      .slice(0, 6)
      .map((finding, index) => {
        const knowns = finding.knowns.slice(0, 2).join('; ');
        const unknowns = finding.unknowns.slice(0, 2).join('; ');
        return `${index + 1}. ${finding.citation || 'Untitled source'}${knowns ? `\nKnown: ${knowns}` : ''}${unknowns ? `\nOpen: ${unknowns}` : ''}${finding.relevance ? `\nNotes: ${finding.relevance.slice(0, 400)}` : ''}`;
      })
      .join('\n\n');
    const userInputs = [
      ...Object.entries(clarifyingAnswers),
      ...Object.entries(objectiveAnswers),
      ...Object.entries(globalQuestionAnswers),
      ...Object.entries(literatureElicitationAnswers),
    ]
      .filter(([, value]) => String(value || '').trim())
      .map(([question, answer]) => `- ${question}: ${answer}`)
      .join('\n');
    return [
      `Project: ${selectedProject?.name || 'No project selected'}`,
      `Goal: ${selectedProject?.project_goal || 'Not set'}`,
      `Collaborator: ${selectedPersona?.name || 'Not selected'}`,
      `Objective: ${selectedObjective?.title || 'Not selected'}`,
      `Working question: ${focusQuestion || researchWorkTemplate.initial_query || 'Not set'}`,
      literatureProcessingSummary ? `Literature processing: ${literatureProcessingSummary}` : '',
      findingNotes ? `Literature insights:\n${findingNotes}` : '',
      userInputs ? `User inputs and tacit judgments:\n${userInputs}` : '',
      reasoningNotes ? `Reasoning notes:\n${reasoningNotes}` : '',
      handoffSummary ? `Handoff summary:\n${handoffSummary}` : '',
    ]
      .filter(Boolean)
      .join('\n\n');
  }, [
    researchWorkTemplate,
    clarifyingAnswers,
    objectiveAnswers,
    globalQuestionAnswers,
    literatureElicitationAnswers,
    selectedProject,
    selectedPersona?.name,
    selectedObjective?.title,
    focusQuestion,
    literatureProcessingSummary,
    reasoningNotes,
    handoffSummary,
  ]);
  const workspaceStatusMessage = loadingWorkspace
    ? 'Loading saved workspace...'
    : workspaceSaveState === 'saving'
      ? 'Saving workspace...'
      : workspaceSaveState === 'saved'
        ? `Workspace saved${workspaceUpdatedAt ? ` at ${new Date(workspaceUpdatedAt).toLocaleString()}` : ''}.`
        : workspaceSaveState === 'error'
          ? 'Workspace save failed. Changes stay local until the next successful save.'
          : 'Workspace changes are kept per project persona.';
  const modeStudioTone: Record<string, string> = {
    general: 'border-slate-200/90 bg-white/78',
    evidence: 'border-sky-200/80 bg-[linear-gradient(135deg,rgba(239,246,255,0.78),rgba(255,255,255,0.74))]',
    data: 'border-indigo-200/80 bg-[linear-gradient(135deg,rgba(238,242,255,0.8),rgba(255,255,255,0.74))]',
    experiment: 'border-emerald-200/80 bg-[linear-gradient(135deg,rgba(236,253,245,0.82),rgba(255,251,235,0.72))]',
    process: 'border-cyan-200/80 bg-[linear-gradient(135deg,rgba(236,254,255,0.8),rgba(255,255,255,0.74))]',
    economics: 'border-amber-200/80 bg-[linear-gradient(135deg,rgba(255,251,235,0.82),rgba(255,255,255,0.74))]',
    sourcing: 'border-lime-200/80 bg-[linear-gradient(135deg,rgba(247,254,231,0.82),rgba(255,251,235,0.72))]',
    recovery: 'border-fuchsia-200/80 bg-[linear-gradient(135deg,rgba(250,245,255,0.82),rgba(255,255,255,0.74))]',
  };
  const modePageTone: Record<string, string> = {
    general: 'bg-emerald-50/20',
    evidence: 'bg-sky-50/50',
    data: 'bg-indigo-50/45',
    experiment: 'bg-emerald-50/50',
    process: 'bg-cyan-50/50',
    economics: 'bg-amber-50/45',
    sourcing: 'bg-lime-50/45',
    recovery: 'bg-fuchsia-50/45',
  };
  const scrollToSection = (target: React.RefObject<HTMLDivElement | null>) => {
    window.requestAnimationFrame(() => {
      target.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  };
  const resetQueryDependentState = (nextQuery = '') => {
    setFocusQuestion(nextQuery);
    setSelectedPersonaId('');
    setCollaboratorPickerCollapsed(false);
    setObjectiveClusters([]);
    setSelectedObjectiveId('');
    setGlobalQuestions([]);
    setObjectiveAnswers({});
    setGlobalQuestionAnswers({});
    setClarifyingAnswers({});
    setReasoningNotes('');
    setResearchWorkTemplate(createEmptyResearchWorkTemplate(nextQuery));
    setAgenticPlan(null);
    setSelectedPlanStepId('');
    setLiteratureToolStatus(null);
    setLiteratureObjectiveLens(null);
    setLiteratureProcessingSummary(null);
    setLiteratureElicitationQuestions([]);
    setLiteratureElicitationAnswers({});
    setActiveFlowStep('collaborator');
  };
  const makeQueryTitle = (query: string, fallback: string) => {
    const trimmed = query.trim();
    return trimmed ? trimmed.slice(0, 72) : fallback;
  };
  const currentQueryState = (): Record<string, unknown> => ({
    selected_persona_id: selectedPersonaId === '' ? null : Number(selectedPersonaId),
    active_flow_step: activeFlowStep,
    objective_clusters: objectiveClusters,
    selected_objective_id: selectedObjectiveId,
    global_questions: globalQuestions,
    objective_answers: objectiveAnswers,
    global_question_answers: globalQuestionAnswers,
    clarifying_answers: clarifyingAnswers,
    reasoning_notes: reasoningNotes,
    research_work_template: researchWorkTemplate,
    agentic_plan: agenticPlan,
    selected_plan_step_id: selectedPlanStepId,
    literature_tool_status: literatureToolStatus,
    literature_objective_lens: literatureObjectiveLens,
    literature_processing_summary: literatureProcessingSummary,
    literature_elicitation_questions: literatureElicitationQuestions,
    literature_elicitation_answers: literatureElicitationAnswers,
  });
  const restoreQueryState = (query: ProjectQuerySession) => {
    const state = query.state || {};
    const personaId = typeof state.selected_persona_id === 'number' ? state.selected_persona_id : '';
    setFocusQuestion(query.query || '');
    setSelectedPersonaId(personaId);
    setActiveFlowStep((state.active_flow_step as FlowStep) || (personaId === '' ? 'collaborator' : 'query'));
    setCollaboratorPickerCollapsed(Boolean(personaId));
    setObjectiveClusters((state.objective_clusters as ObjectiveCluster[]) || []);
    setSelectedObjectiveId(typeof state.selected_objective_id === 'string' ? state.selected_objective_id : '');
    setGlobalQuestions((state.global_questions as string[]) || []);
    setObjectiveAnswers((state.objective_answers as Record<string, string>) || {});
    setGlobalQuestionAnswers((state.global_question_answers as Record<string, string>) || {});
    setClarifyingAnswers((state.clarifying_answers as Record<string, string>) || {});
    setReasoningNotes(typeof state.reasoning_notes === 'string' ? state.reasoning_notes : '');
    setResearchWorkTemplate((state.research_work_template as ResearchWorkTemplate) || createEmptyResearchWorkTemplate(query.query));
    setAgenticPlan((state.agentic_plan as AgenticPlan | null) || null);
    setSelectedPlanStepId(typeof state.selected_plan_step_id === 'string' ? state.selected_plan_step_id : '');
    setLiteratureToolStatus(typeof state.literature_tool_status === 'string' ? state.literature_tool_status : null);
    setLiteratureObjectiveLens(typeof state.literature_objective_lens === 'string' ? state.literature_objective_lens : null);
    setLiteratureProcessingSummary(typeof state.literature_processing_summary === 'string' ? state.literature_processing_summary : null);
    setLiteratureElicitationQuestions((state.literature_elicitation_questions as string[]) || []);
    setLiteratureElicitationAnswers((state.literature_elicitation_answers as Record<string, string>) || {});
    setObjectivePickerCollapsed(Boolean(state.selected_objective_id));
  };

  const loadProjects = async (preferredProjectId?: number) => {
    setLoadingProjects(true);
    try {
      const data = await fetchProjects();
      const rows = data.projects || [];
      setProjects(rows);
      setSelectedProjectId((current) => {
        if (preferredProjectId && rows.some((project) => project.id === preferredProjectId)) {
          return preferredProjectId;
        }
        if (routeProjectId !== '' && rows.some((project) => project.id === Number(routeProjectId))) {
          return Number(routeProjectId);
        }
        if (current !== '' && rows.some((project) => project.id === Number(current))) {
          return current;
        }
        return '';
      });
    } catch (error) {
      setProjects([]);
      setSelectedProjectId('');
      setStatus({ type: 'error', message: error instanceof Error ? error.message : 'Failed to load projects' });
    } finally {
      setLoadingProjects(false);
    }
  };

  useEffect(() => {
    loadProjects().catch(() => {});
  }, [routeProjectId]);

  useEffect(() => {
    if (routeProjectId === '') {
      setSelectedProjectId('');
      return;
    }
    setSelectedProjectId(routeProjectId);
  }, [routeProjectId]);

  useEffect(() => {
    if (!selectedProject) {
      setSelectedPersonaId('');
      setProjectQueries([]);
      setActiveQueryId('');
      return;
    }

    setSelectedPersonaId((current) => {
      if (routePersonaId !== '' && selectedProject.personas.some((persona) => persona.persona_id === Number(routePersonaId))) {
        return Number(routePersonaId);
      }
      if (current !== '' && selectedProject.personas.some((persona) => persona.persona_id === Number(current))) {
        return current;
      }
      return '';
    });
  }, [selectedProject, routePersonaId]);

  useEffect(() => {
    let cancelled = false;
    const loadQueries = async () => {
      if (!selectedProject) {
        return;
      }
      try {
        const response = await fetchProjectQueries(selectedProject.id);
        if (cancelled) return;
        const rows = response.queries || [];
        setProjectQueries(rows);
        if (rows.length > 0) {
          setActiveQueryId(rows[0].id);
          restoreQueryState(rows[0]);
        } else {
          setActiveQueryId('');
          resetQueryDependentState('');
          setActiveFlowStep('query');
          setShowNewQueryForm(true);
        }
      } catch (error) {
        if (!cancelled) {
          setStatus({ type: 'error', message: error instanceof Error ? error.message : 'Failed to load project queries' });
        }
      }
    };
    loadQueries().catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [selectedProject?.id]);

  useEffect(() => {
    if (!selectedProject || activeQueryId === '') {
      return;
    }
    const timer = window.setTimeout(async () => {
      try {
        const saved = await updateProjectQuery(selectedProject.id, activeQueryId, {
          title: makeQueryTitle(focusQuestion, 'Untitled query'),
          query: focusQuestion,
          state: currentQueryState(),
        });
        setProjectQueries((current) => current.map((item) => (item.id === saved.id ? saved : item)));
      } catch {
        // Workspace-level autosave still protects the active draft; query session save can retry on the next edit.
      }
    }, 900);
    return () => window.clearTimeout(timer);
  }, [
    selectedProject?.id,
    activeQueryId,
    focusQuestion,
    selectedPersonaId,
    activeFlowStep,
    JSON.stringify(objectiveClusters),
    selectedObjectiveId,
    JSON.stringify(globalQuestions),
    JSON.stringify(objectiveAnswers),
    JSON.stringify(globalQuestionAnswers),
    JSON.stringify(clarifyingAnswers),
    reasoningNotes,
    JSON.stringify(researchWorkTemplate),
    JSON.stringify(agenticPlan),
    selectedPlanStepId,
    literatureToolStatus,
    literatureObjectiveLens,
    literatureProcessingSummary,
    JSON.stringify(literatureElicitationQuestions),
    JSON.stringify(literatureElicitationAnswers),
  ]);

  useEffect(() => {
    if (!selectedPersona) {
      setCollaboratorPickerCollapsed(false);
    }
  }, [selectedPersona?.persona_id]);

  useEffect(() => {
    if (!selectedProject || selectedPersonaId === '') {
      return;
    }

    const currentProjectId = searchParams.get('projectId') || '';
    const currentPersonaId = searchParams.get('personaId') || '';
    const nextProjectId = String(selectedProject.id);
    const nextPersonaId = String(selectedPersonaId);

    if (currentProjectId === nextProjectId && currentPersonaId === nextPersonaId) {
      return;
    }

    const params = new URLSearchParams(searchParams.toString());
    params.set('projectId', nextProjectId);
    params.set('personaId', nextPersonaId);
    router.replace(`/?${params.toString()}`, { scroll: false });
  }, [router, searchParams, selectedProject?.id, selectedPersonaId]);

  useEffect(() => {
    setAgenticPlan(null);
    setSelectedPlanStepId('');
    setObjectiveClusters([]);
    setSelectedObjectiveId('');
    setGlobalQuestions([]);
    setObjectiveAnswers({});
    setGlobalQuestionAnswers({});
    setClarifyingAnswers({});
    setReasoningNotes('');
    setResearchWorkTemplate(createEmptyResearchWorkTemplate());
    setWorkspaceUpdatedAt(null);
    setWorkspaceReadyForSave(false);
    setWorkspaceSaveState('idle');
    setObjectivePickerCollapsed(false);
    setExecutionRun(null);
    setExecutionEvents([]);
    setLiteratureToolStatus(null);
    setLiteratureObjectiveLens(null);
    setLiteratureProcessingSummary(null);
    setLiteratureElicitationQuestions([]);
    setLiteratureElicitationAnswers({});
    setTacitState([]);
    setHandoffSummary('');
    setMemoryStatus('loading memory...');
    setActiveFlowStep('query');
  }, [selectedProjectId]);

  useEffect(() => {
    let cancelled = false;

    const loadWorkspace = async () => {
      if (!selectedProject || !selectedPersona || selectedPersonaId === '' || activeQueryId !== '') {
        return;
      }

      setLoadingWorkspace(true);
      try {
        const response = await fetchWorkspaceState(selectedProject.id, Number(selectedPersonaId));
        if (cancelled) return;

        if (response.state) {
          const nextFocusQuestion = response.state.focus_question || defaultFocusQuestion(selectedProject, selectedPersona);
          setFocusQuestion(nextFocusQuestion);
          setClarifyingAnswers(response.state.clarifying_answers || {});
          setReasoningNotes(response.state.reasoning_notes || '');
          setResearchWorkTemplate(response.state.work_template || createEmptyResearchWorkTemplate(nextFocusQuestion));
          setAgenticPlan(response.state.plan || null);
          setSelectedPlanStepId(response.state.selected_step_id || response.state.plan?.steps[0]?.id || '');
          setWorkspaceUpdatedAt(response.state.updated_at || null);
          setWorkspaceSaveState('saved');
        } else {
          const nextFocusQuestion = defaultFocusQuestion(selectedProject, selectedPersona);
          setFocusQuestion(nextFocusQuestion);
          setClarifyingAnswers({});
          setReasoningNotes('');
          setResearchWorkTemplate(createEmptyResearchWorkTemplate(nextFocusQuestion));
          setAgenticPlan(null);
          setSelectedPlanStepId('');
          setWorkspaceUpdatedAt(null);
          setWorkspaceSaveState('idle');
        }
      } catch (error) {
        if (cancelled) return;
        const nextFocusQuestion = defaultFocusQuestion(selectedProject, selectedPersona);
        setFocusQuestion(nextFocusQuestion);
        setClarifyingAnswers({});
        setReasoningNotes('');
        setResearchWorkTemplate(createEmptyResearchWorkTemplate(nextFocusQuestion));
        setAgenticPlan(null);
        setSelectedPlanStepId('');
        setWorkspaceUpdatedAt(null);
        setWorkspaceSaveState('error');
        setStatus({ type: 'error', message: error instanceof Error ? error.message : 'Failed to load saved workspace' });
      } finally {
        if (!cancelled) {
          setLoadingWorkspace(false);
          setWorkspaceReadyForSave(true);
        }
      }
    };

    loadWorkspace().catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [selectedProject?.id, selectedPersona?.persona_id, selectedPersonaId, activeQueryId]);

  useEffect(() => {
    let cancelled = false;

    const loadExecutionRun = async () => {
      if (!selectedProject || !selectedPersona || selectedPersonaId === '') {
        return;
      }
      try {
        const response = await fetchLatestExecutionRun(selectedProject.id, Number(selectedPersonaId));
        if (cancelled) return;
        setExecutionRun(response.run || null);
        setExecutionEvents(response.events || []);
      } catch {
        if (!cancelled) {
          setExecutionRun(null);
          setExecutionEvents([]);
        }
      }
    };

    loadExecutionRun().catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [selectedProject?.id, selectedPersona?.persona_id, selectedPersonaId]);

  useEffect(() => {
    if (!workspaceReadyForSave || loadingWorkspace || !selectedProject || !selectedPersona || selectedPersonaId === '' || activeQueryId !== '') {
      return;
    }

    const timer = window.setTimeout(async () => {
      setWorkspaceSaveState('saving');
      try {
        const response = await saveWorkspaceState(selectedProject.id, Number(selectedPersonaId), {
          focus_question: focusQuestion,
          clarifying_answers: clarifyingAnswers,
          reasoning_notes: reasoningNotes,
          work_template: researchWorkTemplate,
          plan: agenticPlan,
          selected_step_id: selectedPlanStepId || undefined,
        });
        setWorkspaceUpdatedAt(response.state?.updated_at || new Date().toISOString());
        setWorkspaceSaveState('saved');
      } catch {
        setWorkspaceSaveState('error');
      }
    }, 900);

    return () => {
      window.clearTimeout(timer);
    };
  }, [
    workspaceReadyForSave,
    loadingWorkspace,
    selectedProject?.id,
    selectedPersona?.persona_id,
    selectedPersonaId,
    activeQueryId,
    focusQuestion,
    JSON.stringify(clarifyingAnswers),
    reasoningNotes,
    JSON.stringify(researchWorkTemplate),
    JSON.stringify(agenticPlan),
    selectedPlanStepId,
  ]);

  useEffect(() => {
    if (!selectedProject || selectedPersonaId === '') {
      return;
    }
    let cancelled = false;
    const loadMemory = async () => {
      try {
        const response = await fetchWorkspaceMemory(workspaceMemoryKey);
        if (cancelled) return;
        if (response.memory) {
          setTacitState(response.memory.tacit_state || []);
          setHandoffSummary(response.memory.handoff_summary || '');
          setMemoryStatus(`loaded memory${response.memory.updated_at ? ` from ${new Date(response.memory.updated_at).toLocaleString()}` : ''}`);
        } else {
          setTacitState([]);
          setHandoffSummary('');
          setMemoryStatus('new memory record');
        }
      } catch {
        if (!cancelled) {
          setMemoryStatus('memory load unavailable');
        }
      }
    };
    loadMemory().catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [selectedProject?.id, selectedPersonaId, workspaceMemoryKey]);

  useEffect(() => {
    if (!selectedProject || selectedPersonaId === '') {
      return;
    }
    const timer = window.setTimeout(async () => {
      try {
        const response = await saveWorkspaceMemory(workspaceMemoryKey, {
          scope: selectedProject.scope_id || `project-${selectedProject.id}`,
          explicit_state: explicitWorkspaceState,
          tacit_state: tacitState,
          handoff_summary: handoffSummary,
        });
        const updatedAt = response.memory?.updated_at;
        setMemoryStatus(`saved${updatedAt ? ` at ${new Date(updatedAt).toLocaleTimeString()}` : ''}`);
      } catch {
        setMemoryStatus('save failed; memory changes are local');
      }
    }, 1100);
    return () => {
      window.clearTimeout(timer);
    };
  }, [
    selectedProject?.id,
    selectedProject?.scope_id,
    selectedPersonaId,
    workspaceMemoryKey,
    JSON.stringify(explicitWorkspaceState),
    JSON.stringify(tacitState),
    handoffSummary,
  ]);

  useEffect(() => {
    if (!selectedProject || !executionRun || !['queued', 'running'].includes(executionRun.status)) {
      return;
    }

    const timer = window.setInterval(async () => {
      try {
        const response = await fetchExecutionRun(selectedProject.id, executionRun.id);
        setExecutionRun(response.run || null);
        setExecutionEvents(response.events || []);
        if (response.run?.final_work_template) {
          setResearchWorkTemplate(response.run.final_work_template);
        }
        if (response.run?.final_plan) {
          setAgenticPlan(response.run.final_plan);
          setSelectedPlanStepId(response.run.final_plan.steps[0]?.id || '');
        }
        if (response.run?.status === 'completed') {
          setStatus({ type: 'success', message: 'Agentic execution completed and the workspace was refreshed.' });
        } else if (response.run?.status === 'failed') {
          setStatus({ type: 'error', message: response.run.error_message || 'Agentic execution failed.' });
        }
      } catch {
        // Keep the existing UI state if polling fails briefly.
      }
    }, 2000);

    return () => {
      window.clearInterval(timer);
    };
  }, [selectedProject?.id, executionRun?.id, executionRun?.status]);

  const handleCreateProject = async () => {
    if (!form.name.trim() || !form.end_product.trim()) {
      setStatus({ type: 'error', message: 'Project name and end product are required.' });
      return;
    }

    setCreatingProject(true);
    setStatus({ type: 'info', message: 'Creating project and generating project-specific collaborators...' });
    try {
      const response = await createProject(form);
      await loadProjects(response.project.id);
      router.push(`/?projectId=${response.project.id}`);
      setSelectedProjectId(response.project.id);
      setSelectedPersonaId('');
      setActiveFlowStep('query');
      setFocusQuestion('');
      setShowNewQueryForm(true);
      setReasoningNotes('');
      setStatus({
        type: 'success',
        message: `Created ${response.project.name} with ${response.created_persona_ids.length} project collaborators.`,
      });
    } catch (error) {
      setStatus({ type: 'error', message: error instanceof Error ? error.message : 'Failed to create project' });
    } finally {
      setCreatingProject(false);
    }
  };

  const handleOpenProject = (projectId: number) => {
    router.push(`/?projectId=${projectId}`);
    setSelectedProjectId(projectId);
  };

  const handleCreateProjectQuery = async () => {
    if (!selectedProject) {
      return;
    }
    const query = newQueryText.trim();
    if (!query) {
      setStatus({ type: 'error', message: 'Write the query before creating the investigation.' });
      return;
    }
    setCreatingQuery(true);
    try {
      const created = await createProjectQuery(selectedProject.id, {
        title: makeQueryTitle(query, `Investigation ${projectQueries.length + 1}`),
        query,
        state: {},
      });
      setProjectQueries((current) => [created, ...current]);
      setActiveQueryId(created.id);
      restoreQueryState(created);
      setNewQueryText('');
      setShowNewQueryForm(false);
      setStatus({ type: 'success', message: 'Created a new query. Choose or create a collaborator next.' });
    } catch (error) {
      setStatus({ type: 'error', message: error instanceof Error ? error.message : 'Failed to create query' });
    } finally {
      setCreatingQuery(false);
    }
  };

  const handleSelectProjectQuery = (queryId: number) => {
    const next = projectQueries.find((item) => item.id === queryId);
    if (!next) return;
    setActiveQueryId(next.id);
    restoreQueryState(next);
    setStatus({ type: 'info', message: 'Switched query. Collaborator, objective, and evidence workspace are ready for this investigation.' });
  };

  const handleManualCollaboratorChange = (field: keyof ManualCollaboratorForm, value: string) => {
    setManualCollaborator((current) => ({ ...current, [field]: value }));
  };

  const splitManualLines = (value: string) =>
    value
      .split('\n')
      .map((item) => item.trim())
      .filter(Boolean);

  const handleCreateManualCollaborator = async () => {
    if (!selectedProject) {
      setStatus({ type: 'error', message: 'Open a project before creating a collaborator.' });
      return;
    }
    if (!manualCollaborator.name.trim()) {
      setStatus({ type: 'error', message: 'Name the collaborator before creating it.' });
      return;
    }

    setCreatingManualCollaborator(true);
    setStatus({ type: 'info', message: 'Creating manual project collaborator...' });
    try {
      const response = await createProjectCollaborator(selectedProject.id, {
        name: manualCollaborator.name,
        role: manualCollaborator.role || 'workflow_partner',
        workflow_stage: manualCollaborator.workflow_stage,
        focus_area: manualCollaborator.focus_area,
        workflow_focus: splitManualLines(manualCollaborator.workflow_focus),
        goals: splitManualLines(manualCollaborator.goals),
        starter_questions: splitManualLines(manualCollaborator.starter_questions),
      });
      setProjects((current) => current.map((project) => (project.id === response.project.id ? response.project : project)));
      setSelectedPersonaId(response.persona.persona_id);
      setManualCollaborator(emptyManualCollaborator);
      setShowManualCollaboratorForm(false);
      setActiveFlowStep('objective');
      scrollToSection(objectiveSectionRef);
      setStatus({ type: 'success', message: `Created and selected ${response.persona.name}.` });
    } catch (error) {
      setStatus({ type: 'error', message: error instanceof Error ? error.message : 'Failed to create collaborator' });
    } finally {
      setCreatingManualCollaborator(false);
    }
  };

  const handleManualObjectiveChange = (field: keyof ManualObjectiveForm, value: string) => {
    setManualObjective((current) => ({ ...current, [field]: value }));
  };

  const handleCreateManualObjective = () => {
    if (!manualObjective.title.trim() || !manualObjective.definition.trim()) {
      setStatus({ type: 'error', message: 'Add at least a title and definition for the objective.' });
      return;
    }
    const next: ObjectiveCluster = {
      id: `manual_${manualObjective.title.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 48) || Date.now()}`,
      title: manualObjective.title.trim(),
      subtitle: manualObjective.subtitle.trim() || 'User-defined objective mode',
      definition: manualObjective.definition.trim(),
      signals: splitManualLines(manualObjective.signals),
      facet_questions: splitManualLines(manualObjective.facet_questions),
      exemplar_answer: manualObjective.exemplar_answer.trim() || 'Use this objective lens to structure the next workspace output.',
    };
    setObjectiveClusters((current) => [next, ...current.filter((item) => item.id !== next.id)]);
    setSelectedObjectiveId(next.id);
    setObjectivePickerCollapsed(true);
    setShowManualObjectiveForm(false);
    setManualObjective(emptyManualObjective);
    setActiveFlowStep('workspace');
    scrollToSection(draftSectionRef);
    setStatus({ type: 'success', message: `Created and selected objective mode: ${next.title}.` });
  };

  const handleDeleteProject = async (project: Project) => {
    const confirmed = window.confirm(`Delete "${project.name}" and its saved project workspace?`);
    if (!confirmed) {
      return;
    }

    setDeletingProjectId(project.id);
    setStatus({ type: 'info', message: `Deleting ${project.name}...` });
    try {
      await deleteProject(project.id);
      if (selectedProjectId === project.id) {
        router.push('/');
        setSelectedProjectId('');
        setSelectedPersonaId('');
      }
      await loadProjects();
      setStatus({ type: 'success', message: `Deleted ${project.name}.` });
    } catch (error) {
      setStatus({ type: 'error', message: error instanceof Error ? error.message : 'Failed to delete project' });
    } finally {
      setDeletingProjectId(null);
    }
  };

  const handleReturnToLanding = () => {
    router.push('/');
  };

  const handleClusterObjectives = async () => {
    const queryText = focusQuestion.trim() || selectedProject?.project_goal?.trim() || '';
    if (!queryText) {
      setStatus({ type: 'error', message: 'Add a working question before clustering objective angles.' });
      return;
    }
    if (!selectedPersona) {
      setStatus({ type: 'error', message: 'Choose or create a collaborator before generating objective modes.' });
      setActiveFlowStep('collaborator');
      return;
    }

    setLoadingObjectiveClusters(true);
    setStatus({ type: 'info', message: 'Clustering objective angles for this project question...' });
    try {
      const response = await clusterObjectives({
        query: queryText,
        context: [
          selectedProject?.project_goal ? `Project goal: ${selectedProject.project_goal}` : '',
          selectedProject?.end_product ? `End product: ${selectedProject.end_product}` : '',
          selectedProject?.target_host ? `Target host: ${selectedProject.target_host}` : '',
          selectedProject?.raw_material_focus ? `Cost or sourcing context: ${selectedProject.raw_material_focus}` : '',
          selectedProject?.notes ? `Project context: ${selectedProject.notes}` : '',
        ]
          .filter(Boolean)
          .join('\n'),
        k: 4,
        persona_id: selectedPersona?.persona_id,
      });
      setObjectiveClusters(response.objectives || []);
      setGlobalQuestions(response.global_questions || []);
      setSelectedObjectiveId('');
      setObjectiveAnswers({});
      setGlobalQuestionAnswers({});
      setObjectivePickerCollapsed(false);
      setActiveFlowStep('objective');
      scrollToSection(objectiveSectionRef);
      setStatus({
        type: 'success',
        message: response.objectives?.length
          ? 'Objective clusters generated. Pick the mode that should govern the next workspace.'
          : 'No objective clusters were returned.',
      });
    } catch (error) {
      setStatus({ type: 'error', message: error instanceof Error ? error.message : 'Failed to cluster objectives' });
    } finally {
      setLoadingObjectiveClusters(false);
    }
  };

  const handleSelectPersona = (personaId: number) => {
    setSelectedPersonaId(personaId);
    setCollaboratorPickerCollapsed(true);
    setActiveFlowStep('objective');
    scrollToSection(objectiveSectionRef);
  };

  const handleSelectObjective = (objectiveId: string) => {
    setSelectedObjectiveId(objectiveId);
    setObjectivePickerCollapsed(true);
    setActiveFlowStep('workspace');
    scrollToSection(draftSectionRef);
  };

  const handleRefineQuery = () => {
    setShowNewQueryForm(true);
    setStatus({ type: 'info', message: 'Use the project query panel to create or switch investigation queries.' });
  };

  const handleChooseAnotherCollaborator = () => {
    setActiveFlowStep('collaborator');
    setCollaboratorPickerCollapsed(false);
    setObjectivePickerCollapsed(false);
    scrollToSection(querySectionRef);
  };

  const handleChooseAnotherObjective = () => {
    setActiveFlowStep('objective');
    setObjectivePickerCollapsed(false);
    scrollToSection(objectiveSectionRef);
  };

  const handleOpenDraftWorkspace = () => {
    setActiveFlowStep(selectedObjective ? 'workspace' : 'objective');
    scrollToSection(selectedObjective ? draftSectionRef : objectiveSectionRef);
  };

  const handleGeneratePlan = async () => {
    if (!selectedProject || !selectedPersona || selectedPersonaId === '') {
      setStatus({ type: 'error', message: 'Select a project persona before generating a plan.' });
      return;
    }
    if (!selectedObjective) {
      setStatus({ type: 'error', message: 'Select an objective mode before generating a draft.' });
      return;
    }

    setLoadingPlan(true);
    setStatus({ type: 'info', message: `Generating a ${selectedObjective.title.toLowerCase()} draft with ${selectedPersona.name}...` });
    try {
      const effectiveReasoningNotes = buildPlanningReasoningNotes({
        reasoningNotes,
        selectedObjective,
        objectiveAnswers,
        globalQuestions,
        globalQuestionAnswers,
      });
      const response = await generateProjectPlan(selectedProject.id, {
        persona_id: Number(selectedPersonaId),
        focus_question: focusQuestion,
        notes: selectedProject.notes || undefined,
        clarifying_answers: clarifyingAnswers,
        reasoning_notes: effectiveReasoningNotes || reasoningNotes,
        work_template: researchWorkTemplate,
      });
      setAgenticPlan(response.plan);
      setSelectedPlanStepId(response.plan.steps[0]?.id || '');
      setWorkspaceSaveState('saved');
      setActiveFlowStep('workspace');
      scrollToSection(draftSectionRef);
      setStatus({ type: 'success', message: `${activeObjectiveFrame?.draftLabel || 'Working Draft'} generated and workspace saved.` });
    } catch (error) {
      setStatus({ type: 'error', message: error instanceof Error ? error.message : 'Failed to generate project draft' });
    } finally {
      setLoadingPlan(false);
    }
  };

  const handleFetchLiterature = async () => {
    if (!selectedProject || !selectedPersona || selectedPersonaId === '') {
      setStatus({ type: 'error', message: 'Select a project persona before fetching literature.' });
      return;
    }
    const queryText = researchWorkTemplate.initial_query.trim() || focusQuestion.trim() || selectedProject.project_goal.trim();
    if (!queryText) {
      setStatus({ type: 'error', message: 'Add an initial query or working question before fetching literature.' });
      return;
    }

    setFetchingLiterature(true);
    setLiteratureToolStatus('Calling multi-source literature search...');
    setStatus({ type: 'info', message: 'Fetching literature with PubMed, Semantic Scholar, OpenAlex, and Crossref...' });
    try {
      const response = await fetchProjectLiterature(selectedProject.id, {
        persona_id: Number(selectedPersonaId),
        query: queryText,
        objective_id: selectedObjective?.id,
        objective_title: selectedObjective?.title,
        objective_definition: selectedObjective?.definition,
        objective_signals: selectedObjective?.signals,
        project_goal: selectedProject.project_goal,
        project_end_product: selectedProject.end_product,
        project_target_host: selectedProject.target_host,
        clarifying_answers: clarifyingAnswers,
        objective_answers: objectiveAnswers,
        global_question_answers: globalQuestionAnswers,
        reasoning_notes: reasoningNotes,
        work_template: researchWorkTemplate,
        max_results: 5,
        existing_citations: researchWorkTemplate.literature_findings.map((item) => item.citation).filter(Boolean),
      });
      const existing = new Set(researchWorkTemplate.literature_findings.map((item) => item.citation.trim().toLowerCase()).filter(Boolean));
      const existingIds = new Set(researchWorkTemplate.literature_findings.map((item) => item.id));
      const newFindings = (response.findings || [])
        .filter((item) => !existing.has(item.citation.trim().toLowerCase()))
        .map((item, index) => ({ ...item, id: uniqueFindingId(item, existingIds, index) }));
      setResearchWorkTemplate((current) => ({
        ...current,
        initial_query: current.initial_query.trim() || queryText,
        literature_findings: [...current.literature_findings, ...newFindings],
      }));
      setLiteratureObjectiveLens(response.objective_lens || selectedObjective?.title || null);
      setLiteratureProcessingSummary(response.processing_summary || null);
      setLiteratureElicitationQuestions(response.elicitation_questions || []);
      setLiteratureElicitationAnswers({});
      const trace = response.tool_trace;
      const traceMessage = `${trace.tool_name} returned ${trace.result_count} result${trace.result_count === 1 ? '' : 's'} for "${trace.query}". Added ${newFindings.length}.`;
      setLiteratureToolStatus(traceMessage);
      setStatus({ type: 'success', message: traceMessage });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to fetch literature';
      setLiteratureToolStatus(message);
      setStatus({ type: 'error', message });
    } finally {
      setFetchingLiterature(false);
    }
  };

  const handlePreparePaperPdf = async (finding: ResearchFinding) => {
    if (!selectedProject || !selectedPersona || selectedPersonaId === '') {
      setStatus({ type: 'error', message: 'Select a project persona before preparing an annotated PDF.' });
      return;
    }
    const queryText = researchWorkTemplate.initial_query.trim() || focusQuestion.trim() || selectedProject.project_goal.trim();
    if (!queryText) {
      setStatus({ type: 'error', message: 'Add an initial query or working question before annotating a PDF.' });
      return;
    }

    setPreparingPdfFindingId(finding.id);
    setPdfAnnotationStatus('Finding an open-access PDF, downloading it, and matching passages to the selected objective...');
    setStatus({ type: 'info', message: 'Preparing an annotated PDF for this finding...' });
    try {
      const response = await preparePaperPdf(selectedProject.id, {
        persona_id: Number(selectedPersonaId),
        finding,
        query: queryText,
        project_goal: selectedProject.project_goal,
        project_end_product: selectedProject.end_product,
        project_target_host: selectedProject.target_host,
        persona_name: selectedPersona.name,
        persona_focus: selectedPersona.focus_area,
        objective_id: selectedObjective?.id,
        objective_title: selectedObjective?.title,
        objective_definition: selectedObjective?.definition,
        objective_signals: selectedObjective?.signals,
        max_annotations: 8,
      });

      if (response.status !== 'success') {
        const message = response.message || 'No downloadable open-access PDF was found for this paper.';
        setPdfAnnotationStatus(message);
        setStatus({ type: response.status === 'not_open_access' ? 'info' : 'error', message });
        return;
      }

      const insightBlock = response.insights.length
        ? `PDF annotation notes:\n${response.insights.map((insight) => `- ${insight}`).join('\n')}`
        : 'PDF annotation notes: the PDF opened, but no high-scoring query/objective passages were detected.';
      setResearchWorkTemplate((current) => ({
        ...current,
        literature_findings: current.literature_findings.map((item) =>
          item.id === finding.id
            ? {
                ...item,
                labels: item.labels.includes('pdf annotated') ? item.labels : [...item.labels, 'pdf annotated'],
                relevance: [item.relevance, insightBlock].filter(Boolean).join('\n\n'),
              }
            : item
        ),
      }));

      if (response.annotated_pdf_url) {
        setPdfViewer({
          findingId: finding.id,
          title: finding.citation || response.paper_id || 'Annotated literature PDF',
          url: `${API_BASE}${response.annotated_pdf_url}`,
          annotatedPath: response.annotated_pdf_path,
          insights: response.insights,
          questions: literatureElicitationQuestions,
        });
      }

      const message = `${response.message} ${response.visual_annotations ? 'Opened in the in-app PDF reader.' : 'PDF reader opened, but visual highlights were unavailable.'}`;
      setPdfAnnotationStatus(message);
      setStatus({ type: 'success', message });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to prepare annotated PDF';
      setPdfAnnotationStatus(message);
      setStatus({ type: 'error', message });
    } finally {
      setPreparingPdfFindingId(null);
    }
  };

  const handleLiteratureElicitationAnswerChange = (question: string, value: string) => {
    setLiteratureElicitationAnswers((current) => ({
      ...current,
      [question]: value,
    }));
  };

  const handleCaptureLiteratureTacitAnswer = (question: string) => {
    const answer = (literatureElicitationAnswers[question] || '').trim();
    if (!answer) {
      return;
    }

    const stableId = `tacit_${question.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 48)}`;
    const nextJudgment: JudgmentCall = {
      id: stableId,
      stance: answer,
      rationale: `Response to literature-processing prompt: ${question}`,
      implication: 'Use this tacit judgment when prioritizing gaps, boundary conditions, and experiment-plan proposals.',
    };
    setResearchWorkTemplate((current) => {
      const existing = current.judgment_calls.some((item) => item.id === stableId);
      return {
        ...current,
        judgment_calls: existing
          ? current.judgment_calls.map((item) => (item.id === stableId ? nextJudgment : item))
          : [...current.judgment_calls, nextJudgment],
      };
    });
    setStatus({ type: 'success', message: 'Captured your literature judgment in the work template.' });
  };

  const handleCapturePaperTacitAnswer = (question: string, paperTitle: string) => {
    const scopedQuestion = `${paperTitle} :: ${question}`;
    const answer = (literatureElicitationAnswers[scopedQuestion] || '').trim();
    if (!answer) return;
    const stableId = `paper_tacit_${scopedQuestion.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 56)}`;
    const nextJudgment: JudgmentCall = {
      id: stableId,
      stance: answer,
      rationale: `Paper-level response for "${paperTitle}": ${question}`,
      implication: 'Use this paper-specific judgment when deciding transferability, boundary conditions, and proposal priority.',
    };
    setResearchWorkTemplate((current) => ({
      ...current,
      literature_findings: current.literature_findings.map((finding) => {
        if (pdfViewer?.findingId && finding.id !== pdfViewer.findingId) {
          return finding;
        }
        const judgments = finding.judgment_calls || [];
        return {
          ...finding,
          judgment_calls: judgments.some((item) => item.id === stableId)
            ? judgments.map((item) => (item.id === stableId ? nextJudgment : item))
            : [...judgments, nextJudgment],
        };
      }),
    }));
    setStatus({ type: 'success', message: 'Captured the paper-specific judgment in the work template.' });
  };

  const updatePdfViewerFinding = (patch: Partial<ResearchFinding>) => {
    if (!pdfViewer) {
      return;
    }
    setResearchWorkTemplate((current) => ({
      ...current,
      literature_findings: current.literature_findings.map((finding) =>
        finding.id === pdfViewer.findingId ? { ...finding, ...patch } : finding
      ),
    }));
  };

  const updateTacitItem = (id: string, patch: Partial<TacitMemoryItem>) => {
    setTacitState((current) => current.map((item) => (item.id === id ? { ...item, ...patch } : item)));
  };

  const handleInferWorkspaceMemory = async () => {
    if (!selectedProject || selectedPersonaId === '') {
      setStatus({ type: 'error', message: 'Open a project and collaborator before inferring workspace memory.' });
      return;
    }
    setInferringMemory(true);
    setStatus({ type: 'info', message: 'Inferring reviewable tacit workspace memory...' });
    try {
      const response = await inferWorkspaceMemory({
        workspace_key: workspaceMemoryKey,
        scope: selectedProject.scope_id || `project-${selectedProject.id}`,
        explicit_state: explicitWorkspaceState,
        existing_tacit_state: tacitState,
      });
      setTacitState(response.tacit_state || []);
      setHandoffSummary(response.handoff_summary || '');
      setMemoryStatus('tacit state inferred; saving...');
      setStatus({ type: 'success', message: 'Tacit memory inferred. Review, confirm, edit, or reject each item.' });
    } catch (error) {
      setStatus({ type: 'error', message: error instanceof Error ? error.message : 'Failed to infer workspace memory' });
    } finally {
      setInferringMemory(false);
    }
  };

  const handleRefreshExecution = async () => {
    if (!selectedProject || !selectedPersona || selectedPersonaId === '') {
      return;
    }
    try {
      const response = executionRun
        ? await fetchExecutionRun(selectedProject.id, executionRun.id)
        : await fetchLatestExecutionRun(selectedProject.id, Number(selectedPersonaId));
      setExecutionRun(response.run || null);
      setExecutionEvents(response.events || []);
      if (response.run?.final_work_template) {
        setResearchWorkTemplate(response.run.final_work_template);
      }
      if (response.run?.final_plan) {
        setAgenticPlan(response.run.final_plan);
        setSelectedPlanStepId(response.run.final_plan.steps[0]?.id || '');
      }
    } catch (error) {
      setStatus({ type: 'error', message: error instanceof Error ? error.message : 'Failed to refresh execution run' });
    }
  };

  const handleStartExecution = async () => {
    if (!selectedProject || !selectedPersona || selectedPersonaId === '') {
      setStatus({ type: 'error', message: 'Select a project persona before starting execution.' });
      return;
    }
    if (!selectedObjective) {
      setStatus({ type: 'error', message: 'Select an objective mode before starting execution.' });
      return;
    }

    setStartingExecution(true);
    setStatus({ type: 'info', message: `Starting agentic execution for ${selectedObjective.title.toLowerCase()}...` });
    try {
      const effectiveReasoningNotes = buildPlanningReasoningNotes({
        reasoningNotes,
        selectedObjective,
        objectiveAnswers,
        globalQuestions,
        globalQuestionAnswers,
      });
      const response = await startExecutionRun(selectedProject.id, {
        persona_id: Number(selectedPersonaId),
        focus_question: focusQuestion,
        notes: selectedProject.notes || undefined,
        clarifying_answers: clarifyingAnswers,
        reasoning_notes: effectiveReasoningNotes || reasoningNotes,
        work_template: researchWorkTemplate,
        objective_id: selectedObjective.id,
        objective_title: selectedObjective.title,
        objective_definition: selectedObjective.definition,
        objective_signals: selectedObjective.signals,
      });
      setExecutionRun(response.run || null);
      setExecutionEvents(response.events || []);
      scrollToSection(draftSectionRef);
      setStatus({ type: 'success', message: 'Agentic execution started. The workspace will update as the run completes.' });
    } catch (error) {
      setStatus({ type: 'error', message: error instanceof Error ? error.message : 'Failed to start execution run' });
    } finally {
      setStartingExecution(false);
    }
  };

  const updatePlanStep = (stepId: string, patch: Partial<PlanStep>) => {
    setAgenticPlan((current) => {
      if (!current) return current;
      return {
        ...current,
        steps: current.steps.map((step) => (step.id === stepId ? { ...step, ...patch } : step)),
      };
    });
  };

  const handleFormChange = (field: keyof ProjectFormState, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const handleCopyWorkspaceDigest = async () => {
    try {
      await navigator.clipboard.writeText(workspaceDigest);
      setStatus({ type: 'success', message: 'Copied workspace digest to clipboard.' });
    } catch {
      setStatus({ type: 'error', message: 'Could not copy the workspace digest. Select the text manually instead.' });
    }
  };

  const handleOpenPdfInSystemViewer = async () => {
    if (!pdfViewer?.annotatedPath || !window.desktopApp?.openPath) {
      setStatus({ type: 'info', message: 'System PDF viewer is only available in the desktop app after annotation creates a local file.' });
      return;
    }
    const opened = await window.desktopApp.openPath(pdfViewer.annotatedPath);
    setStatus({
      type: opened.ok ? 'success' : 'error',
      message: opened.ok ? 'Opened annotated PDF in the system viewer.' : opened.error || 'Could not open the system PDF viewer.',
    });
  };

  return (
    <div className={classNames('relative min-h-screen overflow-hidden p-0 text-slate-950 transition-colors duration-700', modePageTone[modeVisualKey] || modePageTone.general)}>
      <ModeBackdrop modeKey={modeVisualKey} />
      <div className="relative z-10 flex min-h-screen w-full flex-col gap-3 p-3">
        <WorkspaceHeader
          selectedProject={Boolean(selectedProject)}
          onReturnToLanding={handleReturnToLanding}
          onOpenMemory={selectedProject ? () => setMemoryDrawerOpen(true) : undefined}
          memoryItemCount={tacitState.length}
          status={status}
        />

        {!selectedProject ? (
          <ProjectLandingShell
            form={form}
            onFormChange={handleFormChange}
            onCreateProject={handleCreateProject}
            creatingProject={creatingProject}
            loadingProjects={loadingProjects}
            projects={projects}
            selectedProjectId={selectedProjectId}
            onOpenProject={handleOpenProject}
            onDeleteProject={handleDeleteProject}
            deletingProjectId={deletingProjectId}
            onRefreshProjects={() => {
              loadProjects().catch(() => {});
            }}
          />
        ) : (
          <main className="grid min-h-0 flex-1 items-start gap-3 xl:grid-cols-[320px_minmax(0,1fr)]">
            <WorkflowStateSidebar
              selectedProject={selectedProject}
              focusQuestion={focusQuestion}
              selectedPersona={selectedPersona}
              selectedObjective={selectedObjective}
              agenticPlan={agenticPlan}
              workspaceStatusMessage={workspaceStatusMessage}
              onEditQuestion={handleRefineQuery}
              onChangeCollaborator={handleChooseAnotherCollaborator}
              onChangeObjective={handleChooseAnotherObjective}
              onOpenDraft={handleOpenDraftWorkspace}
            />

            <div className="min-w-0 space-y-5">
              <ProjectOverview selectedProject={selectedProject} />

              <section className="rounded-[1.75rem] border border-slate-200 bg-white/90 p-4 shadow-sm backdrop-blur">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">Project Queries</div>
                    <div className="mt-1 text-lg font-semibold text-slate-950">Investigations under the same project goal</div>
                    <div className="mt-1 text-sm leading-6 text-slate-600">
                      The project goal and end product stay fixed. Each query can have its own collaborator, objective mode, literature, and notes.
                    </div>
                  </div>
                  <button
                    onClick={() => setShowNewQueryForm((current) => !current)}
                    className="rounded-2xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800"
                  >
                    {showNewQueryForm ? 'Hide query form' : 'New query'}
                  </button>
                </div>
                {(showNewQueryForm || projectQueries.length === 0) && (
                  <div className="mt-4 rounded-[1.4rem] border border-slate-200 bg-slate-50 p-4">
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Query under this project goal</div>
                    <div className="mt-1 text-sm leading-6 text-slate-600">
                      Write the investigation question. Collaborators and objective modes are chosen after this, so the project goal stays stable while the query changes.
                    </div>
                    <textarea
                      value={newQueryText}
                      onChange={(event) => setNewQueryText(event.target.value)}
                      rows={4}
                      className="mt-3 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900"
                      placeholder="Example: What are the key successful common strategies and examples in microbial flavonoid production? What are the latest improvement options / key challenges?"
                    />
                    <div className="mt-3 flex justify-end">
                      <button
                        onClick={handleCreateProjectQuery}
                        disabled={!newQueryText.trim() || creatingQuery}
                        className="rounded-2xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {creatingQuery ? 'Creating...' : 'Create query and continue'}
                      </button>
                    </div>
                  </div>
                )}
                <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
                  {projectQueries.map((query, index) => {
                    const active = query.id === activeQueryId;
                    return (
                      <button
                        key={query.id}
                        onClick={() => handleSelectProjectQuery(query.id)}
                        className={classNames(
                          'min-w-[220px] rounded-2xl border px-3 py-2 text-left transition',
                          active ? 'border-slate-950 bg-slate-950 text-white' : 'border-slate-200 bg-slate-50 text-slate-800 hover:bg-white'
                        )}
                      >
                        <div className={classNames('text-[10px] font-semibold uppercase tracking-wide', active ? 'text-slate-300' : 'text-slate-500')}>
                          Query {index + 1}
                        </div>
                        <div className="mt-1 line-clamp-2 text-sm font-semibold">{query.title || 'Untitled query'}</div>
                        <div className={classNames('mt-1 text-[11px]', active ? 'text-slate-300' : 'text-slate-500')}>
                          {new Date(query.updated_at).toLocaleString()}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </section>

              {activeQueryId !== '' && (activeFlowStep === 'collaborator' || activeFlowStep === 'query') && (
                <div ref={querySectionRef} className="scroll-mt-28">
                  <QueryAlignmentSection
                    activeStep={activeFlowStep === 'collaborator' ? 'collaborator' : 'query'}
                    focusQuestion={focusQuestion}
                    onFocusQuestionChange={setFocusQuestion}
                    rankedPersonas={rankedPersonas}
                    selectedPersonaId={selectedPersonaId}
                    onSelectPersona={handleSelectPersona}
                    selectedPersona={selectedPersona}
                    topRecommendedPersona={topRecommendedPersona}
                    clarifyingAnswers={clarifyingAnswers}
                    onClarifyingAnswerChange={(question, value) =>
                      setClarifyingAnswers((current) => ({
                        ...current,
                        [question]: value,
                      }))
                    }
                    onSubmitQuery={handleClusterObjectives}
                    submittingQuery={loadingObjectiveClusters}
                    manualCollaborator={manualCollaborator}
                    showManualCollaboratorForm={showManualCollaboratorForm}
                    onToggleManualCollaboratorForm={() => setShowManualCollaboratorForm((current) => !current)}
                    creatingManualCollaborator={creatingManualCollaborator}
                    onManualCollaboratorChange={handleManualCollaboratorChange}
                    onCreateManualCollaborator={handleCreateManualCollaborator}
                  />
                </div>
              )}

              {activeQueryId !== '' && (activeFlowStep === 'objective' || activeFlowStep === 'workspace') && (
                <section
                  ref={objectiveSectionRef}
                  className={classNames(
                    'scroll-mt-28 rounded-[2rem] border p-5 shadow-[0_40px_120px_-60px_rgba(15,23,42,0.36)] backdrop-blur-md transition-all duration-700',
                    modeStudioTone[modeVisualKey] || modeStudioTone.general
                  )}
                >
                  {activeFlowStep === 'objective' && (
                  <ObjectiveClusteringSection
                    objectiveClusters={objectiveClusters}
                    selectedObjective={selectedObjective}
                    selectedObjectiveId={selectedObjectiveId}
                    objectivePickerCollapsed={objectivePickerCollapsed}
                    onSelectObjective={handleSelectObjective}
                    onGenerateModes={handleClusterObjectives}
                    loadingObjectiveClusters={loadingObjectiveClusters}
                    canGenerateModes={Boolean(selectedPersona && workingQuestionText)}
                    objectiveAnswers={objectiveAnswers}
                    onObjectiveAnswerChange={(question, value) =>
                      setObjectiveAnswers((current) => ({
                        ...current,
                        [question]: value,
                      }))
                    }
                    globalQuestions={globalQuestions}
                    globalQuestionAnswers={globalQuestionAnswers}
                    onGlobalQuestionChange={(question, value) =>
                      setGlobalQuestionAnswers((current) => ({
                        ...current,
                        [question]: value,
                      }))
                    }
                    onSetObjectivePickerCollapsed={setObjectivePickerCollapsed}
                    showManualObjectiveForm={showManualObjectiveForm}
                    manualObjective={manualObjective}
                    onToggleManualObjectiveForm={() => setShowManualObjectiveForm((current) => !current)}
                    onManualObjectiveChange={handleManualObjectiveChange}
                    onCreateManualObjective={handleCreateManualObjective}
                  />
                  )}

                  {activeFlowStep === 'workspace' && (
                <div ref={draftSectionRef} className="scroll-mt-28">
                  <WorkingDraftSection
                    selectedObjective={selectedObjective}
                    currentModeTitle={currentModeTitle}
                    currentModeDescription={currentModeDescription}
                    onChooseAnotherObjective={handleChooseAnotherObjective}
                    researchWorkTemplate={researchWorkTemplate}
                    onResearchWorkTemplateChange={setResearchWorkTemplate}
                    onFetchLiterature={handleFetchLiterature}
                    fetchingLiterature={fetchingLiterature}
                    literatureToolStatus={literatureToolStatus}
                    literatureObjectiveLens={literatureObjectiveLens}
                    literatureProcessingSummary={literatureProcessingSummary}
                    literatureElicitationQuestions={literatureElicitationQuestions}
                    onPreparePaperPdf={handlePreparePaperPdf}
                    preparingPdfFindingId={preparingPdfFindingId}
                    pdfAnnotationStatus={pdfAnnotationStatus}
                    agenticPlan={agenticPlan}
                    selectedPlanStepId={selectedPlanStepId}
                    onSelectPlanStep={setSelectedPlanStepId}
                    onUpdatePlanStep={updatePlanStep}
                    onGeneratePlan={handleGeneratePlan}
                    loadingPlan={loadingPlan}
                  />
                </div>
                  )}
                </section>
              )}
            </div>
          </main>
        )}
      </div>

      {pdfViewer && (
        <div className="fixed inset-0 z-50 bg-slate-950">
          <div className="flex h-full w-full flex-col overflow-hidden bg-white">
            <div className="flex flex-col gap-3 border-b border-slate-200 bg-slate-50 px-5 py-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">Annotated PDF Reader</div>
                <div className="mt-1 line-clamp-2 text-sm font-semibold text-slate-950">{pdfViewer.title}</div>
                <div className="mt-1 text-xs text-slate-600">
                  Read the paper in context and use the right-side notebook to edit extracted fields, judgment calls, and transfer notes for this source.
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={handleOpenPdfInSystemViewer}
                  className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-900 hover:bg-slate-50"
                >
                  Open system viewer
                </button>
                <a
                  href={pdfViewer.url}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-900 hover:bg-slate-50"
                >
                  New tab
                </a>
                <button
                  onClick={() => setPdfViewer(null)}
                  className="rounded-2xl bg-slate-950 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-800"
                >
                  Close
                </button>
              </div>
            </div>

            <div className="grid min-h-0 flex-1 gap-0 lg:grid-cols-[minmax(0,1fr)_460px]">
              <iframe title="Annotated PDF" src={pdfViewer.url} className="h-full min-h-0 w-full bg-slate-950" />
              <aside className="overflow-y-auto border-t border-slate-200 bg-white p-5 lg:border-l lg:border-t-0">
                <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Extracted Notes</div>
                {pdfViewer.insights.length === 0 ? (
                  <div className="mt-3 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-3 text-sm leading-6 text-slate-600">
                    No high-scoring passages were detected. The PDF is still available for manual review.
                  </div>
                ) : (
                  <div className="mt-3 space-y-2">
                    {pdfViewer.insights.map((insight, index) => (
                      <div key={`${insight}-${index}`} className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-sm leading-6 text-slate-700">
                        {insight}
                      </div>
                    ))}
                  </div>
                )}

                {pdfViewerFinding && (
                  <div className="mt-5 border-t border-slate-200 pt-4">
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Extracted Fields</div>
                    <div className="mt-1 text-xs leading-5 text-slate-600">
                      These fields write back to the active literature finding, so the paper review and work template stay synced.
                    </div>

                    <label className="mt-3 block">
                      <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Citation</div>
                      <textarea
                        value={pdfViewerFinding.citation}
                        onChange={(event) => updatePdfViewerFinding({ citation: event.target.value })}
                        rows={3}
                        className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                      />
                    </label>

                    <label className="mt-3 block">
                      <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Knowns</div>
                      <textarea
                        value={pdfViewerFinding.knowns.join('\n')}
                        onChange={(event) =>
                          updatePdfViewerFinding({
                            knowns: event.target.value
                              .split('\n')
                              .map((item) => item.trim())
                              .filter(Boolean),
                          })
                        }
                        rows={5}
                        className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                        placeholder="One known per line"
                      />
                    </label>

                    <label className="mt-3 block">
                      <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Unknowns / Transfer Questions</div>
                      <textarea
                        value={pdfViewerFinding.unknowns.join('\n')}
                        onChange={(event) =>
                          updatePdfViewerFinding({
                            unknowns: event.target.value
                              .split('\n')
                              .map((item) => item.trim())
                              .filter(Boolean),
                          })
                        }
                        rows={5}
                        className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                        placeholder="One gap or transfer question per line"
                      />
                    </label>

                    <label className="mt-3 block">
                      <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Relevance</div>
                      <textarea
                        value={pdfViewerFinding.relevance}
                        onChange={(event) => updatePdfViewerFinding({ relevance: event.target.value })}
                        rows={4}
                        className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                        placeholder="What transfers into this project?"
                      />
                    </label>

                    <label className="mt-3 block">
                      <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Paper Memo</div>
                      <textarea
                        value={pdfViewerFinding.synthesis_memo || ''}
                        onChange={(event) => updatePdfViewerFinding({ synthesis_memo: event.target.value })}
                        rows={5}
                        className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                        placeholder="Your reading notes, caveats, and next actions for this paper..."
                      />
                    </label>
                  </div>
                )}

                {pdfViewer.questions.length > 0 && (
                  <div className="mt-5 border-t border-slate-200 pt-4">
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Paper-Level Judgment</div>
                    <div className="mt-1 text-xs leading-5 text-slate-600">
                      Answer these after reviewing this specific paper. The response is stored as a judgment tied to this source.
                    </div>
                    <div className="mt-3 space-y-3">
                      {pdfViewer.questions.map((question) => {
                        const scopedQuestion = `${pdfViewer.title} :: ${question}`;
                        const answer = literatureElicitationAnswers[scopedQuestion] || '';
                        return (
                          <div key={question} className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                            <div className="text-sm leading-6 text-slate-800">{question}</div>
                            <textarea
                              value={answer}
                              onChange={(event) =>
                                setLiteratureElicitationAnswers((current) => ({
                                  ...current,
                                  [scopedQuestion]: event.target.value,
                                }))
                              }
                              rows={3}
                              className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                              placeholder="Transferability, feasibility, boundary condition, or priority judgment for this paper..."
                            />
                            <button
                              onClick={() => handleCapturePaperTacitAnswer(question, pdfViewer.title)}
                              disabled={!answer.trim()}
                              className="mt-2 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-900 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              Add as paper judgment
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </aside>
            </div>
          </div>
        </div>
      )}

      {memoryDrawerOpen && selectedProject && (
        <div className="fixed inset-0 z-40 bg-slate-950/45 backdrop-blur-sm">
          <button className="absolute inset-0 cursor-default" aria-label="Close workspace memory" onClick={() => setMemoryDrawerOpen(false)} />
          <aside className="absolute right-0 top-0 h-full w-full max-w-3xl overflow-y-auto border-l border-amber-200 bg-white p-5 shadow-2xl">
            <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-amber-800">Project Context</div>
                <div className="mt-1 text-2xl font-semibold tracking-tight text-slate-950">Memory, summary, and export</div>
                <div className="mt-1 text-sm leading-6 text-slate-600">
                  This drawer is the durable state layer: objective mode, collaborator, fetched literature notes, tacit user inputs, and handoff context.
                </div>
              </div>
              <button
                onClick={() => setMemoryDrawerOpen(false)}
                className="rounded-2xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800"
              >
                Close
              </button>
            </div>

            <div className="mb-4 rounded-[1.4rem] border border-slate-200 bg-slate-50 p-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Workspace Digest</div>
                  <div className="mt-1 text-sm leading-6 text-slate-700">
                    Copy this as a handoff/export seed. It combines explicit selections, literature notes, and user-entered judgments.
                  </div>
                </div>
                <button
                  onClick={handleCopyWorkspaceDigest}
                  className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-900 hover:bg-slate-50"
                >
                  Copy digest
                </button>
              </div>
              <textarea
                readOnly
                value={workspaceDigest}
                rows={10}
                className="mt-3 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs leading-5 text-slate-800"
              />
            </div>

            {selectedPersona ? (
              <WorkspaceMemoryPanel
                workspaceKey={workspaceMemoryKey}
                memoryStatus={memoryStatus}
                tacitState={tacitState}
                handoffSummary={handoffSummary}
                inferring={inferringMemory}
                onInfer={handleInferWorkspaceMemory}
                onUpdateTacitItem={updateTacitItem}
              />
            ) : (
              <div className="rounded-2xl border border-dashed border-amber-300 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
                Select a collaborator before inferring tacit memory. The digest above can still be used as an explicit project summary.
              </div>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}
