"""Additive local document history. No change to facts, consent or LIVE controls."""
MIGRATION_13 = """
BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS professional_dossiers (
 id INTEGER PRIMARY KEY, facts_hash TEXT NOT NULL, model_version TEXT NOT NULL,
 encrypted_path TEXT NOT NULL, file_hash TEXT NOT NULL, created_at TEXT NOT NULL,
 UNIQUE(facts_hash,model_version));
CREATE TABLE IF NOT EXISTS reference_originals (
 id INTEGER PRIMARY KEY, encrypted_path TEXT NOT NULL, file_hash TEXT NOT NULL,
 metadata BLOB NOT NULL, source_page INTEGER NOT NULL, page_count INTEGER NOT NULL,
 imported_at TEXT NOT NULL, reviewed_at TEXT, revoked_at TEXT,
 UNIQUE(file_hash,source_page));
CREATE TABLE IF NOT EXISTS reference_review_events (
 id INTEGER PRIMARY KEY, reference_id INTEGER NOT NULL REFERENCES reference_originals(id),
 kind TEXT NOT NULL, created_at TEXT NOT NULL, metadata BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS job_document_versions (
 id INTEGER PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id),
 job_content_hash TEXT NOT NULL, facts_hash TEXT NOT NULL, dossier_hash TEXT NOT NULL,
 encrypted_path TEXT NOT NULL, file_hash TEXT NOT NULL, created_at TEXT NOT NULL,
 revoked_at TEXT, UNIQUE(job_id,file_hash));
CREATE INDEX IF NOT EXISTS document_versions_job ON job_document_versions(job_id,id DESC);
CREATE TABLE IF NOT EXISTS job_document_bundles (
 id INTEGER PRIMARY KEY, version_id INTEGER NOT NULL REFERENCES job_document_versions(id),
 job_id TEXT NOT NULL REFERENCES jobs(id), encrypted_path TEXT NOT NULL,
 file_hash TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
 approved_at TEXT NOT NULL, revoked_at TEXT);
CREATE TABLE IF NOT EXISTS job_document_events (
 id INTEGER PRIMARY KEY, job_id TEXT REFERENCES jobs(id), version_id INTEGER REFERENCES job_document_versions(id),
 bundle_id INTEGER REFERENCES job_document_bundles(id), kind TEXT NOT NULL,
 created_at TEXT NOT NULL, details TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS job_document_events_no_update BEFORE UPDATE ON job_document_events
 BEGIN SELECT RAISE(ABORT,'Append-only document audit'); END;
CREATE TRIGGER IF NOT EXISTS job_document_events_no_delete BEFORE DELETE ON job_document_events
 BEGIN SELECT RAISE(ABORT,'Append-only document audit'); END;
PRAGMA user_version=13;
COMMIT;
"""
