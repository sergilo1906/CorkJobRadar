"""Evidence-preserving rules. This module does not claim semantic understanding."""
import re
from .passages import heading_for


def documentary(job, facts):
    text=job['description'];url=job['url']
    def fact(value,quote,status=None):
        return {'value':value,'quote':quote,'source':url,
                'evidence_status':status or ('PUBLICADO' if value is not None else 'NO_PUBLICADO')}
    def matches(pattern):
        return [m[0] for m in re.finditer(pattern,text,re.I)]
    groups={k:[] for k in ('duties','mandatory','desirable')}
    patterns={
        'duties':r'^(?:key |main |your |job )?(?:responsibilities|duties|what you.ll do|the role|your role|job description)\s*[:?]?$',
        'mandatory':r'^(?:essential|minimum|required|mandatory)(?:\s+(?:qualifications|requirements|criteria|experience|skills))?\s*:?$|^(?:qualifications|requirements|what you bring)\s*:?$',
        'desirable':r'^(?:preferred|desirable|advantageous)(?:\s+(?:qualifications|requirements|criteria|experience|skills))?\s*:?$'}
    section=None
    candidate_lines=[]
    lines=re.split(r'\n+|(?<=[.!?])\s+(?=[A-Z0-9])',text)
    for line in lines:
        line=line.strip()
        if not line:
            continue
        if not re.search(r'[A-Za-z0-9À-ÿ]',line):
            continue  # Standalone ':' / bullet separators are not requirements or duties.
        heading=next((key for key,pattern in patterns.items() if re.search(pattern,line,re.I)),None)
        heading=heading or heading_for(line)
        if heading:
            section=heading
            continue
        if len(line)<90 and re.search(r'^(?:benefits|about us|about the company|additional information|equal opportunity|what we offer|salary|location)\s*:?$',line,re.I):
            section=None
        selected=section if section in groups else None
        if section in {'context','benefits'}:
            continue
        candidate_lines.append(line)
        if re.search(r'\b(?:desirable|preferred|advantageous|nice to have|a plus|an advantage)\b',line,re.I):
            selected='desirable'
        elif re.search(r'\b(?:must|required|essential|mandatory|minimum of|at least)\b',line,re.I):
            selected='mandatory'
        elif re.search(r'\b(?:you will|you.ll|responsible for|duties include)\b',line,re.I):
            selected='duties'
        if selected and line not in groups[selected]:
            groups[selected].append(line)
    for key,field in [('duties','responsibilities'),('mandatory','mandatory_requirements'),('desirable','desirable_requirements')]:
        facts[field]=fact(groups[key] or None,groups[key] or None)
    no_exp=[m[0] for line in candidate_lines for m in re.finditer(r'\b(?:no (?:previous |prior |relevant )?experience (?:is )?(?:required|necessary|needed)|experience (?:is )?not (?:required|necessary))\b',line,re.I)]
    years=[];desired=[]
    for line in candidate_lines:
        exp=re.search(r'(?:minimum\s+(?:of\s+)?|at least\s+)?(\d+(?:\.\d+)?)\s*(?:[-–]\s*\d+(?:\.\d+)?)?\+?\s*years?[^.\n]{0,45}experience',line,re.I)
        if exp:
            (desired if line.strip() in groups['desirable'] or re.search(r'desir|prefer|advantage|ideally|a plus',line,re.I) else years).append((float(exp[1]),line.strip()))
    if no_exp and years:
        facts['experience']=fact(None,no_exp+[q for _,q in years],'AMBIGUO')
    elif no_exp:
        facts['experience']=fact(0,no_exp)
    elif years:
        facts['experience']=fact(max(x[0] for x in years),[q for _,q in years])
    else:
        facts['experience']=fact(None,None)
    facts['desirable_experience']=fact([q for _,q in desired] or None,[q for _,q in desired] or None)
    contracts=matches(r'\b(?:permanent|fixed.term|temporary|contractor|internship)\b')
    if len({x.lower() for x in contracts})>1:
        facts['contract']=fact(None,contracts,'AMBIGUO')
    own=matches(r'\b(?:own|personal)\s+(?:car|vehicle|transport)\b')
    vehicle_lines=[line.strip() for line in lines if any(q.lower() in line.lower() for q in own)]
    negative=[line for line in vehicle_lines if re.search(r'not (?:required|necessary)|no (?:need|requirement)|without',line,re.I)]
    optional=[line for line in vehicle_lines if re.search(r'desirable|preferred|advantage',line,re.I)]
    facts['vehicle']=fact(False if negative and len(negative)==len(vehicle_lines) else True if vehicle_lines and not optional and not negative else None,
                          vehicle_lines or None,'AMBIGUO' if optional or (negative and len(negative)!=len(vehicle_lines)) else None)
    fields={
        'weekly_hours':r'\b\d+(?:\.\d+)?\s*(?:[-–]\s*\d+(?:\.\d+)?)?\s*(?:hours?|hrs?)\s*(?:per|a|/)\s*week\b',
        'education':r'\b(?:degree|diploma|certificate|qualification|leaving certificate|QQI|NFQ)\b',
        'tools':r'\b(?:Python|Java(?:Script)?|SQL|Linux|Windows|Active Directory|Microsoft 365|SAP|Excel|forklift|pallet truck|HVAC|Git|ITIL)\b',
        'languages':r'\b(?:English|Spanish|German|French|Italian|Dutch|Portuguese|Polish|Irish language)\b',
        'physical':r'\b(?:lift(?:ing)?|manual handling|standing|physical(?:ly)?|heavy loads|kg|kilograms)\b',
        'growth':r'\b(?:career (?:progression|development|path)|promot(?:ion|ed)|progression opportunities)\b',
        'training':r'\b(?:training provided|full training|paid training|apprenticeship|mentorship|mentoring|training programme)\b',
        'benefits':r'\b(?:pension|bonus|allowance|health insurance|annual leave|paid holidays|shift premium)\b',
        'driving_license':r'\b(?:driving licen[cs]e|driver.s licen[cs]e|category B|B licen[cs]e)\b',
        'employment_hours':r'\b(?:full.time|part.time|whole.time)\b'}
    for key,pattern in fields.items():
        quotes=list(dict.fromkeys(line.strip() for line in lines if re.search(pattern,line,re.I)))
        facts[key]=fact(quotes or None,quotes or None)
    training=facts['training']['value'] or []
    no_training=[q for q in training if re.search(r'no (?:full |paid )?training|training (?:is )?not provided',q,re.I)]
    facts['learning']=fact(False if training and len(no_training)==len(training) else True if training and not no_training else None,facts['training']['quote'])
    # "No weekends" is positive evidence of absence, not a weekend requirement.
    schedule=facts['schedule']['value'] or {}
    exclusions=[]
    for key,pattern in [('fines_semana',r'no weekends?|weekends? (?:are )?not required'),('noches',r'no night (?:shifts?|work)'),('rotacion',r'no (?:rotating|rotational) shifts?')]:
        found=matches(pattern)
        if found:
            exclusions.extend(found);schedule.pop(key,None)
    facts['schedule']=fact(schedule or None,list(schedule.values())+exclusions or None)
    facts['schedule_exclusions']=fact(exclusions or None,exclusions or None)
    return facts


def profile_evidence(facts, profile):
    skills=profile.get('skills',[])
    requirements=(facts['mandatory_requirements']['value'] or [])
    matched=[];unconfirmed=[]
    for requirement in requirements:
        hits=[s for s in skills if re.search(r'(?<!\w)'+re.escape(s)+r'(?!\w)',requirement,re.I)]
        (matched if hits else unconfirmed).append({'requirement_quote':requirement,'confirmed_skill_mentions':hits,
            'status':'COINCIDENCIA_TEXTUAL_PARCIAL' if hits else 'NO_ACREDITADO_EN_PERFIL'})
    return {'matched_mentions':matched,'requires_confirmation':unconfirmed,
            'note':'Una coincidencia textual no demuestra cumplir íntegramente el requisito. La ausencia en el perfil no demuestra falta de capacidad.'}
