"""Offline Playwright sandbox. It NEVER navigates the public internet or exposes user data to it."""
from contextlib import contextmanager
from dataclasses import dataclass, asdict
import hashlib
import os
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from ..config import ROOT,digest

FIXTURE_ORIGIN='https://autoapply-fixture.invalid'


class FormHold(RuntimeError):pass


@contextmanager
def offline_browser(pages):
    from playwright.sync_api import sync_playwright
    for url in pages:
        if not url.startswith(FIXTURE_ORIGIN+'/'):raise ValueError('OFFLINE_FIXTURE_ORIGIN_REQUIRED')
    temp=ROOT/'data'/'browser-temp';temp.mkdir(exist_ok=True)
    environ={**os.environ,'PLAYWRIGHT_BROWSERS_PATH':str(ROOT/'data/playwright-browsers'),
             'TEMP':str(temp),'TMP':str(temp)}
    # The Node driver chooses Chromium's temporary profile before spawning Chromium.
    # Its own environment, as well as the browser environment, must use project TEMP.
    previous={key:os.environ.get(key) for key in ('PLAYWRIGHT_BROWSERS_PATH','TEMP','TMP')}
    for key in previous:os.environ[key]=environ[key]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,env=environ,args=['--disable-background-networking','--disable-breakpad','--no-first-run'])
            context=browser.new_context(service_workers='block',accept_downloads=False,offline=True)
            traffic={'blocked':0,'fixture_posts':0}
            def route(request_route):
                request=request_route.request
                item=pages.get(request.url)
                if item is None:
                    traffic['blocked']+=1;request_route.abort('blockedbyclient');return
                if request.method not in {'GET','POST'}:
                    traffic['blocked']+=1;request_route.abort('blockedbyclient');return
                if request.method=='POST':traffic['fixture_posts']+=1
                # Fulfilled in memory; no network, DNS or real HTTP server is contacted.
                request_route.fulfill(status=200,content_type='text/html; charset=utf-8',body=item)
            context.route('**/*',route)
            context.route_web_socket('**/*',lambda ws:ws.close())
            page=context.new_page();page.set_default_timeout(5000)
            try:yield page,traffic
            finally:context.close();browser.close()
    finally:
        for key,value in previous.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value


class OfflineFormAdapter:
    version='offline-forms-1'
    def __init__(self,page,platform):
        if platform not in {'greenhouse','lever','recruitee'}:raise ValueError('UNSUPPORTED_FIXTURE_PLATFORM')
        self.page=page;self.platform=platform;self.signature=None

    def inspect_form(self):
        if not self.page.url.startswith(FIXTURE_ORIGIN+'/'):raise FormHold('OFFLINE_ONLY')
        if self.page.locator('iframe[src*="captcha"], [class*="captcha"], [id*="captcha"], input[type=password]').count():
            raise FormHold('CAPTCHA_MFA_OR_LOGIN')
        if self.page.locator('form').count()!=1:raise FormHold('FORM_STRUCTURE_CHANGED')
        forms=self.page.locator('form').evaluate('''form => ({action:form.getAttribute('action')||location.href,
          method:(form.method||'get').toLowerCase(), fields:[...form.querySelectorAll('input,textarea,select')].map(e=>({
          id:e.id,name:e.name,type:e.type,required:e.required,disabled:e.disabled,
          label:(e.labels&&[...e.labels].map(l=>l.innerText).join(' '))||e.getAttribute('aria-label')||'',
          options:e.options?[...e.options].map(o=>({value:o.value,text:o.text})):[]}))})''')
        action=urljoin(self.page.url,forms['action'])
        if not action.startswith(FIXTURE_ORIGIN+'/'):raise FormHold('UNAUTHORIZED_FORM_ACTION')
        if forms['method']!='post':raise FormHold('UNSUPPORTED_FORM_METHOD')
        fields=[f for f in forms['fields'] if f['type'] not in {'hidden','submit','button'}]
        if any(not f['id'] or not f['label'] for f in fields):raise FormHold('UNLABELLED_OR_UNADDRESSABLE_FIELD')
        if len({f['id'] for f in fields})!=len(fields):raise FormHold('DUPLICATE_FIELD_ID')
        result={'action':action,'fields':fields,'platform':self.platform,'version':self.version}
        result['hash']=digest(result)
        return result

    def map_questions(self,form,candidate):
        mapping={};unresolved=[]
        aliases={'full name':'full_name','name':'full_name','first name':'first_name','last name':'last_name',
                 'email':'email','email address':'email','phone':'phone','phone number':'phone','location':'location',
                 'linkedin':'linkedin_url','linkedin profile':'linkedin_url','linkedin url':'linkedin_url','linkedin profile url':'linkedin_url'}
        for f in form['fields']:
            if f['disabled']:
                if f['required']:unresolved.append('DISABLED_REQUIRED_FIELD')
                continue
            label=' '.join(f['label'].lower().split()).rstrip(' *:')
            sensitive=f.get('legal') is True or f.get('sensitive') is True or bool(re.search(r'\b(?:consent|agree\w*|certif\w*|signature|religion|health|disabil\w*|race|ethnic\w*|gender|convict\w*|background|accept\w*|privacy|under oath)\b',label))
            if f['type']=='file' and re.fullmatch(r'(resume|cv|resume/cv)( upload)?',label):
                if candidate.get('cv_document_id'):mapping[f['id']]={'document':candidate['cv_document_id']}
                elif f['required']:unresolved.append('CV_MISSING')
                continue
            field=aliases.get(label)
            if field and candidate.get(field) and not sensitive:
                mapping[f['id']]={'value':candidate[field],'fact_id':candidate.get('_fact_ids',{}).get(field)};continue
            # Exact factual questions may reuse already approved facts. Never infer
            # future sponsorship, permanent residence, experience totals or legal assent.
            authorization_questions={'are you authorized to work in ireland for any employer?',
                                     'are you legally authorized to work in ireland?'}
            if label in authorization_questions and candidate.get('work_authorization')=='IRELAND_AUTHORIZED' and candidate.get('_fact_ids',{}).get('work_authorization'):
                yes=[o['value'] for o in f['options'] if o['text'].strip().lower()=='yes']
                value=yes[0] if f['type']=='select-one' and len(yes)==1 else 'Yes' if f['type'] in {'text','textarea'} else None
                if value is not None:
                    mapping[f['id']]={'value':value,'fact_id':candidate['_fact_ids']['work_authorization']};continue
            if label in {'availability','when can you start?'} and f['type'] in {'text','textarea'} and candidate.get('availability') and candidate.get('_fact_ids',{}).get('availability'):
                mapping[f['id']]={'value':candidate['availability'],'fact_id':candidate['_fact_ids']['availability']};continue
            answer=next((a for a in candidate.get('_answers',[]) if a['question']==f['label'] and a['host']==form.get('answer_host',urlsplit(form['action']).hostname) and (not sensitive or a.get('explicit_sensitive') is True)),None)
            if answer:mapping[f['id']]={'value':answer['answer'],'fact_id':answer['id']}
            elif f['required']:unresolved.append('SENSITIVE_OR_LEGAL_QUESTION' if sensitive else 'UNKNOWN_REQUIRED_QUESTION')
        if unresolved:raise FormHold('|'.join(sorted(set(unresolved))))
        return mapping

    def fill(self,form,mapping,documents):
        if self.inspect_form()['hash']!=form['hash']:raise FormHold('FORM_STRUCTURE_CHANGED')
        for f in form['fields']:
            answer=mapping.get(f['id'])
            if answer is None:continue
            locator=self.page.locator('[id='+__import__('json').dumps(f['id'])+']')
            if 'document' in answer:
                content,extension,_=documents(answer['document'])
                locator.set_input_files({'name':'CV.'+extension,'mimeType':'application/pdf' if extension=='pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document','buffer':content})
                if locator.evaluate('(e)=>e.files.length')!=1:raise FormHold('UPLOAD_NOT_VERIFIED')
            elif f['type']=='checkbox':
                if answer['value'] not in {'true','false'}:raise FormHold('EXPLICIT_BOOLEAN_ANSWER_REQUIRED')
                locator.set_checked(answer['value']=='true')
                if locator.is_checked()!=(answer['value']=='true'):raise FormHold('FIELD_VALIDATION_FAILED')
            elif f['type']=='select-one':
                if str(answer['value']) not in [o['value'] for o in f['options']]:raise FormHold('ANSWER_NOT_IN_OPTIONS')
                locator.select_option(str(answer['value']))
                if locator.input_value()!=str(answer['value']):raise FormHold('FIELD_VALIDATION_FAILED')
            elif f['type'] in {'text','email','tel','textarea','number','url'}:
                locator.fill(str(answer['value']))
                if locator.input_value()!=str(answer['value']):raise FormHold('FIELD_VALIDATION_FAILED')
            else:raise FormHold('UNSUPPORTED_FIELD_TYPE')
        self.signature=form['hash']

    def validate_prefinal(self):
        if self.inspect_form()['hash']!=self.signature:raise FormHold('FORM_STRUCTURE_CHANGED')
        if not self.page.locator('form').evaluate('(form)=>form.checkValidity()'):raise FormHold('HTML_VALIDATION_FAILED')
        return True

    def submit(self,db):
        from .policy import require_live
        require_live(db)

    def read_confirmation(self,expected_job,send_started=False):
        # Positive structured receipt, expected posting identity AND confirmation page required.
        if not send_started or not re.search(r'/(confirmation|thanks)(?:[/?#]|$)',self.page.url):return None
        receipt=self.page.locator('[data-application-reference][data-job-id]')
        if receipt.count()!=1:return None
        reference=receipt.get_attribute('data-application-reference') or ''
        if receipt.get_attribute('data-job-id')!=expected_job or not re.fullmatch(r'[A-Za-z0-9-]{5,100}',reference):return None
        if not re.search(r'application (?:was |has been )?received|successfully submitted',receipt.inner_text(),re.I):return None
        return {'reference':reference,'job':expected_job,'evidence_hash':digest(receipt.inner_text()),'simulation':True}
