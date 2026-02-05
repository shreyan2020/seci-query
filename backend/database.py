import sqlite3
import json
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any
from models import LogEventRequest

class DatabaseManager:
    def __init__(self, db_path: str = "data/undspecified_queries.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the SQLite database with required tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create events table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                payload TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create priors table
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
        
        conn.commit()
        conn.close()
    
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

# Global database instance
db = DatabaseManager()