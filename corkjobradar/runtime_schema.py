MIGRATION_12 = """
BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS local_runtime (
 id INTEGER PRIMARY KEY CHECK(id=1), desired TEXT NOT NULL DEFAULT 'STOPPED'
 CHECK(desired IN ('RUNNING','PAUSED','STOPPED')),
 interval_hours REAL NOT NULL DEFAULT 6 CHECK(interval_hours BETWEEN 0.25 AND 168),
 auto_prepare INTEGER NOT NULL DEFAULT 1 CHECK(auto_prepare IN (0,1)),
 sound INTEGER NOT NULL DEFAULT 0 CHECK(sound IN (0,1)),
 state TEXT NOT NULL DEFAULT 'STOPPED', supervisor_pid INTEGER, supervisor_stamp TEXT,
 owner_pid INTEGER, owner_stamp TEXT, heartbeat TEXT, last_tick TEXT,
 next_search_at TEXT, last_search_started TEXT, last_search_finished TEXT,
 last_search_run INTEGER REFERENCES scan_runs(id), active_run INTEGER REFERENCES scan_runs(id),
 resume_run INTEGER REFERENCES scan_runs(id), active_kind TEXT,
 child_pid INTEGER, child_stamp TEXT, restart_after TEXT, launch_after TEXT,
 last_prepare_fingerprint TEXT, last_prepare_at TEXT, failures INTEGER NOT NULL DEFAULT 0,
 updated_at TEXT NOT NULL, last_error_code TEXT);
INSERT OR IGNORE INTO local_runtime(id,updated_at) VALUES(1,datetime('now'));
CREATE TABLE IF NOT EXISTS local_runtime_events (
 id INTEGER PRIMARY KEY, occurred_at TEXT NOT NULL, kind TEXT NOT NULL, code TEXT NOT NULL,
 run_id INTEGER REFERENCES scan_runs(id));
CREATE TABLE IF NOT EXISTS local_runtime_notifications (
 id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, kind TEXT NOT NULL,
 job_id TEXT REFERENCES jobs(id), reference_id TEXT, dedupe_key TEXT NOT NULL UNIQUE,
 resolved_at TEXT, acknowledged_at TEXT);
PRAGMA user_version=12;
COMMIT;
"""
