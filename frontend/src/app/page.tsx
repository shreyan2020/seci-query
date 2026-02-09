'use client';

import React, { useState, useEffect } from 'react';

// Types matching backend v2.0
interface ProgressiveDisclosure {
  tldr: string;
  key_tradeoffs: string[];
  next_actions: string[];
}

interface EnhancedObjective {
  id: string;
  title: string;
  subtitle: string;
  definition: string;
  signals: string[];
  facet_questions: string[];
  exemplar_answer?: string;
  when_this_objective_is_wrong?: string;
  minimum_info_needed?: string[];
  expected_output_format?: string;
  confidence: string;
  is_speculative: boolean;
  rationale?: string;
  summary: ProgressiveDisclosure;
}

interface EvidenceItem {
  id: string;
  type: string;
  title: string;
  snippet: string;
  source_ref: string;
  source_quality?: string;
  score: number;
}

interface ContextRequirement {
  type: string;
  description: string;
  importance: 'required' | 'recommended' | 'optional';
  why: string;
  example: string;
}

interface QueryAnalysis {
  query_type: {
    name: string;
    description: string;
    characteristics: string[];
    complexity: string;
    estimated_time_seconds: number;
  };
  missing_context: ContextRequirement[];
  suggested_objectives_count: number;
  objective_categories: string[];
  user_expertise_inferred: string;
}

interface ExplorationNode {
  id: string;
  parent_id: string | null;
  query: string;
  context: string;
  objectives: EnhancedObjective[];
  selected_objective?: EnhancedObjective;
  answers: Record<string, string>;
  evidence: EvidenceItem[];
  final_answer?: string;
  timestamp: number;
  depth: number;
  dynamic_type?: string;
}

// API base URL
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Session management
const SESSION_ID_KEY = 'seci_session_id';
const USER_ID_KEY = 'seci_user_id';

// Initialize session
async function initializeSession(): Promise<{ session_id: string; user_id: string }> {
  const existingSession = localStorage.getItem(SESSION_ID_KEY);
  const existingUser = localStorage.getItem(USER_ID_KEY);
  
  if (existingSession && existingUser) {
    return { session_id: existingSession, user_id: existingUser };
  }
  
  const response = await fetch(`${API_BASE}/init`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source: 'web_app' })
  });
  
  if (!response.ok) throw new Error('Failed to initialize');
  
  const data = await response.json();
  localStorage.setItem(SESSION_ID_KEY, data.session_id);
  localStorage.setItem(USER_ID_KEY, data.user_id);
  
  return { session_id: data.session_id, user_id: data.user_id };
}

// API functions
async function analyzeQuery(
  query: string, 
  context: string,
  session: { session_id: string; user_id: string }
) {
  const response = await fetch(`${API_BASE}/analyze`, {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'X-User-Id': session.user_id,
      'X-Session-Id': session.session_id
    },
    body: JSON.stringify({ query, context })
  });
  if (!response.ok) throw new Error('Failed to analyze');
  return response.json();
}

async function generateDynamicObjectives(
  query: string,
  context: string,
  session: { session_id: string; user_id: string },
  k: number = 5
) {
  const response = await fetch(`${API_BASE}/objectives/dynamic`, {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'X-User-Id': session.user_id,
      'X-Session-Id': session.session_id
    },
    body: JSON.stringify({ query, context, k })
  });
  if (!response.ok) throw new Error('Failed to generate objectives');
  return response.json();
}

async function augmentWithContext(
  query: string, 
  objectiveId: string, 
  definition: string, 
  context: string,
  session: { session_id: string; user_id: string }
) {
  const response = await fetch(`${API_BASE}/augment`, {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'X-User-Id': session.user_id,
      'X-Session-Id': session.session_id
    },
    body: JSON.stringify({ 
      query, 
      objective_id: objectiveId, 
      objective_definition: definition, 
      context_blob: context 
    })
  });
  if (!response.ok) throw new Error('Failed to augment');
  return response.json();
}

async function finalizeAnswer(
  query: string, 
  objective: EnhancedObjective, 
  answers: Record<string, string>, 
  session: { session_id: string; user_id: string }
) {
  const response = await fetch(`${API_BASE}/finalize`, {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'X-User-Id': session.user_id,
      'X-Session-Id': session.session_id
    },
    body: JSON.stringify({ query, objective, answers })
  });
  if (!response.ok) throw new Error('Failed to finalize');
  return response.json();
}

// UI Components
function cn(...classes: (string | false | null | undefined)[]) {
  return classes.filter(Boolean).join(' ');
}

function ConfidenceBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    high: 'bg-green-100 text-green-800 border-green-200',
    medium: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    low: 'bg-orange-100 text-orange-800 border-orange-200',
    uncertain: 'bg-red-100 text-red-800 border-red-200'
  };
  return (
    <span className={cn('px-2 py-0.5 text-xs font-medium border rounded', colors[level] || colors.medium)}>
      {level}
    </span>
  );
}

function SourceBadge({ quality }: { quality?: string }) {
  const colors: Record<string, string> = {
    primary: 'bg-blue-100 text-blue-800',
    review: 'bg-purple-100 text-purple-800',
    secondary: 'bg-gray-100 text-gray-800',
    anecdotal: 'bg-orange-100 text-orange-800'
  };
  return (
    <span className={cn('px-2 py-0.5 text-xs rounded', colors[quality || 'secondary'])}>
      {quality || 'unknown'}
    </span>
  );
}

function RequirementBadge({ importance }: { importance: string }) {
  const colors: Record<string, string> = {
    required: 'bg-red-100 text-red-800',
    recommended: 'bg-yellow-100 text-yellow-800',
    optional: 'bg-gray-100 text-gray-600'
  };
  return (
    <span className={cn('text-xs px-2 py-0.5 rounded font-medium', colors[importance] || colors.optional)}>
      {importance}
    </span>
  );
}

export default function DynamicQueryExplorer() {
  // Session state
  const [session, setSession] = useState<{ session_id: string; user_id: string } | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  
  // Query and context
  const [query, setQuery] = useState('');
  const [context, setContext] = useState('');
  
  // Analysis state
  const [analysis, setAnalysis] = useState<QueryAnalysis | null>(null);
  const [contextRequirements, setContextRequirements] = useState<ContextRequirement[]>([]);
  const [showContextPrompt, setShowContextPrompt] = useState(false);
  
  // Exploration tree
  const [nodes, setNodes] = useState<ExplorationNode[]>([]);
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null);
  
  // UI state
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isAugmenting, setIsAugmenting] = useState(false);
  const [isFinalizing, setIsFinalizing] = useState(false);
  
  // Active node
  const activeNode = nodes.find(n => n.id === activeNodeId);
  const activeObjective = activeNode?.selected_objective;
  
  // Initialize
  useEffect(() => {
    initializeSession().then(setSession).finally(() => setIsLoading(false));
  }, []);
  
  // Analyze query before generating
  const handleAnalyze = async () => {
    if (!session || !query.trim()) return;
    
    setIsAnalyzing(true);
    try {
      const data = await analyzeQuery(query, context, session);
      setAnalysis(data.analysis);
      
      // Check if context is sufficient
      if (data.context_assessment && !data.context_assessment.is_sufficient) {
        const missing = data.context_assessment.missing_requirements || [];
        setContextRequirements(missing);
        setShowContextPrompt(true);
      } else {
        // Context is sufficient, proceed to generate
        setShowContextPrompt(false);
        await handleGenerate();
      }
    } catch (error) {
      console.error('Error analyzing:', error);
      alert('Failed to analyze query.');
    } finally {
      setIsAnalyzing(false);
    }
  };
  
  // Generate objectives (after analysis)
  const handleGenerate = async () => {
    if (!session || !query.trim()) return;
    
    setIsGenerating(true);
    setShowContextPrompt(false);
    
    try {
      const data = await generateDynamicObjectives(query, context, session, 5);
      
      // Check if we got a context prompt instead of objectives
      if (data.status === 'context_needed') {
        setContextRequirements(data.missing_requirements || []);
        setShowContextPrompt(true);
        setIsGenerating(false);
        return;
      }
      
      const newNode: ExplorationNode = {
        id: `node-${Date.now()}`,
        parent_id: null,
        query: query,
        context: context,
        objectives: data.objectives,
        answers: {},
        evidence: [],
        timestamp: Date.now(),
        depth: 0,
        dynamic_type: data.router_info?.context_hints?.dynamic_type
      };
      
      setNodes([newNode]);
      setActiveNodeId(newNode.id);
    } catch (error) {
      console.error('Error generating:', error);
      alert('Failed to generate objectives.');
    } finally {
      setIsGenerating(false);
    }
  };
  
  // Select objective
  const handleSelectObjective = (objective: EnhancedObjective) => {
    if (!activeNode) return;
    
    const updatedNodes = nodes.map(n => 
      n.id === activeNode.id 
        ? { ...n, selected_objective: objective, answers: {} }
        : n
    );
    setNodes(updatedNodes);
  };
  
  // Update answer
  const handleAnswerChange = (question: string, answer: string) => {
    if (!activeNode) return;
    
    const updatedNodes = nodes.map(n => 
      n.id === activeNode.id 
        ? { ...n, answers: { ...n.answers, [question]: answer } }
        : n
    );
    setNodes(updatedNodes);
  };
  
  // Augment with context
  const handleAugment = async () => {
    if (!session || !activeNode || !activeObjective || !context.trim()) return;
    
    setIsAugmenting(true);
    try {
      const data = await augmentWithContext(
        activeNode.query,
        activeObjective.id,
        activeObjective.definition,
        context,
        session
      );
      
      const updatedNodes = nodes.map(n => 
        n.id === activeNode.id 
          ? { ...n, evidence: data.evidence_items }
          : n
      );
      setNodes(updatedNodes);
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setIsAugmenting(false);
    }
  };
  
  // Finalize
  const handleFinalize = async () => {
    if (!session || !activeNode || !activeObjective) return;
    
    setIsFinalizing(true);
    try {
      const data = await finalizeAnswer(
        activeNode.query,
        activeObjective,
        activeNode.answers,
        session
      );
      
      const updatedNodes = nodes.map(n => 
        n.id === activeNode.id 
          ? { ...n, final_answer: data.final_answer }
          : n
      );
      setNodes(updatedNodes);
    } catch (error) {
      console.error('Error:', error);
      alert('Failed to generate answer.');
    } finally {
      setIsFinalizing(false);
    }
  };
  
  // Navigate
  const navigateToNode = (nodeId: string) => {
    const node = nodes.find(n => n.id === nodeId);
    if (node) {
      setActiveNodeId(nodeId);
      setQuery(node.query);
      setContext(node.context);
    }
  };
  
  // Reset
  const handleReset = () => {
    setQuery('');
    setContext('');
    setNodes([]);
    setActiveNodeId(null);
    setAnalysis(null);
    setContextRequirements([]);
    setShowContextPrompt(false);
  };
  
  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Initializing...</p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Sidebar - Exploration Tree */}
      <div className="w-80 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-4 border-b border-gray-200">
          <h1 className="text-lg font-bold text-gray-900">Dynamic Query Explorer</h1>
          <p className="text-xs text-gray-500 mt-1">AI-generated types • Smart context detection</p>
        </div>
        
        <div className="flex-1 overflow-y-auto p-4">
          {nodes.length === 0 ? (
            <div className="text-sm text-gray-500 text-center py-8">
              Start a query to begin exploration
            </div>
          ) : (
            <div className="space-y-2">
              {nodes.map(node => (
                <button
                  key={node.id}
                  onClick={() => navigateToNode(node.id)}
                  className={cn(
                    'w-full text-left p-3 rounded-lg border transition-all',
                    activeNodeId === node.id
                      ? 'bg-blue-50 border-blue-300'
                      : 'bg-white border-gray-200 hover:border-gray-300'
                  )}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-gray-400">L{node.depth}</span>
                    <span className="text-sm font-medium text-gray-900 truncate">
                      {node.query.slice(0, 40)}...
                    </span>
                  </div>
                  {node.dynamic_type && (
                    <div className="text-xs text-blue-600 mt-1">
                      Type: {node.dynamic_type}
                    </div>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
      
      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 p-4">
          <div className="flex gap-4">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Enter your research question..."
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()}
            />
            <button
              onClick={handleAnalyze}
              disabled={isAnalyzing || isGenerating || !query.trim()}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium"
            >
              {isAnalyzing ? 'Analyzing...' : isGenerating ? 'Generating...' : 'Explore'}
            </button>
            {nodes.length > 0 && (
              <button
                onClick={handleReset}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
              >
                Reset
              </button>
            )}
          </div>
          
          {/* Context input */}
          <div className="mt-3">
            <textarea
              value={context}
              onChange={(e) => setContext(e.target.value)}
              placeholder="Context: papers, data, experimental notes, constraints, timeline... (optional but recommended)"
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            />
          </div>
          
          {/* Dynamic type info */}
          {analysis && (
            <div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-sm font-medium text-blue-900">
                    Detected Type: {analysis.query_type.name}
                  </span>
                  <span className="text-xs text-blue-600 ml-2">
                    ({analysis.query_type.complexity})
                  </span>
                </div>
                <div className="text-xs text-blue-600">
                  Est. time: {analysis.query_type.estimated_time_seconds}s
                </div>
              </div>
              <div className="text-xs text-blue-700 mt-1">
                {analysis.query_type.description}
              </div>
            </div>
          )}
        </div>
        
        {/* Context Requirements Prompt */}
        {showContextPrompt && contextRequirements.length > 0 && (
          <div className="bg-amber-50 border-b border-amber-200 p-4">
            <div className="flex items-start gap-3">
              <div className="text-amber-600 text-xl">⚠️</div>
              <div className="flex-1">
                <h3 className="font-semibold text-amber-900">Additional Context Recommended</h3>
                <p className="text-sm text-amber-700 mt-1">
                  To generate the most relevant objectives, please provide:
                </p>
                <div className="mt-3 space-y-2">
                  {contextRequirements.map((req, idx) => (
                    <div key={idx} className="bg-white p-3 rounded border border-amber-200">
                      <div className="flex items-center gap-2 mb-1">
                        <RequirementBadge importance={req.importance} />
                        <span className="font-medium text-gray-900">{req.description}</span>
                      </div>
                      <p className="text-sm text-gray-600">{req.why}</p>
                      <p className="text-xs text-gray-500 mt-1">Example: {req.example}</p>
                    </div>
                  ))}
                </div>
                <div className="mt-4 flex gap-2">
                  <button
                    onClick={handleGenerate}
                    className="px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 text-sm"
                  >
                    Proceed Anyway
                  </button>
                  <button
                    onClick={() => setShowContextPrompt(false)}
                    className="px-4 py-2 border border-amber-300 text-amber-700 rounded-lg hover:bg-amber-100 text-sm"
                  >
                    Add Context First
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
        
        {/* Main content area */}
        <div className="flex-1 overflow-y-auto p-6">
          {!activeNode ? (
            <div className="max-w-2xl mx-auto text-center py-20">
              <h2 className="text-2xl font-bold text-gray-900 mb-4">
                Dynamic Query Analysis
              </h2>
              <p className="text-gray-600 mb-8">
                Enter a research question and our AI will:
              </p>
              <ul className="text-left max-w-md mx-auto space-y-3 text-gray-700">
                <li className="flex items-start gap-2">
                  <span className="text-blue-600">1.</span>
                  <span>Analyze your query to determine its unique characteristics</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-blue-600">2.</span>
                  <span>Identify what context would help generate better results</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-blue-600">3.</span>
                  <span>Generate custom objective types specific to your query</span>
                </li>
              </ul>
            </div>
          ) : (
            <div className="max-w-6xl mx-auto space-y-6">
              {/* Objectives */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-4">
                  Generated Objectives
                  {activeNode.dynamic_type && (
                    <span className="ml-2 text-sm font-normal text-blue-600">
                      (Type: {activeNode.dynamic_type})
                    </span>
                  )}
                </h3>
                
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {activeNode.objectives.map(objective => (
                    <button
                      key={objective.id}
                      onClick={() => handleSelectObjective(objective)}
                      className={cn(
                        'text-left p-4 rounded-lg border-2 transition-all',
                        activeObjective?.id === objective.id
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200 bg-white hover:border-gray-300'
                      )}
                    >
                      <div className="flex items-start justify-between mb-2">
                        <h4 className="font-semibold text-gray-900">{objective.title}</h4>
                        <ConfidenceBadge level={objective.confidence} />
                      </div>
                      <p className="text-sm text-gray-600 mb-3">{objective.subtitle}</p>
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
              
              {/* Selected objective detail */}
              {activeObjective && (
                <div className="bg-white rounded-lg border border-gray-200 p-6">
                  <h3 className="text-xl font-bold text-gray-900 mb-4">{activeObjective.title}</h3>
                  <p className="text-gray-700 mb-4">{activeObjective.definition}</p>
                  
                  {activeObjective.when_this_objective_is_wrong && (
                    <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6">
                      <div className="text-sm font-medium text-amber-800">When this doesn't apply:</div>
                      <div className="text-sm text-amber-700">{activeObjective.when_this_objective_is_wrong}</div>
                    </div>
                  )}
                  
                  {/* Facet questions */}
                  <div className="mb-6">
                    <h4 className="font-semibold text-gray-900 mb-3">Clarifying Questions</h4>
                    <div className="space-y-3">
                      {activeObjective.facet_questions.map((question, idx) => (
                        <div key={idx}>
                          <label className="block text-sm text-gray-700 mb-1">{question}</label>
                          <input
                            type="text"
                            value={activeNode.answers[question] || ''}
                            onChange={(e) => handleAnswerChange(question, e.target.value)}
                            placeholder="Your answer..."
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                  
                  {/* Context analysis */}
                  {context.trim() && (
                    <div className="mb-6">
                      <button
                        onClick={handleAugment}
                        disabled={isAugmenting}
                        className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50"
                      >
                        {isAugmenting ? 'Analyzing...' : 'Analyze Context'}
                      </button>
                    </div>
                  )}
                  
                  {/* Evidence */}
                  {activeNode.evidence.length > 0 && (
                    <div className="mb-6">
                      <h4 className="font-semibold text-gray-900 mb-3">Extracted Evidence</h4>
                      <div className="space-y-3">
                        {activeNode.evidence.map(item => (
                          <div key={item.id} className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                            <div className="flex items-center gap-2 mb-2">
                              <span className="font-medium">{item.title}</span>
                              <SourceBadge quality={item.source_quality} />
                            </div>
                            <p className="text-sm text-gray-700">{item.snippet}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  {/* Generate answer */}
                  {!activeNode.final_answer && (
                    <button
                      onClick={handleFinalize}
                      disabled={isFinalizing}
                      className="w-full py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium"
                    >
                      {isFinalizing ? 'Generating...' : 'Generate Grounded Answer'}
                    </button>
                  )}
                  
                  {/* Final answer */}
                  {activeNode.final_answer && (
                    <div className="bg-green-50 border border-green-200 rounded-lg p-6">
                      <h4 className="font-semibold text-green-900 mb-3">Research Answer</h4>
                      <div className="text-gray-800 whitespace-pre-wrap">{activeNode.final_answer}</div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}