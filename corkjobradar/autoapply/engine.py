import json
from datetime import datetime
from zoneinfo import ZoneInfo
from ..config import now
from ..repository import latest_analyses
from ..worker import worker_lock
from .policy import current_policy,pause,event,require_live
from .eligibility import evaluate_autoapply
from .platforms import platform_for
from .vault import candidate_snapshot,clearance_for
from .store import already_applied,quota_reason,save_plan,reserve,transition,prefinal_check


def decisions(db):
    control,row,policy=current_policy(db)
    candidate=candidate_snapshot(db);analyses=latest_analyses(db)
    from ..config import load_profile
    profile=load_profile()
    for job in db.rows('SELECT * FROM jobs ORDER BY first_seen_at,id'):
        # Pause and revisions are observed throughout the loop, including jobs after an error.
        control,row,policy=current_policy(db)
        latest=db.rows("SELECT id FROM job_analyses WHERE job_id=? AND COALESCE(json_extract(result,'$.model_validation'),'') NOT IN ('RECHAZADO','EN_EVALUACION') ORDER BY id DESC LIMIT 1",(job['id'],))
        decision=evaluate_autoapply(job,analyses.get(job['id'],{}),profile,policy,
            db.rows('SELECT * FROM commute_checks WHERE job_id=? ORDER BY id DESC',(job['id'],)),
            platform=platform_for(job.get('apply_url') or job['url']),control=control,candidate=candidate,db=db,
            clearance=clearance_for(db,job['id']),policy_version=row['version'] if row else None,
            duplicate=already_applied(db,job),quota_reason=quota_reason(db,policy,job['company']) if policy else None)
        yield job,decision,row['id'] if row else None,candidate,latest[0]['id'] if latest else None


def preview(db,limit=25,it_only=True):
    # Limit affects this read-only view only; run_simulation always processes the complete database.
    rows=[]
    for job,d,pid,candidate,analysis_id in decisions(db):
        from .it_scope import classify_it_functions
        classification=classify_it_functions(job)
        if it_only and classification.status!='CONFIRMED_IT':continue
        rows.append({'job_id':job['id'],'title':job['title'],'company':job['company'],'decision':d.outcome,
                     'it_classification':classification.to_dict(),
                     'reason_codes':[r.code for r in d.reasons],'reason_messages':[r.message for r in d.reasons],'policy_id':pid,'url':job['url']})
        if len(rows)>=limit:break
    return rows


def run_simulation(db):
    counts={'processed':0,'ALLOW':0,'HOLD':0,'BLOCK':0,'prepared':0,'confirmed_live':0,'errors':0}
    with worker_lock(db):
        for job,decision,policy_id,candidate,analysis_id in decisions(db):
            plan_id=save_plan(db,job,decision,policy_id,candidate['_facts_hash'],analysis_id)
            counts['processed']+=1;counts[decision.outcome]+=1
            if decision.outcome!='ALLOW':continue
            attempt_id=None
            try:
                attempt_id=reserve(db,plan_id,job)
                from .it_scope import require_it_job
                require_it_job(db.rows('SELECT * FROM jobs WHERE id=?',(job['id'],))[0])
                from .documents import document_bytes
                _,_,sha=document_bytes(db,candidate['cv_document_id'])
                db.execute('UPDATE application_attempts SET document_id=? WHERE id=?',(candidate['cv_document_id'],attempt_id))
                transition(db,attempt_id,'PREPARADA')
                prefinal_check(db,attempt_id)
                # Production simulation does NOT fill public web forms: typing/uploading can itself transmit PII.
                transition(db,attempt_id,'REQUIERE_REVISION','OFFLINE_FORM_TRIAL_AND_ADAPTER_PERMISSION_REQUIRED')
                counts['prepared']+=1
            except Exception as exc:
                counts['errors']+=1
                if attempt_id:
                    state=db.rows('SELECT state FROM application_attempts WHERE id=?',(attempt_id,))[0]['state']
                    if state in {'APROBADA_POR_POLITICA','PREPARADA','RELLENANDO','LISTA_PARA_ENVIO'}:
                        transition(db,attempt_id,'CANCELADA','SIMULATION_PREPARATION_FAILED')
                # Exception text can contain personal input. Retain only type and structured state.
                event(db,'SIMULATION_FAILURE',{'error_type':type(exc).__name__},plan_id,attempt_id)
                _,_,policy=current_policy(db)
                if isinstance(exc,PermissionError) or counts['errors']>=(policy.max_failures if policy else 1):
                    pause(db,'SIMULATION_FAILURE_THRESHOLD',alert=True)
        event(db,'SIMULATION_COMPLETED',counts)
    return counts


def report(db):
    control,row,policy=current_policy(db)
    clock=datetime.now(ZoneInfo('Europe/Dublin'))
    from datetime import timedelta
    monday=clock.date()-timedelta(days=clock.weekday())
    reservations=db.rows('SELECT environment,reserved_at FROM application_reservations')
    usage={env:{'daily':0,'weekly':0} for env in ('SIMULATION','LIVE')}
    for reservation in reservations:
        date=datetime.fromisoformat(reservation['reserved_at']).astimezone(ZoneInfo('Europe/Dublin')).date()
        if date==clock.date():usage[reservation['environment']]['daily']+=1
        if monday<=date<=clock.date():usage[reservation['environment']]['weekly']+=1
    from collections import Counter
    from .it_scope import classify_it_functions,AUTHORIZATION_SCOPE
    classifications=Counter(classify_it_functions(j).status for j in db.rows('SELECT title,description,category,detail_complete FROM jobs'))
    return {'generated_at':now(),'authorization_scope':AUTHORIZATION_SCOPE,'it_classification_counts':dict(classifications),
            'mode':'ALERTA' if control['alert'] else 'DESACTIVADO' if not control['enabled'] else 'PAUSADO' if control['paused'] else 'SIMULACION',
            'live_submission_enabled':False,'policy_id':control['policy_id'],
            'quota_usage':usage,'quota_limits':{'daily':policy.max_daily,'weekly':policy.max_weekly} if policy else None,
            'plans':[dict(r) for r in db.rows('SELECT decision,state,COUNT(*) n FROM application_plans GROUP BY 1,2')],
            'attempts':db.rows('SELECT state,COUNT(*) n FROM application_attempts GROUP BY state'),
            'last_confirmation':db.rows("SELECT id,updated_at,confirmation_reference FROM application_attempts WHERE state='ENVIADA_CONFIRMADA' ORDER BY id DESC LIMIT 1"),
            'retention':'Hechos/documentos cifrados locales hasta revocación/borrado explícito; auditoría mínima de duplicados conservada.',
            'limitations':['Sin ensayo real autorizado','Ningún ATS autorizado para enviar','No se consulta correo','Simulación nunca expone datos a formularios públicos']}
