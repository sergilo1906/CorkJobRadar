"""Literal, versioned academic evidence. A completed CFGS is never a Bachelor."""
import re

VERSION='ACADEMIC_DAM_2'
SOURCES=[
    'https://www.todofp.es/en/que-estudiar/familias-profesionales/informatica-comunicaciones/des-aplicaciones-multiplataforma.html',
    'https://qsdocs.qqi.ie/QualRec%20Comparability%20Statements/Spain_ID_208.pdf',
    'https://www.qqi.ie/recognition-of-foreign-qualifications',
]
CREDENTIAL=re.compile(r'\b(?:degree|bachelor|honours?|master[’\x27]?s?|doctorate|PhD|diploma|CFGS|DAM|NFQ|QQI|MECES|higher (?:technician|certificate)|third.level|(?:relevant|IT|computing|technical|educational) qualification)\b',re.I)
SPECIFIC=re.compile(r'\b(?:degree|bachelor|honours?|master[’\x27]?s?|doctorate|PhD|NFQ|QQI|HND|higher national|university|MECES)\b',re.I)
STUDENT=re.compile(r'\b(?:currently (?:pursuing|studying|enrolled)|current student|enrolled in|must be (?:a )?student)\b',re.I)
LABELS={
 'DAM_COMPLETION_CONFIRMED':'DAM terminado: formación acreditada',
 'DAM_COMPLETION_PENDING':'Titulación DAM pendiente en esa versión del perfil',
 'ACADEMIC_EQUIVALENCE_PENDING':'Equivalencia académica por confirmar con la empresa',
 'ACADEMIC_ALTERNATIVE_PENDING':'Titulación o experiencia alternativa por contrastar',
 'CURRENT_STUDENT_STATUS_PENDING':'Exige estudios en curso: matrícula actual por confirmar',
 'RELATED_QUALIFICATION_REVIEW':'DAM terminado y relacionado; aceptación del requisito por confirmar',
 'ACADEMIC_DETAILS_PENDING':'Condición académica por aclarar',
}


def dam_state(candidate):
    for claim in candidate.get('_claims',[]):
        if claim.get('section')!='Education':continue
        text=claim.get('text_en','')
        if not re.search(r'\bDAM\b|Multiplatform Application Development',text,re.I):continue
        # Negation and unfinished studies must never count as an obtained qualification.
        if re.search(r'\b(?:ongoing|remaining|not completed|in progress|pending|studying|en curso)\b',text,re.I):
            return {'state':'ONGOING','fact_ids':[claim['id']]}
        if re.search(r'\b(?:completed|obtained|awarded|graduated|terminado|obtenido)\b',text,re.I):
            return {'state':'COMPLETED','fact_ids':[claim['id']]}
    return {'state':'UNKNOWN','fact_ids':[]}


def review_requirement(quote,candidate):
    """Only standalone, literal completion requirements can be automatically satisfied."""
    if not CREDENTIAL.search(quote):return None
    dam=dam_state(candidate)
    status='PENDIENTE';ids=[]
    if STUDENT.search(quote):code='CURRENT_STUDENT_STATUS_PENDING'
    elif SPECIFIC.search(quote):
        experience_alternative=bool(re.search(r'\bor\b.{0,60}\bexperience\b|\bequivalent (?:practical |work |professional )?experience\b',quote,re.I))
        code='ACADEMIC_ALTERNATIVE_PENDING' if experience_alternative else 'ACADEMIC_EQUIVALENCE_PENDING'
    else:
        # A compound clause, grade, named institution, specialism, or another skill
        # must not pass just because one part mentions a diploma or DAM.
        clean=quote.strip().rstrip('.').strip()
        standalone=bool(re.fullmatch(
            r'(?:a |an )?(?:completed |obtained )?(?:(?:CFGS )?DAM|T[eé]cnico Superior en Desarrollo de Aplicaciones Multiplataforma|Higher Technician qualification in Multiplatform Application Development|(?:relevant )?(?:IT|computing|software development|information technology) qualification)(?: (?:is )?(?:required|essential|mandatory))?',clean,re.I))
        if standalone:
            code='DAM_COMPLETION_CONFIRMED' if dam['state']=='COMPLETED' else 'DAM_COMPLETION_PENDING'
            if dam['state']=='COMPLETED':status='CUMPLIDO';ids=dam['fact_ids']
        else:code='RELATED_QUALIFICATION_REVIEW' if dam['state']=='COMPLETED' else 'ACADEMIC_DETAILS_PENDING'
    return {'status':status,'fact_ids':ids,'code':code,'reason':LABELS[code],
            'equivalence_assumed':False}


def assessment(job,candidate):
    from .manual_requirements import requirement_items
    items=[]
    for requirement in requirement_items(job):
        review=review_requirement(requirement['quote'],candidate)
        if review:items.append({**requirement,**review})
    return {'version':VERSION,'facts_hash':candidate.get('_cv_facts_hash',candidate.get('_facts_hash')),
            'dam':dam_state(candidate),'items':items,'degree_equivalence_assumed':False,
            'sources':SOURCES,'recognition':'Referencia genérica no personalizada; aceptación final del empleador. No modifica los hechos ni el CV.'}


def label(review):
    items=review.get('items',[])
    if any(i['code']=='CURRENT_STUDENT_STATUS_PENDING' for i in items):return LABELS['CURRENT_STUDENT_STATUS_PENDING']
    if any(i['code'] in {'ACADEMIC_EQUIVALENCE_PENDING','ACADEMIC_ALTERNATIVE_PENDING'} and i['level']!='DESEABLE' for i in items):return 'DAM terminado · Equivalencia o alternativa académica pendiente' if review.get('dam',{}).get('state')=='COMPLETED' else 'Equivalencia o alternativa académica pendiente'
    if review.get('dam',{}).get('state')=='COMPLETED':return 'DAM terminado · '+('Requisito académico acreditado' if any(i['status']=='CUMPLIDO' for i in items) else 'Aceptación académica por revisar' if items else 'Sin requisito académico específico extraído')
    return 'Formación académica por revisar'
