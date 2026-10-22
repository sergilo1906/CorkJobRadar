"""Assisted application view models. API permission/policy are never manual holds."""
from collections import Counter
from datetime import datetime,timedelta,date,time
import json
import re
from urllib.parse import urlsplit
from ..config import now,load_profile
from ..geography import effective_checks,valid_commute
from ..verification import deadline_state,evidence_status
from .it_scope import classify_it_functions
from .manual_requirements import checklist
from .opportunities import TITLE_HINT
from .store import already_applied
from .vault import candidate_snapshot


def assess_manual_job(db,job,candidate=None,profile=None):
    candidate=candidate or candidate_snapshot(db);profile=profile or load_profile();scope=classify_it_functions(job)
    requirements=checklist(db,job,candidate,profile)
    unresolved=[r for r in requirements if r['level']!='DESEABLE' and r['status']=='PENDIENTE']
    unmet=[r for r in requirements if r['level']!='DESEABLE' and r['status']=='NO_CUMPLIDO']
    raw=json.loads(job['raw']) if isinstance(job['raw'],str) else job['raw']
    deadline,_=deadline_state(raw);source_status=evidence_status({**job,'raw':raw})[0]
    try:fresh=timedelta(0)<=datetime.fromisoformat(now())-datetime.fromisoformat(job['last_verified_at'])<=timedelta(hours=24)
    except (ValueError,TypeError):fresh=False
    open_ok=fresh and job['open_status']=='OPEN_CONFIRMED' and source_status!='CLOSED_CONFIRMED' and deadline in {'ABSENT','NOT_EXPIRED'}
    closed=source_status=='CLOSED_CONFIRMED' or job['open_status']=='CLOSED_CONFIRMED'
    duplicate=already_applied(db,job,'LIVE')
    routes=db.rows('SELECT * FROM commute_checks WHERE job_id=? ORDER BY id DESC',(job['id'],))
    clearance=db.rows('SELECT * FROM job_clearances WHERE job_id=? ORDER BY id DESC LIMIT 1',(job['id'],));cleared={};bound=False
    if clearance:
        row=clearance[0]
        try:
            cleared=json.loads(row['payload']);bound=row['facts_hash']==candidate['_facts_hash'] and row['content_hash']==job['content_hash'] and datetime.fromisoformat(row['expires_at'])>datetime.fromisoformat(now())
        except (ValueError,TypeError):pass
    transport=False;route_details=[];manual_schedule={}
    if job['mode']=='REMOTE':transport=bound and cleared.get('remote_from_ireland') is True
    else:
        for route in effective_checks(routes):
            details=json.loads(route['details']) if isinstance(route['details'],str) else route['details']
            route_details.append({'mode':route['mode'],'viability':route['viability'],'evidence_url':route['evidence_url'],
                                  **{k:details.get(k) for k in ('destination','duration_minutes','shift_start','shift_end','days','valid_until')}})
            exact=bound and all(cleared.get(k) and cleared[k]==details.get(k) for k in ('shift_start','shift_end','days'))
            manual=details.get('manual_assisted_only') is True and details.get('method')=='USER_VERIFIED_EXACT_SHIFT' and all(details.get(k) for k in ('shift_start','shift_end','days','schedule'))
            if valid_commute(route,profile) and details.get('job_content_hash')==job['content_hash'] and ((exact and details.get('schedule')==cleared.get('schedule')) or manual):
                transport=True
                if manual:manual_schedule=details
    # Aggregate old factual clearances remain evidence; new per-item reviews never feed AutoApply.
    if not requirements:unresolved=[{'reason':'Revisión íntegra de requisitos pendiente; no se interpreta una lista vacía como aptitud.'}]
    reasons=[]
    if scope.status!='CONFIRMED_IT':reasons.append('FUNCIONES_IT_POR_CONFIRMAR')
    if candidate.get('work_authorization')!='IRELAND_AUTHORIZED':reasons.append('DERECHO_LABORAL_IRLANDA_PENDIENTE')
    if job['scope']=='FUERA_DE_ALCANCE':reasons.append('FUERA_DEL_ALCANCE_GEOGRAFICO')
    if not open_ok:reasons.append('VIGENCIA_POR_COMPROBAR' if not closed else 'OFERTA_CERRADA')
    if unmet:reasons.append('REQUISITOS_NO_CUMPLIDOS')
    if unresolved:reasons.append('REQUISITOS_POR_CONTRASTAR')
    if not transport:reasons.append('TRANSPORTE_Y_HORARIO_PENDIENTES')
    if duplicate:reasons.append('CANDIDATURA_YA_REGISTRADA_O_RESERVADA')
    compatible=not reasons
    state='YA_REGISTRADA' if duplicate else 'CERRADA' if closed else 'FUERA_DE_ALCANCE' if job['scope']=='FUERA_DE_ALCANCE' else 'NO_CUMPLE_OBLIGATORIOS' if unmet else 'COMPATIBLE_VERIFICADA' if compatible else 'POR_REVISAR'
    return {'job_id':job['id'],'company':job['company'],'title':job['title'],'location':job['location'],
            'junior_or_support_title':bool(re.search(r'junior|trainee|intern|graduate|helpdesk|service desk|desktop support|IT support|application support|software support|support technician',job['title'],re.I)),
            'senior_title':bool(re.search(r'\b(?:senior|principal|lead|staff|head|director|manager|architect)\b',job['title'],re.I)),
            'mode':job['mode'],'it_status':scope.status,'state':state,'reasons':reasons,'open_confirmed':open_ok,
            'source_open_status':job['open_status'],'last_verified_at':job['last_verified_at'],'deadline':deadline,
            'requirements':requirements,'unmet_mandatory':len(unmet),'pending_mandatory':len(unresolved),
            'fulfilled':sum(r['status']=='CUMPLIDO' for r in requirements),'desirable':sum(r['level']=='DESEABLE' for r in requirements),
            'transport_verified':bool(transport),'route_details':route_details,'schedule':manual_schedule.get('schedule') or (cleared.get('schedule') if bound else None),
            'shift_start':manual_schedule.get('shift_start') or (cleared.get('shift_start') if bound else None),'shift_end':manual_schedule.get('shift_end') or (cleared.get('shift_end') if bound else None),
            'compatible_verified':compatible,'cv_approved':bool(candidate.get('cv_document_id')),
            'manual_package_possible':scope.status=='CONFIRMED_IT' and not duplicate and bool(candidate.get('cv_document_id')),
            'api_authorization_required_for_manual':False,'live_enabled':False}


def manual_inventory(db):
    with db.transaction() as con:
        if not con.in_transaction:con.execute('BEGIN')
        return _manual_inventory(db)


def _manual_inventory(db):
    candidate=candidate_snapshot(db);profile=load_profile();jobs=db.rows('SELECT * FROM jobs ORDER BY company,title,id');offers=[]
    for job in jobs:
        scope=classify_it_functions(job)
        if scope.status=='CONFIRMED_IT' or TITLE_HINT.search(job['title']):offers.append(assess_manual_job(db,job,candidate,profile))
    offers.sort(key=lambda r:(r['state']!='COMPATIBLE_VERIFICADA',r['state'] in {'YA_REGISTRADA','CERRADA','FUERA_DE_ALCANCE','NO_CUMPLE_OBLIGATORIOS'},r['senior_title'],not r['junior_or_support_title'],r['unmet_mandatory'],r['pending_mandatory'],r['title']))
    return {'generated_at':now(),'jobs_processed':len(jobs),'it_or_related_reviewed':len(offers),
            'states':dict(Counter(r['state'] for r in offers)),'offers':offers,'live_enabled':False,
            'limit':'Todos los registros se examinan; el orden no limita el análisis. Pendiente no significa compatible ni excluido. Sin permiso API para el uso manual.'}


def factual_introduction(candidate,job):
    from .it_scope import require_it_job
    require_it_job(job)
    experience=([c['text_en'] for c in candidate['_claims'] if c['section']=='Experience'] or [c['text_en'] for c in candidate['_claims']])[:2]
    if not experience or not candidate.get('full_name'):raise ValueError('APPROVED_EXPERIENCE_AND_NAME_REQUIRED')
    return ('Dear Hiring Team,\n\nPlease consider my application for '+job['title']+' at '+job['company']+'.\n'
            'My verified background includes:\n\n'+'\n\n'.join(experience)+'\n\nKind regards,\n'+candidate['full_name'])


def save_manual_transport(db,job_id,mode,evidence_url,details,expected_job_hash,*,confirmed=False):
    """Reuse route validation without requiring any AutoApply policy or clearance."""
    from .it_scope import require_it_job
    from .vault import approve_route
    if not confirmed:raise PermissionError('EXPLICIT_MANUAL_ROUTE_REVIEW_REQUIRED')
    with db.transaction() as con:
        if not con.in_transaction:con.execute('BEGIN IMMEDIATE')
        job=db.rows('SELECT * FROM jobs WHERE id=?',(job_id,))[0];require_it_job(job)
        if job['content_hash']!=expected_job_hash:raise ValueError('JOB_CHANGED_RECHECK_ROUTE')
        days=details.get('days')
        if not isinstance(days,list) or not days or not set(days).issubset({'Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'}):raise ValueError('EXACT_DAYS_REQUIRED')
        start=time.fromisoformat(details['shift_start']);end=time.fromisoformat(details['shift_end'])
        if end<=start and not details.get('overnight'):raise ValueError('CONFIRM_OVERNIGHT_SHIFT')
        if date.fromisoformat(details['valid_until'])<date.fromisoformat(now()[:10]):raise ValueError('ROUTE_EXPIRED')
        if not details.get('duration_minutes') or details.get('shift_compatible') is not True:raise ValueError('DURATION_AND_SHIFT_CHECK_REQUIRED')
        payload={**details,'manual_assisted_only':True,'days':sorted(set(days)),
                 'schedule':', '.join(days)+' '+start.isoformat(timespec='minutes')+' - '+end.isoformat(timespec='minutes')+(' (+1 day)' if details.get('overnight') else '')}
        return approve_route(db,job_id,mode,evidence_url,payload,transfers=0,confirmed=True)
