"""Independent diagnostic axes. No authorization, dispatch or eligibility grant."""
from collections import Counter,defaultdict
from datetime import datetime,timedelta
import hashlib
import json
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo
from ..config import ROOT,now,load_profile
from ..geography import effective_checks,valid_commute
from ..verification import deadline_state,evidence_status
from .documents import document_bytes
from .forms import answer_plan
from .interaction_modes import interaction_route
from .it_scope import classify_it_functions
from .opportunities import identify_ats,requirement_signals,TITLE_HINT,ATS_DOCS
from .platforms import platform_for
from .policy import current_policy
from .vault import candidate_snapshot,private_folder,protect

AXES=('permission','adapter','human_access','answers','transport','cv_policy','compatible_offer')
PROVIDER_ACTIONS={
 'greenhouse':'El titular del tablero debe autorizar una integración y, si procede, facilitar una credencial limitada y un entorno de prueba. Un candidato no puede generarlos.',
 'lever':'El Super Admin del empleador debe autorizar/generar la clave Postings y especificar campos; solicitar prueba controlada, no acceso general.',
 'ashby':'El titular de la organización debe autorizar acceso con candidatesWrite y una oferta/entorno de prueba; no usar el endpoint interno del navegador.',
 'smartrecruiters':'El cliente/partner debe autorizar OAuth candidate_applications_manage, preguntas/privacidad y consulta de estado.',
 'recruitee':'Acreditar permiso del destino y acceso a Careers Site API. El entorno RC de partners requiere concesión y no acredita por sí solo una Careers API de prueba.',
 'unidentified':'Revisar condiciones y mecanismo oficial del destino; hasta entonces preparación manual.',
}


def _axis(status,owner,code,detail='',**extra):
    return {'status':status,'owner':owner,'code':code,'detail':detail,**extra}


def _history(db,row,candidate,clock):
    """Read immutable public schema for diagnosis only; never bypass load_inspection."""
    if not row:return {'state':'NOT_INSPECTED','unresolved':[],'blockers':[]}
    try:
        path=Path(row['encrypted_path']).resolve()
        if not path.is_relative_to(private_folder(db)):raise ValueError('OUTSIDE_VAULT')
        raw=protect(path.read_bytes(),True)
        if hashlib.sha256(raw).hexdigest()!=path.name.split('.')[0]:raise ValueError('HASH_CHANGED')
        data=json.loads(raw)
        if data['form_hash']!=row['form_hash'] or data['job_id']!=row['job_id']:raise ValueError('BINDING_CHANGED')
        age=clock-datetime.fromisoformat(data['checked_at'])
        fresh=timedelta(0)<=age<=timedelta(hours=24)
        plan=answer_plan(data,candidate)
        missing=[{'field':f['id'],'label':f['label'],'required':f['required']} for f in data['fields'] if f['id'] not in plan['mapping']]
        return {'state':'CURRENT_STORED_SCHEMA' if fresh else 'STALE_STORED_SCHEMA','unresolved':missing,
                'blockers':data.get('blockers',[]),'inspected_at':row['inspected_at'],'inspection_id':row['id'],
                'content_hash':data['content_hash']}
    except Exception:return {'state':'UNREADABLE_STORED_SCHEMA','unresolved':[],'blockers':['REINSPECTION_REQUIRED']}


def build_blocker_report(db):
    clock=datetime.now(ZoneInfo('Europe/Dublin'));candidate=candidate_snapshot(db);control,policy_row,policy=current_policy(db)
    with db.read_snapshot() as view:
        jobs=view.rows('SELECT * FROM jobs ORDER BY company,title,id')
        inspections=view.rows('SELECT * FROM autoapply_form_inspections ORDER BY id DESC')
        clearances=view.rows('SELECT * FROM job_clearances ORDER BY id DESC')
        routes=view.rows('SELECT * FROM commute_checks ORDER BY id DESC')
    latest={};clear={};by_job=defaultdict(list)
    for row in inspections:latest.setdefault(row['job_id'],row)
    for row in clearances:clear.setdefault(row['job_id'],row)
    for row in routes:by_job[row['job_id']].append(row)
    doc_ok=False
    if candidate.get('cv_document_id'):
        try:document_bytes(db,candidate['cv_document_id']);doc_ok=True
        except Exception:pass
    policy_ok=bool(policy and control['enabled'] and not control['paused'] and not control['alert']
                   and datetime.fromisoformat(policy.expires_at)>clock)
    profile=load_profile();offers=[];company_rows=defaultdict(list)
    for job in jobs:
        url=job.get('apply_url') or job['url'];ats=identify_ats(url);cap=platform_for(url);mode=interaction_route(url,source_url=job['url'])
        scope=classify_it_functions(job);relevant=scope.status=='CONFIRMED_IT' or bool(TITLE_HINT.search(job['title']))
        history=_history(db,latest.get(job['id']),candidate,clock)
        if history.get('content_hash') not in {None,job['content_hash']}:history['state']='CHANGED_JOB_SCHEMA'
        facts=clear.get(job['id']);bound=False;clearance={}
        if facts:
            try:
                clearance=json.loads(facts['payload']);bound=(facts['content_hash']==job['content_hash'] and facts['facts_hash']==candidate['_facts_hash']
                           and datetime.fromisoformat(facts['expires_at'])>clock)
            except (ValueError,TypeError):pass
        mandatory_ok=bound and all(clearance.get(k) is True for k in ('requirements_met','legal_eligibility','experience_met'))
        transport_ok=False
        if job['mode']=='REMOTE':transport_ok=bound and clearance.get('remote_from_ireland') is True
        else:
            for route in effective_checks(by_job[job['id']]):
                try:
                    details=route['details'] if isinstance(route['details'],dict) else json.loads(route['details'])
                    exact=all(clearance.get(k) and details.get(k)==clearance[k] for k in ('shift_start','shift_end','days'))
                    if bound and exact and valid_commute(route,profile) and details.get('job_content_hash')==job['content_hash'] and details.get('schedule')==clearance.get('schedule'):
                        transport_ok=True
                except (ValueError,KeyError,TypeError):pass
        try:
            age=clock-datetime.fromisoformat(job['last_verified_at'])
            current=job['open_status']=='OPEN_CONFIRMED' and timedelta(0)<=age<=timedelta(hours=policy.max_verification_hours if policy else 24)
        except (ValueError,TypeError):current=False
        try:
            raw=json.loads(job['raw']) if isinstance(job['raw'],str) else job['raw']
            deadline,_=deadline_state(raw,clock)
            current=current and deadline in {'ABSENT','NOT_EXPIRED'} and evidence_status({**job,'raw':raw},clock)[0]!='CLOSED_CONFIRMED'
        except (ValueError,TypeError):current=False;deadline='UNPARSEABLE'
        axes={
          'permission':_axis('MANUAL_ONLY' if mode['mode'] in {'LINKEDIN_MANUAL','INDEED_MANUAL'} else 'NOT_GRANTED' if not cap['automation_permitted'] else 'REVIEWED',
              'THIRD_PARTY' if mode['mode']=='HOLD' else 'USER',mode['reason'],PROVIDER_ACTIONS.get(ats,PROVIDER_ACTIONS['unidentified'])),
          'adapter':_axis('PREPARATION_ONLY' if cap.get('preparation_supported') else 'MISSING','DEVELOPMENT','EXTERNAL_TRANSPORT_AND_RECEIPT_UNVERIFIED',
              'Inspección y preparación existentes se conservan; no hay despacho/recibo externo comprobado.',inspection_supported=bool(cap.get('inspection_supported'))),
          'human_access':_axis('HISTORICAL_BLOCK_OBSERVED' if any('CAPTCHA' in b or 'MFA' in b for b in history['blockers']) else 'NOT_CURRENTLY_VERIFIED',
              'USER','HUMAN_ACCESS_RECHECK_REQUIRED','Una observación antigua no acredita la sesión actual.',schema_state=history['state'],observed_at=history.get('inspected_at')),
          'answers':_axis('REINSPECTION_REQUIRED' if history['state']!='CURRENT_STORED_SCHEMA' else 'ANSWERS_PENDING' if history['unresolved'] else 'MAPPED_STORED_SCHEMA',
              'USER','REVIEW_EXACT_UNANSWERED_QUESTIONS','Solo respuestas aprobadas; ninguna respuesta se deduce para cerrar el formulario.',unresolved_questions=history['unresolved']),
          'transport':_axis('EVIDENCE_PRESENT_RECHECK_AT_SUBMISSION' if transport_ok else 'UNVERIFIED','USER',
              'REMOTE_IRELAND_AND_ONSITE_TERMS_REVIEW' if job['mode']=='REMOTE' else 'EXACT_NON_CAR_ROUND_TRIP_REQUIRED',
              'Origen Ballinlough; sin coche. Validar centro, días, turno e ida/vuelta. Remoto no implica elegibilidad desde Irlanda.'),
          'cv_policy':_axis('PENDING' if not doc_ok or not policy_ok else 'REVIEWED_VERSIONS','USER','CV_AND_POLICY_ARE_SEPARATE_APPROVALS',
              'Los hechos ya aprobados no requieren nueva aprobación. Descargar para uso manual no exige autorizar AutoApply.',approved_cv_available=doc_ok,authorized_policy_available=policy_ok),
          'compatible_offer':_axis('OUTSIDE_SCOPE' if job['scope']=='FUERA_DE_ALCANCE' else 'REVIEW_REQUIRED','USER','NO_COMPATIBLE_TRIAL_CERTIFIED',
              'Funciones IT, requisitos y vigencia se revisan por separado.',it_status=scope.status,requirements_verified=bool(mandatory_ok),
              current_acceptance_verified=current,deadline_state=deadline,mandatory_signals=requirement_signals(job['description']) if relevant else [])}
        record={'job_id':job['id'],'company':job['company'],'title':job['title'],'location':job['location'],'stored_scope':job['scope'],
                'ats':ats,'mode':mode['mode'],'it_relevant_for_research':relevant,'axes':axes,'ready_to_submit':False,'live_enabled':False}
        offers.append(record)
        if relevant:company_rows[(job['company'],ats)].append(record)
    companies=[]
    for (company,ats),rows in company_rows.items():
        companies.append({'company':company,'ats':ats,'stored_research_offers':len(rows),'in_stored_scope':sum(r['stored_scope']!='FUERA_DE_ALCANCE' for r in rows),
                          'third_party_action':PROVIDER_ACTIONS.get(ats,PROVIDER_ACTIONS['unidentified']),'documentation':ATS_DOCS.get(ats,[]),
                          'external_adapter_verified':False})
    return {'generated_at':now(),'version':'independent-blockers-1','jobs_processed':len(offers),'axes':list(AXES),'companies':companies,'offers':offers,
            'approved_facts_count':len(candidate['_claims'])+len(candidate['_fact_ids'])+len(candidate['_answers']),
            'approved_cv_available':doc_ok,'authorized_policy_available':policy_ok,'live_enabled':False,'external_submission_verified':False,
            'limit':'Diagnóstico independiente; no es una decisión ALLOW ni certifica compatibilidad. No crea candidaturas ni permisos.'}


def persist_blocker_report(db):
    report=build_blocker_report(db);folder=ROOT/'data/ats-reviews';folder.mkdir(exist_ok=True)
    path=folder/('blockers-'+now().replace(':','')+'-'+uuid4().hex[:8]+'.json')
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report,path
