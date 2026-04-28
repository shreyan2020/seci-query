'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';

import { ModeBackdrop } from '@/features/biotech-workspace/components/ModeBackdrop';
import { ObjectiveClusteringSection } from '@/features/biotech-workspace/components/ObjectiveClusteringSection';
import { ProjectLandingShell } from '@/features/biotech-workspace/components/ProjectLandingShell';
import { ProjectOverview } from '@/features/biotech-workspace/components/ProjectOverview';
import { QueryAlignmentSection } from '@/features/biotech-workspace/components/QueryAlignmentSection';
import { WorkingDraftSection } from '@/features/biotech-workspace/components/WorkingDraftSection';
import { WorkflowStateSidebar } from '@/features/biotech-workspace/components/WorkflowStateSidebar';
import { WorkspaceHeader } from '@/features/biotech-workspace/components/WorkspaceHeader';
import {
  clusterObjectives,
  createProject,
  deleteProject,
  fetchExecutionRun,
  fetchLatestExecutionRun,
  fetchProjectLiterature,
  fetchProjects,
  fetchWorkspaceState,
  generateProjectPlan,
  saveWorkspaceState,
  startExecutionRun,
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
  ResearchWorkTemplate,
  StatusState,
} from '@/features/biotech-workspace/types';

type FlowStep = 'collaborator' | 'query' | 'objective' | 'workspace';

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
  const [loadingWorkspace, setLoadingWorkspace] = useState(false);
  const [collaboratorPickerCollapsed, setCollaboratorPickerCollapsed] = useState(false);
  const [objectivePickerCollapsed, setObjectivePickerCollapsed] = useState(false);
  const [workspaceReadyForSave, setWorkspaceReadyForSave] = useState(false);
  const [workspaceSaveState, setWorkspaceSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [workspaceUpdatedAt, setWorkspaceUpdatedAt] = useState<string | null>(null);
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
    setActiveFlowStep(selectedPersonaId === '' ? 'collaborator' : 'query');
  }, [selectedProjectId, selectedPersonaId]);

  useEffect(() => {
    let cancelled = false;

    const loadWorkspace = async () => {
      if (!selectedProject || !selectedPersona || selectedPersonaId === '') {
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
  }, [selectedProject?.id, selectedPersona?.persona_id, selectedPersonaId]);

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
    if (!workspaceReadyForSave || loadingWorkspace || !selectedProject || !selectedPersona || selectedPersonaId === '') {
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
    focusQuestion,
    JSON.stringify(clarifyingAnswers),
    reasoningNotes,
    JSON.stringify(researchWorkTemplate),
    JSON.stringify(agenticPlan),
    selectedPlanStepId,
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
      setActiveFlowStep('collaborator');
      setFocusQuestion(defaultFocusQuestion(response.project, null));
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
    setActiveFlowStep('query');
    scrollToSection(querySectionRef);
  };

  const handleSelectObjective = (objectiveId: string) => {
    setSelectedObjectiveId(objectiveId);
    setObjectivePickerCollapsed(true);
    setActiveFlowStep('workspace');
    scrollToSection(draftSectionRef);
  };

  const handleRefineQuery = () => {
    setActiveFlowStep('query');
    scrollToSection(querySectionRef);
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
    setLiteratureToolStatus('Calling search_pubmed...');
    setStatus({ type: 'info', message: 'Fetching literature with search_pubmed...' });
    try {
      const response = await fetchProjectLiterature(selectedProject.id, {
        persona_id: Number(selectedPersonaId),
        query: queryText,
        objective_id: selectedObjective?.id,
        objective_title: selectedObjective?.title,
        objective_definition: selectedObjective?.definition,
        objective_signals: selectedObjective?.signals,
        max_results: 5,
        existing_citations: researchWorkTemplate.literature_findings.map((item) => item.citation).filter(Boolean),
      });
      const existing = new Set(researchWorkTemplate.literature_findings.map((item) => item.citation.trim().toLowerCase()).filter(Boolean));
      const newFindings = (response.findings || []).filter((item) => !existing.has(item.citation.trim().toLowerCase()));
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

  return (
    <div className={classNames('relative min-h-screen overflow-hidden p-6 text-slate-950 transition-colors duration-700', modePageTone[modeVisualKey] || modePageTone.general)}>
      <ModeBackdrop modeKey={modeVisualKey} />
      <div className="relative z-10 mx-auto max-w-7xl space-y-6">
        <WorkspaceHeader selectedProject={Boolean(selectedProject)} onReturnToLanding={handleReturnToLanding} status={status} />

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
          <main className="grid gap-5 xl:grid-cols-[280px_minmax(0,1fr)]">
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

              {(activeFlowStep === 'collaborator' || activeFlowStep === 'query') && (
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
                  />
                </div>
              )}

              {(activeFlowStep === 'objective' || activeFlowStep === 'workspace') && (
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
                  />
                  )}

                  {activeFlowStep === 'workspace' && (
                <div ref={draftSectionRef} className="scroll-mt-28">
                  <WorkingDraftSection
                    selectedObjective={selectedObjective}
                    currentModeTitle={currentModeTitle}
                    currentModeDescription={currentModeDescription}
                    onChooseAnotherObjective={handleChooseAnotherObjective}
                    focusQuestion={focusQuestion}
                    researchWorkTemplate={researchWorkTemplate}
                    onResearchWorkTemplateChange={setResearchWorkTemplate}
                    onFetchLiterature={handleFetchLiterature}
                    fetchingLiterature={fetchingLiterature}
                    literatureToolStatus={literatureToolStatus}
                    literatureObjectiveLens={literatureObjectiveLens}
                    literatureProcessingSummary={literatureProcessingSummary}
                    literatureElicitationQuestions={literatureElicitationQuestions}
                    literatureElicitationAnswers={literatureElicitationAnswers}
                    onLiteratureElicitationAnswerChange={handleLiteratureElicitationAnswerChange}
                    onCaptureLiteratureTacitAnswer={handleCaptureLiteratureTacitAnswer}
                    reasoningNotes={reasoningNotes}
                    onReasoningNotesChange={setReasoningNotes}
                    agenticPlan={agenticPlan}
                    selectedPlanStepId={selectedPlanStepId}
                    onSelectPlanStep={setSelectedPlanStepId}
                    onUpdatePlanStep={updatePlanStep}
                    onGeneratePlan={handleGeneratePlan}
                    loadingPlan={loadingPlan}
                    executionRun={executionRun}
                    executionEvents={executionEvents}
                    onStartExecution={handleStartExecution}
                    onRefreshExecution={handleRefreshExecution}
                    startingExecution={startingExecution}
                  />
                </div>
                  )}
                </section>
              )}
            </div>
          </main>
        )}
      </div>
    </div>
  );
}
