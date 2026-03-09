import sqlite3
import json
import hashlib
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from models import LogEventRequest

class DatabaseManager:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.getenv("DATABASE_PATH", "data/undspecified_queries.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_database()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Initialize the SQLite database with required tables."""
        conn = self._connect()
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

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                objective_id TEXT,
                persona_id INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'draft',
                qmd_path TEXT NOT NULL,
                last_output_html_path TEXT,
                last_output_pdf_path TEXT,
                last_render_at DATETIME,
                content_hash TEXT,
                last_manifest_path TEXT,
                last_log_path TEXT,
                error_message TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS render_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                started_at DATETIME,
                finished_at DATETIME,
                params_json TEXT,
                engine TEXT DEFAULT 'python',
                output_formats TEXT,
                lock_owner TEXT,
                log_path TEXT,
                error_message TEXT,
                FOREIGN KEY(report_id) REFERENCES reports(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS personas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                scope TEXT NOT NULL,
                identity_key TEXT,
                source TEXT NOT NULL DEFAULT 'interviews',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                persona_json TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                last_summary TEXT NOT NULL DEFAULT ''
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS interviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope TEXT NOT NULL,
                transcript_path TEXT,
                transcript_text TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                metadata_json TEXT
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_render_jobs_status_created
            ON render_jobs(status, created_at)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_personas_scope
            ON personas(scope)
        ''')

        try:
            cursor.execute("ALTER TABLE personas ADD COLUMN identity_key TEXT")
        except sqlite3.OperationalError:
            pass

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_personas_scope_name_norm
            ON personas(lower(trim(scope)), lower(trim(name)))
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_personas_scope_identity
            ON personas(lower(trim(scope)), identity_key)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_interviews_scope
            ON interviews(scope)
        ''')
        
        conn.commit()
        conn.close()
    
    def log_event(self, event_request: LogEventRequest):
        """Log an event to the database."""
        conn = self._connect()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO events (event_type, payload)
            VALUES (?, ?)
        ''', (event_request.event_type, json.dumps(event_request.payload)))
        
        conn.commit()
        conn.close()
    
    def get_prior(self, query_signature: str) -> Optional[Dict[str, Any]]:
        """Retrieve prior information for a query signature."""
        conn = self._connect()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT objective_id, common_facet_answers
            FROM priors
            WHERE query_signature = ?
        ''', (query_signature,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            objective_id, common_facet_answers = result[0], result[1]
            return {
                "objective_id": objective_id,
                "common_facet_answers": json.loads(common_facet_answers) if common_facet_answers else {}
            }
        return None
    
    def update_prior(self, query_signature: str, objective_id: str, facet_answers: Dict[str, str]):
        """Update prior information for a query signature."""
        conn = self._connect()
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

    def create_report(self, title: str, qmd_path: str, objective_id: Optional[str] = None) -> int:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO reports (title, objective_id, qmd_path, status, content_hash)
            VALUES (?, ?, ?, 'draft', '')
            ''',
            (title, objective_id, qmd_path),
        )
        report_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return int(report_id)

    def get_report(self, report_id: int) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM reports WHERE id = ?', (report_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def list_reports_for_objective(self, objective_id: str) -> List[Dict[str, Any]]:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM reports WHERE objective_id = ? ORDER BY updated_at DESC', (objective_id,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    def list_reports(self, objective_id: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self._connect()
        cursor = conn.cursor()
        if objective_id:
            cursor.execute('SELECT * FROM reports WHERE objective_id = ? ORDER BY updated_at DESC', (objective_id,))
        else:
            cursor.execute('SELECT * FROM reports ORDER BY updated_at DESC')
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    def update_report_qmd(self, report_id: int, content_hash: str):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            '''
            UPDATE reports
            SET content_hash = ?, updated_at = CURRENT_TIMESTAMP, status = 'draft', error_message = NULL
            WHERE id = ?
            ''',
            (content_hash, report_id),
        )
        conn.commit()
        conn.close()

    def set_report_qmd_path(self, report_id: int, qmd_path: str):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            '''
            UPDATE reports
            SET qmd_path = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            ''',
            (qmd_path, report_id),
        )
        conn.commit()
        conn.close()

    def update_report_status(
        self,
        report_id: int,
        status: str,
        error_message: Optional[str] = None,
        persona_id: Optional[int] = None,
    ):
        conn = self._connect()
        cursor = conn.cursor()
        if persona_id is None:
            cursor.execute(
                '''
                UPDATE reports
                SET status = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                ''',
                (status, error_message, report_id),
            )
        else:
            cursor.execute(
                '''
                UPDATE reports
                SET status = ?, error_message = ?, persona_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                ''',
                (status, error_message, persona_id, report_id),
            )
        conn.commit()
        conn.close()

    def update_report_render_result(
        self,
        report_id: int,
        html_path: Optional[str],
        pdf_path: Optional[str],
        manifest_path: str,
        log_path: str,
        status: str,
        error_message: Optional[str] = None,
    ):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            '''
            UPDATE reports
            SET status = ?,
                last_output_html_path = COALESCE(?, last_output_html_path),
                last_output_pdf_path = COALESCE(?, last_output_pdf_path),
                last_manifest_path = ?,
                last_log_path = ?,
                last_render_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP,
                error_message = ?
            WHERE id = ?
            ''',
            (status, html_path, pdf_path, manifest_path, log_path, error_message, report_id),
        )
        conn.commit()
        conn.close()

    def enqueue_render_job(
        self,
        report_id: int,
        params: Dict[str, Any],
        output_formats: List[str],
        engine: str = "python",
    ) -> int:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO render_jobs (report_id, status, params_json, output_formats, engine)
            VALUES (?, 'queued', ?, ?, ?)
            ''',
            (report_id, json.dumps(params), json.dumps(output_formats), engine),
        )
        job_id = cursor.lastrowid
        cursor.execute(
            '''
            UPDATE reports SET status='queued', updated_at=CURRENT_TIMESTAMP, error_message=NULL WHERE id=?
            ''',
            (report_id,),
        )
        conn.commit()
        conn.close()
        return int(job_id)

    def get_latest_render_job_for_report(self, report_id: int) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT * FROM render_jobs
            WHERE report_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            ''',
            (report_id,),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def claim_next_render_job(self, worker_id: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            '''
            SELECT * FROM render_jobs
            WHERE status='queued'
            ORDER BY created_at ASC, id ASC
            LIMIT 1
            '''
        )
        row = cursor.fetchone()
        if not row:
            conn.commit()
            conn.close()
            return None

        job_id = row["id"]
        cursor.execute(
            '''
            UPDATE render_jobs
            SET status='running', started_at=CURRENT_TIMESTAMP, lock_owner=?
            WHERE id=? AND status='queued'
            ''',
            (worker_id, job_id),
        )
        if cursor.rowcount != 1:
            conn.commit()
            conn.close()
            return None

        cursor.execute(
            '''
            UPDATE reports
            SET status='running', updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            ''',
            (row["report_id"],),
        )
        conn.commit()
        cursor.execute('SELECT * FROM render_jobs WHERE id = ?', (job_id,))
        claimed = cursor.fetchone()
        conn.close()
        return dict(claimed) if claimed else None

    def update_render_job_result(self, job_id: int, status: str, log_path: str, error_message: Optional[str] = None):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            '''
            UPDATE render_jobs
            SET status=?, finished_at=CURRENT_TIMESTAMP, log_path=?, error_message=?
            WHERE id=?
            ''',
            (status, log_path, error_message, job_id),
        )
        conn.commit()
        conn.close()

    def create_interview(
        self,
        scope: str,
        transcript_text: Optional[str],
        transcript_path: Optional[str],
        metadata_json: Dict[str, Any],
    ) -> int:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO interviews (scope, transcript_path, transcript_text, metadata_json)
            VALUES (?, ?, ?, ?)
            ''',
            (scope, transcript_path, transcript_text, json.dumps(metadata_json)),
        )
        interview_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return int(interview_id)

    def get_interview_by_scope_path(self, scope: str, transcript_path: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT * FROM interviews
            WHERE scope = ? AND transcript_path = ?
            ORDER BY id DESC
            LIMIT 1
            ''',
            (scope, transcript_path),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        payload = dict(row)
        payload["metadata_json"] = json.loads(payload.get("metadata_json") or "{}")
        return payload

    def get_interviews(self, scope: str, interview_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        conn = self._connect()
        cursor = conn.cursor()
        if interview_ids:
            placeholders = ",".join(["?" for _ in interview_ids])
            cursor.execute(
                f'''
                SELECT * FROM interviews WHERE scope = ? AND id IN ({placeholders}) ORDER BY created_at ASC
                ''',
                [scope, *interview_ids],
            )
        else:
            cursor.execute('SELECT * FROM interviews WHERE scope = ? ORDER BY created_at ASC', (scope,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        for row in rows:
            row["metadata_json"] = json.loads(row.get("metadata_json") or "{}")
        return rows

    def create_persona(
        self,
        name: str,
        scope: str,
        persona_json: Dict[str, Any],
        last_summary: str,
        identity_key: Optional[str] = None,
        version: Optional[int] = None,
    ) -> int:
        conn = self._connect()
        cursor = conn.cursor()
        final_version = version if version is not None else 1
        cursor.execute(
            '''
            INSERT INTO personas (name, scope, identity_key, source, persona_json, version, last_summary)
            VALUES (?, ?, ?, 'interviews', ?, ?, ?)
            ''',
            (name, scope, identity_key, json.dumps(persona_json), final_version, last_summary),
        )
        persona_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return int(persona_id)

    def update_persona(
        self,
        persona_id: int,
        persona_json: Dict[str, Any],
        last_summary: str,
        name: Optional[str] = None,
        identity_key: Optional[str] = None,
    ):
        conn = self._connect()
        cursor = conn.cursor()
        if name:
            if identity_key is None:
                cursor.execute(
                    '''
                    UPDATE personas
                    SET name=?, persona_json=?, last_summary=?, version=version+1, updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    ''',
                    (name, json.dumps(persona_json), last_summary, persona_id),
                )
            else:
                cursor.execute(
                    '''
                    UPDATE personas
                    SET name=?, identity_key=?, persona_json=?, last_summary=?, version=version+1, updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    ''',
                    (name, identity_key, json.dumps(persona_json), last_summary, persona_id),
                )
        else:
            if identity_key is None:
                cursor.execute(
                    '''
                    UPDATE personas
                    SET persona_json=?, last_summary=?, version=version+1, updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    ''',
                    (json.dumps(persona_json), last_summary, persona_id),
                )
            else:
                cursor.execute(
                    '''
                    UPDATE personas
                    SET identity_key=?, persona_json=?, last_summary=?, version=version+1, updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    ''',
                    (identity_key, json.dumps(persona_json), last_summary, persona_id),
                )
        conn.commit()
        conn.close()

    def get_persona(self, persona_id: int) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM personas WHERE id=?', (persona_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        payload = dict(row)
        payload["persona_json"] = json.loads(payload.get("persona_json") or "{}")
        return payload

    def get_persona_by_scope_name(self, scope: str, name: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT * FROM personas
            WHERE scope = ? AND name = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            ''',
            (scope, name),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        payload = dict(row)
        payload["persona_json"] = json.loads(payload.get("persona_json") or "{}")
        return payload

    def get_persona_by_scope_name_normalized(self, scope: str, name: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT * FROM personas
            WHERE lower(trim(scope)) = lower(trim(?))
              AND lower(trim(name)) = lower(trim(?))
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            ''',
            (scope, name),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        payload = dict(row)
        payload["persona_json"] = json.loads(payload.get("persona_json") or "{}")
        return payload

    def get_persona_by_scope_identity(self, scope: str, identity_key: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT * FROM personas
            WHERE lower(trim(scope)) = lower(trim(?))
              AND identity_key = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            ''',
            (scope, identity_key),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        payload = dict(row)
        payload["persona_json"] = json.loads(payload.get("persona_json") or "{}")
        return payload

    def list_personas_by_scope_identity(self, scope: str, identity_key: str) -> List[Dict[str, Any]]:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT * FROM personas
            WHERE lower(trim(scope)) = lower(trim(?))
              AND identity_key = ?
            ORDER BY updated_at DESC, id DESC
            ''',
            (scope, identity_key),
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        for row in rows:
            row["persona_json"] = json.loads(row.get("persona_json") or "{}")
        return rows

    def list_personas_by_scope_name_normalized(self, scope: str, name: str) -> List[Dict[str, Any]]:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT * FROM personas
            WHERE lower(trim(scope)) = lower(trim(?))
              AND lower(trim(name)) = lower(trim(?))
            ORDER BY updated_at DESC, id DESC
            ''',
            (scope, name),
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        for row in rows:
            row["persona_json"] = json.loads(row.get("persona_json") or "{}")
        return rows

    def delete_persona(self, persona_id: int):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM personas WHERE id = ?', (persona_id,))
        conn.commit()
        conn.close()

    def list_personas(self, scope: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self._connect()
        cursor = conn.cursor()
        if scope:
            cursor.execute('SELECT * FROM personas WHERE scope=? ORDER BY updated_at DESC', (scope,))
        else:
            cursor.execute('SELECT * FROM personas ORDER BY updated_at DESC')
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        for row in rows:
            row["persona_json"] = json.loads(row.get("persona_json") or "{}")
        return rows

# Global database instance
db = DatabaseManager()