import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import uuid4
from .config import DB_PATH, now

MIGRATION_2 = """
BEGIN IMMEDIATE;
ALTER TABLE run_jobs ADD COLUMN content_hash TEXT;
ALTER TABLE run_jobs ADD COLUMN observed_at TEXT;
ALTER TABLE run_jobs ADD COLUMN change_status TEXT NOT NULL DEFAULT 'LEGACY_UNKNOWN';
CREATE INDEX IF NOT EXISTS analyses_latest ON job_analyses(job_id,id DESC);
CREATE INDEX IF NOT EXISTS sources_by_job ON job_sources(job_id);
CREATE INDEX IF NOT EXISTS snapshots_by_job ON job_snapshots(job_id,id DESC);
CREATE INDEX IF NOT EXISTS run_jobs_by_job ON run_jobs(job_id,run_id);
CREATE INDEX IF NOT EXISTS queue_pending ON task_queue(run_id,status,id);
CREATE INDEX IF NOT EXISTS actions_by_job ON user_actions(job_id,id DESC);
PRAGMA user_version=2;
COMMIT;
"""

MIGRATION_3 = """
BEGIN IMMEDIATE;
ALTER TABLE run_jobs ADD COLUMN baseline_hash TEXT;
CREATE TABLE discovery_runs (
 id INTEGER PRIMARY KEY, seed_url TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
 status TEXT NOT NULL DEFAULT 'pending', message TEXT DEFAULT '');
CREATE TABLE discovery_resources (
 id INTEGER PRIMARY KEY, discovery_id INTEGER NOT NULL REFERENCES discovery_runs(id),
 url TEXT NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
 parent_url TEXT, checked_at TEXT, error TEXT, UNIQUE(discovery_id,url));
CREATE TABLE discovery_candidates (
 id INTEGER PRIMARY KEY, discovery_id INTEGER NOT NULL REFERENCES discovery_runs(id),
 url TEXT NOT NULL, title TEXT, kind TEXT NOT NULL, parent_url TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'PENDIENTE_REVISION', discovered_at TEXT NOT NULL,
 UNIQUE(discovery_id,url));
CREATE INDEX discovery_queue ON discovery_resources(discovery_id,status,id);
PRAGMA user_version=3;
COMMIT;
"""

MIGRATION_4 = """
BEGIN IMMEDIATE;
ALTER TABLE jobs ADD COLUMN identity_url TEXT;
UPDATE jobs SET identity_url=canonical_job_url(url);
CREATE INDEX jobs_identity ON jobs(company,identity_url);
CREATE INDEX jobs_possible_match ON jobs(company,title,location);
ALTER TABLE source_runs ADD COLUMN source_snapshot TEXT;
ALTER TABLE source_runs ADD COLUMN query_signature TEXT;
ALTER TABLE job_sources ADD COLUMN last_query_signature TEXT;
PRAGMA user_version=4;
COMMIT;
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, url TEXT NOT NULL,
 config TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 0,
 permission TEXT NOT NULL DEFAULT 'PENDIENTE', status TEXT NOT NULL DEFAULT 'SIN_COMPROBAR',
 checked_at TEXT, last_success TEXT, notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS scan_runs (
 id INTEGER PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL,
 profile TEXT NOT NULL, cancel_requested INTEGER NOT NULL DEFAULT 0, worker_pid INTEGER,
 heartbeat TEXT, message TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS source_runs (
 id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES scan_runs(id),
 source_id TEXT NOT NULL REFERENCES sources(id), status TEXT NOT NULL DEFAULT 'pending',
 pages_visited INTEGER NOT NULL DEFAULT 0, expected_total INTEGER,
 observed INTEGER NOT NULL DEFAULT 0, pagination_complete INTEGER,
 cursor TEXT, message TEXT DEFAULT '', started_at TEXT, finished_at TEXT,
 UNIQUE(run_id, source_id));
CREATE TABLE IF NOT EXISTS jobs (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, company TEXT NOT NULL, location TEXT NOT NULL,
 url TEXT NOT NULL, apply_url TEXT, description TEXT NOT NULL DEFAULT '',
 detail_complete INTEGER NOT NULL DEFAULT 0, category TEXT DEFAULT 'Otras',
 scope TEXT DEFAULT 'ACCESIBILIDAD_PENDIENTE', scope_reason TEXT DEFAULT '',
 mode TEXT DEFAULT 'DESCONOCIDO', posted_at TEXT, first_seen_at TEXT NOT NULL,
 last_seen_at TEXT NOT NULL, last_verified_at TEXT,
 open_status TEXT NOT NULL DEFAULT 'UNKNOWN', analysis_status TEXT NOT NULL DEFAULT 'PENDIENTE',
 content_hash TEXT NOT NULL, raw TEXT NOT NULL, possible_duplicate TEXT);
CREATE INDEX IF NOT EXISTS jobs_url ON jobs(url);
CREATE INDEX IF NOT EXISTS jobs_scope ON jobs(scope, analysis_status);
CREATE TABLE IF NOT EXISTS job_sources (
 source_id TEXT NOT NULL REFERENCES sources(id), external_id TEXT NOT NULL,
 job_id TEXT NOT NULL REFERENCES jobs(id), url TEXT NOT NULL, first_seen_at TEXT NOT NULL,
 last_seen_at TEXT NOT NULL, missing_successes INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(source_id, external_id));
CREATE TABLE IF NOT EXISTS run_jobs (
 run_id INTEGER NOT NULL REFERENCES scan_runs(id), source_id TEXT NOT NULL,
 external_id TEXT NOT NULL, job_id TEXT NOT NULL REFERENCES jobs(id),
 PRIMARY KEY(run_id, source_id, external_id));
CREATE TABLE IF NOT EXISTS job_snapshots (
 id INTEGER PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id), content_hash TEXT NOT NULL,
 captured_at TEXT NOT NULL, description TEXT NOT NULL, raw TEXT NOT NULL,
 UNIQUE(job_id,content_hash));
CREATE TABLE IF NOT EXISTS job_analyses (
 id INTEGER PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id), content_hash TEXT NOT NULL,
 profile_hash TEXT NOT NULL, analyzer_version TEXT NOT NULL, status TEXT NOT NULL,
 result TEXT NOT NULL, created_at TEXT NOT NULL,
 UNIQUE(job_id,content_hash,profile_hash,analyzer_version));
CREATE TABLE IF NOT EXISTS verification_events (
 id INTEGER PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id), source_id TEXT,
 checked_at TEXT NOT NULL, status TEXT NOT NULL, evidence TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS commute_checks (
 id INTEGER PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id), origin TEXT NOT NULL,
 mode TEXT NOT NULL, transfers INTEGER, viability TEXT NOT NULL, evidence_url TEXT,
 checked_at TEXT NOT NULL, details TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS user_actions (
 id INTEGER PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id), action TEXT NOT NULL,
 notes TEXT DEFAULT '', application_date TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS source_errors (
 id INTEGER PRIMARY KEY, run_id INTEGER, source_id TEXT, job_id TEXT,
 occurred_at TEXT NOT NULL, kind TEXT NOT NULL, message TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_events (
 id INTEGER PRIMARY KEY, run_id INTEGER, job_id TEXT, created_at TEXT NOT NULL,
 kind TEXT NOT NULL, details TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS task_queue (
 id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES scan_runs(id),
 source_id TEXT, job_id TEXT, kind TEXT NOT NULL, payload TEXT NOT NULL DEFAULT '{}',
 status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
 error TEXT, updated_at TEXT NOT NULL,
 UNIQUE(run_id,source_id,job_id,kind));
CREATE TABLE IF NOT EXISTS http_cache (
 url TEXT PRIMARY KEY, etag TEXT, modified TEXT, body BLOB, headers TEXT, checked_at TEXT);
"""

class Database:
    def __init__(self, path=DB_PATH):
        self.path = Path(path)
        self._transaction_connection=ContextVar('radar_transaction_'+str(id(self)),default=None)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            version = con.execute("PRAGMA user_version").fetchone()[0]
            if version > 12:
                raise RuntimeError("Base de datos de una versión más reciente")
            if 0 < version < 12:
                folder=self.path.parent/'backups'
                folder.mkdir(exist_ok=True)
                filename=folder/(self.path.stem+'-before-v12-'+now().replace(':','')+'-'+uuid4().hex[:8]+'.sqlite3')
                backup=sqlite3.connect(filename)
                try:
                    con.backup(backup)
                    if backup.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                        raise RuntimeError('La copia previa no supera integridad; migración cancelada')
                finally:
                    backup.close()
            if version < 1:
                if self.path.exists() and self.path.stat().st_size:
                    backup = sqlite3.connect(str(self.path.with_suffix('.before_v1.sqlite3')))
                    con.backup(backup)
                    backup.close()
                con.executescript(SCHEMA + "\nPRAGMA user_version=1;")
            if version < 2:
                con.executescript(MIGRATION_2)
            if version < 3:
                con.executescript(MIGRATION_3)
            if version < 4:
                from .normalization import canonical_url
                con.create_function('canonical_job_url',1,canonical_url)
                con.executescript(MIGRATION_4)
            if version < 5:
                from .autoapply.schema import MIGRATION_5
                con.executescript(MIGRATION_5)
            if version < 6:
                from .autoapply.schema import MIGRATION_6
                con.executescript(MIGRATION_6)
            if version < 7:
                from .autoapply.schema import MIGRATION_7
                con.executescript(MIGRATION_7)
            if version < 8:
                from .autoapply.schema import MIGRATION_8
                con.executescript(MIGRATION_8)
            if version < 9:
                from .autoapply.schema import MIGRATION_9
                con.executescript(MIGRATION_9)
            if version < 10:
                from .autoapply.schema import MIGRATION_10
                con.executescript(MIGRATION_10)
            if version < 11:
                from .autoapply.schema import MIGRATION_11
                con.executescript(MIGRATION_11)
            if version < 12:
                from .runtime_schema import MIGRATION_12
                con.executescript(MIGRATION_12)

    @contextmanager
    def connect(self):
        active=self._transaction_connection.get()
        if active is not None:
            yield active
            return
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA journal_mode=WAL")
        try:
            yield con
            con.commit()
        except BaseException:
            con.rollback()
            raise
        finally:
            con.close()

    @contextmanager
    def transaction(self):
        """One durable commit for a short unit of local work, never network/LLM calls."""
        with self.connect() as con:
            token=self._transaction_connection.set(con)
            try:
                yield con
            finally:
                self._transaction_connection.reset(token)

    @contextmanager
    def read_snapshot(self):
        """Consistent read view across export/report queries while WAL permits writers."""
        with self.connect() as con:
            con.execute('BEGIN')
            class ReadView:
                def rows(self,sql,params=()):
                    return [dict(r) for r in con.execute(sql,params).fetchall()]
            yield ReadView()

    def rows(self, sql, params=()):
        with self.connect() as con:
            return [dict(row) for row in con.execute(sql, params).fetchall()]

    def execute(self, sql, params=()):
        with self.connect() as con:
            return con.execute(sql, params).lastrowid

    def error(self, source_id, kind, message, run_id=None, job_id=None):
        self.execute("INSERT INTO source_errors(run_id,source_id,job_id,occurred_at,kind,message) VALUES(?,?,?,?,?,?)",
                     (run_id, source_id, job_id, now(), kind, str(message)[:3000]))
        from .logging_config import log_event
        log_event(self.path,'error',source=source_id,run_id=run_id,job_id=job_id,kind=kind)

    def event(self, kind, details, run_id=None, job_id=None):
        self.execute("INSERT INTO audit_events(run_id,job_id,created_at,kind,details) VALUES(?,?,?,?,?)",
                     (run_id, job_id, now(), kind, json.dumps(details, ensure_ascii=False)))
        from .logging_config import log_event
        log_event(self.path,kind,run_id=run_id,job_id=job_id)
