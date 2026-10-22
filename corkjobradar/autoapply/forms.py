"""Public GET inspection and completely disconnected preparation, never a submission."""
import json
import re
import hashlib
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from html import escape
from urllib.parse import urlsplit,urljoin
from ..config import now,digest
from .platforms import inspect_greenhouse,platform_for
from .browser import OfflineFormAdapter,offline_browser,FIXTURE_ORIGIN,FormHold
from .vault import candidate_snapshot,private_folder,protect
from .documents import document_bytes,cv_review_bytes
from .policy import event


def inspection_route(db,job):
    """GET schema via a known public source; never grant hosted automation rights."""
    url=job.get('apply_url') or job['url'];cap=platform_for(url)
    if cap.get('inspection_supported'):return {'cap':cap,'locator':url,'source_binding':None}
    sources=db.rows('''SELECT s.id,s.url,js.external_id FROM sources s JOIN job_sources js ON js.source_id=s.id
                       WHERE js.job_id=? AND s.kind='greenhouse' AND s.enabled=1 AND s.permission='PUBLIC_API_DOCUMENTADA' ORDER BY s.id''',(job['id'],))
    choices=[]
    for source in sources:
        match=re.fullmatch(r'https://boards-api\.greenhouse\.io/v1/boards/([A-Za-z0-9_-]+)/jobs/?',source['url'])
        if match and re.fullmatch(r'\d{1,20}',source['external_id']):
            locator='https://job-boards.greenhouse.io/'+match[1]+'/jobs/'+source['external_id']
            choices.append({'cap':platform_for(locator),'locator':locator,'source_binding':source})
    if len(choices)!=1:raise ValueError('UNSUPPORTED_OR_AMBIGUOUS_PUBLIC_SCHEMA_SOURCE')
    return choices[0]


def greenhouse_fields(schema):
    fields=[];blockers=[]
    if schema.get('compliance'):blockers.append('COMPLIANCE_QUESTIONS_REQUIRE_REVIEW')
    groups=list(schema.get('questions',[]))+list(schema.get('location_questions',[]))
    demographics=schema.get('demographic_questions') or {}
    groups+=demographics.get('questions',[]) if isinstance(demographics,dict) else []
    for q in groups:
        variants=q.get('fields')
        if not variants:
            blockers.append('UNSUPPORTED_OR_UNDESCRIBED_QUESTION');continue
        files=[f for f in variants if f.get('type')=='input_file']
        for f in files[:1] or variants:
            kind={'input_file':'file','input_text':'text','textarea':'textarea','multi_value_single_select':'select-one',
                  'multi_value_multi_select':'select-multiple','input_hidden':'hidden'}.get(f.get('type'))
            if not kind or not f.get('name') or not q.get('label'):
                blockers.append('UNSUPPORTED_SCHEMA_FIELD');continue
            if kind=='hidden':continue
            options=[{'value':str(o['value']),'text':str(o['label'])} for o in f.get('values',[])]
            fields.append({'id':f['name'],'name':f['name'],'label':q['label'],'type':kind,'required':bool(q.get('required')),'disabled':False,'options':options})
    for index,rule in enumerate(schema.get('data_compliance',[])):
        for flag in ('requires_processing_consent','requires_retention_consent'):
            if rule.get(flag):
                fields.append({'id':f'compliance_{index}_{flag}','name':flag,'label':'Legal consent: '+flag,'type':'checkbox','required':True,'disabled':False,'options':[]})
                blockers.append('EXACT_LEGAL_CONSENT_TEXT_REQUIRED')
    if len({f['id'] for f in fields})!=len(fields):blockers.append('DUPLICATE_FIELD_ID')
    if not fields:blockers.append('EMPTY_APPLICATION_FORM')
    return fields,sorted(set(blockers))


def inspect_lever(url,client):
    from lxml import html
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname not in {'jobs.lever.co','jobs.eu.lever.co'} or parsed.username or parsed.password or parsed.port not in {None,443}:
        raise ValueError('UNSUPPORTED_LEVER_URL')
    match=re.fullmatch(r'/([A-Za-z0-9_-]+)/([a-fA-F0-9-]{36})(?:/apply)?/?',parsed.path)
    if not match:raise ValueError('LEVER_POSTING_ID_REQUIRED')
    board,posting=match.groups();target=f'https://{parsed.hostname}/{board}/{posting}/apply'
    response=client.get(target,check_robots=True);response.raise_for_status()
    tree=html.fromstring(response.content);forms=tree.xpath('//form');fields=[];blockers=[]
    if re.search(r'hcaptcha|g-recaptcha|cf-chl-|type=["\']password',response.text,re.I):blockers.append('CAPTCHA_MFA_OR_ACCESS_BLOCK')
    if len(forms)!=1:blockers.append('FORM_STRUCTURE_CHANGED')
    else:
        form=forms[0]
        action=urljoin(target,form.get('action') or target)
        if urlsplit(action).netloc!=parsed.netloc or urlsplit(action).scheme!='https':blockers.append('UNAUTHORIZED_FORM_ACTION')
        if form.get('method','get').lower()!='post':blockers.append('UNSUPPORTED_FORM_METHOD')
        for index,element in enumerate(form.xpath('.//input|.//textarea|.//select')):
            kind=element.get('type','text') if element.tag=='input' else 'select-one' if element.tag=='select' else 'textarea'
            if kind in {'hidden','submit','button'}:continue
            labels=tree.xpath('//label[@for=$id]',id=element.get('id','')) if element.get('id') else []
            containers=element.xpath('ancestor::*[contains(concat(" ",normalize-space(@class)," ")," application-question ")][1]')
            if not labels and containers:labels=containers[0].xpath('.//*[contains(@class,"application-label")]')[:1]
            label=' '.join(' '.join(l.itertext()) for l in labels).strip()
            if not label:label=element.get('aria-label','')
            if not label:blockers.append('UNLABELLED_OR_DYNAMIC_FIELD')
            name=element.get('name','');key=element.get('id') or name or 'unlabelled_'+str(index)
            options=[{'value':o.get('value',''),'text':' '.join(o.itertext()).strip()} for o in element.xpath('./option')]
            fields.append({'id':key,'name':name,'type':kind,'required':element.get('required') is not None or label.endswith('*'),'disabled':element.get('disabled') is not None,'label':label,'options':options})
    return {'platform':'lever','posting_id':posting,'public_url':target,'fields':fields,'blockers':sorted(set(blockers)),
            'response_sha256':hashlib.sha256(response.content).hexdigest(),'source_kind':'HOSTED_HTML_GET',
            'inspected_read_only':True,'submitted':False,'live_supported':False}


def inspect_job_form(db,job_id,client,include_hosted=False):
    from .it_scope import require_it_job
    rows=db.rows('SELECT * FROM jobs WHERE id=?',(job_id,))
    if not rows:raise ValueError('JOB_NOT_FOUND')
    job=rows[0];require_it_job(job)
    url=job.get('apply_url') or job['url'];route=inspection_route(db,job);platform=route['cap']
    if route['source_binding'] and include_hosted:raise ValueError('CUSTOM_DOMAIN_HOSTED_INSPECTION_NOT_SUPPORTED')
    if platform['id']=='greenhouse':
        schema=inspect_greenhouse(route['locator'],client)
        if route['source_binding']:
            from ..normalization import canonical_url
            if not schema.get('published_absolute_url') or canonical_url(schema['published_absolute_url'])!=canonical_url(job['url']):raise ValueError('PUBLIC_SCHEMA_JOB_URL_MISMATCH')
            schema.update(public_url=url,readonly_source_binding=route['source_binding'])
        fields,blockers=greenhouse_fields(schema)
        result={**schema,'fields':fields,'blockers':blockers,'source_kind':'PUBLIC_JOB_BOARD_API_GET',
                'hosted_form_verified':False}
    elif platform['id']=='lever':result=inspect_lever(url,client)
    elif platform['id']=='recruitee':
        from .recruitee import inspect_recruitee
        result=inspect_recruitee(url,client)
    else:raise ValueError('UNSUPPORTED_PLATFORM')
    if include_hosted and platform['id']=='greenhouse':
        from .hosted_probe import inspect_hosted_greenhouse
        assessment=inspect_hosted_greenhouse(url)
        result['hosted_assessment']=assessment
        if assessment['captcha_detected']:result['blockers']=sorted(set(result['blockers']+['HOSTED_CAPTCHA_DECLARED_OR_DETECTED']))
    result.update(adapter_version=platform['version'],checked_at=now(),job_id=job_id,content_hash=job['content_hash'])
    # Endpoint JSON / hosted HTML never imply permission to fill or submit remotely.
    result.update(remote_fill_authorized=False,live_supported=False,submitted=False)
    result['form_hash']=digest({'platform':result['platform'],'fields':result['fields'],'blockers':result['blockers']})
    content=json.dumps(result,ensure_ascii=False).encode('utf-8');path=private_folder(db)/(hashlib.sha256(content).hexdigest()+'.form-inspection.dpapi')
    if not path.exists():path.write_bytes(protect(content))
    iid=db.execute('''INSERT INTO autoapply_form_inspections(job_id,content_hash,platform,adapter_version,inspected_at,source_url,form_hash,encrypted_path,status)
                      VALUES(?,?,?,?,?,?,?,?,?)''',(job_id,job['content_hash'],platform['id'],platform['version'],now(),url,result['form_hash'],str(path),'HELD' if result['blockers'] else 'READ_ONLY_INSPECTED'))
    event(db,'PUBLIC_FORM_INSPECTED',{'inspection_id':iid,'form_hash':result['form_hash'],'remote_fill':False,'submitted':False})
    return {**result,'inspection_id':iid}


def load_inspection(db,inspection_id,clock=None):
    from pathlib import Path
    rows=db.rows('SELECT * FROM autoapply_form_inspections WHERE id=?',(inspection_id,))
    if not rows:raise ValueError('FORM_INSPECTION_NOT_FOUND')
    row=rows[0];path=Path(row['encrypted_path']).resolve()
    if not path.is_relative_to(private_folder(db)):raise ValueError('INSPECTION_OUTSIDE_VAULT')
    content=protect(path.read_bytes(),True)
    if hashlib.sha256(content).hexdigest()!=path.name.split('.')[0]:raise ValueError('INSPECTION_HASH_MISMATCH')
    result=json.loads(content)
    checked=datetime.fromisoformat(result['checked_at'])
    if checked.tzinfo is None or not timedelta(0)<=((clock or datetime.now(ZoneInfo('Europe/Dublin')))-checked)<=timedelta(hours=24):raise ValueError('INSPECTION_EXPIRED')
    job=db.rows('SELECT * FROM jobs WHERE id=?',(row['job_id'],))[0]
    from .it_scope import require_it_job
    require_it_job(job)
    if result['content_hash']!=job['content_hash'] or result['form_hash']!=row['form_hash']:raise ValueError('INSPECTION_STALE')
    route=inspection_route(db,job)
    if result.get('readonly_source_binding')!=route['source_binding']:raise ValueError('INSPECTION_SOURCE_CHANGED')
    if result['adapter_version']!=route['cap']['version']:raise ValueError('INSPECTION_ADAPTER_CHANGED')
    return result


def answer_plan(inspection,candidate):
    """Resolve each field separately; never fabricate an answer to finish a form."""
    form={'action':FIXTURE_ORIGIN+'/thanks','answer_host':urlsplit(inspection['public_url']).hostname,'fields':inspection['fields']}
    adapter=OfflineFormAdapter(None,inspection['platform']);mapping={};unresolved=[]
    for field in inspection['fields']:
        try:mapping.update(adapter.map_questions({**form,'fields':[field]},candidate))
        except FormHold as exc:unresolved.append({'field':field['id'],'label':field['label'],'code':str(exc)})
    return {'mapping':mapping,'unresolved':unresolved,'blockers':inspection['blockers'],'answer_host':form['answer_host']}


def disconnected_preparation(db,inspection_id,review_document_id=None):
    """Use the retrieved schema in an offline browser, with zero remote input/upload."""
    inspection=load_inspection(db,inspection_id);candidate=candidate_snapshot(db)
    unapproved=False;review_content=None
    if review_document_id is not None:
        content,ext,sha,_=cv_review_bytes(db,review_document_id)
        unapproved=not db.rows('SELECT approved_at FROM candidate_documents WHERE id=?',(review_document_id,))[0]['approved_at']
        review_content=(content,ext,sha)
        candidate={**candidate,'cv_document_id':review_document_id}
    plan=answer_plan(inspection,candidate)
    base={'inspection_id':inspection_id,'form_hash':inspection['form_hash'],'facts_hash':candidate['_facts_hash'],
          'resolved_fields':list(plan['mapping']),'unresolved_questions':plan['unresolved'],'source_kind':inspection['source_kind'],
          'external_personal_data_sent':False,'posts':0,'hosted_form_verified':False,'live_supported':False,
          'using_unapproved_cv_for_local_review_only':bool(unapproved),'ready_for_submission':False}
    if plan['blockers'] and inspection['platform']!='recruitee':return {**base,'state':'HOLD','blockers':plan['blockers'],'browser_validation':False}
    parts=['<!doctype html><meta charset="utf-8"><form method="post" action="/thanks">']
    for field in inspection['fields']:
        key=escape(field['id'],quote=True);required=' required' if field['required'] else ''
        parts.append('<label for="'+key+'">'+escape(field['label'])+'</label>')
        if field['type']=='select-one':
            parts.append('<select id="'+key+'"'+required+'><option value=""></option>')
            parts.extend('<option value="'+escape(o['value'],quote=True)+'">'+escape(o['text'])+'</option>' for o in field['options']);parts.append('</select>')
        elif field['type']=='textarea':parts.append('<textarea id="'+key+'"'+required+'></textarea>')
        elif field['type'] in {'text','email','tel','file','checkbox','url','number'}:parts.append('<input id="'+key+'" type="'+field['type']+'"'+required+'>')
        else:return {**base,'state':'HOLD','blockers':['UNSUPPORTED_SCHEMA_FIELD'],'browser_validation':False}
    parts.append('<button type="submit">Submit application</button></form>')
    with offline_browser({FIXTURE_ORIGIN+'/form':''.join(parts)}) as (page,traffic):
        page.goto(FIXTURE_ORIGIN+'/form');adapter=OfflineFormAdapter(page,inspection['platform'])
        form=adapter.inspect_form()
        adapter.fill(form,plan['mapping'],lambda did:review_content if review_content and did==review_document_id else document_bytes(db,did))
        valid=False
        if not plan['unresolved']:valid=adapter.validate_prefinal()
        result={**base,'state':('REVIEW_ONLY' if unapproved else 'PREPARED_OFFLINE') if valid and not plan['blockers'] else 'HOLD','blockers':plan['blockers'],
                'browser_validation':valid,'posts':traffic['fixture_posts'],'browser_fields_checked':True}
    event(db,'DISCONNECTED_FORM_PREPARED',{'inspection_id':inspection_id,'state':result['state'],'unresolved_count':len(plan['unresolved']),'posts':0})
    return result
