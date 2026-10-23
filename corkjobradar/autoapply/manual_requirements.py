"""Evidence checklist for assisted applications. Never releases an AutoApply gate."""
import json
import re
from ..config import digest,now,load_profile
from ..passages import source_passages
from .it_scope import require_it_job
from .vault import candidate_snapshot

PREFERRED=re.compile(r'\b(?:preferred|desirable|advantageous|an advantage|a plus|nice.to.have|ideally|not required|not essential)\b',re.I)
MANDATORY=re.compile(r'\b(?:must|required|essential|mandatory|minimum|at least)\b',re.I)
TECHNICAL=re.compile(r'\b(?:experience|knowledge|familiarity|proficien\w*|qualification|degree|diploma|certificat\w*|English|Windows|Linux|SQL|Azure|AWS|network\w*|licen[cs]e|vehicle|car|eligib\w*|right to work)\b',re.I)
STATUSES={'CUMPLIDO','NO_CUMPLIDO','PENDIENTE'}


def requirement_items(job,section_aliases=None):
    text=job['description'];passages,_=source_passages(text,section_aliases=section_aliases);items=[]
    for passage in passages:
        if passage['section'] in {'duties','benefits','context'}:continue
        # Split explicit contrasting clauses; never split "degree OR equivalent experience".
        for match in re.finditer(r'[^;\n]+',passage['text']):
            segment=match.group().strip(' \t\r\n•*-')
            if not segment or not (passage['section'] in {'mandatory','desirable'} or TECHNICAL.search(segment) or MANDATORY.search(segment) or PREFERRED.search(segment)):continue
            pieces=re.split(r'(?<=[.!?])\s+|\s+(?:but|while)\s+(?=[A-Z])',segment)
            for quote in pieces:
                if not (passage['section'] in {'mandatory','desirable'} or TECHNICAL.search(quote) or MANDATORY.search(quote) or PREFERRED.search(quote)):continue
                explicit_required=MANDATORY.search(re.sub(r'\bnot (?:required|essential)\b','',quote,flags=re.I))
                header_preferred=passage['section']=='desirable'
                mixed=bool((PREFERRED.search(quote) or header_preferred) and (explicit_required or re.search(r'\b(?:will|should|need to)\b.{0,35}\bhave\b',quote,re.I)))
                conditional=bool(re.search(r'\b(?:if|when|unless|depending on)\b',quote,re.I))
                level='POR_ACLARAR' if mixed or conditional else 'DESEABLE' if PREFERRED.search(quote) or header_preferred else 'OBLIGATORIO' if passage['section']=='mandatory' or explicit_required else 'POR_ACLARAR'
                # No phrase is synthesized: source offset must still bind exactly.
                start=text.find(quote,passage['offset'])
                if start<0:continue
                key=digest({'quote':quote,'offset':start,'level':level})
                if not any(i['id']==key for i in items):items.append({'id':key,'quote':quote,'offset':start,'level':level})
    return items


def _automatic(item,candidate,profile):
    quote=item['quote'];status='PENDIENTE';fact_ids=[];reason='Revisar contra hechos aprobados; ausencia de evidencia no demuestra incumplimiento.'
    if item['level']=='DESEABLE':return status,fact_ids,'Preferible: no bloquea por sí solo la candidatura.'
    if item['level']=='POR_ACLARAR':return status,fact_ids,'Necesidad o condiciones por aclarar; no se interpreta como obligatorio incumplido ni como preferible.'
    from .academic import review_requirement
    academic=review_requirement(quote,candidate)
    if academic:return academic['status'],academic['fact_ids'],academic['reason']
    if re.search(r'\b(?:own|personal) (?:car|vehicle)\b',quote,re.I) and not profile.get('owns_car') and not re.search(r'\bor\b|not|without|no need',quote,re.I):
        return 'NO_CUMPLIDO',[],'El perfil de movilidad declara que no dispone de coche propio.'
    if re.search(r'\b(?:right|authori[sz]ed|eligible|eligibility)\b.{0,45}\bwork\b.{0,35}\bIreland\b',quote,re.I) and not re.search(r'future|sponsor|permanent resid|UK|United Kingdom',quote,re.I):
        if candidate.get('work_authorization')=='IRELAND_AUTHORIZED':return 'CUMPLIDO',[candidate['_fact_ids']['work_authorization']],'Derecho a trabajar en Irlanda aprobado; no responde preguntas distintas de patrocinio futuro.'
    years=re.search(r'\b(\d+(?:\.\d+)?)\s*(?:[-–]\s*\d+(?:\.\d+)?)?\+?\s*years?\b.{0,35}\bexperience\b|\bexperience\b.{0,15}\b(\d+(?:\.\d+)?)\+?\s*years?\b',quote,re.I)
    general=re.search(r'\b(?:IT support|helpdesk|service desk|desktop support)\b',quote,re.I)
    general_words=set('minimum at least of a an in the role roles position positions similar relevant related previous prior hands on work working experience it support helpdesk service desk desktop years year required essential mandatory must have possess to or and technical'.split())
    only_general=set(re.findall(r'[a-z]+',quote.lower())).issubset(general_words)
    if years and general and only_general and len(re.findall(r'\d+(?:\.\d+)?\+?\s*years?',quote,re.I))==1:
        durations=[]
        for claim in candidate['_claims']:
            if claim['section']!='Experience' or not re.search(r'\b(?:IT support|helpdesk|service desk|desktop support)\b',claim['text_en'],re.I):continue
            duration=re.search(r'\b(\d+)\s+years?\s*(?:and\s*)?(\d+)\s+months?\b',claim['text_en'],re.I)
            if duration:durations.append((int(duration[1])*12+int(duration[2]),claim['id']))
        # Only one explicitly documented duration; never sum overlapping jobs or round up.
        if len(durations)==1:
            needed=float(years[1] or years[2])*12;actual,fid=durations[0]
            return ('CUMPLIDO' if actual>=needed else 'NO_CUMPLIDO'),[fid],'Comparación literal de duración aprobada, sin redondear ni acreditar herramientas específicas.'
    return status,fact_ids,reason


def checklist(db,job,candidate=None,profile=None,section_aliases=None):
    candidate=candidate or candidate_snapshot(db);profile=profile or load_profile()
    reviews=db.rows('''SELECT * FROM manual_requirement_reviews WHERE job_id=? AND job_content_hash=? AND facts_hash=? ORDER BY id DESC''',
                    (job['id'],job['content_hash'],candidate['_facts_hash']))
    latest={}
    for review in reviews:latest.setdefault(review['requirement_hash'],review)
    output=[]
    for item in requirement_items(job,section_aliases=section_aliases):
        status,ids,reason=_automatic(item,candidate,profile);review=latest.get(item['id'])
        if review:status=review['status'];ids=json.loads(review['fact_ids']);reason='Contraste factual registrado por el usuario para estas versiones.'
        output.append({**item,'status':status,'fact_ids':ids,'reason':reason,'reviewed_at':review['reviewed_at'] if review else None})
    return output


def review_requirement(db,job_id,requirement_id,status,fact_ids,expected_content_hash,expected_facts_hash,*,confirmed=False):
    if not confirmed:raise PermissionError('EXPLICIT_FACTUAL_REVIEW_REQUIRED')
    if status not in STATUSES or not isinstance(fact_ids,list) or any(type(i) is not int for i in fact_ids):raise ValueError('INVALID_REQUIREMENT_REVIEW')
    with db.transaction() as con:
        if not con.in_transaction:con.execute('BEGIN IMMEDIATE')
        job=db.rows('SELECT * FROM jobs WHERE id=?',(job_id,))[0];require_it_job(job);candidate=candidate_snapshot(db)
        if job['content_hash']!=expected_content_hash or candidate['_facts_hash']!=expected_facts_hash:raise ValueError('REQUIREMENT_OR_PROFILE_CHANGED')
        if requirement_id not in {r['id'] for r in requirement_items(job)}:raise ValueError('SOURCE_REQUIREMENT_NOT_FOUND')
        valid_ids=set(candidate['_fact_ids'].values())|{r['id'] for r in candidate['_claims']}
        if not set(fact_ids).issubset(valid_ids) or status=='CUMPLIDO' and not fact_ids:raise ValueError('APPROVED_FACTS_REQUIRED')
        old=db.rows('''SELECT * FROM manual_requirement_reviews WHERE job_id=? AND job_content_hash=? AND facts_hash=? AND requirement_hash=? ORDER BY id DESC LIMIT 1''',
                    (job_id,expected_content_hash,expected_facts_hash,requirement_id))
        ids=json.dumps(sorted(set(fact_ids)))
        if old and old[0]['status']==status and old[0]['fact_ids']==ids:return old[0]['id']
        return db.execute('''INSERT INTO manual_requirement_reviews(job_id,job_content_hash,facts_hash,requirement_hash,status,fact_ids,reviewed_at) VALUES(?,?,?,?,?,?,?)''',
                          (job_id,expected_content_hash,expected_facts_hash,requirement_id,status,ids,now()))
