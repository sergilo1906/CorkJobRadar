"""Exact source spans and section context; no translations or inferred personal facts."""
import re

SECTION_PATTERNS={
 'duties':r'(?:key |main |your |job )?(?:responsibilities(?: include)?|duties|what you.ll do|the role|your role|job description)|your impact',
 'mandatory':r'(?:(?:essential|minimum|required|mandatory)\s+)?(?:qualifications|requirements|criteria|experience and skills|experience)|what you bring|essential requirements|your experience|technical skills|required skills and experience',
 'desirable':r'(?:preferred|desirable|advantageous)(?: qualifications| requirements| criteria| experience| skills)?',
 'benefits':r'offer|benefits|what we offer|our offer|compensation and benefits|the offer',
 'context':r'company description|about us|about the company|about [a-z][a-z &]{1,35}|overview|additional information|diversity and inclusion|equal opportunit(?:y|ies)',
}


def heading_for(text):
    text=text.strip().rstrip(':?').strip()
    if len(text)>90:return None
    return next((key for key,pattern in SECTION_PATTERNS.items() if re.fullmatch(pattern,text,re.I)),None)


def source_passages(text,max_characters=1200,section_aliases=None):
    units=[];retained=[];section='unknown';offset=0;conditional=False
    for line in text.splitlines(keepends=True):
        start=offset;offset+=len(line)
        value=line.strip();heading=heading_for(value)
        if not heading and section_aliases:
            heading=section_aliases.get(re.sub(r'\s+',' ',value.rstrip(':?').strip()).casefold())
        if heading:
            section=heading;conditional=False
            retained.append({'offset':start,'text':line,'kind':'SECTION_HEADING','section':section})
            continue
        if not value or len(re.findall(r'[A-Za-zÀ-ÿ]',value))<4:
            retained.append({'offset':start,'text':line,'kind':'SEPARATOR','section':section});continue
        if re.search(r'^depending on experience.*(?:include|duties)',value,re.I):conditional=True
        # Contiguous spans, split at sentence/word boundaries with every character retained.
        position=0
        while position<len(line):
            end=min(len(line),position+max_characters)
            if end<len(line):
                candidates=list(re.finditer(r'[.!?]\s+|\s+',line[position:end]))
                if candidates and candidates[-1].end()>max_characters//2:end=position+candidates[-1].end()
            quote=line[position:end]
            necessity='not_requirement';field=section if section in {'duties','mandatory','desirable','benefits'} else 'context'
            if section in {'mandatory','desirable'}:necessity=section
            if conditional and section=='duties':necessity='conditional'
            preferred=bool(re.search(r'\b(?:desirable|preferred|nice to have|advantageous|an advantage|a plus)\b',quote,re.I))
            if preferred and section not in {'benefits','context'}:field='desirable';necessity='desirable'
            elif section not in {'duties','benefits','context'} and re.search(r'\b(?:must have|must hold|essential|required|mandatory|at least)\b',quote,re.I):
                field='mandatory';necessity='mandatory'
            facets=[]
            for facet,pattern in (
                ('education',r'\b(?:degree|diploma|leaving certificate|QQI|NFQ|qualification)\b'),
                ('tools',r'\b(?:Python|Java(?:Script)?|SQL|SAP|MS Word|Excel|Outlook|One Vault|forklift|Windows|Linux)\b'),
                ('languages',r'\b(?:native speaker|English|Spanish|Danish|Dutch|German|French|language required)\b'),
                ('physical',r'\b(?:lift(?:ing)?|manual handling|standing|heavy loads|kilograms)\b'),
                ('conditions',r'\b(?:salary|per annum|per hour|contract|fixed.term|permanent|hours per week|onsite|on.site|shift|Monday|weekend)\b'),
                ('training',r'\b(?:training (?:provided|programme|program)|full training|paid training|intensive training and familiarisation|apprenticeship|mentoring provided)\b'),
                ('growth',r'\b(?:career progression|international career|promotion opportunities)\b')):
                if re.search(pattern,quote,re.I):facets.append(facet)
            if section=='benefits' and 'training' in facets:field='training'
            elif section=='benefits' and 'conditions' in facets:field='conditions'
            units.append({'id':len(units),'offset':start+position,'text':quote,'section':section,
                          'field':field,'facets':facets,'requirement_level':necessity})
            position=end
    # Integrity is checked against exact offsets; identical repeated text remains distinct.
    spans=sorted([*units,*retained],key=lambda p:p['offset'])
    if ''.join(p['text'] for p in spans)!=text:raise ValueError('SOURCE_SPAN_ACCOUNTING_FAILED')
    return units,retained
