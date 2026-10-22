"""Reviewable, version-bound, single-application trial protocol; no released sender."""
import getpass
import json
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from ..config import now,digest,load_profile
from ..repository import latest_analyses
from .policy import current_policy,event,require_live
from .platforms import platform_for
from .vault import candidate_snapshot,clearance_for
from .eligibility import evaluate_autoapply
from .it_scope import require_it_job
from .forms import load_inspection,answer_plan
from .store import already_applied,quota_reason

TRIAL_CONSENT='AUTHORIZE_ONE_CONTROLLED_APPLICATION'


def trial_snapshot(db,job_id,inspection_id=None):
    rows=db.rows('SELECT * FROM jobs WHERE id=?',(job_id,))
    if not rows:raise ValueError('JOB_NOT_FOUND')
    job=rows[0];require_it_job(job)
    control,row,policy=current_policy(db);candidate=candidate_snapshot(db)
    doc=db.rows('SELECT id,file_hash FROM candidate_documents WHERE id=?',(candidate.get('cv_document_id'),))
    inspection=load_inspection(db,inspection_id) if inspection_id else None
    if inspection and inspection['job_id']!=job_id:raise ValueError('INSPECTION_JOB_MISMATCH')
    platform=platform_for(job.get('apply_url') or job['url'])
    return {'job_id':job_id,'job_content_hash':job['content_hash'],'facts_hash':candidate['_facts_hash'],
            'document_id':doc[0]['id'] if doc else None,'document_hash':doc[0]['file_hash'] if doc else None,
            'policy_id':row['id'] if row else None,'policy_hash':row['integrity_hash'] if row else None,'policy_epoch':control['epoch'],
            'adapter':platform['id'],'adapter_version':platform['version'],'target_url':job.get('apply_url') or job['url'],
            'inspection_id':inspection_id,'form_hash':inspection['form_hash'] if inspection else None,
            'max_submissions':1,'autonomous_activation_authorized':False}


def trial_readiness(db,job_id,inspection_id=None):
    snap=trial_snapshot(db,job_id,inspection_id)
    job=db.rows('SELECT * FROM jobs WHERE id=?',(job_id,))[0]
    control,row,policy=current_policy(db);candidate=candidate_snapshot(db)
    platform=platform_for(snap['target_url'])
    decision=evaluate_autoapply(job,latest_analyses(db).get(job_id,{}),load_profile(),policy,
        db.rows('SELECT * FROM commute_checks WHERE job_id=? ORDER BY id DESC',(job_id,)),platform=platform,control=control,candidate=candidate,
        clearance=clearance_for(db,job_id),duplicate=already_applied(db,job),quota_reason=quota_reason(db,policy,job['company']) if policy else None,db=db)
    blockers=[r.code for r in decision.reasons]
    if not snap['document_id']:blockers.append('APPROVED_CV_REQUIRED')
    if not inspection_id:blockers.append('FRESH_FORM_INSPECTION_REQUIRED')
    else:
        inspection=load_inspection(db,inspection_id)
        blockers+=inspection['blockers']
        blockers+=['UNRESOLVED_VERIFIED_ANSWERS'] if answer_plan(inspection,candidate)['unresolved'] else []
        if not inspection.get('hosted_form_verified'):blockers.append('HOSTED_FORM_COMPLETION_UNVERIFIED')
    if not platform.get('automation_permitted'):blockers.append('PLATFORM_SUBMISSION_PERMISSION_UNVERIFIED')
    if not platform.get('trial_sender_released'):blockers.append('CONTROLLED_TRIAL_TRANSPORT_NOT_RELEASED')
    return {'ready':not blockers,'blockers':sorted(set(blockers)),'snapshot':snap,'live_enabled':False,
            'procedure':['Revisar CV final y autorizar política IT con límites explícitos.',
                         'Comprobar adaptador/permiso y todos los requisitos, preguntas, vigencia y rutas.',
                         'Elegir una vacante y revisar versión/hash del paquete completo.',
                         'Autorizar expresamente un único ensayo limitado y con caducidad.',
                         'Revalidar y reservar identidad/cupo transaccionalmente antes del despacho.',
                         'Enviar una sola vez; si no hay recepción fiable conservar ENVIO_INCIERTO y no repetir.',
                         'Auditar el recibo y autorizar por separado la futura política autónoma.']}


def create_trial_plan(db,job_id,inspection_id=None):
    snap=trial_snapshot(db,job_id,inspection_id)
    expires=(datetime.now(ZoneInfo('Europe/Dublin'))+timedelta(hours=24)).isoformat(timespec='seconds')
    payload={**snap,'expires_at':expires};sha=digest(payload)
    tid=db.execute('INSERT INTO autoapply_trial_plans(job_id,created_at,snapshot,snapshot_hash,expires_at) VALUES(?,?,?,?,?)',
                   (job_id,now(),json.dumps(payload,sort_keys=True),sha,expires))
    event(db,'CONTROLLED_TRIAL_DRAFT_CREATED',{'trial_id':tid,'snapshot_hash':sha,'authorized':False})
    return {'trial_id':tid,'snapshot_hash':sha,'expires_at':expires,'authorized':False,'readiness':trial_readiness(db,job_id,inspection_id)}


def authorize_trial(db,trial_id,expected_hash,consent):
    if consent!=TRIAL_CONSENT:raise ValueError('SPECIFIC_SINGLE_TRIAL_AUTHORIZATION_REQUIRED')
    with db.transaction() as con:
        if not con.in_transaction:con.execute('BEGIN IMMEDIATE')
        rows=db.rows('SELECT * FROM autoapply_trial_plans WHERE id=?',(trial_id,))
        if not rows:raise ValueError('TRIAL_NOT_FOUND')
        row=rows[0];snapshot=json.loads(row['snapshot'])
        if expected_hash!=row['snapshot_hash'] or digest(snapshot)!=expected_hash:raise ValueError('TRIAL_REVIEW_HASH_MISMATCH')
        if datetime.fromisoformat(row['expires_at'])<=datetime.now(ZoneInfo('Europe/Dublin')):raise ValueError('TRIAL_EXPIRED')
        current=trial_snapshot(db,row['job_id'],snapshot['inspection_id'])
        if {k:v for k,v in snapshot.items() if k!='expires_at'}!=current:raise ValueError('TRIAL_PACKAGE_CHANGED_REVIEW_REQUIRED')
        if not trial_readiness(db,row['job_id'],snapshot['inspection_id'])['ready']:raise PermissionError('CONTROLLED_TRIAL_NOT_READY')
        existing=db.rows('SELECT id FROM autoapply_trial_consents WHERE trial_id=?',(trial_id,))
        if existing:return existing[0]['id']
        cid=db.execute('INSERT INTO autoapply_trial_consents(trial_id,snapshot_hash,authorized_at,local_user,consent,max_submissions) VALUES(?,?,?,?,?,1)',
                       (trial_id,expected_hash,now(),getpass.getuser(),consent))
        event(db,'SINGLE_TRIAL_EXPLICITLY_AUTHORIZED',{'trial_id':trial_id,'consent_id':cid,'max_submissions':1})
        return cid


def execute_trial(db,trial_id):
    # No released transport exists. Even an inserted/forged consent cannot dispatch data.
    if not db.rows('SELECT id FROM autoapply_trial_consents WHERE trial_id=?',(trial_id,)):
        raise PermissionError('SPECIFIC_SINGLE_TRIAL_AUTHORIZATION_REQUIRED')
    raise PermissionError('CONTROLLED_TRIAL_TRANSPORT_NOT_RELEASED')


def autonomous_readiness(db):
    control,row,policy=current_policy(db);candidate=candidate_snapshot(db)
    blockers=[]
    if not candidate.get('cv_document_id'):blockers.append('APPROVED_CV_REQUIRED')
    if not policy or not control['enabled'] or control['paused'] or control['alert']:blockers.append('ACTIVE_IT_POLICY_REQUIRED')
    blockers+=['REAL_ADAPTER_AND_SUBMISSION_PERMISSION_REQUIRED','AUTHORIZED_REAL_TRIAL_NOT_COMPLETED','LIVE_RELEASE_LOCKED']
    return {'ready':False,'live_enabled':False,'blockers':blockers,'individual_application_approval_after_activation':False,
            'current_policy_id':row['id'] if row else None,'candidate_document_id':candidate.get('cv_document_id')}


def autonomous_cycle(db,live=False):
    if live:require_live(db)
    from .engine import run_simulation
    return run_simulation(db)
