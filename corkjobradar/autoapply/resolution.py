"""Manual audit resolution and preparation-only retry. Never releases identities or sends."""
import getpass
import json
from ..config import now,digest,load_profile
from ..worker import worker_lock
from ..repository import latest_analyses
from .policy import current_policy,event
from .store import transition,already_applied,quota_reason,prefinal_check
from .vault import candidate_snapshot,clearance_for
from .platforms import platform_for
from .eligibility import evaluate_autoapply


def _attempt(db,attempt_id,expected_updated_at):
    rows=db.rows('SELECT * FROM application_attempts WHERE id=?',(attempt_id,))
    if not rows:raise ValueError('ATTEMPT_NOT_FOUND')
    attempt=rows[0]
    if attempt['updated_at']!=expected_updated_at:raise PermissionError('ATTEMPT_CHANGED_REFRESH_VIEW')
    plan=db.rows('SELECT * FROM application_plans WHERE id=?',(attempt['plan_id'],))[0]
    return attempt,plan


def manual_resolution(db,attempt_id,action,accepted,expected_updated_at):
    if accepted is not True:raise ValueError('EXPLICIT_MANUAL_ACK_REQUIRED')
    if action not in {'NO_REPETIR','MARCAR_RESUELTA'}:raise ValueError('UNKNOWN_RESOLUTION_ACTION')
    with worker_lock(db),db.transaction() as con:
        if not con.in_transaction:con.execute('BEGIN IMMEDIATE')
        attempt,plan=_attempt(db,attempt_id,expected_updated_at)
        if attempt['state']=='ENVIANDO':raise PermissionError('RECONCILE_INTERRUPTED_SEND_FIRST')
        kind='MANUAL_NO_REPEAT' if action=='NO_REPETIR' else 'MANUAL_RESOLVED'
        if not db.rows('SELECT id FROM application_events WHERE attempt_id=? AND kind=?',(attempt_id,kind)):
            if action=='NO_REPETIR' and attempt['state'] in {'APROBADA_POR_POLITICA','PREPARADA','RELLENANDO','LISTA_PARA_ENVIO','REQUIERE_REVISION','FALLO_REINTENTABLE'}:
                transition(db,attempt_id,'CANCELADA','MANUAL_NO_REPEAT')
            event(db,kind,{'local_user':getpass.getuser(),'retains_identities':True,'retains_quota':True,
                          'external_confirmation_verified':False},plan['id'],attempt_id)
        current=db.rows('SELECT state FROM application_attempts WHERE id=?',(attempt_id,))[0]['state']
        return {'attempt_id':attempt_id,'state':current,'manual_action':action,
                'external_confirmation_verified':False,'automatic_retry':False}


def retry_simulation_preparation(db,attempt_id,accepted,expected_updated_at):
    """Reuse one reserved identity only after checking its complete pre-send journal.

    Public form filling is not invoked. Live attempts and any sending uncertainty are
    rejected regardless of user acknowledgement. Eligibility is recalculated now.
    """
    if accepted is not True:raise ValueError('EXPLICIT_MANUAL_ACK_REQUIRED')
    with worker_lock(db),db.transaction() as con:
        if not con.in_transaction:con.execute('BEGIN IMMEDIATE')
        attempt,plan=_attempt(db,attempt_id,expected_updated_at)
        if plan['environment']!='SIMULATION':raise PermissionError('LIVE_RETRY_NOT_RELEASED')
        if attempt['state'] not in {'CANCELADA','REQUIERE_REVISION','FALLO_REINTENTABLE'}:
            raise PermissionError('ONLY_INTERRUPTED_PRESEND_PREPARATION_CAN_RETRY')
        journal=db.rows('SELECT * FROM application_events WHERE attempt_id=? ORDER BY id',(attempt_id,))
        if any(e['kind'] in {'MANUAL_NO_REPEAT','MANUAL_RESOLVED'} for e in journal):
            raise PermissionError('MANUAL_RESOLUTION_FORBIDS_RETRY')
        send_states={'ENVIANDO','ENVIO_INCIERTO','ENVIADA_CONFIRMADA'}
        if any(e['before_state'] in send_states or e['after_state'] in send_states for e in journal):
            raise PermissionError('SEND_HISTORY_FORBIDS_RETRY')
        if attempt['confirmation_reference'] or attempt['confirmation_hash']:
            raise PermissionError('CONFIRMATION_EVIDENCE_FORBIDS_RETRY')
        bindings=[e for e in journal if e['kind']=='PREFINAL_BINDING']
        if not any(e['kind']=='RESERVED' and json.loads(e['details']).get('environment')=='SIMULATION' for e in journal) or not bindings:
            raise PermissionError('COMPLETE_PRESEND_JOURNAL_REQUIRED')
        job=db.rows('SELECT * FROM jobs WHERE id=?',(plan['job_id'],))[0]
        from .it_scope import require_it_job
        require_it_job(job)
        control,policy_row,policy=current_policy(db)
        candidate=candidate_snapshot(db)
        if not policy_row or policy_row['id']!=plan['policy_id'] or plan['facts_hash']!=candidate.get('_facts_hash') or job['content_hash']!=plan['content_hash']:
            raise PermissionError('POLICY_CANDIDATE_OR_JOB_CHANGED')
        binding=json.loads(bindings[-1]['details'])
        analysis=db.rows('SELECT result FROM job_analyses WHERE id=?',(plan['analysis_id'],))
        if binding.get('clearance_hash')!=digest(clearance_for(db,job['id'])) or binding.get('analysis_hash')!=digest(analysis[0]['result'] if analysis else None):
            raise PermissionError('REQUIREMENTS_OR_ANALYSIS_CHANGED')
        owned=db.rows('SELECT * FROM application_reservations WHERE attempt_id=? AND environment=?',(attempt_id,'SIMULATION'))
        if len(owned)!=1:raise PermissionError('ORIGINAL_RESERVATION_REQUIRED')
        decision=evaluate_autoapply(job,latest_analyses(db).get(job['id'],{}),load_profile(),policy,
            db.rows('SELECT * FROM commute_checks WHERE job_id=? ORDER BY id DESC',(job['id'],)),
            platform=platform_for(job.get('apply_url') or job['url']),control=control,candidate=candidate,db=db,
            clearance=clearance_for(db,job['id']),policy_version=policy_row['version'],
            duplicate=already_applied(db,job,'SIMULATION',exclude_attempt=attempt_id),
            quota_reason=quota_reason(db,policy,job['company'],'SIMULATION',exclude_attempt=attempt_id))
        if decision.outcome!='ALLOW':
            return {'attempt_id':attempt_id,'state':attempt['state'],'retry_prepared':False,'decision':decision.to_dict()}
        # The original reservation is moved to NOW, after checking quotas without
        # counting this attempt twice. The prior timestamp remains in the audit.
        timestamp=now()
        db.execute('UPDATE application_reservations SET reserved_at=? WHERE attempt_id=?',(timestamp,attempt_id))
        db.execute("UPDATE application_attempts SET state='APROBADA_POR_POLITICA',updated_at=?,policy_epoch=?,error_code=NULL,document_id=NULL,form_hash=NULL WHERE id=?",
                   (timestamp,control['epoch'],attempt_id))
        db.execute("UPDATE application_plans SET state='APROBADA_POR_POLITICA' WHERE id=?",(plan['id'],))
        event(db,'MANUAL_SIMULATION_RETRY_PREPARED',{'local_user':getpass.getuser(),'previous_reservation_at':owned[0]['reserved_at'],
              'evidence':'COMPLETE_SIMULATION_PRESEND_JOURNAL','identities_reused':True,'no_network_activity':True},
              plan['id'],attempt_id,attempt['state'],'APROBADA_POR_POLITICA')
        from .documents import document_bytes
        document_bytes(db,candidate['cv_document_id'])
        db.execute('UPDATE application_attempts SET document_id=? WHERE id=?',(candidate['cv_document_id'],attempt_id))
        transition(db,attempt_id,'PREPARADA')
        prefinal_check(db,attempt_id)
        transition(db,attempt_id,'REQUIERE_REVISION','OFFLINE_FORM_TRIAL_AND_ADAPTER_PERMISSION_REQUIRED')
        return {'attempt_id':attempt_id,'state':'REQUIERE_REVISION','retry_prepared':True,'live_enabled':False,
                'public_forms_filled':False}
