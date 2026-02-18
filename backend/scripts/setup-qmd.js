#!/usr/bin/env node
/**
 * QMD Setup Script for DSM Interface
 * 
 * Initializes QMD collections for the SECI context structure
 */

const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const CONTEXT_ROOT = path.join(__dirname, '..', 'data', 'context');

// Collection definitions
const COLLECTIONS = [
  { path: path.join(CONTEXT_ROOT, 'seci', 'S_socialization'), name: 'socialization' },
  { path: path.join(CONTEXT_ROOT, 'seci', 'E_externalization'), name: 'externalization' },
  { path: path.join(CONTEXT_ROOT, 'seci', 'C_combination'), name: 'combination' },
  { path: path.join(CONTEXT_ROOT, 'seci', 'I_internalization'), name: 'internalization' },
  { path: path.join(CONTEXT_ROOT, 'persona'), name: 'persona' },
  { path: path.join(CONTEXT_ROOT, 'behavior'), name: 'behavior' },
  { path: path.join(CONTEXT_ROOT, 'tools'), name: 'tools' },
  { path: path.join(CONTEXT_ROOT, 'sessions'), name: 'sessions' },
  { path: path.join(CONTEXT_ROOT, 'history'), name: 'history' },
  { path: path.join(CONTEXT_ROOT, 'pad'), name: 'pad' },
];

// Context metadata for search relevance
const CONTEXTS = [
  { collection: 'socialization', description: 'Tacit knowledge: field notes, observations, norms, constraints, cultural context' },
  { collection: 'externalization', description: 'Explicit knowledge: hypotheses, assumptions, decision rationales, articulated insights' },
  { collection: 'combination', description: 'Synthesized knowledge: literature summaries, protocol syntheses, evidence tables' },
  { collection: 'internalization', description: 'Operational knowledge: playbooks, checklists, lessons learned, procedures' },
  { collection: 'persona', description: 'User profiles, preferences, capabilities, risk posture, interaction style' },
  { collection: 'behavior', description: 'Behavioral calibration: belief states, reliability models, delegation policies, telemetry' },
  { collection: 'tools', description: 'Tool metadata, function definitions, API documentation' },
  { collection: 'sessions', description: 'Session artifacts, temporary working notes, conversation history' },
  { collection: 'history', description: 'Immutable interaction logs, audit trail across agents and sessions' },
  { collection: 'pad', description: 'Scratchpad notes, temporary working memory, draft content' },
];

function exec(cmd, description) {
  console.log(`\n→ ${description || cmd}`);
  try {
    const result = execSync(cmd, { encoding: 'utf-8', stdio: 'pipe' });
    if (result) console.log(result.trim());
    return result;
  } catch (err) {
    console.error(`Error: ${err.message}`);
    if (err.stderr) console.error(err.stderr);
    return null;
  }
}

function ensureDirectory(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
    console.log(`Created directory: ${dir}`);
  }
}

function setup() {
  console.log('═══════════════════════════════════════════════════════════════');
  console.log('  QMD Setup for DSM Interface - SECI Context Structure');
  console.log('═══════════════════════════════════════════════════════════════\n');
  
  // Ensure context root exists
  ensureDirectory(CONTEXT_ROOT);
  
  // Create all SECI subdirectories
  console.log('\n📁 Setting up directory structure...\n');
  
  const seciDirs = [
    'seci/S_socialization/field_notes',
    'seci/S_socialization/shadowing_transcripts',
    'seci/S_socialization/norms_and_constraints',
    'seci/S_socialization/disagreements',
    'seci/E_externalization/elicited_hypotheses',
    'seci/E_externalization/assumptions_register',
    'seci/E_externalization/decision_rationales',
    'seci/C_combination/literature_summaries',
    'seci/C_combination/protocol_syntheses',
    'seci/C_combination/evidence_tables',
    'seci/I_internalization/playbooks',
    'seci/I_internalization/checklists',
    'seci/I_internalization/lessons_learned',
    'persona/capabilities',
    'persona/risk_posture',
    'persona/interaction_style',
    'behavior/calibration',
    'behavior/telemetry',
  ];
  
  seciDirs.forEach(dir => ensureDirectory(path.join(CONTEXT_ROOT, dir)));
  
  // Add collections
  console.log('\n📚 Adding QMD collections...\n');
  
  COLLECTIONS.forEach(({ path: dirPath, name }) => {
    ensureDirectory(dirPath);
    exec(`qmd collection add "${dirPath}" --name ${name}`, `Adding collection: ${name}`);
  });
  
  // Add context metadata
  console.log('\n🏷️  Adding context metadata...\n');
  
  CONTEXTS.forEach(({ collection, description }) => {
    exec(`qmd context add qmd://${collection} "${description}"`, `Adding context for: ${collection}`);
  });
  
  // Generate embeddings
  console.log('\n🧠 Generating embeddings (this may take a while)...\n');
  exec('qmd embed', 'Generating embeddings for semantic search');
  
  console.log('\n✅ Setup complete!\n');
  console.log('═══════════════════════════════════════════════════════════════');
  console.log('  Available collections:');
  COLLECTIONS.forEach(({ name }) => console.log(`    • ${name}`));
  console.log('═══════════════════════════════════════════════════════════════\n');
  
  console.log('Next steps:');
  console.log('  1. Add markdown files to the context directories');
  console.log('  2. Run "qmd embed" again after adding new files');
  console.log('  3. Test search: qmd query "your search term"\n');
}

// Run setup
setup();
