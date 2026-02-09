'use client';

import React, { useState, useEffect, useCallback } from 'react';

// ============================================================================
// TYPES
// ============================================================================

interface DynamicNode {
  id: string;
  type: string;
  label: string;
  description: string;
  tool?: string;
  validation: string[];
  parameters: Record<string, any>;
}

interface DynamicEdge {
  source: string;
  target: string;
  type: string;
  condition?: string;
}

interface ExecutionStep {
  step: number;
  node_id: string;
  type: string;
  label: string;
  description: string;
  tool?: string;
  validation: string[];
}

interface DynamicGraph {
  query: string;
  strategy: string;
  uncertainty: {
    score: number;
    level: string;
    need_disambiguation: boolean;
  };
  graph: {
    nodes: DynamicNode[];
    edges: DynamicEdge[];
  };
  execution_plan: ExecutionStep[];
  visualization: {
    mermaid: string;
    format: string;
  };
  metadata: Record<string, any>;
}

interface Objective {
  id: string;
  title: string;
  subtitle: string;
  definition: string;
  signals: string[];
  confidence: string;
  is_speculative: boolean;
  summary: {
    tldr: string;
    key_tradeoffs: string[];
    next_actions: string[];
  };
}

interface QuerySession {
  id: string;
  query: string;
  timestamp: number;
  objectives?: Objective[];
  selected_objective?: Objective;
  graph?: DynamicGraph;
  answer?: string;
}

// ============================================================================
// API FUNCTIONS
// ============================================================================

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Step 1: Get objective clusters
async function getSmartObjectives(
  query: string,
  context: string,
  userId: string,
  sessionId: string
): Promise<{ objectives: Objective[]; strategy: string; uncertainty_score: number }> {
  const response = await fetch(`${API_BASE}/objectives/smart`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-Id': userId,
      'X-Session-Id': sessionId
    },
    body: JSON.stringify({ query, context, k: 5 })
  });
  
  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to get objectives: ${error}`);
  }
  
  const data = await response.json();
  return {
    objectives: data.objectives,
    strategy: data.processing_metadata?.strategy || 'direct',
    uncertainty_score: data.processing_metadata?.uncertainty_score || 0
  };
}

// Step 2: Generate workflow for selected objective
async function generateGraphForObjective(
  query: string,
  objective: Objective,
  context: string,
  userId: string,
  sessionId: string
): Promise<DynamicGraph> {
  const response = await fetch(`${API_BASE}/graph/for-objective`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-Id': userId,
      'X-Session-Id': sessionId
    },
    body: JSON.stringify({ query, objective, context })
  });
  
  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to generate workflow: ${error}`);
  }
  
  return response.json();
}

async function finalizeAnswer(
  query: string,
  graph: DynamicGraph,
  userId: string,
  sessionId: string
): Promise<{ final_answer: string }> {
  // For dynamic graphs, we use the first node as the objective
  const objective = graph.graph.nodes[0];
  
  const response = await fetch(`${API_BASE}/finalize`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-Id': userId,
      'X-Session-Id': sessionId
    },
    body: JSON.stringify({
      query,
      objective: {
        id: objective?.id || 'dynamic',
        title: objective?.label || 'Dynamic Objective',
        subtitle: 'LLM-generated workflow',
        definition: objective?.description || '',
        signals: ['dynamic_generation'],
        facet_questions: [],
        confidence: 'high',
        is_speculative: false,
        summary: {
          tldr: graph.execution_plan.map(s => s.label).join(' → '),
          key_tradeoffs: [],
          next_actions: graph.execution_plan.slice(0, 3).map(s => s.label)
        }
      },
      answers: {},
      evidence_items: []
    })
  });
  
  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to finalize: ${error}`);
  }
  
  return response.json();
}

// ============================================================================
// COMPONENTS
// ============================================================================

function cn(...classes: (string | false | null | undefined)[]) {
  return classes.filter(Boolean).join(' ');
}

function UncertaintyBadge({ score }: { score: number }) {
  const percentage = Math.round(score * 100);
  let color = 'bg-green-100 text-green-800';
  let label = 'Low';
  
  if (score > 0.6) {
    color = 'bg-red-100 text-red-800';
    label = 'High';
  } else if (score > 0.3) {
    color = 'bg-yellow-100 text-yellow-800';
    label = 'Medium';
  }
  
  return (
    <span className={cn('px-2 py-1 text-xs font-medium rounded', color)}>
      {label} ({percentage}%)
    </span>
  );
}

function NodeCard({ 
  node, 
  isActive, 
  onClick 
}: { 
  node: DynamicNode; 
  isActive: boolean;
  onClick: () => void;
}) {
  const typeColors: Record<string, string> = {
    intent: 'border-blue-400 bg-blue-50',
    decision: 'border-yellow-400 bg-yellow-50',
    action: 'border-green-400 bg-green-50',
    output: 'border-purple-400 bg-purple-50',
    verification: 'border-orange-400 bg-orange-50'
  };
  
  return (
    <div
      onClick={onClick}
      className={cn(
        'p-3 rounded-lg border-2 cursor-pointer transition-all hover:shadow-md',
        typeColors[node.type] || 'border-gray-300 bg-white',
        isActive && 'ring-2 ring-blue-500 shadow-lg'
      )}
    >
      <div className="flex items-center gap-2 mb-1">
        <span className={cn(
          'text-xs px-2 py-0.5 rounded uppercase font-bold',
          node.type === 'intent' && 'bg-blue-200 text-blue-800',
          node.type === 'decision' && 'bg-yellow-200 text-yellow-800',
          node.type === 'action' && 'bg-green-200 text-green-800',
          node.type === 'output' && 'bg-purple-200 text-purple-800',
          node.type === 'verification' && 'bg-orange-200 text-orange-800'
        )}>
          {node.type}
        </span>
        {node.tool && (
          <span className="text-xs text-gray-500">🔧 {node.tool}</span>
        )}
      </div>
      <h4 className="font-semibold text-sm text-gray-900">{node.label}</h4>
      <p className="text-xs text-gray-600 mt-1 line-clamp-2">{node.description}</p>
    </div>
  );
}

function MermaidViewer({ diagram }: { diagram: string }) {
  const [copied, setCopied] = useState(false);
  
  const copyToClipboard = () => {
    navigator.clipboard.writeText(diagram);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  
  return (
    <div className="bg-gray-900 rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
        <span className="text-sm text-gray-300">Mermaid Diagram</span>
        <button
          onClick={copyToClipboard}
          className="text-xs px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <pre className="p-4 text-xs text-green-400 overflow-x-auto whitespace-pre">
        {diagram}
      </pre>
    </div>
  );
}

// ============================================================================
// MAIN APP
// ============================================================================

export default function DynamicQueryInterface() {
  // Session
  const [sessionId] = useState(() => `session-${Date.now()}`);
  const [userId] = useState(() => `user-${Math.random().toString(36).substr(2, 9)}`);
  
  // Query state
  const [query, setQuery] = useState('');
  const [context, setContext] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  
  // Step 1: Objectives
  const [objectives, setObjectives] = useState<Objective[]>([]);
  const [strategy, setStrategy] = useState<string>('');
  const [uncertaintyScore, setUncertaintyScore] = useState<number>(0);
  const [selectedObjective, setSelectedObjective] = useState<Objective | null>(null);
  
  // Step 2: Workflow Graph
  const [currentGraph, setCurrentGraph] = useState<DynamicGraph | null>(null);
  const [selectedNode, setSelectedNode] = useState<DynamicNode | null>(null);
  const [answer, setAnswer] = useState('');
  const [isGeneratingAnswer, setIsGeneratingAnswer] = useState(false);
  
  // History
  const [history, setHistory] = useState<QuerySession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  
  // Step 1: Get objective clusters
  const handleGenerateObjectives = async () => {
    if (!query.trim()) return;
    
    setIsLoading(true);
    setObjectives([]);
    setSelectedObjective(null);
    setCurrentGraph(null);
    setAnswer('');
    
    try {
      const result = await getSmartObjectives(query, context, userId, sessionId);
      setObjectives(result.objectives);
      setStrategy(result.strategy);
      setUncertaintyScore(result.uncertainty_score);
      
      // Add to history
      const newSession: QuerySession = {
        id: `session-${Date.now()}`,
        query,
        timestamp: Date.now(),
        objectives: result.objectives
      };
      setHistory(prev => [newSession, ...prev]);
      setActiveSessionId(newSession.id);
      
    } catch (error) {
      console.error('Error:', error);
      alert(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsLoading(false);
    }
  };
  
  // Step 2: Select objective and generate workflow
  const handleSelectObjective = async (objective: Objective) => {
    setSelectedObjective(objective);
    setIsLoading(true);
    
    try {
      const graph = await generateGraphForObjective(query, objective, context, userId, sessionId);
      setCurrentGraph(graph);
      
      // Update history
      setHistory(prev => prev.map(h => 
        h.id === activeSessionId 
          ? { ...h, selected_objective: objective, graph }
          : h
      ));
      
    } catch (error) {
      console.error('Error:', error);
      alert(`Error generating workflow: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsLoading(false);
    }
  };
  
  // Generate answer (works without Ollama - creates summary from execution plan)
  const handleGenerateAnswer = async () => {
    if (!currentGraph) return;
    
    setIsGeneratingAnswer(true);
    
    // Simulate processing delay
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Generate answer from execution plan (no LLM needed)
    const steps = currentGraph.execution_plan;
    const intent = steps.find(s => s.type === 'intent');
    const actions = steps.filter(s => s.type === 'action');
    const outputs = steps.filter(s => s.type === 'output');
    
    // Build summary answer
    let summary = `# Workflow Execution Summary\n\n`;
    summary += `**Query:** ${currentGraph.query}\n\n`;
    summary += `**Objective:** ${intent?.description || 'Process user query'}\n\n`;
    summary += `**Strategy:** ${currentGraph.strategy === 'direct' ? 'Direct Execution' : 'Disambiguation Required'}\n`;
    summary += `**Uncertainty:** ${(currentGraph.uncertainty.score * 100).toFixed(1)}%\n\n`;
    
    summary += `## Execution Steps\n\n`;
    actions.forEach((step, idx) => {
      summary += `${idx + 1}. **${step.label}**\n`;
      summary += `   - ${step.description}\n`;
      if (step.tool) {
        summary += `   - Tool: ${step.tool}\n`;
      }
      if (step.validation.length > 0) {
        summary += `   - Validation: ${step.validation.join(', ')}\n`;
      }
      summary += `\n`;
    });
    
    summary += `## Expected Output\n\n`;
    outputs.forEach(output => {
      summary += `- **${output.label}**: ${output.description}\n`;
    });
    
    summary += `\n---\n`;
    summary += `*Note: This is a workflow visualization. To get actual data, execute the suggested tools.*`;
    
    setAnswer(summary);
    
    // Update history
    setHistory(prev => prev.map(h => 
      h.id === activeSessionId 
        ? { ...h, answer: summary }
        : h
    ));
    
    setIsGeneratingAnswer(false);
  };
  
  // Load from history
  const loadSession = (session: QuerySession) => {
    setQuery(session.query);
    setObjectives(session.objectives || []);
    setSelectedObjective(session.selected_objective || null);
    setCurrentGraph(session.graph || null);
    setAnswer(session.answer || '');
    setActiveSessionId(session.id);
    if (session.graph?.graph.nodes[0]) {
      setSelectedNode(session.graph.graph.nodes[0]);
    }
  };
  
  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">SECI Query Explorer</h1>
            {/* <p className="text-sm text-gray-600">Dynamic LLM-Powered Workflow Generation</p> */}
          </div>
          <div className="text-sm text-gray-500">
            User: {userId}
          </div>
        </div>
      </header>
      
      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        
        {/* LEFT SIDEBAR - History & Strategy */}
        <aside className="w-80 bg-white border-r border-gray-200 flex flex-col">
          {/* Query Input */}
          <div className="p-4 border-b border-gray-200">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Enter your query..."
               className="w-full h-16 px-3 py-2 mt-2 border border-gray-300 rounded-lg resize-none
             bg-white text-gray-900 placeholder:text-gray-400
             focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            />
            <textarea
              value={context}
              onChange={(e) => setContext(e.target.value)}
              placeholder="Additional context (optional)..."
              className="w-full h-16 px-3 py-2 mt-2 border border-gray-300 rounded-lg resize-none
             bg-white text-gray-900 placeholder:text-gray-400
             focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            />
            <button
              onClick={handleGenerateObjectives}
              disabled={isLoading || !query.trim()}
              className="w-full mt-3 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium"
            >
              {isLoading ? 'Analyzing...' : 'Analyze Query'}
            </button>
          </div>
          
          {/* Step 1: Objective Clusters */}
          {objectives.length > 0 && !currentGraph && (
            <div className="flex-1 overflow-y-auto">
              <div className="p-4 border-b border-gray-200 bg-yellow-50">
                <h3 className="font-semibold text-sm text-gray-900 mb-2">Select an Objective</h3>
                <p className="text-xs text-gray-600">
                  Strategy: {strategy === 'direct' ? 'Direct Execution' : 'Disambiguation'}
                </p>
                <p className="text-xs text-gray-600">
                  Uncertainty: {(uncertaintyScore * 100).toFixed(1)}%
                </p>
              </div>
              
              <div className="divide-y divide-gray-100">
                {objectives.map((objective) => (
                  <button
                    key={objective.id}
                    onClick={() => handleSelectObjective(objective)}
                    disabled={isLoading}
                    className={cn(
                      'w-full px-4 py-4 text-left hover:bg-blue-50 transition-colors',
                      selectedObjective?.id === objective.id && 'bg-blue-50 border-l-4 border-blue-500'
                    )}
                  >
                    <div className="flex items-start justify-between mb-1">
                      <h4 className="font-semibold text-sm text-gray-900">{objective.title}</h4>
                      <span className={cn(
                        'text-xs px-2 py-0.5 rounded',
                        objective.confidence === 'high' ? 'bg-green-100 text-green-800' : 
                        objective.confidence === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                        'bg-orange-100 text-orange-800'
                      )}>
                        {objective.confidence}
                      </span>
                    </div>
                    <p className="text-xs text-gray-600 mb-2">{objective.subtitle}</p>
                    <p className="text-xs text-gray-500 line-clamp-2">{objective.definition}</p>
                    {objective.is_speculative && (
                      <span className="inline-block mt-2 text-xs text-amber-600 bg-amber-50 px-2 py-0.5 rounded">
                        Speculative
                      </span>
                    )}
                  </button>
                ))}
              </div>
            </div>
          )}
          
          {/* Step 2: Current Workflow */}
          {currentGraph && (
            <div className="p-4 border-b border-gray-200 bg-green-50">
              <h3 className="font-semibold text-sm text-gray-900 mb-2">Active Workflow</h3>
              <p className="text-sm text-gray-700 mb-2">{selectedObjective?.title}</p>
              <div className="space-y-1 text-xs text-gray-600">
                <div className="flex items-center justify-between">
                  <span>Nodes:</span>
                  <span className="font-medium">{currentGraph.graph.nodes.length}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Steps:</span>
                  <span className="font-medium">{currentGraph.execution_plan.length}</span>
                </div>
              </div>
            </div>
          )}
          
          {/* History */}
          <div className="flex-1 overflow-y-auto">
            <h3 className="font-semibold text-sm text-gray-900 px-4 py-3 border-b border-gray-200">
              Query History
            </h3>
            {history.length === 0 ? (
              <p className="px-4 py-4 text-sm text-gray-500">No queries yet</p>
            ) : (
              <div className="divide-y divide-gray-100">
                {history.map((session) => (
                  <button
                    key={session.id}
                    onClick={() => loadSession(session)}
                    className={cn(
                      'w-full px-4 py-3 text-left hover:bg-gray-50 transition-colors',
                      activeSessionId === session.id && 'bg-blue-50 border-l-4 border-blue-500'
                    )}
                  >
                    <p className="text-sm font-medium text-gray-900 line-clamp-2">
                      {session.query}
                    </p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs text-gray-500">
                        {new Date(session.timestamp).toLocaleTimeString()}
                      </span>
                      {session.answer && (
                        <span className="text-xs text-green-600">✓ Answered</span>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </aside>
        
        {/* CENTER - Main Content */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {currentGraph ? (
            <>
              {/* Graph Visualization */}
              <div className="flex-1 overflow-y-auto p-6">
                <div className="max-w-4xl mx-auto space-y-6">
                  {/* Query Display */}
                  <div className="bg-white rounded-lg border border-gray-200 p-4">
                    <h2 className="text-lg font-semibold text-gray-900 mb-2">Query</h2>
                    <p className="text-gray-700">{currentGraph.query}</p>
                  </div>
                  
                  {/* Selected Objective Info */}
                  {selectedObjective && (
                    <div className="bg-blue-50 rounded-lg border border-blue-200 p-4">
                      <h3 className="font-semibold text-blue-900 mb-1">Selected Objective</h3>
                      <h4 className="text-lg font-bold text-gray-900">{selectedObjective.title}</h4>
                      <p className="text-sm text-gray-700">{selectedObjective.definition}</p>
                    </div>
                  )}
                  
                  {/* Node Details */}
                  {selectedNode && (
                    <div className="bg-white rounded-lg border border-gray-200 p-6">
                      <div className="flex items-start justify-between mb-4">
                        <div>
                          <span className={cn(
                            'inline-block text-xs px-2 py-1 rounded uppercase font-bold mb-2',
                            selectedNode.type === 'intent' && 'bg-blue-100 text-blue-800',
                            selectedNode.type === 'decision' && 'bg-yellow-100 text-yellow-800',
                            selectedNode.type === 'action' && 'bg-green-100 text-green-800',
                            selectedNode.type === 'output' && 'bg-purple-100 text-purple-800',
                            selectedNode.type === 'verification' && 'bg-orange-100 text-orange-800'
                          )}>
                            {selectedNode.type}
                          </span>
                          <h2 className="text-xl font-bold text-gray-900">{selectedNode.label}</h2>
                        </div>
                        {selectedNode.tool && (
                          <span className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm">
                            🔧 {selectedNode.tool}
                          </span>
                        )}
                      </div>
                      
                      <p className="text-gray-700 mb-4">{selectedNode.description}</p>
                      
                      {selectedNode.validation.length > 0 && (
                        <div className="mt-4">
                          <h3 className="font-semibold text-sm text-gray-900 mb-2">Validation Criteria</h3>
                          <ul className="space-y-1">
                            {selectedNode.validation.map((criteria, idx) => (
                              <li key={idx} className="flex items-center gap-2 text-sm text-gray-600">
                                <span className="text-green-500">✓</span>
                                {criteria}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      
                      {Object.keys(selectedNode.parameters).length > 0 && (
                        <div className="mt-4">
                          <h3 className="font-semibold text-sm text-gray-900 mb-2">Parameters</h3>
                          <pre className="bg-gray-50 p-3 rounded text-xs overflow-x-auto">
                            {JSON.stringify(selectedNode.parameters, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}
                  
                  {/* Generate Answer */}
                  {!answer && (
                    <div className="bg-white rounded-lg border border-gray-200 p-6 text-center">
                      <button
                        onClick={handleGenerateAnswer}
                        disabled={isGeneratingAnswer}
                        className="px-8 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 font-medium text-lg"
                      >
                        {isGeneratingAnswer ? 'Generating Answer...' : 'Generate Final Answer'}
                      </button>
                      <p className="text-sm text-gray-500 mt-2">
                        This will execute the workflow and provide a grounded answer
                      </p>
                    </div>
                  )}
                  
                  {/* Answer Display */}
                  {answer && (
                    <div className="bg-green-50 border border-green-200 rounded-lg p-6">
                      <h2 className="text-lg font-bold text-green-900 mb-3">Research Answer</h2>
                      <div className="prose prose-green max-w-none">
                        <div className="whitespace-pre-wrap text-gray-800">{answer}</div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </>
          ) : objectives.length > 0 ? (
            /* Step 1: Objectives Available - Show Selection Prompt */
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center max-w-lg">
                <div className="text-6xl mb-4">🎯</div>
                <h2 className="text-2xl font-bold text-gray-900 mb-4">
                  Multiple Interpretations Detected
                </h2>
                <p className="text-gray-600 mb-6">
                  Your query could be interpreted in {objectives.length} different ways. 
                  Please select the objective that best matches your intent from the sidebar.
                </p>
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-left">
                  <h3 className="font-semibold text-yellow-900 mb-2">Available Objectives:</h3>
                  <ul className="space-y-2">
                    {objectives.map((obj, idx) => (
                      <li key={obj.id} className="flex items-center gap-2 text-sm text-gray-700">
                        <span className="font-bold text-yellow-700">{idx + 1}.</span>
                        {obj.title}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          ) : (
            /* Initial State */
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <div className="text-6xl mb-4">🧬</div>
                <h2 className="text-2xl font-bold text-gray-900 mb-2">
                  Welcome to SECI Query Explorer
                </h2>
                <p className="text-gray-600 max-w-md mx-auto">
                  Enter a query and click "Analyze Query" to get started. 
                  The system will identify possible interpretations and help you refine your search.
                </p>
              </div>
            </div>
          )}
        </main>
        
        {/* RIGHT SIDEBAR - Graph & Execution */}
        {currentGraph && (
          <aside className="w-96 bg-white border-l border-gray-200 flex flex-col overflow-hidden">
            {/* Tabs */}
            <div className="flex border-b border-gray-200">
              <button className="flex-1 px-4 py-3 text-sm font-medium text-blue-600 border-b-2 border-blue-600">
                Workflow
              </button>
              <button className="flex-1 px-4 py-3 text-sm font-medium text-gray-600 hover:text-gray-900">
                Graph
              </button>
            </div>
            
            {/* Execution Plan */}
            <div className="flex-1 overflow-y-auto p-4">
              <h3 className="font-semibold text-sm text-gray-900 mb-3">Execution Steps</h3>
              <div className="space-y-2">
                {currentGraph.execution_plan.map((step, idx) => (
                  <div
                    key={step.node_id}
                    onClick={() => {
                      const node = currentGraph.graph.nodes.find(n => n.id === step.node_id);
                      if (node) setSelectedNode(node);
                    }}
                    className={cn(
                      'p-3 rounded-lg border cursor-pointer transition-all hover:shadow-sm',
                      selectedNode?.id === step.node_id 
                        ? 'border-blue-500 bg-blue-50' 
                        : 'border-gray-200 hover:border-gray-300'
                    )}
                  >
                    <div className="flex items-center gap-2">
                      <span className="flex-shrink-0 w-6 h-6 bg-gray-200 text-gray-700 rounded-full flex items-center justify-center text-xs font-bold">
                        {idx + 1}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {step.label}
                        </p>
                        <p className="text-xs text-gray-500 truncate">
                          {step.description}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              
              {/* Mermaid Diagram */}
              <div className="mt-6">
                <h3 className="font-semibold text-sm text-gray-900 mb-3">Causal Graph</h3>
                <MermaidViewer diagram={currentGraph.visualization.mermaid} />
              </div>
              
              {/* Metadata */}
              <div className="mt-6 p-4 bg-gray-50 rounded-lg">
                <h3 className="font-semibold text-sm text-gray-900 mb-2">Metadata</h3>
                <div className="space-y-1 text-xs text-gray-600">
                  <div className="flex justify-between">
                    <span>Processing time:</span>
                    <span>{currentGraph.metadata.processing_time_ms?.toFixed(0)}ms</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Personalized:</span>
                    <span>{currentGraph.metadata.personalized ? 'Yes' : 'No'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Complexity:</span>
                    <span className="capitalize">{currentGraph.metadata.complexity}</span>
                  </div>
                </div>
              </div>
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}
