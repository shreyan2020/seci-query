# Frontend Migration Guide - SECI Query Explorer v2.0

## Overview

This guide helps frontend developers migrate from SECI Query Explorer v1.0 to v2.0, leveraging new features like progressive disclosure, uncertainty markers, and query refinements.

---

## 1. API Compatibility

### 1.1 Breaking Changes

**None** - All v2.0 endpoints are backward compatible with v1.0 requests. However, v2.0 responses include significant new fields.

### 1.2 Schema Versioning

Check `schema_version` field in responses:
- `"2.0.0"` = Full v2.0 feature set
- Missing or `"1.0.0"` = Legacy response (if implemented)

```javascript
const isV2 = response.schema_version === "2.0.0";
```

---

## 2. New Response Fields

### 2.1 POST /objectives

**New Top-Level Fields**:

```typescript
interface ObjectivesResponseV2 {
  schema_version: string;
  objectives: EnhancedObjective[];  // Same structure + new fields
  global_questions: string[];
  
  // NEW: Query classification
  router_info: {
    query_type: string;           // e.g., "ambiguity_preference"
    confidence: number;           // 0.0 - 1.0
    missing_inputs: string[];     // What context is needed
    recommended_workflow: string;
    context_hints: object;
  };
  
  // NEW: Query improvements
  query_refinements: QueryRefinement[];
  
  // NEW: Uncertainty transparency
  uncertainty_markers: UncertaintyMarker[];
  
  // NEW: Progressive disclosure
  progressive_summary: ProgressiveDisclosure;
  
  // NEW: Metadata
  processing_metadata: {
    processing_time_ms: number;
    prompt_length: number;
    query_signature: string;
  };
}
```

**EnhancedObjective New Fields**:

```typescript
interface EnhancedObjective {
  id: string;
  title: string;
  subtitle: string;
  definition: string;
  signals: string[];
  facet_questions: string[];
  exemplar_answer: string;
  
  // NEW:
  when_this_objective_is_wrong: string;  // "Don't use when..."
  minimum_info_needed: string[];         // Requirements checklist
  expected_output_format: string;        // What answer looks like
  confidence: "high" | "medium" | "low" | "uncertain";
  is_speculative: boolean;               // True if unsure
  rationale: string;                     // Why generated
  summary: ProgressiveDisclosure;        // Progressive disclosure
}
```

**ProgressiveDisclosure Structure**:

```typescript
interface ProgressiveDisclosure {
  tldr: string;                // 1-2 line summary
  key_tradeoffs: string[];     // Max 3 items
  next_actions: string[];      // Max 3 items
  details?: string;            // Optional full text
  glossary?: Record<string, string>;  // Optional terms
}
```

**QueryRefinement Structure**:

```typescript
interface QueryRefinement {
  refined_query: string;       // Improved query text
  what_changed: string;        // Brief description
  why_it_helps: string;        // Benefit explanation
  expected_benefit: string;
  confidence: "high" | "medium" | "low" | "uncertain";
}
```

**UncertaintyMarker Structure**:

```typescript
interface UncertaintyMarker {
  aspect: string;              // What is unclear
  uncertainty_type: "domain_knowledge" | "ambiguity" | "missing_context" | "conflicting_evidence";
  clarification_questions: string[];  // How to resolve
  fallback_recommendation?: string;   // What to do if unresolved
}
```

### 2.2 POST /augment

**New Fields**:

```typescript
interface AugmentResponseV2 {
  schema_version: string;
  evidence_items: EvidenceItem[];     // Enhanced with quality
  augmented_answer?: string;
  
  // NEW:
  grounded_claims: Claim[];           // Claims with evidence
  grounding_report?: GroundingReport; // Full grounding analysis
  extraction_confidence: string;      // "high", "medium", etc.
  need_external_sources: boolean;     // Flag if more info needed
  recommended_sources: string[];      // Suggested sources
}

interface EvidenceItem {
  id: string;
  type: string;
  title: string;
  snippet: string;
  source_ref: string;
  
  // NEW:
  source_quality: "primary" | "review" | "secondary" | "preprint" | "anecdotal" | "unknown";
  retrieval_method: string;    // "provided", "searched", etc.
  citation_key?: string;
}

interface Claim {
  claim_text: string;
  supporting_evidence_ids: string[];  // Links to evidence_items
  confidence: string;
  is_assumption: boolean;
  reasoning?: string;
}
```

### 2.3 POST /finalize

**New Fields**:

```typescript
interface FinalizeResponseV2 {
  schema_version: string;
  final_answer: string;
  assumptions: string[];
  next_questions: string[];
  
  // NEW:
  progressive_disclosure?: ProgressiveDisclosure;
  grounding_report?: GroundingReport;
  action_items: ActionItem[];
  claims: Claim[];
  follow_up_queries: QueryRefinement[];
}

interface ActionItem {
  action: string;
  priority: "high" | "medium" | "low";
  rationale: string;
  estimated_effort?: string;   // e.g., "2 hours"
}
```

---

## 3. New UI Components

### 3.1 Query Type Indicator

**Purpose**: Show users how their query was classified

**Design**:
```jsx
function QueryTypeIndicator({ routerInfo }) {
  const typeLabels = {
    ambiguity_preference: "Decision Help",
    factual_lookup: "Information Request",
    planning_protocol: "Planning",
    troubleshooting: "Problem Solving",
    synthesis_survey: "Comparison",
    methodology: "Methods",
    open_ideation: "Ideas"
  };
  
  return (
    <div className="query-type-indicator">
      <span className="type-badge">
        {typeLabels[routerInfo.query_type]}
      </span>
      <span className="confidence">
        Confidence: {Math.round(routerInfo.confidence * 100)}%
      </span>
      {routerInfo.missing_inputs.length > 0 && (
        <div className="missing-context">
          Missing: {routerInfo.missing_inputs.join(", ")}
        </div>
      )}
    </div>
  );
}
```

### 3.2 Progressive Disclosure Card

**Purpose**: Reduce cognitive load with tiered information

**Design**:
```jsx
function ProgressiveDisclosureCard({ data }) {
  const [showDetails, setShowDetails] = useState(false);
  
  return (
    <div className="progressive-card">
      {/* Always visible: TL;DR */}
      <div className="tldr">
        <strong>TL;DR:</strong> {data.tldr}
      </div>
      
      {/* Collapsible: Tradeoffs */}
      {data.key_tradeoffs.length > 0 && (
        <div className="tradeoffs">
          <h4>Key Tradeoffs</h4>
          <ul>
            {data.key_tradeoffs.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
        </div>
      )}
      
      {/* Action buttons */}
      {data.next_actions.length > 0 && (
        <div className="actions">
          <h4>Next Steps</h4>
          {data.next_actions.map((action, i) => (
            <button key={i} className="action-btn">
              {action}
            </button>
          ))}
        </div>
      )}
      
      {/* Expandable: Full details */}
      {data.details && (
        <div className="details-section">
          <button onClick={() => setShowDetails(!showDetails)}>
            {showDetails ? "Hide Details" : "Show Details"}
          </button>
          {showDetails && (
            <div className="details-content">
              {data.details}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

### 3.3 Uncertainty Banner

**Purpose**: Be transparent about system limitations

**Design**:
```jsx
function UncertaintyBanner({ markers }) {
  if (!markers || markers.length === 0) return null;
  
  return (
    <div className="uncertainty-banner">
      <h4>⚠️ I'm not certain about:</h4>
      {markers.map((marker, i) => (
        <div key={i} className="uncertainty-item">
          <p className="aspect">{marker.aspect}</p>
          <div className="clarification">
            <strong>Help me understand:</strong>
            <ul>
              {marker.clarification_questions.map((q, j) => (
                <li key={j}>{q}</li>
              ))}
            </ul>
          </div>
          {marker.fallback_recommendation && (
            <p className="fallback">
              <em>If unclear: {marker.fallback_recommendation}</em>
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
```

### 3.4 Query Refinement Suggestions

**Purpose**: Help users ask better questions

**Design**:
```jsx
function QueryRefinements({ refinements, onAdopt }) {
  if (!refinements || refinements.length === 0) return null;
  
  return (
    <div className="refinements-panel">
      <h4>💡 Want clearer results? Try:</h4>
      {refinements.map((refinement, i) => (
        <div key={i} className="refinement-card">
          <div className="refined-query">
            <strong>{refinement.refined_query}</strong>
            <button 
              onClick={() => onAdopt(refinement.refined_query)}
              className="adopt-btn"
            >
              Use This
            </button>
          </div>
          <div className="refinement-details">
            <p><strong>Changed:</strong> {refinement.what_changed}</p>
            <p><strong>Why:</strong> {refinement.why_it_helps}</p>
            <p><strong>Benefit:</strong> {refinement.expected_benefit}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
```

### 3.5 Enhanced Objective Card

**Purpose**: Display objectives with new metadata

**Design**:
```jsx
function EnhancedObjectiveCard({ objective, onSelect }) {
  const [expanded, setExpanded] = useState(false);
  
  return (
    <div className={`objective-card ${objective.is_speculative ? 'speculative' : ''}`}>
      {/* Header */}
      <div className="objective-header">
        <h3>{objective.title}</h3>
        {objective.is_speculative && (
          <span className="speculative-badge">Speculative</span>
        )}
        <span className={`confidence-badge ${objective.confidence}`}>
          {objective.confidence}
        </span>
      </div>
      
      {/* TL;DR */}
      <div className="objective-tldr">
        {objective.summary.tldr}
      </div>
      
      {/* Signals */}
      <div className="signals">
        {objective.signals.slice(0, 3).map((s, i) => (
          <span key={i} className="signal-tag">{s}</span>
        ))}
      </div>
      
      {/* Expandable content */}
      <button onClick={() => setExpanded(!expanded)}>
        {expanded ? "Less" : "More"}
      </button>
      
      {expanded && (
        <div className="objective-details">
          <p><strong>When this is wrong:</strong> {objective.when_this_objective_is_wrong}</p>
          
          {objective.minimum_info_needed.length > 0 && (
            <div className="requirements">
              <strong>Need to know:</strong>
              <ul>
                {objective.minimum_info_needed.map((req, i) => (
                  <li key={i}>{req}</li>
                ))}
              </ul>
            </div>
          )}
          
          <p><strong>Expected output:</strong> {objective.expected_output_format}</p>
          <p><strong>Why:</strong> {objective.rationale}</p>
          
          {/* Tradeoffs */}
          {objective.summary.key_tradeoffs.length > 0 && (
            <div className="tradeoffs">
              <strong>Tradeoffs:</strong>
              <ul>
                {objective.summary.key_tradeoffs.map((t, i) => (
                  <li key={i}>{t}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
      
      {/* Select button */}
      <button onClick={() => onSelect(objective)} className="select-btn">
        Select This Objective
      </button>
    </div>
  );
}
```

### 3.6 Grounding Panel

**Purpose**: Show evidence backing for claims

**Design**:
```jsx
function GroundingPanel({ groundingReport, evidenceItems }) {
  if (!groundingReport) return null;
  
  const evidenceMap = new Map(evidenceItems.map(e => [e.id, e]));
  
  return (
    <div className="grounding-panel">
      <h4>📚 Evidence & Grounding</h4>
      
      <div className="grounding-summary">
        <p><strong>Overall confidence:</strong> {groundingReport.overall_confidence}</p>
        <p>{groundingReport.evidence_summary}</p>
      </div>
      
      {/* Claims with evidence */}
      <div className="claims-list">
        <h5>Claims & Evidence</h5>
        {groundingReport.claims.map((claim, i) => (
          <div key={i} className={`claim-item ${claim.is_assumption ? 'assumption' : ''}`}>
            <p className="claim-text">
              {claim.is_assumption && "⚠️ Assumption: "}
              {claim.claim_text}
            </p>
            {!claim.is_assumption && claim.supporting_evidence_ids.length > 0 && (
              <div className="evidence-links">
                <strong>Supported by:</strong>
                {claim.supporting_evidence_ids.map(evId => {
                  const ev = evidenceMap.get(evId);
                  return ev ? (
                    <span key={evId} className="evidence-tag">
                      {ev.title} ({ev.source_quality})
                    </span>
                  ) : null;
                })}
              </div>
            )}
          </div>
        ))}
      </div>
      
      {/* Missing evidence */}
      {groundingReport.missing_evidence.length > 0 && (
        <div className="missing-evidence">
          <h5>Would strengthen with:</h5>
          <ul>
            {groundingReport.missing_evidence.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
```

### 3.7 Action Items List

**Purpose**: Show concrete next steps

**Design**:
```jsx
function ActionItemsList({ actionItems }) {
  if (!actionItems || actionItems.length === 0) return null;
  
  const priorityOrder = { high: 0, medium: 1, low: 2 };
  const sorted = [...actionItems].sort(
    (a, b) => priorityOrder[a.priority] - priorityOrder[b.priority]
  );
  
  return (
    <div className="action-items">
      <h4>✅ Action Items</h4>
      {sorted.map((item, i) => (
        <div key={i} className={`action-item priority-${item.priority}`}>
          <div className="action-header">
            <span className={`priority-badge ${item.priority}`}>
              {item.priority}
            </span>
            {item.estimated_effort && (
              <span className="effort">{item.estimated_effort}</span>
            )}
          </div>
          <p className="action-text">{item.action}</p>
          <p className="rationale"><em>{item.rationale}</em></p>
        </div>
      ))}
    </div>
  );
}
```

---

## 4. State Management

### 4.1 New State to Track

```typescript
interface AppState {
  // Existing
  query: string;
  context: string;
  objectives: EnhancedObjective[];
  selectedObjective: EnhancedObjective | null;
  
  // NEW: Query routing
  queryType: string | null;
  routerConfidence: number;
  missingInputs: string[];
  
  // NEW: UI state
  showUncertainties: boolean;
  adoptedRefinement: string | null;
  expandedObjectives: Set<string>;
  completedActions: Set<string>;
  
  // NEW: Tracking
  viewedRefinements: Set<number>;
  progressiveDisclosureState: {
    showDetails: boolean;
    showTradeoffs: boolean;
    showGlossary: boolean;
  };
}
```

### 4.2 Event Tracking

Track these user interactions for evaluation:

```javascript
// Log when user views refinements
trackEvent('query_refinement_viewed', {
  refinement_index: index,
  refinement_type: 'specificity'
});

// Log when user adopts refinement
trackEvent('query_refinement_adopted', {
  original_query: originalQuery,
  refined_query: adoptedQuery
});

// Log progressive disclosure interactions
trackEvent('progressive_disclosure_interaction', {
  interaction_type: 'expand_details',
  element_id: 'objective_1_details',
  time_after_objectives_ms: Date.now() - objectivesTimestamp
});

// Log action item completion
trackEvent('action_item_completed', {
  action_id: actionId,
  priority: 'high',
  completion_time_ms: timeToComplete
});
```

---

## 5. Migration Steps

### Step 1: Update Type Definitions

```bash
# Add new types
npm install -D @types/seci-explorer-v2

# Or manually update your types
```

### Step 2: Create New Components

1. Create `QueryTypeIndicator.tsx`
2. Create `ProgressiveDisclosureCard.tsx`
3. Create `UncertaintyBanner.tsx`
4. Create `QueryRefinements.tsx`
5. Update `ObjectiveCard.tsx` to use EnhancedObjective
6. Create `GroundingPanel.tsx`
7. Create `ActionItemsList.tsx`

### Step 3: Update API Layer

```typescript
// api.ts
export async function generateObjectives(request: ObjectivesRequest): Promise<ObjectivesResponse> {
  const response = await fetch('/objectives', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ...request,
      schema_version: "2.0.0"  // Request v2 format
    })
  });
  
  const data = await response.json();
  
  // Handle both v1 and v2 responses
  if (data.schema_version === "2.0.0") {
    return data as ObjectivesResponseV2;
  }
  
  // Fallback for legacy
  return {
    ...data,
    schema_version: "1.0.0",
    router_info: null,
    query_refinements: [],
    uncertainty_markers: [],
    progressive_summary: null
  };
}
```

### Step 4: Update Main Flow

```tsx
// Main.tsx
function QueryExplorer() {
  const [state, setState] = useState<AppState>({
    query: '',
    context: '',
    objectives: [],
    // ... rest of state
  });
  
  const handleGenerateObjectives = async () => {
    const response = await generateObjectives({
      query: state.query,
      context: state.context,
      k: 5
    });
    
    setState(prev => ({
      ...prev,
      objectives: response.objectives,
      queryType: response.router_info?.query_type,
      routerConfidence: response.router_info?.confidence,
      missingInputs: response.router_info?.missing_inputs || [],
      // Store new fields
      query_refinements: response.query_refinements,
      uncertainty_markers: response.uncertainty_markers,
      progressive_summary: response.progressive_summary
    }));
  };
  
  return (
    <div className="query-explorer">
      {/* Query input */}
      
      {/* NEW: Query type indicator */}
      {state.queryType && (
        <QueryTypeIndicator routerInfo={{
          query_type: state.queryType,
          confidence: state.routerConfidence,
          missing_inputs: state.missingInputs,
          recommended_workflow: '',
          context_hints: {}
        }} />
      )}
      
      {/* NEW: Uncertainty banner */}
      {state.uncertainty_markers && state.uncertainty_markers.length > 0 && (
        <UncertaintyBanner markers={state.uncertainty_markers} />
      )}
      
      {/* NEW: Query refinements */}
      {state.query_refinements && state.query_refinements.length > 0 && (
        <QueryRefinements 
          refinements={state.query_refinements}
          onAdopt={(refined) => {
            setState(prev => ({ ...prev, query: refined }));
            // Re-generate with refined query
            handleGenerateObjectives();
          }}
        />
      )}
      
      {/* Objectives list */}
      {state.objectives.map(obj => (
        <EnhancedObjectiveCard
          key={obj.id}
          objective={obj}
          onSelect={(obj) => setState(prev => ({ 
            ...prev, 
            selectedObjective: obj 
          }))}
        />
      ))}
    </div>
  );
}
```

### Step 5: Update Finalize Flow

```tsx
// Finalize.tsx
function FinalizeAnswer({ request }) {
  const [response, setResponse] = useState<FinalizeResponseV2 | null>(null);
  
  useEffect(() => {
    finalizeAnswer(request).then(setResponse);
  }, []);
  
  if (!response) return <Loading />;
  
  return (
    <div className="finalize-result">
      {/* Progressive disclosure */}
      {response.progressive_disclosure && (
        <ProgressiveDisclosureCard data={response.progressive_disclosure} />
      )}
      
      {/* Grounding panel */}
      {response.grounding_report && (
        <GroundingPanel 
          groundingReport={response.grounding_report}
          evidenceItems={request.evidence_items || []}
        />
      )}
      
      {/* Full answer */}
      <div className="final-answer">
        {response.final_answer}
      </div>
      
      {/* Action items */}
      {response.action_items && response.action_items.length > 0 && (
        <ActionItemsList actionItems={response.action_items} />
      )}
      
      {/* Follow-up queries */}
      {response.follow_up_queries && response.follow_up_queries.length > 0 && (
        <div className="follow-ups">
          <h4>Want to explore further?</h4>
          {response.follow_up_queries.map((ref, i) => (
            <button key={i} onClick={() => loadQuery(ref.refined_query)}>
              {ref.refined_query}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

---

## 6. Styling Recommendations

### 6.1 Color Coding

```css
/* Confidence levels */
.confidence-high { color: #22c55e; }
.confidence-medium { color: #eab308; }
.confidence-low { color: #f97316; }
.confidence-uncertain { color: #ef4444; }

/* Priority */
.priority-high { border-left: 4px solid #ef4444; }
.priority-medium { border-left: 4px solid #eab308; }
.priority-low { border-left: 4px solid #22c55e; }

/* Speculative objectives */
.speculative {
  background: #fef3c7;
  border: 1px dashed #f59e0b;
}
```

### 6.2 Progressive Disclosure UX

- Always show TL;DR prominently
- Use visual hierarchy for tradeoffs
- Make action buttons prominent
- Use accordions for details
- Show "(X words)" for expandable sections

### 6.3 Uncertainty UX

- Use warning icons sparingly
- Provide clear paths forward
- Don't overwhelm with multiple uncertainties
- Highlight actionable clarification questions

---

## 7. Testing Checklist

### 7.1 Component Tests

- [ ] QueryTypeIndicator shows correct type and confidence
- [ ] ProgressiveDisclosureCard expands/collapses correctly
- [ ] UncertaintyBanner displays all markers
- [ ] QueryRefinements handle adoption correctly
- [ ] EnhancedObjectiveCard shows all metadata
- [ ] GroundingPanel maps claims to evidence
- [ ] ActionItemsList sorts by priority

### 7.2 Integration Tests

- [ ] Full workflow: query → objectives → augment → finalize
- [ ] Query refinement adoption reloads objectives
- [ ] Progressive disclosure state persists
- [ ] Action item completion tracked
- [ ] All v2 fields handled correctly

### 7.3 Edge Cases

- [ ] Empty uncertainty_markers
- [ ] No query_refinements
- [ ] Speculative objectives highlighted
- [ ] Missing grounding_report
- [ ] Legacy response handling

---

## 8. Performance Considerations

### 8.1 Lazy Loading

```tsx
// Lazy load heavy components
const GroundingPanel = lazy(() => import('./GroundingPanel'));
const ProgressiveDisclosureCard = lazy(() => import('./ProgressiveDisclosureCard'));
```

### 8.2 Memoization

```tsx
// Memoize expensive renders
const MemoizedObjectiveCard = memo(EnhancedObjectiveCard, (prev, next) => {
  return prev.objective.id === next.objective.id;
});
```

### 8.3 Virtual Lists

For many objectives or evidence items:
```tsx
<VirtualizedList
  items={objectives}
  renderItem={(obj) => <EnhancedObjectiveCard objective={obj} />}
/>
```

---

## 9. Accessibility

### 9.1 ARIA Labels

```tsx
<div 
  role="region" 
  aria-label="Uncertainty warnings"
  className="uncertainty-banner"
>
  {/* content */}
</div>

<button
  aria-expanded={expanded}
  aria-controls="details-section"
  onClick={() => setExpanded(!expanded)}
>
  {expanded ? "Hide Details" : "Show Details"}
</button>
```

### 9.2 Keyboard Navigation

- Tab through action items
- Enter/Space to expand/collapse
- Escape to close modals/panels

### 9.3 Screen Reader Support

- Announce confidence levels
- Read uncertainty markers
- Describe progressive disclosure state

---

## 10. Common Pitfalls

### ❌ Don't

1. **Don't hide all objectives behind click** - Show TL;DRs immediately
2. **Don't overwhelm with uncertainties** - Show max 2-3 at once
3. **Don't auto-adopt refinements** - Let users choose
4. **Don't ignore legacy responses** - Handle v1.0 gracefully
5. **Don't block on missing inputs** - Work with what you have

### ✅ Do

1. **Do prioritize cognitive load** - Progressive disclosure helps
2. **Do make confidence visible** - Users should know certainty levels
3. **Do enable refinement adoption** - One-click improvements
4. **Do track user interactions** - For evaluation
5. **Do provide fallback paths** - When system is uncertain

---

**Version**: 2.0.0
**Last Updated**: 2024-01-15
**Contact**: Engineering Team