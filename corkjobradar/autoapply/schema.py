MIGRATION_5 = """
BEGIN IMMEDIATE;
CREATE TABLE autoapply_policies (
 id INTEGER PRIMARY KEY, version TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
 local_user TEXT NOT NULL, consent TEXT NOT NULL, config TEXT NOT NULL,
 integrity_hash TEXT NOT NULL, profile_hash TEXT NOT NULL);
CREATE TABLE autoapply_control (
 id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL DEFAULT 0,
 live_enabled INTEGER NOT NULL DEFAULT 0 CHECK(live_enabled=0),
 paused INTEGER NOT NULL DEFAULT 1, alert INTEGER NOT NULL DEFAULT 0,
 epoch INTEGER NOT NULL DEFAULT 0, policy_id INTEGER REFERENCES autoapply_policies(id),
 updated_at TEXT, reason TEXT NOT NULL DEFAULT 'INITIAL_OFF');
INSERT INTO autoapply_control(id) VALUES(1);
CREATE TABLE candidate_facts (
 id INTEGER PRIMARY KEY, field TEXT NOT NULL, encrypted_value BLOB NOT NULL,
 origin TEXT NOT NULL, approved_at TEXT NOT NULL, local_user TEXT NOT NULL,
 revoked_at TEXT);
CREATE TABLE candidate_documents (
 id INTEGER PRIMARY KEY, kind TEXT NOT NULL, encrypted_path TEXT NOT NULL,
 file_hash TEXT NOT NULL, facts_hash TEXT NOT NULL, claim_ids TEXT NOT NULL,
 created_at TEXT NOT NULL, approved_at TEXT, revoked_at TEXT);
CREATE TABLE job_clearances (
 id INTEGER PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id),
 content_hash TEXT NOT NULL, facts_hash TEXT NOT NULL, payload TEXT NOT NULL,
 approved_at TEXT NOT NULL, expires_at TEXT NOT NULL, local_user TEXT NOT NULL);
CREATE TABLE application_plans (
 id INTEGER PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id),
 policy_id INTEGER REFERENCES autoapply_policies(id), content_hash TEXT NOT NULL,
 facts_hash TEXT NOT NULL, fingerprint TEXT NOT NULL, environment TEXT NOT NULL CHECK(environment IN ('SIMULATION','LIVE')),
 decision TEXT NOT NULL, reasons TEXT NOT NULL, state TEXT NOT NULL,
 analysis_id INTEGER REFERENCES job_analyses(id), created_at TEXT NOT NULL,
 UNIQUE(job_id,policy_id,content_hash,facts_hash,environment));
CREATE TABLE application_attempts (
 id INTEGER PRIMARY KEY, plan_id INTEGER NOT NULL REFERENCES application_plans(id),
 state TEXT NOT NULL, adapter TEXT NOT NULL, target_url TEXT NOT NULL,
 started_at TEXT NOT NULL, updated_at TEXT NOT NULL, policy_epoch INTEGER NOT NULL,
 document_id INTEGER REFERENCES candidate_documents(id), form_hash TEXT,
 error_code TEXT, confirmation_reference TEXT, confirmation_hash TEXT,
 UNIQUE(plan_id));
CREATE TABLE application_answers (
 id INTEGER PRIMARY KEY, attempt_id INTEGER NOT NULL REFERENCES application_attempts(id),
 question_hash TEXT NOT NULL, fact_id INTEGER REFERENCES candidate_facts(id),
 answer_hash TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE application_events (
 id INTEGER PRIMARY KEY, plan_id INTEGER REFERENCES application_plans(id),
 attempt_id INTEGER REFERENCES application_attempts(id), occurred_at TEXT NOT NULL,
 kind TEXT NOT NULL, before_state TEXT, after_state TEXT, details TEXT NOT NULL);
CREATE TRIGGER application_events_no_update BEFORE UPDATE ON application_events
 BEGIN SELECT RAISE(ABORT,'Append-only application audit'); END;
CREATE TRIGGER application_events_no_delete BEFORE DELETE ON application_events
 BEGIN SELECT RAISE(ABORT,'Append-only application audit'); END;
CREATE TRIGGER autoapply_policies_immutable BEFORE UPDATE ON autoapply_policies
 BEGIN SELECT RAISE(ABORT,'Immutable policy; create a new version'); END;
CREATE TABLE application_reservations (
 id INTEGER PRIMARY KEY, attempt_id INTEGER NOT NULL UNIQUE REFERENCES application_attempts(id),
 environment TEXT NOT NULL, employer_key TEXT NOT NULL, reserved_at TEXT NOT NULL);
CREATE TABLE application_identities (
 identity_key TEXT NOT NULL, environment TEXT NOT NULL,
 attempt_id INTEGER NOT NULL REFERENCES application_attempts(id),
 PRIMARY KEY(identity_key,environment));
CREATE INDEX application_plans_job ON application_plans(job_id,id DESC);
CREATE INDEX application_reservations_time ON application_reservations(environment,reserved_at);
PRAGMA user_version=5;
COMMIT;
"""

MIGRATION_6 = """
BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS autoapply_form_inspections (
 id INTEGER PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id), content_hash TEXT NOT NULL,
 platform TEXT NOT NULL, adapter_version TEXT NOT NULL, inspected_at TEXT NOT NULL,
 source_url TEXT NOT NULL, form_hash TEXT NOT NULL, encrypted_path TEXT NOT NULL, status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS autoapply_trial_plans (
 id INTEGER PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id), created_at TEXT NOT NULL,
 snapshot TEXT NOT NULL, snapshot_hash TEXT NOT NULL, expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS autoapply_trial_consents (
 id INTEGER PRIMARY KEY, trial_id INTEGER NOT NULL UNIQUE REFERENCES autoapply_trial_plans(id),
 snapshot_hash TEXT NOT NULL, authorized_at TEXT NOT NULL, local_user TEXT NOT NULL,
 consent TEXT NOT NULL, max_submissions INTEGER NOT NULL CHECK(max_submissions=1));
CREATE TABLE IF NOT EXISTS application_receipt_evidence (
 id INTEGER PRIMARY KEY, attempt_id INTEGER NOT NULL REFERENCES application_attempts(id),
 received_at TEXT NOT NULL, environment TEXT NOT NULL, platform TEXT NOT NULL,
 evidence_hash TEXT NOT NULL, encrypted_path TEXT NOT NULL, status TEXT NOT NULL,
 UNIQUE(attempt_id,evidence_hash));
CREATE TRIGGER IF NOT EXISTS form_inspections_no_update BEFORE UPDATE ON autoapply_form_inspections
 BEGIN SELECT RAISE(ABORT,'Immutable form inspection'); END;
CREATE TRIGGER IF NOT EXISTS trial_plans_no_update BEFORE UPDATE ON autoapply_trial_plans
 BEGIN SELECT RAISE(ABORT,'Immutable controlled trial'); END;
CREATE TRIGGER IF NOT EXISTS trial_consents_no_update BEFORE UPDATE ON autoapply_trial_consents
 BEGIN SELECT RAISE(ABORT,'Immutable trial consent'); END;
CREATE TRIGGER IF NOT EXISTS trial_consents_no_delete BEFORE DELETE ON autoapply_trial_consents
 BEGIN SELECT RAISE(ABORT,'Immutable trial consent'); END;
CREATE TRIGGER IF NOT EXISTS receipt_evidence_no_update BEFORE UPDATE ON application_receipt_evidence
 BEGIN SELECT RAISE(ABORT,'Immutable receipt evidence'); END;
PRAGMA user_version=6;
COMMIT;
"""

MIGRATION_7 = """
BEGIN IMMEDIATE;
CREATE TABLE manual_application_handoffs (
 id INTEGER PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id),
 created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
 package_hash TEXT NOT NULL, encrypted_path TEXT NOT NULL);
CREATE TABLE manual_application_declarations (
 id INTEGER PRIMARY KEY, handoff_id INTEGER NOT NULL UNIQUE REFERENCES manual_application_handoffs(id),
 user_action_id INTEGER NOT NULL UNIQUE REFERENCES user_actions(id), declared_at TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status='DECLARED_NO_EXTERNAL_RECEIPT'));
CREATE TRIGGER manual_handoffs_no_update BEFORE UPDATE ON manual_application_handoffs
 BEGIN SELECT RAISE(ABORT,'Immutable handoff snapshot'); END;
CREATE TRIGGER manual_declarations_no_update BEFORE UPDATE ON manual_application_declarations
 BEGIN SELECT RAISE(ABORT,'Immutable manual declaration'); END;
CREATE TRIGGER manual_declarations_no_delete BEFORE DELETE ON manual_application_declarations
 BEGIN SELECT RAISE(ABORT,'Immutable manual declaration'); END;
PRAGMA user_version=7;
COMMIT;
"""

MIGRATION_8 = """
BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS autoapply_interventions (
 id TEXT PRIMARY KEY, attempt_id INTEGER NOT NULL UNIQUE REFERENCES application_attempts(id),
 inspection_id INTEGER NOT NULL REFERENCES autoapply_form_inspections(id),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, last_verified_at TEXT,
 status TEXT NOT NULL, reason_code TEXT NOT NULL, form_state TEXT NOT NULL,
 binding_hash TEXT NOT NULL, filled_count INTEGER NOT NULL DEFAULT 0,
 worker_pid INTEGER, heartbeat TEXT, fixture_url TEXT,
 submission_started INTEGER NOT NULL DEFAULT 0 CHECK(submission_started IN (0,1)),
 local_receipt_verified INTEGER NOT NULL DEFAULT 0 CHECK(local_receipt_verified IN (0,1)));
CREATE TABLE IF NOT EXISTS autoapply_intervention_commands (
 id INTEGER PRIMARY KEY, session_id TEXT NOT NULL REFERENCES autoapply_interventions(id),
 command TEXT NOT NULL CHECK(command IN ('OPEN','CONTINUE','RECOVER','FOCUS','CLOSE')),
 requested_at TEXT NOT NULL, processed_at TEXT, status TEXT NOT NULL DEFAULT 'PENDING');
CREATE UNIQUE INDEX IF NOT EXISTS intervention_one_pending_command ON autoapply_intervention_commands(session_id) WHERE status='PENDING';
PRAGMA user_version=8;
COMMIT;
"""

MIGRATION_9 = """
BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS manual_application_evidence (
 id INTEGER PRIMARY KEY, declaration_id INTEGER NOT NULL REFERENCES manual_application_declarations(id),
 uploaded_at TEXT NOT NULL, extension TEXT NOT NULL CHECK(extension IN ('eml','pdf')),
 content_hash TEXT NOT NULL, payload_hash TEXT NOT NULL, encrypted_path TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status='USER_SUPPLIED_NOT_AUTHENTICATED'),
 UNIQUE(declaration_id,content_hash));
CREATE TABLE IF NOT EXISTS manual_application_evidence_reviews (
 id INTEGER PRIMARY KEY, evidence_id INTEGER NOT NULL UNIQUE REFERENCES manual_application_evidence(id),
 content_hash TEXT NOT NULL, reviewed_at TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status='USER_REVIEWED_NOT_EXTERNALLY_AUTHENTICATED'));
CREATE TRIGGER IF NOT EXISTS manual_evidence_immutable BEFORE UPDATE ON manual_application_evidence
 BEGIN SELECT RAISE(ABORT,'Immutable manual evidence'); END;
CREATE TRIGGER IF NOT EXISTS manual_evidence_reviews_immutable BEFORE UPDATE ON manual_application_evidence_reviews
 BEGIN SELECT RAISE(ABORT,'Immutable evidence review'); END;
CREATE TRIGGER IF NOT EXISTS manual_evidence_no_delete BEFORE DELETE ON manual_application_evidence
 BEGIN SELECT RAISE(ABORT,'Preserve manual evidence audit'); END;
CREATE TRIGGER IF NOT EXISTS manual_evidence_reviews_no_delete BEFORE DELETE ON manual_application_evidence_reviews
 BEGIN SELECT RAISE(ABORT,'Preserve manual evidence review'); END;
PRAGMA user_version=9;
COMMIT;
"""

MIGRATION_10 = """
BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS manual_requirement_reviews (
 id INTEGER PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id),
 job_content_hash TEXT NOT NULL, facts_hash TEXT NOT NULL, requirement_hash TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('CUMPLIDO','NO_CUMPLIDO','PENDIENTE')),
 fact_ids TEXT NOT NULL, reviewed_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS manual_requirement_binding ON manual_requirement_reviews(job_id,job_content_hash,facts_hash,requirement_hash,id);
CREATE TRIGGER IF NOT EXISTS manual_requirement_no_update BEFORE UPDATE ON manual_requirement_reviews
 BEGIN SELECT RAISE(ABORT,'Preserve factual review history'); END;
CREATE TRIGGER IF NOT EXISTS manual_requirement_no_delete BEFORE DELETE ON manual_requirement_reviews
 BEGIN SELECT RAISE(ABORT,'Preserve factual review history'); END;
PRAGMA user_version=10;
COMMIT;
"""

MIGRATION_11 = """
BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS it_selection_origins (
 id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, encrypted_value BLOB NOT NULL,
 ciphertext_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS it_worksite_evidence (
 id INTEGER PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id), content_hash TEXT NOT NULL,
 latitude REAL NOT NULL, longitude REAL NOT NULL, evidence_url TEXT NOT NULL,
 verified_at TEXT NOT NULL, expires_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS it_worksite_binding ON it_worksite_evidence(job_id,content_hash,id);
CREATE TABLE IF NOT EXISTS it_application_queue (
 job_id TEXT PRIMARY KEY REFERENCES jobs(id), binding_hash TEXT NOT NULL,
 professional_state TEXT NOT NULL, application_state TEXT NOT NULL,
 workflow_state TEXT NOT NULL, route TEXT NOT NULL, assessment TEXT NOT NULL,
 updated_at TEXT NOT NULL, lease_token TEXT, lease_until TEXT,
 handoff_id INTEGER REFERENCES manual_application_handoffs(id), error_code TEXT);
CREATE TABLE IF NOT EXISTS it_application_queue_events (
 id INTEGER PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id), occurred_at TEXT NOT NULL,
 binding_hash TEXT NOT NULL, workflow_state TEXT NOT NULL, code TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS it_queue_pending ON it_application_queue(workflow_state,updated_at,job_id);
PRAGMA user_version=11;
COMMIT;
"""
