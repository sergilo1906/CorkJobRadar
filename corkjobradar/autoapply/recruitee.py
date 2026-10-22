"""Documented Careers Site API: public GET and in-memory request preparation.

No POST transport, token scraping, hosted fill or receipt claim. The employer's
scope/privacy review and external authorized trial are still required.
"""
from dataclasses import dataclass,field
from datetime import date
import hashlib
import math
import re
from urllib.parse import urlsplit,urlunsplit
from ..config import digest,now
from ..normalization import clean_html
from .browser import FormHold

VERSION='recruitee-careers-prepare-1'
TOKEN_DEADLINE=date(2027,2,10)
RESERVED={'app','api','docs','support','www','recruiteedemo'}


def tenant_host(host):
    return bool(isinstance(host,str) and re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.recruitee\.com',host)
                and host.split('.')[0] not in RESERVED)


def target(url):
    p=urlsplit(url)
    if p.scheme!='https' or not tenant_host(p.hostname) or p.username or p.password or p.port not in {None,443} or p.query or p.fragment:
        raise ValueError('UNSUPPORTED_RECRUITEE_TARGET')
    match=re.fullmatch(r'/o/([a-zA-Z0-9_-]{1,180})(?:/c/new)?/?',p.path)
    if not match:raise ValueError('RECRUITEE_POSTING_SLUG_REQUIRED')
    slug=match[1];origin='https://'+p.hostname
    return {'host':p.hostname,'slug':slug,'public_url':origin+'/o/'+slug,
            'application_url':origin+'/o/'+slug+'/c/new','endpoint':origin+'/api/offers/'+slug+'/candidates',
            'schema_endpoint':origin+'/api/offers'}


def normalize_offer(offer):
    """Preserve every question. Unknown types/options are holds, never dropped silently."""
    fields=[];blockers=[];notices=[]
    def add(key,label,kind,required,wire,**extra):
        fields.append({'id':key,'name':key,'label':label,'type':kind,'required':required,'disabled':False,
                       'options':[],'wire':wire,**extra})
    add('name','Full name','text',True,'candidate[name]')
    add('email','Email','email',True,'candidate[email]')
    for key,label,kind,option in [('phone','Phone','tel','options_phone'),('cv','Resume/CV','file','options_cv'),
                                  ('cover_letter','Cover letter','textarea','options_cover_letter'),
                                  ('photo','Photo','file','options_photo'),('title','Title','text','options_title'),
                                  ('salutation','Salutation','text','options_salutation')]:
        value=offer.get(option)
        if value not in {'required','optional','off'}:
            blockers.append('UNRECOGNIZED_APPLICATION_OPTION:'+option);continue
        if value!='off':add(key,label,kind,value=='required','candidate['+key+']')
    questions=offer.get('open_questions')
    if not isinstance(questions,list):blockers.append('SCREENING_QUESTIONS_NOT_DESCRIBED');questions=[]
    seen=set()
    for q in questions:
        if not isinstance(q,dict) or type(q.get('id')) is not int or q['id']<=0 or not isinstance(q.get('body'),str) or type(q.get('required')) is not bool:
            blockers.append('INVALID_SCREENING_QUESTION');continue
        qid=q['id'];label=clean_html(q['body']).strip();kind=q.get('kind')
        if qid in seen:blockers.append('DUPLICATE_SCREENING_QUESTION');continue
        seen.add(qid)
        if kind=='infobox':
            notices.append({'id':qid,'text':label})
            # A displayed notice may impose terms without an answer input.
            blockers.append('INFORMATIONAL_NOTICE_REQUIRES_REVIEW');continue
        html_kind={'string':'text','text':'textarea','number':'number','salary':'number','date':'text',
                   'boolean':'select-one','legal':'select-one','file':'file'}.get(kind)
        if not html_kind:
            html_kind='unsupported';blockers.append('UNSUPPORTED_SCREENING_KIND:'+str(kind))
        if not label or len(label)>10000:blockers.append('QUESTION_LABEL_NOT_REVIEWABLE')
        index=len([f for f in fields if f.get('question_id') is not None])
        prefix=f'candidate[open_question_answers_attributes][{index}]'
        answer_key='flag' if kind in {'boolean','legal'} else 'file' if kind=='file' else 'content'
        add('question_'+str(qid),label,html_kind,q['required'],prefix+'['+answer_key+']',question_id=qid,
            question_kind=kind,wire_question_id=prefix+'[open_question_id]',legal=kind=='legal',
            sensitive=bool(re.search(r'fair employment|monitoring questionnaire|demographic',label,re.I)))
        if re.search(r'https?://',label,re.I):blockers.append('EXTERNAL_QUESTIONNAIRE_MANUAL_REVIEW')
        if kind in {'boolean','legal'}:fields[-1]['options']=[{'value':'true','text':'Yes'},{'value':'false','text':'No'}]
        if q.get('open_question_options'):blockers.append('SCREENING_OPTIONS_REQUIRE_SPECIFIC_ENCODER')
    if offer.get('location_question_visible') is not False:
        blockers.append('LOCATION_SELECTION_REQUIRES_REVIEW')
        add('work_location',str(offer.get('locations_question') or 'Work location (provider label unavailable)'),
            'unsupported',True,'UNSUPPORTED_LOCATION_ENCODING')
    return fields,sorted(set(blockers)),notices


def inspect_recruitee(url,client,*,today=None):
    destination=target(url)
    if (today or date.fromisoformat(now()[:10]))>=TOKEN_DEADLINE:
        raise PermissionError('RECRUITEE_CAREERS_TOKEN_REQUIRED_NOT_CONFIGURED')
    response=client.get(destination['schema_endpoint'],check_robots=True);response.raise_for_status()
    observed=urlsplit(str(response.url));expected=urlsplit(destination['schema_endpoint'])
    if observed.scheme!='https' or observed.netloc!=expected.netloc or observed.path.rstrip('/')!=expected.path:
        raise ValueError('RECRUITEE_SCHEMA_REDIRECTED_TO_DIFFERENT_TARGET')
    payload=response.json()
    if not isinstance(payload,dict) or not isinstance(payload.get('offers'),list):raise ValueError('RECRUITEE_SCHEMA_CHANGED')
    matches=[o for o in payload['offers'] if isinstance(o,dict) and o.get('slug')==destination['slug']]
    if len(matches)!=1:raise ValueError('RECRUITEE_POSTING_NOT_PUBLISHED_OR_AMBIGUOUS')
    offer=matches[0]
    for name,value in [('careers_url',destination['public_url']),('careers_apply_url',destination['application_url'])]:
        if offer.get(name)!=value:raise ValueError('RECRUITEE_PUBLISHED_URL_MISMATCH')
    if type(offer.get('id')) is not int or offer['id']<=0:raise ValueError('RECRUITEE_POSTING_ID_REQUIRED')
    fields,blockers,notices=normalize_offer(offer)
    if offer.get('status')!='published':blockers.append('CURRENT_PUBLICATION_STATUS_UNVERIFIED')
    # Careers API documentation describes integrations. It does not establish
    # permission/privacy/CAPTCHA state for every employer or authorize this user.
    blockers+=['EMPLOYER_AUTOMATION_SCOPE_UNVERIFIED','HOSTED_PRIVACY_AND_ACCESS_REVIEW_REQUIRED']
    description=clean_html(str(offer.get('description') or ''))+'\nRequirements\n'+clean_html(str(offer.get('requirements') or ''))
    from .it_scope import classify_it_functions
    scope=classify_it_functions({'title':offer.get('title',''),'description':description,'detail_complete':bool(offer.get('description') and offer.get('requirements'))})
    if scope.status!='CONFIRMED_IT':blockers.append('LIVE_SOURCE_IT_FUNCTIONS_UNCONFIRMED')
    return {'platform':'recruitee','adapter_version':VERSION,'public_url':url,'posting_id':str(offer['id']),
            'posting_slug':destination['slug'],'endpoint':destination['endpoint'],'title':offer.get('title'),
            'fields':fields,'blockers':sorted(set(blockers)),'notices':notices,'source_kind':'DOCUMENTED_CAREERS_SITE_API_GET',
            'response_sha256':hashlib.sha256(response.content).hexdigest(),'offer_hash':digest(offer),
            'schema_endpoint':destination['schema_endpoint'],'source_it_classification':scope.to_dict(),
            'authentication_deadline':TOKEN_DEADLINE.isoformat(),'inspected_read_only':True,'remote_fill_authorized':False,
            'hosted_form_verified':False,'api_submission_verified':False,'live_supported':False,'submitted':False}


@dataclass(repr=False)
class PreparedRequest:
    """Personal values/files stay in memory. Only summary() may enter public logs."""
    endpoint:str
    data:dict=field(repr=False)
    files:dict=field(repr=False)
    holds:list
    form_hash:str
    def __repr__(self):return '<PreparedRecruiteeRequest: private data redacted; not submitted>'
    def summary(self):
        return {'platform':'recruitee','fields_prepared':len(self.data),'file_count':len(self.files),
                'form_hash':self.form_hash,'holds':self.holds,'state':'HOLD' if self.holds else 'PREPARED_LOCAL_ONLY',
                'submitted':False,'external_receipt_verified':False,'live_supported':False}


def prepare_request(inspection,candidate,documents):
    """Prepare documented multipart names without making any network request."""
    from .forms import answer_plan
    destination=target(inspection['public_url'])
    if inspection['platform']!='recruitee' or inspection['endpoint']!=destination['endpoint'] or inspection['adapter_version']!=VERSION:
        raise ValueError('RECRUITEE_TARGET_OR_ADAPTER_CHANGED')
    plan=answer_plan(inspection,candidate);holds=list(inspection['blockers'])
    holds+=['UNRESOLVED_VERIFIED_ANSWERS'] if plan['unresolved'] else []
    data={};files={}
    for f in inspection['fields']:
        answer=plan['mapping'].get(f['id'])
        if answer is None:continue
        wire=f['wire']
        if f.get('question_id') is None:
            if wire not in {'candidate['+key+']' for key in ('name','email','phone','cv','cover_letter','photo','title','salutation')}:
                raise ValueError('UNSUPPORTED_MULTIPART_FIELD')
        else:
            prefix=re.fullmatch(r'(candidate\[open_question_answers_attributes\]\[\d+\])\[(content|flag|file)\]',wire)
            if not prefix or f.get('wire_question_id')!=prefix[1]+'[open_question_id]':raise ValueError('UNSUPPORTED_SCREENING_ENCODING')
        if 'document' in answer:
            # The supplied loader must be document_bytes(db, id), which rejects
            # drafts, revoked facts/CVs and hash failures. No remote CV URL.
            content,extension,sha=documents(answer['document'])
            if extension not in {'pdf','docx'}:raise ValueError('APPROVED_CV_FORMAT_REQUIRED')
            if hashlib.sha256(content).hexdigest()!=sha:raise ValueError('CV_HASH_MISMATCH')
            files[wire]=('CV.'+extension,content,'application/pdf' if extension=='pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        else:
            value=str(answer['value'])
            if f.get('question_kind') in {'boolean','legal'} and value not in {'true','false'}:raise FormHold('EXPLICIT_BOOLEAN_ANSWER_REQUIRED')
            if f.get('question_kind') in {'number','salary'}:
                try:valid=math.isfinite(float(value))
                except ValueError:valid=False
                if not valid:raise FormHold('NONFINITE_OR_INVALID_NUMERIC_ANSWER')
            if f.get('question_kind')=='date':
                try:date.fromisoformat(value)
                except ValueError:raise FormHold('EXACT_DATE_ANSWER_REQUIRED') from None
            data[wire]=value
        if f.get('question_id') is not None:data[f['wire_question_id']]=str(f['question_id'])
    return PreparedRequest(destination['endpoint'],data,files,sorted(set(holds)),inspection['form_hash'])


def final_prepared_request(db,attempt_id,inspection_id):
    """Future permitted sender entry point; rechecks policy and all current facts.

    Does not dispatch. The current capability/permission/inspection holds reject
    here, independently of someone having generated a partial local request.
    """
    from .final_gate import final_submission_gate
    from .forms import load_inspection
    from .vault import candidate_snapshot
    from .documents import document_bytes
    with db.transaction() as con:
        if not con.in_transaction:con.execute('BEGIN IMMEDIATE')
        binding=final_submission_gate(db,attempt_id,inspection_id)
        inspection=load_inspection(db,inspection_id)
        prepared=prepare_request(inspection,candidate_snapshot(db),lambda did:document_bytes(db,did))
        if prepared.holds or prepared.form_hash!=binding['form_hash']:raise FormHold('FINAL_RECRUITEE_REQUEST_NOT_READY')
        return prepared
