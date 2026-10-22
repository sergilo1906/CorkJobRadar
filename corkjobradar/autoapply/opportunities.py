"""Inventory of actual stored ATS/vacancies, without changing eligibility or approvals."""
from collections import Counter,defaultdict
import json
from pathlib import Path
import re
from urllib.parse import urlsplit,urlunsplit
from uuid import uuid4
from ..config import ROOT,now,digest
from ..passages import source_passages
from .it_scope import classify_it_functions
from .platforms import platform_for
from .policy import current_policy
from .vault import candidate_snapshot

TITLE_HINT=re.compile(r'\bIT\b|\bICT\b|software|developer|helpdesk|service desk|desktop support|application support|support technician|\bQA\b|technical support|systems? engineer|\bERP\b|Oracle.*consultant|cloud.*consultant|network engineer|computer technician',re.I)
ATS_DOCS={
 'greenhouse':['https://docs.greenhouse.io/job-board.html'],
 'ashby':['https://developers.ashbyhq.com/reference/applicationformsubmit','https://developers.ashbyhq.com/reference/authentication'],
 'lever':['https://github.com/lever/postings-api#apply-to-a-job-posting'],
 'smartrecruiters':['https://developers.smartrecruiters.com/docs/application-api','https://developers.smartrecruiters.com/docs/authentication'],
 'recruitee':['https://docs.recruitee.com/reference/intro-to-careers-site-api','https://docs.recruitee.com/reference/authentication-1'],
}


def identify_ats(url):
    p=urlsplit(url);cap=platform_for(url)
    if cap['id']!='unsupported':return cap['id']
    if p.hostname=='jobs.ashbyhq.com':return 'ashby'
    if p.hostname in {'jobs.smartrecruiters.com','api.smartrecruiters.com'}:return 'smartrecruiters'
    return 'unidentified'


def requirement_signals(description):
    """Only literal mandatory passages. Signals require review, never grant clearance."""
    passages,_=source_passages(description);signals=[]
    for p in passages:
        if p['section']!='mandatory':continue
        for quote in p['text'].splitlines():
            quote=quote.strip()
            if not quote:continue
            kind=None
            if re.search(r'\b\d+(?:\.\d+)?\s*(?:[-–]\s*\d+)?\+?\s*years?\b.{0,70}\bexperience\b',quote,re.I):kind='EXPERIENCE_REVIEW_REQUIRED'
            elif re.search(r'\bnative\b|\bfluent\b|\bfluency\b',quote,re.I):kind='LANGUAGE_REVIEW_REQUIRED'
            elif re.search(r'\bdegree\b|\bLevel\s*8\b|\bbachelor',quote,re.I):kind='EDUCATION_REVIEW_REQUIRED'
            if kind and quote in description:signals.append({'kind':kind,'quote':quote,'offset':description.index(quote)})
    return signals


def inventory(db):
    # A consistent read snapshot: every stored job has an explicit outcome.
    with db.read_snapshot() as snapshot:
        jobs=snapshot.rows('SELECT * FROM jobs ORDER BY id')
    control,policy_row,policy=current_policy(db);candidate=candidate_snapshot(db)
    groups=defaultdict(list);records=[]
    for job in jobs:
        scope=classify_it_functions(job);url=job.get('apply_url') or job['url'];p=urlsplit(url)
        ats=identify_ats(url);cap=platform_for(url)
        relevant=scope.status=='CONFIRMED_IT' or bool(TITLE_HINT.search(job['title']))
        reasons=[]
        if scope.status!='CONFIRMED_IT':reasons.append(scope.reason)
        if job['scope']=='FUERA_DE_ALCANCE':reasons.append('OUTSIDE_STORED_SEARCH_SCOPE')
        if job['open_status']!='OPEN_CONFIRMED':reasons.append('CURRENT_ACCEPTANCE_REQUIRES_VERIFICATION')
        if not candidate.get('cv_document_id'):reasons.append('FINAL_CV_NOT_APPROVED')
        if not policy or not control['enabled'] or control['paused']:reasons.append('AUTHORIZED_ACTIVE_POLICY_REQUIRED')
        if not cap.get('automation_permitted'):reasons.append('PROVIDER_SUBMISSION_SCOPE_NOT_VERIFIED')
        if not cap.get('live_supported'):reasons.append('EXTERNAL_TRANSPORT_NOT_VERIFIED')
        if job['mode']!='REMOTE':reasons.append('EXACT_NON_CAR_COMMUTE_REVIEW_REQUIRED')
        else:reasons.append('IRELAND_REMOTE_ELIGIBILITY_REVIEW_REQUIRED')
        signals=requirement_signals(job['description']) if relevant else []
        reasons+=sorted({s['kind'] for s in signals})
        state='OUTSIDE_SCOPE_RETAINED' if job['scope']=='FUERA_DE_ALCANCE' else 'NON_IT_OR_UNCONFIRMED_RETAINED' if not relevant else 'HOLD'
        clean_url=urlunsplit((p.scheme,p.netloc,p.path,'','')) if not p.username and not p.password else None
        local=bool(re.search(r'\bcork\b|\bireland\b',job['location'],re.I)) and job['scope']!='FUERA_DE_ALCANCE'
        record={'job_id':job['id'],'company':job['company'],'title':job['title'],'location':job['location'],'mode':job['mode'],
                'url':clean_url,'content_hash':job['content_hash'],'ats':ats,'it_classification':scope.status,
                'it_relevance_for_research':relevant,'local_or_ireland_candidate':local,'state':state,
                'reasons':sorted(set(reasons)),'mandatory_signals':signals,'trial_ready':False}
        records.append(record)
        if relevant:groups[(job['company'],ats)].append(record)
    companies=[]
    for (company,ats),rows in groups.items():
        companies.append({'company':company,'ats':ats,'stored_it_or_related':len(rows),
                          'confirmed_it':sum(r['it_classification']=='CONFIRMED_IT' for r in rows),
                          'local_or_ireland_candidates':sum(r['local_or_ireland_candidate'] for r in rows),
                          'submission_classification':'PENDING_VALIDATION','documentation':ATS_DOCS.get(ats,[])})
    return {'created_at':now(),'version':'stored-ats-inventory-1','jobs_processed':len(records),
            'confirmed_it':sum(r['it_classification']=='CONFIRMED_IT' for r in records),
            'outcomes':dict(Counter(r['state'] for r in records)),
            'companies':sorted(companies,key=lambda r:(-r['local_or_ireland_candidates'],-r['confirmed_it'],r['company'])),
            'offers':records,'facts_hash':candidate['_facts_hash'],'approved_cv_document_id':candidate.get('cv_document_id'),
            'policy_id':policy_row['id'] if policy_row else None,'live_enabled':False,'compatible_real_trial_identified':False,
            'limitation':'Inventario y señales literales; no acredita compatibilidad, revisión íntegra de requisitos ni permiso de envío. Sin candidaturas creadas.'}


def persist_inventory(db):
    report=inventory(db);folder=ROOT/'data/ats-reviews';folder.mkdir(exist_ok=True)
    path=folder/('inventory-'+now().replace(':','')+'-'+uuid4().hex[:8]+'.json')
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report,path
