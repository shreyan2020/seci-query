import type {
  CreateProjectResponse,
  CreateProjectCollaboratorResponse,
  FetchProjectLiteratureResponse,
  GeneratePlanResponse,
  InferWorkspaceMemoryResponse,
  ObjectiveClustersResponse,
  PreparePaperPdfResponse,
  ProjectExecutionRunResponse,
  ProjectFormState,
  ProjectJourneyResponse,
  ProjectQuerySession,
  ProjectQuerySessionListResponse,
  ResearchFinding,
  ResearchWorkTemplate,
  ProjectsResponse,
  TacitMemoryItem,
  ProjectWorkspaceResponse,
  WorkspaceMemoryResponse,
} from '@/features/biotech-workspace/types';

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function fetchProjects(): Promise<ProjectsResponse> {
  const response = await fetch(`${API_BASE}/api/projects`, { cache: 'no-store' });
  if (!response.ok) throw new Error('Failed to load projects');
  return response.json();
}

export async function clusterObjectives(payload: {
  query: string;
  context?: string;
  k?: number;
  persona_id?: number;
}): Promise<ObjectiveClustersResponse> {
  const response = await fetch(`${API_BASE}/objectives`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to cluster objectives');
  }
  return response.json();
}

export async function createProject(payload: ProjectFormState): Promise<CreateProjectResponse> {
  const response = await fetch(`${API_BASE}/api/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to create project');
  }
  return response.json();
}

export async function deleteProject(projectId: number): Promise<{ deleted: boolean; project_id: number }> {
  const response = await fetch(`${API_BASE}/api/projects/${projectId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to delete project');
  }
  return response.json();
}

export async function generateProjectPlan(
  projectId: number,
  payload: {
    persona_id: number;
    focus_question?: string;
    notes?: string;
    clarifying_answers?: Record<string, string>;
    reasoning_notes?: string;
    work_template?: ResearchWorkTemplate | null;
  }
): Promise<GeneratePlanResponse> {
  const response = await fetch(`${API_BASE}/api/projects/${projectId}/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to generate project draft');
  }
  return response.json();
}

export async function fetchWorkspaceState(projectId: number, personaId: number): Promise<ProjectWorkspaceResponse> {
  const response = await fetch(`${API_BASE}/api/projects/${projectId}/workspace/${personaId}`, { cache: 'no-store' });
  if (!response.ok) throw new Error('Failed to load saved workspace');
  return response.json();
}

export async function fetchProjectLiterature(
  projectId: number,
  payload: {
    persona_id: number;
    query: string;
    objective_id?: string;
    objective_title?: string;
    objective_definition?: string;
    objective_signals?: string[];
    project_goal?: string;
    project_end_product?: string;
    project_target_host?: string;
    clarifying_answers?: Record<string, string>;
    objective_answers?: Record<string, string>;
    global_question_answers?: Record<string, string>;
    reasoning_notes?: string;
    work_template?: ResearchWorkTemplate | null;
    max_results?: number;
    existing_citations?: string[];
  }
): Promise<FetchProjectLiteratureResponse> {
  const response = await fetch(`${API_BASE}/api/projects/${projectId}/literature`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to fetch literature');
  }
  return response.json();
}

export async function createProjectCollaborator(
  projectId: number,
  payload: {
    name: string;
    role?: string;
    workflow_stage?: string;
    focus_area?: string;
    goals?: string[];
    workflow_focus?: string[];
    starter_questions?: string[];
    summary?: string;
  }
): Promise<CreateProjectCollaboratorResponse> {
  const response = await fetch(`${API_BASE}/api/projects/${projectId}/collaborators`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to create project collaborator');
  }
  return response.json();
}

export async function fetchProjectQueries(projectId: number): Promise<ProjectQuerySessionListResponse> {
  const response = await fetch(`${API_BASE}/api/projects/${projectId}/queries`, { cache: 'no-store' });
  if (!response.ok) throw new Error('Failed to load project queries');
  return response.json();
}

export async function fetchProjectJourney(projectId: number): Promise<ProjectJourneyResponse> {
  const response = await fetch(`${API_BASE}/api/projects/${projectId}/journey`, { cache: 'no-store' });
  if (!response.ok) throw new Error('Failed to load project journey');
  return response.json();
}

export async function logProjectEvent(event_type: string, payload: Record<string, unknown>): Promise<{ status: string }> {
  const response = await fetch(`${API_BASE}/log_event`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ event_type, payload }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to log project event');
  }
  return response.json();
}

export async function createProjectQuery(
  projectId: number,
  payload: { title?: string; query: string; state?: Record<string, unknown> }
): Promise<ProjectQuerySession> {
  const response = await fetch(`${API_BASE}/api/projects/${projectId}/queries`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to create project query');
  }
  return response.json();
}

export async function updateProjectQuery(
  projectId: number,
  queryId: number,
  payload: { title?: string; query?: string; state?: Record<string, unknown> }
): Promise<ProjectQuerySession> {
  const response = await fetch(`${API_BASE}/api/projects/${projectId}/queries/${queryId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to save project query');
  }
  return response.json();
}

export async function preparePaperPdf(
  projectId: number,
  payload: {
    persona_id: number;
    finding: ResearchFinding;
    query: string;
    project_goal?: string;
    project_end_product?: string;
    project_target_host?: string;
    persona_name?: string;
    persona_focus?: string;
    objective_id?: string;
    objective_title?: string;
    objective_definition?: string;
    objective_signals?: string[];
    max_annotations?: number;
  }
): Promise<PreparePaperPdfResponse> {
  const response = await fetch(`${API_BASE}/api/projects/${projectId}/literature/pdf`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to prepare annotated PDF');
  }
  return response.json();
}

export async function fetchWorkspaceMemory(workspaceKey: string): Promise<WorkspaceMemoryResponse> {
  const response = await fetch(`${API_BASE}/api/workspace-memory/${encodeURIComponent(workspaceKey)}`, { cache: 'no-store' });
  if (!response.ok) throw new Error('Failed to load workspace memory');
  return response.json();
}

export async function saveWorkspaceMemory(
  workspaceKey: string,
  payload: {
    scope: string;
    explicit_state: Record<string, unknown>;
    tacit_state: TacitMemoryItem[];
    handoff_summary: string;
  }
): Promise<WorkspaceMemoryResponse> {
  const response = await fetch(`${API_BASE}/api/workspace-memory/${encodeURIComponent(workspaceKey)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to save workspace memory');
  }
  return response.json();
}

export async function inferWorkspaceMemory(payload: {
  workspace_key: string;
  scope: string;
  explicit_state: Record<string, unknown>;
  existing_tacit_state: TacitMemoryItem[];
}): Promise<InferWorkspaceMemoryResponse> {
  const response = await fetch(`${API_BASE}/api/workspace-memory/infer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to infer workspace memory');
  }
  return response.json();
}

export async function fetchLatestExecutionRun(projectId: number, personaId: number): Promise<ProjectExecutionRunResponse> {
  const response = await fetch(`${API_BASE}/api/projects/${projectId}/execution-runs/latest?persona_id=${personaId}`, { cache: 'no-store' });
  if (!response.ok) throw new Error('Failed to load execution run');
  return response.json();
}

export async function fetchExecutionRun(projectId: number, runId: number): Promise<ProjectExecutionRunResponse> {
  const response = await fetch(`${API_BASE}/api/projects/${projectId}/execution-runs/${runId}`, { cache: 'no-store' });
  if (!response.ok) throw new Error('Failed to load execution run');
  return response.json();
}

export async function startExecutionRun(
  projectId: number,
  payload: {
    persona_id: number;
    focus_question?: string;
    notes?: string;
    clarifying_answers?: Record<string, string>;
    reasoning_notes?: string;
    work_template?: ResearchWorkTemplate | null;
    objective_id?: string;
    objective_title?: string;
    objective_definition?: string;
    objective_signals?: string[];
  }
): Promise<ProjectExecutionRunResponse> {
  const response = await fetch(`${API_BASE}/api/projects/${projectId}/execution-runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to start execution run');
  }
  return response.json();
}

export async function saveWorkspaceState(
  projectId: number,
  personaId: number,
  payload: {
    focus_question?: string;
    clarifying_answers?: Record<string, string>;
    reasoning_notes?: string;
    work_template?: ResearchWorkTemplate | null;
    plan?: GeneratePlanResponse['plan'] | null;
    selected_step_id?: string;
  }
): Promise<ProjectWorkspaceResponse> {
  const response = await fetch(`${API_BASE}/api/projects/${projectId}/workspace/${personaId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to save workspace');
  }
  return response.json();
}
