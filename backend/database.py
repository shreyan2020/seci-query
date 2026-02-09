import sqlite3
import json
import hashlib
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from models import LogEventRequest

class DatabaseManager:
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Get the directory where this file is located
            current_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(current_dir, "data", "undspecified_queries.db")
        self.db_path = db_path
        # Ensure the data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_database()
    
    def init_database(self):
        """Initialize the SQLite database with required tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create events table (existing)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                payload TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create priors table (existing)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS priors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_signature TEXT UNIQUE NOT NULL,
                objective_id TEXT,
                common_facet_answers TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # NEW: User sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT,  -- NULL for anonymous users
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_active_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                total_queries INTEGER DEFAULT 0,
                total_objectives_selected INTEGER DEFAULT 0,
                total_answers_finalized INTEGER DEFAULT 0,
                session_metadata TEXT  -- JSON with device, browser, etc.
            )
        ''')
        
        # NEW: User persona table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_personas (
                user_id TEXT PRIMARY KEY,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                
                -- Preferences
                preferred_query_types TEXT,  -- JSON array of preferred types
                preferred_objective_types TEXT,  -- JSON array of objective characteristics
                preferred_depth_level TEXT,  -- "brief", "detailed", "comprehensive"
                
                -- Behavioral patterns
                avg_time_to_objective_selection REAL,  -- in seconds
                avg_facet_questions_answered REAL,
                frequently_used_signals TEXT,  -- JSON array
                commonly_selected_objectives TEXT,  -- JSON object with counts
                
                -- Domain knowledge
                domain_expertise TEXT,  -- JSON object {domain: level}
                frequently_asked_domains TEXT,  -- JSON array
                
                -- Constraints and preferences from answers
                typical_constraints TEXT,  -- JSON object {constraint_type: frequency}
                preferred_evidence_sources TEXT,  -- JSON array
                
                -- Query patterns
                query_complexity_trend TEXT,  -- "increasing", "decreasing", "stable"
                common_query_patterns TEXT,  -- JSON array of regex patterns
                
                -- Performance metrics
                satisfaction_scores TEXT,  -- JSON array of ratings
                success_rate REAL,  -- % of queries that led to finalize
                
                -- Persona metadata
                persona_version INTEGER DEFAULT 1,
                last_query_at DATETIME
            )
        ''')
        
        # NEW: Query interactions table (detailed interaction tracking)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS query_interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                user_id TEXT,
                query_signature TEXT NOT NULL,
                query_text TEXT NOT NULL,
                query_type TEXT,
                query_type_confidence REAL,
                
                -- Timing
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                objectives_generated_at DATETIME,
                objective_selected_at DATETIME,
                answers_submitted_at DATETIME,
                finalized_at DATETIME,
                total_duration_ms INTEGER,
                
                -- Selection details
                selected_objective_id TEXT,
                selected_objective_confidence TEXT,
                is_speculative_selection BOOLEAN,
                
                -- Facet answers
                facet_answers TEXT,  -- JSON object
                num_facet_questions_answered INTEGER,
                
                -- Evidence
                evidence_count INTEGER,
                evidence_sources TEXT,  -- JSON array
                
                -- Outcome
                final_answer TEXT,
                assumptions_made TEXT,  -- JSON array
                action_items TEXT,  -- JSON array
                
                -- Feedback
                user_satisfaction INTEGER,  -- 1-5 rating
                was_helpful BOOLEAN,
                feedback_text TEXT,
                
                -- Refinement tracking
                refinement_adopted TEXT,
                refinement_improvement TEXT,
                
                FOREIGN KEY (session_id) REFERENCES user_sessions(session_id)
            )
        ''')
        
        # NEW: User feedback table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                user_id TEXT,
                query_signature TEXT,
                feedback_type TEXT,  -- "objective_relevance", "answer_quality", "grounding_satisfaction"
                rating INTEGER,  -- 1-5
                comment TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (session_id) REFERENCES user_sessions(session_id)
            )
        ''')
        
        # NEW: Objective selection history
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS objective_selections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                user_id TEXT,
                query_signature TEXT,
                objective_id TEXT,
                objective_title TEXT,
                objective_type TEXT,
                selection_context TEXT,  -- JSON with surrounding info
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (session_id) REFERENCES user_sessions(session_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        print("Database initialized with enhanced schema for persona tracking")
    
    def log_event(self, event_request: LogEventRequest):
        """Log an event to the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO events (event_type, payload)
            VALUES (?, ?)
        ''', (event_request.event_type, json.dumps(event_request.payload)))
        
        conn.commit()
        conn.close()
    
    def get_prior(self, query_signature: str) -> Optional[Dict[str, Any]]:
        """Retrieve prior information for a query signature."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT objective_id, common_facet_answers
            FROM priors
            WHERE query_signature = ?
        ''', (query_signature,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            objective_id, common_facet_answers = result
            return {
                "objective_id": objective_id,
                "common_facet_answers": json.loads(common_facet_answers) if common_facet_answers else {}
            }
        return None
    
    def update_prior(self, query_signature: str, objective_id: str, facet_answers: Dict[str, str]):
        """Update prior information for a query signature."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO priors (query_signature, objective_id, common_facet_answers, updated_at)
            VALUES (?, ?, ?, ?)
        ''', (query_signature, objective_id, json.dumps(facet_answers), datetime.now()))
        
        conn.commit()
        conn.close()
    
    def query_signature(self, query: str) -> str:
        """Generate a simple hash signature for a query."""
        return hashlib.md5(query.lower().strip().encode()).hexdigest()[:16]
    
    # ============================================================================
    # NEW: User Session Management
    # ============================================================================
    
    def create_session(self, session_id: str, user_id: Optional[str] = None, metadata: Optional[Dict] = None):
        """Create a new user session."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO user_sessions (session_id, user_id, session_metadata)
            VALUES (?, ?, ?)
        ''', (session_id, user_id, json.dumps(metadata) if metadata else None))
        
        conn.commit()
        conn.close()
    
    def update_session_activity(self, session_id: str):
        """Update last active timestamp for a session."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE user_sessions 
            SET last_active_at = CURRENT_TIMESTAMP
            WHERE session_id = ?
        ''', (session_id,))
        
        conn.commit()
        conn.close()
    
    def increment_session_stats(self, session_id: str, field: str):
        """Increment a session counter (total_queries, total_objectives_selected, etc.)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(f'''
            UPDATE user_sessions 
            SET {field} = {field} + 1
            WHERE session_id = ?
        ''', (session_id,))
        
        conn.commit()
        conn.close()
    
    # ============================================================================
    # NEW: User Persona Management
    # ============================================================================
    
    def get_or_create_persona(self, user_id: str) -> Dict[str, Any]:
        """Get existing persona or create a new one."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM user_personas WHERE user_id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        
        if result:
            # Parse existing persona
            columns = [description[0] for description in cursor.description]
            persona = dict(zip(columns, result))
            
            # Parse JSON fields
            json_fields = [
                'preferred_query_types', 'preferred_objective_types', 'frequently_used_signals',
                'commonly_selected_objectives', 'domain_expertise', 'frequently_asked_domains',
                'typical_constraints', 'preferred_evidence_sources', 'common_query_patterns',
                'satisfaction_scores'
            ]
            
            for field in json_fields:
                if persona.get(field):
                    try:
                        persona[field] = json.loads(persona[field])
                    except:
                        persona[field] = None
            
            conn.close()
            return persona
        else:
            # Create new persona with defaults
            cursor.execute('''
                INSERT INTO user_personas (user_id)
                VALUES (?)
            ''', (user_id,))
            
            conn.commit()
            conn.close()
            
            return {
                'user_id': user_id,
                'preferred_query_types': [],
                'preferred_objective_types': [],
                'preferred_depth_level': 'detailed',
                'frequently_used_signals': [],
                'commonly_selected_objectives': {},
                'domain_expertise': {},
                'frequently_asked_domains': [],
                'typical_constraints': {},
                'preferred_evidence_sources': [],
                'satisfaction_scores': [],
                'success_rate': 0.0
            }
    
    def update_persona(self, user_id: str, updates: Dict[str, Any]):
        """Update user persona with new information."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Build dynamic update query
        json_fields = [
            'preferred_query_types', 'preferred_objective_types', 'frequently_used_signals',
            'commonly_selected_objectives', 'domain_expertise', 'frequently_asked_domains',
            'typical_constraints', 'preferred_evidence_sources', 'common_query_patterns',
            'satisfaction_scores'
        ]
        
        set_clauses = []
        values = []
        
        for key, value in updates.items():
            if key in json_fields:
                set_clauses.append(f"{key} = ?")
                values.append(json.dumps(value))
            else:
                set_clauses.append(f"{key} = ?")
                values.append(value)
        
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        set_clauses.append("persona_version = persona_version + 1")
        values.append(user_id)
        
        query = f'''
            UPDATE user_personas 
            SET {', '.join(set_clauses)}
            WHERE user_id = ?
        '''
        
        cursor.execute(query, values)
        conn.commit()
        conn.close()
    
    def record_query_interaction(self, interaction_data: Dict[str, Any]):
        """Record a detailed query interaction."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Serialize JSON fields
        json_fields = ['facet_answers', 'assumptions_made', 'action_items', 'evidence_sources', 'selection_context']
        for field in json_fields:
            if field in interaction_data and interaction_data[field] is not None:
                interaction_data[field] = json.dumps(interaction_data[field])
        
        cursor.execute('''
            INSERT INTO query_interactions (
                session_id, user_id, query_signature, query_text, query_type, query_type_confidence,
                created_at, selected_objective_id, selected_objective_confidence, is_speculative_selection,
                facet_answers, num_facet_questions_answered, evidence_count, evidence_sources,
                final_answer, assumptions_made, action_items, refinement_adopted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            interaction_data.get('session_id'),
            interaction_data.get('user_id'),
            interaction_data.get('query_signature'),
            interaction_data.get('query_text'),
            interaction_data.get('query_type'),
            interaction_data.get('query_type_confidence'),
            datetime.now(),
            interaction_data.get('selected_objective_id'),
            interaction_data.get('selected_objective_confidence'),
            interaction_data.get('is_speculative_selection'),
            interaction_data.get('facet_answers'),
            interaction_data.get('num_facet_questions_answered'),
            interaction_data.get('evidence_count'),
            interaction_data.get('evidence_sources'),
            interaction_data.get('final_answer'),
            interaction_data.get('assumptions_made'),
            interaction_data.get('action_items'),
            interaction_data.get('refinement_adopted')
        ))
        
        conn.commit()
        conn.close()
    
    def get_user_interaction_history(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent interaction history for a user."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM query_interactions
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        ''', (user_id, limit))
        
        columns = [description[0] for description in cursor.description]
        results = []
        
        for row in cursor.fetchall():
            result = dict(zip(columns, row))
            # Parse JSON fields
            for field in ['facet_answers', 'evidence_sources', 'assumptions_made', 'action_items']:
                if result.get(field):
                    try:
                        result[field] = json.loads(result[field])
                    except:
                        result[field] = None
            results.append(result)
        
        conn.close()
        return results
    
    def analyze_user_patterns(self, user_id: str) -> Dict[str, Any]:
        """Analyze patterns from user interaction history for persona updates."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get query type distribution
        cursor.execute('''
            SELECT query_type, COUNT(*) as count
            FROM query_interactions
            WHERE user_id = ?
            GROUP BY query_type
            ORDER BY count DESC
        ''', (user_id,))
        
        query_type_dist = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Get average metrics
        cursor.execute('''
            SELECT 
                AVG(CASE WHEN objective_selected_at IS NOT NULL 
                    THEN (julianday(objective_selected_at) - julianday(created_at)) * 86400 
                    END) as avg_time_to_selection,
                AVG(num_facet_questions_answered) as avg_facet_answered,
                AVG(CASE WHEN finalized_at IS NOT NULL THEN 1.0 ELSE 0.0 END) as success_rate,
                COUNT(DISTINCT query_type) as query_type_diversity
            FROM query_interactions
            WHERE user_id = ?
        ''', (user_id,))
        
        metrics = cursor.fetchone()
        
        # Get most common domains from query text
        cursor.execute('''
            SELECT query_text FROM query_interactions
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 20
        ''', (user_id,))
        
        recent_queries = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            'query_type_distribution': query_type_dist,
            'avg_time_to_selection_seconds': metrics[0],
            'avg_facet_questions_answered': metrics[1],
            'success_rate': metrics[2],
            'query_type_diversity': metrics[3],
            'recent_queries': recent_queries
        }
    
    def get_user_statistics(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive statistics for a user."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                COUNT(*) as total_queries,
                COUNT(DISTINCT query_type) as unique_query_types,
                AVG(user_satisfaction) as avg_satisfaction,
                SUM(CASE WHEN finalized_at IS NOT NULL THEN 1 ELSE 0 END) as completed_queries,
                MIN(created_at) as first_query,
                MAX(created_at) as last_query
            FROM query_interactions
            WHERE user_id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        return {
            'total_queries': result[0],
            'unique_query_types': result[1],
            'avg_satisfaction': result[2],
            'completed_queries': result[3],
            'completion_rate': (result[3] / result[0] * 100) if result[0] > 0 else 0,
            'first_query': result[4],
            'last_query': result[5]
        }

# Global database instance
db = DatabaseManager()