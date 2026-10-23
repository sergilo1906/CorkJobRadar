"""Batched read model. No HTTP, queue mutation or per-job SQLite queries."""
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st
from ..config import ROOT,digest
from ..repository import latest_analyses,all_jobs
from ..autoapply.it_scope import classify_it_functions
from ..autoapply.broad_selection import experience_requirements
from ..autoapply.vault import candidate_snapshot
from ..autoapply.academic import assessment as academic_assessment,label as academic_label,VERSION as ACADEMIC_VERSION
from .visibility import application_state
from ..verification import deadline_state


def date_label(value,empty='Pendiente'):
    if not value:return empty
    try:return datetime.fromisoformat(value).astimezone(ZoneInfo('Europe/Dublin')).strftime('%d/%m/%Y · %H:%M')
    except (ValueError,TypeError):return str(value)


def parse(value,default=None):
    try:return json.loads(value) if isinstance(value,str) else value if value is not None else default
    except (ValueError,TypeError):return default


def load_view(db):
    # Heartbeats do not invalidate the list. Content/documents/history changes do.
    # The bounded TTL also expires geographical evidence and public verification displays.
    signature=db.rows('''SELECT
      (SELECT group_concat(id||content_hash||open_status||COALESCE(last_verified_at,'')) FROM jobs) jobs,
      (SELECT MAX(id) FROM job_analyses) analysis,
      (SELECT group_concat(id||COALESCE(revoked_at,'')) FROM candidate_facts) facts,
      (SELECT group_concat(id||COALESCE(approved_at,'')||COALESCE(revoked_at,'')) FROM candidate_documents) documents,
      (SELECT group_concat(binding_hash||workflow_state||application_state) FROM it_application_queue) queue,
      (SELECT group_concat(id||state||updated_at) FROM application_attempts) attempts,
      (SELECT group_concat(id||status) FROM application_receipt_evidence) receipts,
      (SELECT group_concat(id||status) FROM autoapply_interventions) interventions,
      (SELECT MAX(id) FROM manual_application_handoffs) handoffs,
      (SELECT MAX(id) FROM manual_application_declarations) declarations,
      (SELECT MAX(id) FROM job_document_events) document_events,
      (SELECT group_concat(id||COALESCE(revoked_at,'')) FROM job_document_bundles) document_bundles,
      (SELECT MAX(id) FROM user_actions) actions''')[0]
    return _load_view((str(db.path.resolve()),digest(signature),(ROOT/'config/profile.yaml').stat().st_mtime_ns),db)


@st.cache_data(ttl=20,show_spinner=False)
def _load_view(signature,_db):
    db=_db
    analyses=latest_analyses(db);jobs=all_jobs(db,analyses)
    queue={r['job_id']:r for r in db.rows('SELECT * FROM it_application_queue')}
    manual={r['job_id']:r for r in db.rows('''SELECT h.job_id,MAX(d.declared_at) at FROM manual_application_declarations d
        JOIN manual_application_handoffs h ON h.id=d.handoff_id GROUP BY h.job_id''')}
    prepared={r['job_id']:r for r in db.rows('SELECT job_id,MAX(created_at) at FROM manual_application_handoffs WHERE expires_at>? GROUP BY job_id',(datetime.now(ZoneInfo('Europe/Dublin')).isoformat(),))}
    attempts=db.rows('''SELECT p.job_id,p.environment,a.state,a.updated_at,
        EXISTS(SELECT 1 FROM application_receipt_evidence r WHERE r.attempt_id=a.id AND r.environment='LIVE' AND r.status='VERIFIED_REAL_RECEIPT') receipt
        FROM application_attempts a JOIN application_plans p ON p.id=a.plan_id ORDER BY a.id''')
    states={}
    for a in attempts:
        if a['environment']=='LIVE':states[a['job_id']]=a
    interventions={r['job_id']:r for r in db.rows('''SELECT p.job_id,s.status FROM autoapply_interventions s
        JOIN application_attempts a ON a.id=s.attempt_id JOIN application_plans p ON p.id=a.plan_id
        WHERE s.status NOT IN ('PRUEBA_LOCAL_CONFIRMADA','ENVIO_INCIERTO')''')}
    marks={};historical_manual=set()
    for r in db.rows('SELECT job_id,action,created_at FROM user_actions ORDER BY id'):
        marks[r['job_id']]=r
        if r['action']=='solicitada':historical_manual.add(r['job_id'])
    # Snapshot is used only to derive validity. Personal values never enter the list model.
    candidate=candidate_snapshot(db)
    cv_approved=bool(candidate.get('cv_document_id'))
    # A job-specific CV does not become the general CV. Retained per-job packets
    # are nevertheless visible; load/download always repeats the full gate.
    job_prepared={r['job_id']:r for r in db.rows('''SELECT b.job_id,MAX(b.id) bundle_id FROM job_document_bundles b
        JOIN job_document_versions v ON v.id=b.version_id JOIN jobs j ON j.id=b.job_id
        JOIN job_document_events e ON e.bundle_id=b.id AND e.kind='LOCAL_HANDOFF_PREPARED'
        WHERE b.revoked_at IS NULL AND v.revoked_at IS NULL AND b.expires_at>? AND v.facts_hash=?
          AND v.job_content_hash=j.content_hash AND v.id=(SELECT MAX(n.id) FROM job_document_versions n WHERE n.job_id=b.job_id)
        GROUP BY b.job_id''',(datetime.now(ZoneInfo('Europe/Dublin')).isoformat(),candidate['_facts_hash']))}
    for job in jobs:
        q=queue.get(job['id'],{});selection=parse(q.get('assessment'),{})
        it=classify_it_functions(job);exp=experience_requirements(job)
        job['it_status']=it.status;job['families']=list(it.families)
        job['selection']=selection
        saved=analyses.get(job['id'],{}).get('academic_review',{})
        job['academic_current']=saved.get('version')==ACADEMIC_VERSION and saved.get('facts_hash')==candidate['_cv_facts_hash'] and not job.get('analysis_stale')
        job['academic_review']=saved if job['academic_current'] else academic_assessment(job,candidate)
        job['academic_label']=academic_label(job['academic_review'])
        essential_academic=any(i['code'] in {'CURRENT_STUDENT_STATUS_PENDING','ACADEMIC_EQUIVALENCE_PENDING','ACADEMIC_ALTERNATIVE_PENDING'} and i['level']!='DESEABLE' for i in job['academic_review']['items'])
        essential_language=bool(re.search(r'\b(?:native|fluent|fluency)\b',job['description'],re.I) and re.search(r'locali[sz]ation|linguist|language',job['title'],re.I))
        job['review_priority']=2 if essential_academic or essential_language else 1 if re.search(r'\b(?:senior|lead|staff|principal|architect)\b',job['title'],re.I) else 0
        job['priority_note']='Candidatura condicionada a un requisito académico o lingüístico imprescindible; no se presume cumplido.' if essential_academic or essential_language else 'Revisar requisitos, vigencia y transporte; las diferencias menores no excluyen.'
        job['experience_items']=exp
        mandatory=[r['minimum_years'] for r in exp if r['level']=='OBLIGATORIO']
        job['minimum_years']=max(mandatory) if mandatory else None
        job['experience_label']=(str(job['minimum_years']).rstrip('0').rstrip('.') if isinstance(job['minimum_years'],float) else str(job['minimum_years']))+' años mín.' if mandatory else 'Experiencia por aclarar'
        geography=selection.get('geography',{})
        job['deadline_status'],job['deadline_at']=deadline_state(parse(job.get('raw'),{}))
        distance=geography.get('distance_km')
        job['distance_label']=f'{distance:.1f} km' if geography.get('worksite_verified') and distance is not None else 'Distancia pendiente'
        job['location_label']=job['location'] or 'Ubicación pendiente'
        # A locality hint prioritizes the list; it never establishes a distance or eligibility.
        nearby_hint=bool(re.search(r'\b(cork|ballinlough|cobh|midleton|carrigtwohill|ringaskiddy|little island|ballincollig|kinsale|mallow|fermoy|bandon|macroom|watergrasshill|glanmire|douglas)\b',job['location'],re.I))
        unknown_place=not job['location'].strip() or job['location'].strip().casefold() in {'unknown','not specified','ireland'}
        local_review=nearby_hint or unknown_place or geography.get('state')=='WITHIN_RADIUS'
        unknown_published_location=unknown_place or job['location'].strip().casefold() in {'no indicado por la empresa','no indicado','ubicación pendiente'}
        technical_title=bool(re.search(r'\b(?:software|developer|helpdesk|service desk|desktop support|application support|network engineer|junior support technician)\b',job['title'],re.I))
        job['pending_it_review']=it.status=='AMBIGUOUS' and technical_title and (nearby_hint or unknown_published_location) and job['open_status']!='CLOSED_CONFIRMED' and not any(r['excludes'] for r in exp)
        job['potential']=bool(local_review and it.status=='CONFIRMED_IT' and not any(r['excludes'] for r in exp) and not selection.get('exclusions') and geography.get('state')!='REMOTE_SEPARATE' and job['mode']!='REMOTE' and job['open_status']!='CLOSED_CONFIRMED' and job['deadline_status']!='EXPIRED')
        a=states.get(job['id'],{});mark=marks.get(job['id'],{})
        confirmed=a.get('state')=='ENVIADA_CONFIRMADA' and bool(a.get('receipt'))
        uncertain=a.get('state') in {'ENVIANDO','ENVIO_INCIERTO','ENVIADA_CONFIRMADA'} and not confirmed
        declared=job['id'] in manual or job['id'] in historical_manual
        job['manual_declared']=declared;job['external_confirmed']=confirmed
        # Prepared means a retained local packet, never an assertion of sending or current eligibility.
        # The existing load/download services revalidate content, CV, answers and duplicates on opening.
        valid_package=job['id'] in prepared and (cv_approved or job['id'] in job_prepared)
        job['document_bundle_id']=job_prepared.get(job['id'],{}).get('bundle_id')
        job['application']=application_state(closed=job['open_status']=='CLOSED_CONFIRMED' or mark.get('action')=='rechazada',
            manual=declared,confirmed=confirmed,uncertain=uncertain,intervention=job['id'] in interventions,
            prepared=valid_package,needs_review=it.status=='CONFIRMED_IT' and q.get('workflow_state') in {'INTERVENTION','FAILED_RETRY'})
        job['has_application']=bool(declared or a or job['id'] in prepared or job['id'] in interventions)
        job['application_at']=a.get('updated_at') or manual.get(job['id'],{}).get('at') or prepared.get(job['id'],{}).get('at')
        job['compatibility']='Para revisar' if job['potential'] else 'Remoto separado' if geography.get('state')=='REMOTE_SEPARATE' else 'Fuera de criterios' if selection.get('exclusions') or any(r['excludes'] for r in exp) else 'Funciones IT pendientes'
        # Only current backend selection can warrant the word compatible; no inference from a title.
        if selection.get('state') in {'ENVIABLE','ENVIABLE_CON_ADVERTENCIAS'} and cv_approved and selection.get('cv_approved') and not job.get('analysis_stale'):
            job['compatibility']='Evaluación favorable; revalidar'
        fact=analyses.get(job['id'],{}).get('facts',{}).get('salary',{}).get('value')
        job['salary_label']=(f"{fact.get('min','?')}–{fact.get('max',fact.get('min','?'))} {fact.get('currency','EUR')}/{fact.get('unit','')}" if isinstance(fact,dict) else str(fact) if fact else 'No publicado')
    return {'jobs':jobs,'analyses':analyses,'cv_approved':cv_approved,
            'approved_facts':len(candidate.get('_claims',[]))+len(candidate.get('_fact_ids',{})),
            'prepared':sum(j['application']=='Preparadas' for j in jobs),
            'confirmed':sum(j['external_confirmed'] for j in jobs),
            'manual':sum(j['manual_declared'] for j in jobs),
            'potential':sum(j['potential'] for j in jobs),
            'academic_reviewed':sum(j['academic_current'] for j in jobs),
            'priority_local':sum(j['potential'] and j['review_priority']==0 for j in jobs),
            'conditional_local':sum(j['potential'] and j['review_priority']==2 for j in jobs)}
            


def filter_jobs(jobs,query='',scope='Oportunidades IT',mode='Todas',status='Todas',family='Todas'):
    needle=query.strip().casefold()
    return sorted([j for j in jobs if (not needle or needle in (j['title']+' '+j['company']+' '+j['location_label']).casefold())
        and (scope=='Todas las ofertas' or (j.get('pending_it_review',False) if scope=='IT por confirmar' else j['potential'] if scope=='Oportunidades IT' else j['it_status']=='CONFIRMED_IT'))
        and (mode=='Todas' or j['mode']==mode) and (status=='Todas' or j['open_status']==status)
        and (family=='Todas' or family in j['families'])],key=lambda j:(j.get('review_priority',0),j.get('deadline_at') or '9999',j['company'],j['title']))
