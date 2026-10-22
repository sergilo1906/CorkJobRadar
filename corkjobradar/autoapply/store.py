import json
import hashlib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit
from ..config import now, digest
from ..normalization import normalized, canonical_url
from .policy import event, current_policy, require_live
from .it_scope import require_it_job

TERMINAL={'ENVIADA_CONFIRMADA','ENVIO_INCIERTO','CANCELADA','FALLO_DEFINITIVO','SIMULADA_SIN_ENVIO'}
TRANSITIONS={
 'APROBADA_POR_POLITICA':{'PREPARADA','REQUIERE_REVISION','CANCELADA'},
 'PREPARADA':{'RELLENANDO','REQUIERE_REVISION','CANCELADA'},
 'RELLENANDO':{'LISTA_PARA_ENVIO','REQUIERE_REVISION','FALLO_REINTENTABLE','CANCELADA'},
 'LISTA_PARA_ENVIO':{'SIMULADA_SIN_ENVIO','ENVIANDO','CANCELADA','REQUIERE_REVISION'},
 'ENVIANDO':{'ENVIADA_CONFIRMADA','ENVIO_INCIERTO'},
 'ENVIO_INCIERTO':{'ENVIADA_CONFIRMADA'},
 'FALLO_REINTENTABLE':{'PREPARADA','CANCELADA'},
 'REQUIERE_REVISION':{'CANCELADA'},
}


def identities(job, sources=()):
    raw=job.get('raw',{})
    if isinstance(raw,str):raw=json.loads(raw)
    company=normalized(job['company'])
    # Conservatively hold equal employer/title/location even if the ATS changed.
    values=[('position',company,normalized(job['title']),normalized(job['location']))]
    for url in (job.get('url'),job.get('apply_url')):
        if url:
            values.append(('url-section',canonical_url(url),company,str(raw['_career_section_id'])) if raw.get('_career_section_id') else ('url',canonical_url(url)))
    for field in ('requisition_id','requisitionId','jobReqId'):
        if raw.get(field):values.append(('requisition',company,str(raw[field])))
    for s in sources:values.append(('source',s['source_id'],str(s['external_id'])))
    return sorted({digest(v) for v in values})


def already_applied(db, job, environment='SIMULATION', exclude_attempt=None):
    # Existing manual applications also block; a later rejection never permits reapplication.
    rows=db.rows("SELECT j.* FROM jobs j JOIN user_actions a ON a.job_id=j.id WHERE a.action IN ('solicitada','respuesta recibida','entrevista','rechazada','oferta recibida','seguimiento')")
    keys=set(identities(job,db.rows('SELECT * FROM job_sources WHERE job_id=?',(job['id'],))))
    for row in rows:
        if keys.intersection(identities(row,db.rows('SELECT * FROM job_sources WHERE job_id=?',(row['id'],)))):return True
    placeholders=','.join('?' for _ in keys)
    return bool(db.rows(f'SELECT 1 FROM application_identities WHERE identity_key IN ({placeholders}) AND environment IN (?,?) AND (? IS NULL OR attempt_id<>?) LIMIT 1',(*keys,environment,'LIVE',exclude_attempt,exclude_attempt)))


def quota_reason(db, policy, company, environment='SIMULATION', clock=None, exclude_attempt=None):
    clock=clock or datetime.now(ZoneInfo('Europe/Dublin'))
    rows=db.rows('SELECT employer_key,reserved_at FROM application_reservations WHERE environment=? AND (? IS NULL OR attempt_id<>?)',(environment,exclude_attempt,exclude_attempt))
    daily=0;weekly=0;company_week=0;last=None
    monday=clock.date()-timedelta(days=clock.weekday())
    for row in rows:
        date=datetime.fromisoformat(row['reserved_at']).astimezone(ZoneInfo('Europe/Dublin'))
        if date.date()==clock.date():daily+=1
        if monday<=date.date()<=clock.date():
            weekly+=1
            if row['employer_key']==normalized(company):company_week+=1
        if row['employer_key']==normalized(company):last=max(last,date) if last else date
    if daily>=policy.max_daily:return 'DAILY_QUOTA'
    if weekly>=policy.max_weekly:return 'WEEKLY_QUOTA'
    if company_week>=policy.max_company_weekly:return 'COMPANY_WEEKLY_QUOTA'
    if last and clock-last<timedelta(hours=policy.cooldown_hours):return 'COMPANY_COOLDOWN'
    return None


def save_plan(db, job, decision, policy_id, facts_hash='', analysis_id=None, environment='SIMULATION'):
    state={'ALLOW':'LISTA_PARA_PREPARAR','HOLD':'PENDIENTE_VERIFICACION','BLOCK':'NO_ELEGIBLE'}[decision.outcome]
    with db.transaction():
        prior=db.rows('SELECT id FROM application_plans WHERE job_id=? AND policy_id IS ? AND content_hash=? AND facts_hash=? AND environment=?',
                      (job['id'],policy_id,job['content_hash'],facts_hash,environment))
        if prior:
            pid=prior[0]['id']
            if not db.rows('SELECT id FROM application_attempts WHERE plan_id=?',(pid,)):
                db.execute('UPDATE application_plans SET decision=?,reasons=?,state=?,analysis_id=? WHERE id=?',
                           (decision.outcome,json.dumps(decision.to_dict()['reasons'],ensure_ascii=False),state,analysis_id,pid))
                event(db,'ELIGIBILITY_REEVALUATED',{'decision':decision.outcome},pid,after=state)
            return pid
        pid=db.execute('''INSERT INTO application_plans(job_id,policy_id,content_hash,facts_hash,fingerprint,environment,decision,reasons,state,analysis_id,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(job['id'],policy_id,job['content_hash'],facts_hash,digest(identities(job)),environment,decision.outcome,
            json.dumps(decision.to_dict()['reasons'],ensure_ascii=False),state,analysis_id,now()))
        event(db,'ELIGIBILITY_EVALUATED',{'decision':decision.outcome},pid,after=state)
    return pid


def reserve(db, plan_id, job, environment='SIMULATION'):
    if environment!='SIMULATION':require_live(db)
    with db.transaction() as con:
        if not con.in_transaction:con.execute('BEGIN IMMEDIATE')
        control,row,policy=current_policy(db)
        plan=db.rows('SELECT * FROM application_plans WHERE id=?',(plan_id,))[0]
        if not policy or control['paused'] or not control['enabled'] or control['alert'] or plan['policy_id']!=row['id']:
            raise PermissionError('POLICY_CHANGED_OR_PAUSED')
        if datetime.fromisoformat(policy.expires_at)<=datetime.now(ZoneInfo('Europe/Dublin')):raise PermissionError('POLICY_EXPIRED')
        if plan['decision']!='ALLOW' or plan['content_hash']!=job['content_hash']:raise PermissionError('PLAN_STALE_OR_HELD')
        if plan['environment']!=environment:raise PermissionError('PLAN_ENVIRONMENT_MISMATCH')
        if plan['job_id']!=job['id']:raise PermissionError('PLAN_JOB_MISMATCH')
        stored=db.rows('SELECT * FROM jobs WHERE id=?',(plan['job_id'],))[0]
        if stored['content_hash']!=plan['content_hash']:raise PermissionError('JOB_CHANGED')
        require_it_job(stored)
        if already_applied(db,job,environment):raise PermissionError('ALREADY_APPLIED_OR_RESERVED')
        reason=quota_reason(db,policy,job['company'],environment)
        if reason:raise PermissionError(reason)
        aid=db.execute('''INSERT INTO application_attempts(plan_id,state,adapter,target_url,started_at,updated_at,policy_epoch)
            VALUES(?,?,?,?,?,?,?)''',(plan_id,'APROBADA_POR_POLITICA','pending',job.get('apply_url') or job['url'],now(),now(),control['epoch']))
        for key in identities(job,db.rows('SELECT * FROM job_sources WHERE job_id=?',(job['id'],))):
            db.execute('INSERT INTO application_identities VALUES(?,?,?)',(key,environment,aid))
        db.execute('INSERT INTO application_reservations(attempt_id,environment,employer_key,reserved_at) VALUES(?,?,?,?)',(aid,environment,normalized(job['company']),now()))
        db.execute("UPDATE application_plans SET state='APROBADA_POR_POLITICA' WHERE id=?",(plan_id,))
        from .vault import clearance_for
        analysis=db.rows('SELECT result FROM job_analyses WHERE id=?',(plan['analysis_id'],))
        event(db,'PREFINAL_BINDING',{'clearance_hash':digest(clearance_for(db,job['id'])),
              'analysis_hash':digest(analysis[0]['result'] if analysis else None)},plan_id,aid)
        event(db,'RESERVED',{'environment':environment},plan_id,aid,after='APROBADA_POR_POLITICA')
    return aid


def transition(db, attempt_id, state, code=None, confirmation=None):
    with db.transaction() as con:
        if not con.in_transaction:con.execute('BEGIN IMMEDIATE')
        row=db.rows('SELECT * FROM application_attempts WHERE id=?',(attempt_id,))[0]
        if state not in TRANSITIONS.get(row['state'],set()):raise ValueError('INVALID_STATE_TRANSITION')
        if state=='ENVIANDO':
            prefinal_check(db,attempt_id)
            require_live(db)
            # Kept behind the independent LIVE lock. A future released transport
            # cannot rely on the older selection decision or just the IT title.
            inspection=db.rows('''SELECT i.id FROM autoapply_form_inspections i
                JOIN application_plans p ON p.job_id=i.job_id WHERE p.id=? AND i.form_hash=? ORDER BY i.id DESC LIMIT 1''',
                               (row['plan_id'],row['form_hash']))
            if not inspection:raise PermissionError('FRESH_FORM_INSPECTION_REQUIRED')
            from .final_gate import final_submission_gate
            final_submission_gate(db,attempt_id,inspection[0]['id'])
        if state=='ENVIADA_CONFIRMADA':
            require_live(db)
            if not confirmation:raise ValueError('CONFIRMATION_REQUIRED')
            receipts=db.rows("SELECT id FROM application_receipt_evidence WHERE id=? AND attempt_id=? AND environment='LIVE' AND status='VERIFIED_REAL_RECEIPT'",(confirmation.get('receipt_id'),attempt_id))
            if not receipts:raise PermissionError('VERIFIED_CORRELATED_RECEIPT_REQUIRED')
        db.execute('UPDATE application_attempts SET state=?,updated_at=?,error_code=?,confirmation_reference=?,confirmation_hash=? WHERE id=?',
            (state,now(),code,(confirmation or {}).get('reference'),digest(confirmation) if confirmation else None,attempt_id))
        db.execute('UPDATE application_plans SET state=? WHERE id=?',(state,row['plan_id']))
        event(db,'STATE_CHANGED',{'code':code},row['plan_id'],attempt_id,row['state'],state)


def prefinal_check(db, attempt_id):
    with db.transaction() as con:
        if not con.in_transaction:con.execute('BEGIN IMMEDIATE')
        attempt=db.rows('SELECT * FROM application_attempts WHERE id=?',(attempt_id,))[0]
        control,row,policy=current_policy(db)
        if not policy or not control['enabled'] or control['paused'] or control['alert'] or control['epoch']!=attempt['policy_epoch']:
            raise PermissionError('POLICY_CHANGED_OR_PAUSED')
        if datetime.fromisoformat(policy.expires_at)<=datetime.now(ZoneInfo('Europe/Dublin')):raise PermissionError('POLICY_EXPIRED')
        plan=db.rows('SELECT * FROM application_plans WHERE id=?',(attempt['plan_id'],))[0]
        if plan['policy_id']!=row['id']:raise PermissionError('POLICY_VERSION_CHANGED')
        job=db.rows('SELECT * FROM jobs WHERE id=?',(plan['job_id'],))[0]
        if job['content_hash']!=plan['content_hash']:raise PermissionError('JOB_CHANGED')
        require_it_job(job)
        from .vault import candidate_snapshot
        candidate=candidate_snapshot(db)
        if candidate.get('_facts_hash','')!=plan['facts_hash']:raise PermissionError('CANDIDATE_CHANGED')
        if candidate.get('cv_document_id')!=attempt['document_id'] or attempt['document_id'] not in policy.authorized_document_ids:
            raise PermissionError('CV_VERSION_CHANGED')
        from .vault import clearance_for
        binding=db.rows("SELECT details FROM application_events WHERE attempt_id=? AND kind='PREFINAL_BINDING' ORDER BY id DESC LIMIT 1",(attempt_id,))
        expected=json.loads(binding[0]['details']) if binding else {}
        analysis=db.rows('SELECT result FROM job_analyses WHERE id=?',(plan['analysis_id'],))
        if expected.get('clearance_hash')!=digest(clearance_for(db,job['id'])) or expected.get('analysis_hash')!=digest(analysis[0]['result'] if analysis else None):
            raise PermissionError('REQUIREMENTS_OR_ANALYSIS_CHANGED')
        verification=datetime.fromisoformat(job.get('last_verified_at') or '1900-01-01T00:00:00+00:00')
        if job.get('open_status')!='OPEN_CONFIRMED' or verification.tzinfo is None or not timedelta(0)<=datetime.now(ZoneInfo('Europe/Dublin'))-verification<=timedelta(hours=policy.max_verification_hours):
            raise PermissionError('VACANCY_NO_LONGER_CONFIRMED')
        from ..verification import deadline_state,evidence_status
        raw=json.loads(job['raw']) if isinstance(job['raw'],str) else job['raw']
        deadline,_=deadline_state(raw)
        if deadline=='EXPIRED' or evidence_status({**job,'raw':raw})[0]=='CLOSED_CONFIRMED':
            raise PermissionError('VACANCY_CLOSED_BEFORE_FINAL')
        if deadline not in {'ABSENT','NOT_EXPIRED'}:raise PermissionError('DEADLINE_NOT_VERIFIABLE')
        if raw.get('_listing_type')=='BOLSA_DE_TALENTO_SIN_VACANTE_CONCRETA' and not policy.allow_talent_pools:
            raise PermissionError('TALENT_POOL_NOT_AUTHORIZED')
        environment=plan['environment']
        reservations=db.rows('SELECT * FROM application_reservations WHERE attempt_id=? AND environment=?',(attempt_id,environment))
        if len(reservations)!=1:raise PermissionError('RESERVATION_MISSING_BEFORE_FINAL')
        if already_applied(db,job,environment,exclude_attempt=attempt_id):raise PermissionError('DUPLICATE_DISCOVERED_BEFORE_FINAL')
        quota=quota_reason(db,policy,job['company'],environment,exclude_attempt=attempt_id)
        if quota:raise PermissionError(quota)
        if not policy.window_start<=datetime.now(ZoneInfo('Europe/Dublin')).strftime('%H:%M')<policy.window_end:raise PermissionError('OUTSIDE_TIME_WINDOW')
        reserved_at=datetime.fromisoformat(reservations[0]['reserved_at'])
        clock=datetime.now(ZoneInfo('Europe/Dublin'))
        if reserved_at.tzinfo is None or reserved_at>clock:raise PermissionError('RESERVATION_TIME_INVALID')
        if reserved_at.astimezone(ZoneInfo('Europe/Dublin')).date()!=clock.date():
            db.execute('UPDATE application_reservations SET reserved_at=? WHERE attempt_id=?',(clock.isoformat(timespec='seconds'),attempt_id))
            event(db,'RESERVATION_MOVED_TO_FINAL_DAY',{'previous_reservation_at':reservations[0]['reserved_at']},plan['id'],attempt_id)
        return control


def reconcile(db):
    # No automated retry/click. An interrupted final action is uncertain forever until evidenced reconciliation.
    with db.transaction():
        sending=db.rows("SELECT id FROM application_attempts WHERE state='ENVIANDO'")
        for a in sending:transition(db,a['id'],'ENVIO_INCIERTO','PROCESS_INTERRUPTED_AFTER_SEND_BEGAN')
        interrupted=db.rows("SELECT id FROM application_attempts WHERE state IN ('APROBADA_POR_POLITICA','PREPARADA','RELLENANDO','LISTA_PARA_ENVIO')")
        for a in interrupted:transition(db,a['id'],'CANCELADA','INTERRUPTED_NO_AUTOMATIC_RESEND')
        uncertain=db.rows("SELECT id,plan_id,state FROM application_attempts WHERE state='ENVIO_INCIERTO'")
    return {'uncertain':uncertain,'interrupted_presend_cancelled':len(interrupted),'email_checked':False,'live_enabled':False}
