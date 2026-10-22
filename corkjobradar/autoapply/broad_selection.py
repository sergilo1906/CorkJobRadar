"""IT 50 km / minimum requested experience <=3. No invented qualifications or consent."""
import json
import re
from collections import Counter
from datetime import datetime,timedelta
from ..config import now,digest,load_profile
from ..verification import deadline_state,evidence_status
from ..passages import heading_for
from .it_scope import classify_it_functions
from .manual_requirements import checklist,requirement_items,PREFERRED
from .radius import origin,location_assessment
from .store import already_applied
from .vault import candidate_snapshot

RULES_VERSION='IT_50KM_MINIMUM_EXPERIENCE_MAX3_V2_ACADEMIC'
STATES=['ENVIABLE','ENVIABLE_CON_ADVERTENCIAS','INTERVENCION_REQUERIDA','EXCLUIDA','ENVIADA_CONFIRMADA','ENVIO_INCIERTO']
NUM=r'(?:\d+(?:\.\d+)?|zero|one|two|three|four|five|six|seven|eight|nine|ten)'
EXPERIENCE=re.compile(r'(?P<more>more than|over|greater than|m[aá]s de)?\s*(?P<low>'+NUM+r')\s*(?:[-–—]|to|a)\s*(?P<high>'+NUM+r')\s*\+?\s*(?P<unit>years?|yrs?|months?|mos?|a[nñ]os?|meses)\b|(?P<more1>more than|over|greater than|m[aá]s de)?\s*(?P<single>'+NUM+r')\s*\+?\s*(?P<unit1>years?|yrs?|months?|mos?|a[nñ]os?|meses)\b',re.I)
WORDS={w:i for i,w in enumerate('zero one two three four five six seven eight nine ten'.split())}


def experience_requirements(job):
    out=[]
    for item in requirement_items(job):
        quote=item['quote']
        explicit_experience=bool(re.search(r'\b(?:experience|experiencia)\b',quote,re.I))
        heading=next((line.strip() for line in reversed(job['description'][:item['offset']].splitlines()) if heading_for(line)), '')
        experience_context=bool(re.search(r'\bexperience\b',heading,re.I))
        implicit_work=bool(item['level']=='OBLIGATORIO' and re.search(r'\b(?:IT support|helpdesk|service desk|software development|programming|systems administration|network administration|network engineering)\b',quote,re.I))
        if not explicit_experience and not experience_context and not implicit_work:continue
        if not explicit_experience and re.search(r'\b(?:contract|duration|degree|diploma|course|programme|program|aged?|old)\b',quote,re.I):continue
        for match in EXPERIENCE.finditer(quote):
            # Ignore age/company history, deadlines and education duration.
            vicinity=quote[max(0,match.start()-70):min(len(quote),match.end()+110)]
            if not experience_context and not implicit_work and not re.search(r'\b(?:experience|experiencia)\b',vicinity,re.I):continue
            before=quote[:match.start()]
            if re.search(r'\b(?:age|aged|contract(?: of)?|duration(?: of)?)\s*$',before,re.I):continue
            if re.match(r'\s*[-–]?\s*(?:degree|diploma|course|programme|program|contract)\b',quote[match.end():],re.I):continue
            if re.search(r'\b(?:up to|no more than|maximum|at most|hasta|m[aá]ximo de)\s*$',before,re.I):continue
            if (match['more'] or match['more1']) and re.search(r'\bno\s*$',before,re.I):continue
            if re.search(r'(?:degree|course|program|diploma)\s*$',before,re.I):continue
            number=(match['low'] or match['single']).lower();minimum=float(WORDS[number]) if number in WORDS else float(number)
            unit=(match['unit'] or match['unit1']).lower()
            if unit.startswith(('mo','mes')):minimum/=12
            exclusive=bool(match['more'] or match['more1'])
            # A "plus" following years means a lower inclusive bound, not preference.
            boundaries=[(m.start(),m.end()) for m in re.finditer(r'[,;]|\b(?:and|but)\b(?=\s+(?:\d|preferred|desirable))',quote,re.I)]
            left=max([end for start,end in boundaries if end<=match.start()]+[0])
            right=min([start for start,end in boundaries if start>=match.end()]+[len(quote)])
            clause=quote[left:right]
            optional=bool(PREFERRED.search(clause)) or item['level']=='DESEABLE'
            explicit=bool(re.search(r'\b(?:minimum|at least|must|required|essential|m[ií]nimo|obligatori\w*)\b',clause,re.I))
            required=explicit or item['level']=='OBLIGATORIO'
            mixed=bool(PREFERRED.search(clause) and explicit)
            alternative=bool(re.search(r'\bor\b|\bo bien\b',quote,re.I)) and bool(re.search(r'degree|qualification|equivalent|diploma|certific|a[nñ]os?|years?',quote[:match.start()]+quote[match.end():],re.I))
            level='POR_ACLARAR' if mixed or alternative else 'DESEABLE' if optional else 'OBLIGATORIO' if required else 'POR_ACLARAR'
            exceeds=minimum>3 or exclusive and minimum>=3
            out.append({'quote':quote,'offset':item['offset'],'minimum_years':minimum,'exclusive_minimum':exclusive,
                        'level':level,'excludes':exceeds and level=='OBLIGATORIO','needs_clarification':exceeds and level=='POR_ACLARAR'})
    return out


def _delivery_state(db,job):
    from .store import identities
    keys=identities(job,db.rows('SELECT * FROM job_sources WHERE job_id=?',(job['id'],)))
    marks=','.join('?' for _ in keys)
    attempts=db.rows(f'''SELECT DISTINCT a.* FROM application_attempts a JOIN application_identities i ON i.attempt_id=a.id
                         WHERE i.environment='LIVE' AND i.identity_key IN ({marks}) ORDER BY a.id DESC''',tuple(keys))
    for attempt in attempts:
        if attempt['state']=='ENVIADA_CONFIRMADA' and db.rows("SELECT id FROM application_receipt_evidence WHERE attempt_id=? AND environment='LIVE' AND status='VERIFIED_REAL_RECEIPT'",(attempt['id'],)):
            return 'ENVIADA_CONFIRMADA'
        if attempt['state'] in {'ENVIANDO','ENVIO_INCIERTO','ENVIADA_CONFIRMADA'}:return 'ENVIO_INCIERTO'
    return None


def assess_selection(db,job,candidate=None,profile=None,origin_point=None,*,exclude_attempt=None):
    candidate=candidate or candidate_snapshot(db);profile=profile or load_profile();o=origin_point or origin(db)
    it=classify_it_functions(job);geo=location_assessment(db,job,o);experience=experience_requirements(job)
    requirements=checklist(db,job,candidate,profile);exclusions=[];essential=[];warnings=[]
    from .academic import assessment as academic_assessment
    academic=academic_assessment(job,candidate)
    if any(i['status']=='PENDIENTE' and i['level']!='DESEABLE' for i in academic['items']):warnings.append('ACADEMIC_ACCEPTANCE_PENDING')
    if it.status=='NON_IT':exclusions.append('NON_IT')
    elif it.status!='CONFIRMED_IT':essential.append('IT_FUNCTIONS_PENDING')
    if geo['state']=='OUTSIDE_RADIUS':exclusions.append('OUTSIDE_50_KM')
    elif geo['state']=='REMOTE_SEPARATE':essential.append('REMOTE_ADDITIONAL_AUTHORIZATION_REQUIRED')
    elif geo['state']!='WITHIN_RADIUS':essential.append('WORKSITE_RADIUS_PENDING')
    if any(r['excludes'] for r in experience):exclusions.append('MANDATORY_MINIMUM_EXPERIENCE_OVER_3')
    if any(r['needs_clarification'] for r in experience):warnings.append('EXPERIENCE_ALTERNATIVE_OR_PREFERENCE_TO_CLARIFY')
    for item in requirements:
        if item['status']=='CUMPLIDO':continue
        q=item['quote'];mandatory=item['level']=='OBLIGATORIO'
        # An experience shortfall within the user's allowed requested minimum is intentional.
        exp=any(r['quote']==q for r in experience)
        own_car=bool(re.search(r'\b(?:own|personal) (?:car|vehicle)\b|\bown\s+(?:a|your)\s+(?:car|vehicle)\b',q,re.I))
        legal=bool(re.search(r'\b(?:right to work|authori[sz]ation|visa|sponsorship|clearance|licen[cs]e|registration|legally|required certification)\b',q,re.I))
        if mandatory and item['status']=='NO_CUMPLIDO' and not exp:exclusions.append('PROVEN_MANDATORY_INCOMPATIBILITY')
        elif mandatory and own_car and not profile.get('owns_car') and not re.search(r'\bor\b|not|without|no need',q,re.I):exclusions.append('OWN_CAR_REQUIRED')
        elif mandatory and legal:essential.append('ESSENTIAL_LEGAL_OR_LICENSE_ANSWER_PENDING')
        else:warnings.append('EXPERIENCE_SHORTFALL_DISCLOSED' if exp and item['status']=='NO_CUMPLIDO' else 'NONESSENTIAL_REQUIREMENT_NOT_PROVEN')
    if candidate.get('work_authorization')!='IRELAND_AUTHORIZED':essential.append('IRELAND_WORK_AUTHORIZATION_PENDING')
    checks=db.rows('SELECT * FROM commute_checks WHERE job_id=? ORDER BY id DESC',(job['id'],))
    # Only explicit, current, job-bound evidence of impossibility blocks. A failed bus route alone cannot rule out cycling.
    blocked=False
    for check in checks:
        try:d=json.loads(check['details']) if isinstance(check['details'],str) else check['details']
        except (ValueError,TypeError):continue
        if check['viability']=='NO_VIABLE' and d.get('all_available_modes_incompatible') is True and d.get('job_content_hash')==job['content_hash']:
            try:blocked=datetime.fromisoformat(d['valid_until']).date()>=datetime.fromisoformat(now()).date() and bool(check['evidence_url'])
            except (KeyError,ValueError):pass
        if blocked:break
    if blocked:exclusions.append('PROVEN_COMMUTE_INCOMPATIBILITY')
    elif job['mode']!='REMOTE':
        from ..geography import valid_commute,effective_checks
        verified_route=False
        for check in effective_checks(checks):
            try:d=json.loads(check['details']) if isinstance(check['details'],str) else check['details']
            except (ValueError,TypeError):continue
            if valid_commute(check,profile) and d.get('job_content_hash')==job['content_hash'] and all(d.get(k) for k in ('valid_until','shift_start','shift_end','days')):verified_route=True
        if not verified_route:warnings.append('COMMUTE_AND_SHIFT_PENDING')
    raw=json.loads(job['raw']) if isinstance(job.get('raw'),str) else job.get('raw',{})
    deadline=deadline_state(raw)[0];closed=job['open_status']=='CLOSED_CONFIRMED' or evidence_status({**job,'raw':raw})[0]=='CLOSED_CONFIRMED' or deadline=='EXPIRED'
    if closed:exclusions.append('VACANCY_CLOSED')
    try:fresh=timedelta(0)<=datetime.fromisoformat(now())-datetime.fromisoformat(job['last_verified_at'])<=timedelta(hours=24)
    except (ValueError,TypeError):fresh=False
    operational=[]
    if not fresh or job['open_status']!='OPEN_CONFIRMED':operational.append('CURRENT_OPEN_STATUS_PENDING')
    if deadline not in {'ABSENT','NOT_EXPIRED'}:operational.append('DEADLINE_PENDING')
    if not candidate.get('cv_document_id'):operational.append('APPROVED_CV_PENDING')
    if job.get('possible_duplicate'):operational.append('POSSIBLE_DUPLICATE_REVIEW')
    duplicate=already_applied(db,job,'LIVE',exclude_attempt=exclude_attempt)
    if duplicate:operational.append('ALREADY_APPLIED_OR_RESERVED')
    professional='EXCLUIDA' if exclusions else 'INTERVENCION_REQUERIDA' if essential else 'ENVIABLE_CON_ADVERTENCIAS' if warnings else 'ENVIABLE'
    delivery=_delivery_state(db,job)
    state=delivery or ('EXCLUIDA' if exclusions else 'INTERVENCION_REQUERIDA' if essential or operational else professional)
    from .interaction_modes import interaction_route
    route=interaction_route(job.get('apply_url') or job['url'])
    binding=digest({'job':job['content_hash'],'facts':candidate['_facts_hash'],'cv':candidate.get('cv_document_id'),
                    'origin':o['binding_hash'],'version':RULES_VERSION,'it_scope':it.to_dict(),'geo':geo,'requirements':requirements,'checks':checks,
                    'profile':profile,'open_status':job['open_status'],'last_verified_at':job['last_verified_at'],'deadline':deadline,
                    'experience':experience,'exclusions':sorted(set(exclusions)),'essential':sorted(set(essential))})
    return {'job_id':job['id'],'company':job['company'],'title':job['title'],'location':job['location'],
            'it_status':it.status,'it_families':it.families,'professional_state':professional,'state':state,
            'exclusions':sorted(set(exclusions)),'essential_pending':sorted(set(essential)),
            'warnings':sorted(set(warnings)),'operational_pending':operational,'geography':geo,'experience':experience,
            'cv_approved':bool(candidate.get('cv_document_id')),'duplicate':duplicate,'interaction_mode':route['mode'],'academic_review':academic,
            'selection_eligible':not exclusions and not essential,'preparation_allowed':it.status=='CONFIRMED_IT' and not exclusions and not duplicate,
            'binding_hash':binding,'rules_version':RULES_VERSION,'origin_hash':o['binding_hash'],'live_enabled':False,
            'authorization':'Clasificación para preparación; no es permiso de envío. CV/política/prueba externa/activación separados.'}


def selection_inventory(db):
    # One read snapshot avoids reopening thousands of SQLite/WAL connections and
    # prevents mixing profile/document/job versions across a complete inventory.
    with db.transaction() as con:
        if not con.in_transaction:con.execute('BEGIN')
        candidate=candidate_snapshot(db);profile=load_profile();o=origin(db)
        offers=[assess_selection(db,j,candidate,profile,o) for j in db.rows('SELECT * FROM jobs ORDER BY first_seen_at,id')]
    return {'generated_at':now(),'rules_version':RULES_VERSION,'jobs_processed':len(offers),
            'states':dict(Counter(r['state'] for r in offers)),
            'professional_states':dict(Counter(r['professional_state'] for r in offers)),
            'it_confirmed':sum(r['it_status']=='CONFIRMED_IT' for r in offers),
            'eligible_professionally':sum(r['selection_eligible'] for r in offers),
            'remote_separate':sum(r['geography']['state']=='REMOTE_SEPARATE' for r in offers),
            'offers':offers,'live_enabled':False,'no_score_filter':True,'all_stored_jobs_processed':True}
