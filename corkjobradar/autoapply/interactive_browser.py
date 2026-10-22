"""Human-paused browser actor. External interactive transport is NOT released.

Only an explicitly marked, isolated, owned loopback fixture can run today.
The user/test operates the simulated verification control; this actor never does.
"""
import hashlib
import json
import os
from urllib.parse import urlsplit
from ..config import ROOT,now,digest
from .browser import FormHold
from .documents import document_bytes
from .human_sessions import (session_row,validate_session,update_session,require_owned_fixture,PAUSED,EXPIRED)


def detect_human_check(page):
    if page.is_closed():return 'BROWSER_CLOSED'
    checks=[('AUTHENTICATION_REQUIRED','input[type="password"], input[autocomplete="one-time-code"], [data-mfa-required]'),
            ('HUMAN_VERIFICATION_REQUIRED','iframe[src*="captcha" i], iframe[src*="challenge" i], .g-recaptcha, .h-captcha, [data-human-verification], #challenge-running, [id^="cf-chl"]')]
    for code,selector in checks:
        locators=page.locator(selector)
        if any(locators.nth(i).is_visible() for i in range(locators.count())):return code
    # Cross-origin frames are only classified by URL, never read for tokens.
    for frame in page.frames:
        p=urlsplit(frame.url)
        if p.path.startswith(('/login','/signin','/sign-in','/mfa')):return 'AUTHENTICATION_REQUIRED'
    return None


class InteractiveBrowser:
    def __init__(self,db,sid,*,headless=False):
        self.db=db;self.sid=sid;self.headless=headless;self.page=None;self.browser=None;self.context=None
        self.pw=None;self.driver=None;self.environs={};self.armed=False;self.dispatches=0;self.network_issue=None
        self.expected_signature=None;self.ctx=None

    def __enter__(self):return self
    def __exit__(self,*args):self.dispose()

    def _set(self,status,code,form_state,filled=None):
        update_session(self.db,self.sid,status,code,form_state,filled)

    def _current(self):
        row=session_row(self.db,self.sid)
        self.ctx=validate_session(self.db,self.sid)
        if not row['fixture_url']:raise FormHold('EXTERNAL_INTERACTIVE_ADAPTER_NOT_VERIFIED')
        require_owned_fixture(self.db,self.ctx['job'],row['fixture_url'])
        return self.ctx

    def _launch(self):
        from playwright.sync_api import sync_playwright
        temp=ROOT/'data/browser-temp';temp.mkdir(exist_ok=True)
        settings={'PLAYWRIGHT_BROWSERS_PATH':str(ROOT/'data/playwright-browsers'),'TEMP':str(temp),'TMP':str(temp)}
        self.environs={key:os.environ.get(key) for key in settings};os.environ.update(settings)
        self.driver=sync_playwright();self.pw=self.driver.start()
        self.browser=self.pw.chromium.launch(headless=self.headless,args=['--disable-background-networking','--disable-breakpad','--no-first-run'])
        self.context=self.browser.new_context(service_workers='block',accept_downloads=False)
        origin=urlsplit(self.ctx['target_url'])
        def forward_without_redirect(route):
            # Chromium may follow redirects from continue_ without a second
            # route callback. Inspect the first HTTP response before exposing it.
            response=route.fetch(max_redirects=0,timeout=5000)
            if 300<=response.status<400:
                self.network_issue='INDEPENDENT_DESTINATION_REVIEW_REQUIRED'
                route.fulfill(status=403,content_type='application/json',body='{}');return
            route.fulfill(response=response)
        def guard(route):
            req=route.request;p=urlsplit(req.url)
            same=(p.scheme,p.netloc)==(origin.scheme,origin.netloc)
            if same and req.method=='GET' and p.path in {'/form','/session-status'} and not p.query:
                forward_without_redirect(route);return
            if same and req.method=='POST' and p.path=='/human-verify' and not p.query and not req.post_data_buffer:
                # OWNED simulated challenge only. This actor never calls it;
                # the user/test presses the visible human verification button.
                forward_without_redirect(route);return
            if same and req.method=='POST' and p.path=='/submit' and not p.query and self.armed and self.dispatches==0:
                # The final DB gate also runs in the network handler, immediately
                # before the one authorized OWNED request is let through.
                try:self._current()
                except Exception:
                    self.network_issue='FINAL_AUTHORIZATION_CHANGED';route.abort();return
                self.armed=False;self.dispatches+=1
                self.db.execute('UPDATE autoapply_interventions SET submission_started=1 WHERE id=?',(self.sid,))
                forward_without_redirect(route);return
            self.network_issue='INDEPENDENT_DESTINATION_REVIEW_REQUIRED' if not same else 'UNAUTHORIZED_REQUEST_BLOCKED'
            route.abort('blockedbyclient')
        self.context.route('**/*',guard)
        self.context.route_web_socket('**/*',lambda ws:ws.close())
        self.page=self.context.new_page();self.page.set_default_timeout(5000)
        self.page.expose_function('__cjr_owned_human_pause',lambda:self._set(PAUSED,'HUMAN_VERIFICATION_REQUIRED','CAMPOS_EN_MEMORIA'))
        # The local DOM guard runs BEFORE navigation starts. DOM queries from a
        # paused navigation request callback can wait for that same navigation.
        # This listener never solves anything; it cancels submit and signals pause.
        self.page.add_init_script('''window.addEventListener('submit',event=>{
          const visible=e=>!!(e.getClientRects().length && getComputedStyle(e).visibility!=='hidden');
          const selector='iframe[src*="captcha" i],iframe[src*="challenge" i],.g-recaptcha,.h-captcha,[data-human-verification],#challenge-running,[id^="cf-chl"],input[type=password],input[autocomplete="one-time-code"],[data-mfa-required]';
          if([...document.querySelectorAll(selector)].some(visible)){
            event.preventDefault();window.__cjr_owned_human_pause();}
        },false);''')
        # No traces, screenshots, storage_state, cookies() or response-token reads.

    def _pause_if_needed(self):
        if not self.page or self.page.is_closed():
            self._set(EXPIRED,'BROWSER_CLOSED','RECONSTRUIR_CAMPOS_Y_VERIFICACION');return True
        if self.network_issue:
            self._set('HOLD',self.network_issue,'CONSERVADO_SIN_REANUDAR');return True
        code=detect_human_check(self.page)
        if code:
            self._set(PAUSED,code,'CAMPOS_EN_MEMORIA');return True
        return False

    def _form(self):
        if self.page.locator('form').count()!=1:raise FormHold('FORM_STRUCTURE_CHANGED')
        form=self.page.locator('form').evaluate('''f=>({action:f.action,method:f.method,
          fields:[...f.querySelectorAll('input,select,textarea')].filter(e=>!['hidden','submit','button'].includes(e.type)).map(e=>({
          id:e.id,name:e.name,type:e.type,required:e.required,disabled:e.disabled,
          label:e.labels?[...e.labels].map(l=>l.innerText).join(' '):'',
          options:e.options?[...e.options].map(o=>({value:o.value,text:o.text})):[]}))})''')
        p=urlsplit(self.ctx['target_url']);expected=p.scheme+'://'+p.netloc+'/submit'
        if form['method'].lower()!='post' or form['action']!=expected:raise FormHold('UNAUTHORIZED_FORM_ACTION')
        declared=self.ctx['inspection']['fields'];actual=form['fields']
        keys=('id','type','required','disabled','label','options')
        project=lambda f:{k:f[k] for k in keys}
        if [project(f) for f in actual]!=[project(f) for f in declared]:raise FormHold('FORM_STRUCTURE_CHANGED')
        return form,digest(form)

    def open(self):
        self._current()
        if self.page and not self.page.is_closed():raise FormHold('EXISTING_BROWSER_MUST_BE_RESUMED')
        if self.driver:self.dispose()
        self.network_issue=None;self._launch()
        try:response=self.page.goto(self.ctx['target_url'],wait_until='domcontentloaded')
        except Exception:
            if self.network_issue:
                self._set('HOLD',self.network_issue,'CONSERVADO_SIN_REANUDAR');return
            raise
        if self.network_issue:
            self._set('HOLD',self.network_issue,'CONSERVADO_SIN_REANUDAR');return
        if not response or response.status!=200:
            self._set(EXPIRED,'FORM_SESSION_EXPIRED','RECONSTRUIR_CAMPOS_Y_VERIFICACION');return
        if self._pause_if_needed():return
        _,self.expected_signature=self._form()
        self._fill_missing()

    def _fill_missing(self):
        self._current();count=0
        for f in self.ctx['inspection']['fields']:
            if self._pause_if_needed():return
            _,signature=self._form()
            if self.expected_signature and signature!=self.expected_signature:raise FormHold('FORM_STRUCTURE_CHANGED')
            self.expected_signature=signature
            answer=self.ctx['mapping'].get(f['id'])
            if answer is None:continue
            el=self.page.locator('[id='+json.dumps(f['id'])+']')
            if 'document' in answer:
                data,ext,_=document_bytes(self.db,answer['document'])
                if not el.evaluate('(e)=>e.files.length'):
                    el.set_input_files({'name':'CV.'+ext,'mimeType':'application/pdf' if ext=='pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document','buffer':data})
            elif f['type']=='checkbox':el.set_checked(str(answer['value'])=='true')
            elif f['type']=='select-one':el.select_option(str(answer['value']))
            elif f['type'] in {'text','email','tel','textarea','number','url'}:
                if el.input_value()!=str(answer['value']):el.fill(str(answer['value']))
            else:raise FormHold('UNSUPPORTED_FIELD_TYPE')
            count+=1
            self.db.execute('UPDATE autoapply_interventions SET filled_count=? WHERE id=?',(count,self.sid))
            if self._pause_if_needed():return
        # An explicit human Continue is required, including when no widget appears.
        self._set(PAUSED,'MANUAL_REVIEW_REQUIRED','CAMPOS_EN_MEMORIA',count)

    def _verify_fields(self):
        _,signature=self._form()
        if self.expected_signature!=signature:raise FormHold('FORM_STRUCTURE_CHANGED')
        for f in self.ctx['inspection']['fields']:
            answer=self.ctx['mapping'].get(f['id']);el=self.page.locator('[id='+json.dumps(f['id'])+']')
            if answer is None:
                # Manually filled unknown optional answers are not silently sent.
                if f['type']=='file':extra=el.evaluate('(e)=>e.files.length')>0
                elif f['type']=='checkbox':extra=el.is_checked()
                else:extra=bool(el.input_value())
                if extra:raise FormHold('MANUAL_ANSWER_REQUIRES_VERIFICATION')
                continue
            if 'document' in answer:
                _,_,sha=document_bytes(self.db,answer['document'])
                # File bytes are hashed in memory, never saved to a screenshot/log.
                actual=el.evaluate('''async e=>{if(e.files.length!==1)return null;
                  const h=await crypto.subtle.digest('SHA-256',await e.files[0].arrayBuffer());
                  return [...new Uint8Array(h)].map(b=>b.toString(16).padStart(2,'0')).join('');}''')
                if actual!=sha:raise FormHold('ATTACHED_CV_CHANGED')
            elif f['type']=='checkbox':
                if el.is_checked()!=(str(answer['value'])=='true'):raise FormHold('VERIFIED_FIELD_CHANGED')
            elif el.input_value()!=str(answer['value']):raise FormHold('VERIFIED_FIELD_CHANGED')
        if not self.page.locator('form').evaluate('(f)=>f.checkValidity()'):raise FormHold('HTML_VALIDATION_FAILED')

    def continue_after_human(self):
        row=session_row(self.db,self.sid)
        if row['status']!=PAUSED:raise FormHold('PAUSED_SESSION_REQUIRED')
        self._current()
        if self._pause_if_needed():return
        # Owned fixture protocol only. A hidden widget is insufficient: ask the
        # actual owned server about this still-open browser session, without
        # exporting cookies/tokens or carrying verification to another context.
        status=self.page.evaluate("async()=>{const r=await fetch('/session-status',{cache:'no-store'});return {http:r.status,body:await r.json()};}")
        if status['http']!=200 or status['body'].get('active') is not True:
            self._set(EXPIRED,'FORM_SESSION_EXPIRED','RECONSTRUIR_CAMPOS_Y_VERIFICACION');return
        if status['body'].get('human_verified') is not True:
            self._set(PAUSED,'HUMAN_VERIFICATION_NOT_CONFIRMED','CAMPOS_EN_MEMORIA');return
        # Complete only remaining known fields; never overwrite a human edit.
        self._verify_partial_fields()
        self._fill_missing()
        if self._pause_if_needed():return
        self._current();self._verify_fields()
        self.armed=True
        try:
            with self.page.expect_response(lambda r:r.request.method=='POST' and urlsplit(r.url).path=='/submit') as capture:
                self.page.get_by_role('button',name='Submit owned test',exact=True).click()
            response=capture.value;body=response.json();raw=response.body()
            request_hash=hashlib.sha256(response.request.post_data_buffer or b'').hexdigest()
            sha=self.ctx['binding']['document_hash']
            verified=(response.status==200 and body.get('received') is True and body.get('environment')=='OWNED_HUMAN_TEST_ONLY'
                      and body.get('job_id')==self.ctx['job']['id'] and body.get('cv_hash')==sha and body.get('request_hash')==request_hash
                      and isinstance(body.get('reference'),str) and body['reference'].startswith('OWNED-HUMAN-'))
            self.db.execute('UPDATE autoapply_interventions SET local_receipt_verified=? WHERE id=?',(int(verified),self.sid))
            self._set('PRUEBA_LOCAL_CONFIRMADA' if verified else 'ENVIO_INCIERTO',
                      'OWNED_RECEIVER_CONFIRMED' if verified else 'RECEIPT_NOT_VERIFIED','PRUEBA_LOCAL_FINALIZADA')
            event_details={'session_id':self.sid,'response_hash':hashlib.sha256(raw).hexdigest(),'request_hash':request_hash,
                           'http_status':response.status,'local_receipt_verified':verified,'external_receipt_verified':False}
            from .policy import event
            event(self.db,'OWNED_HUMAN_TEST_RESULT',event_details,attempt_id=row['attempt_id'])
        except Exception:
            current=session_row(self.db,self.sid)
            if current['submission_started']:
                self._set('ENVIO_INCIERTO','NO_CORRELATED_RECEIPT','NO_REINTENTAR')
            elif current['status']==PAUSED and detect_human_check(self.page):
                self._set(PAUSED,detect_human_check(self.page),'CAMPOS_EN_MEMORIA');return
            else:raise
        finally:self.armed=False

    def _verify_partial_fields(self):
        # Preserve all existing values. Reject changes rather than silently
        # replacing a human answer with an old approved one.
        for f in self.ctx['inspection']['fields']:
            answer=self.ctx['mapping'].get(f['id'])
            if answer is None or 'document' in answer:continue
            el=self.page.locator('[id='+json.dumps(f['id'])+']')
            value=el.input_value() if f['type']!='checkbox' else ('true' if el.is_checked() else 'false')
            if value and value!=str(answer['value']):raise FormHold('VERIFIED_FIELD_CHANGED')

    def recover(self):
        self._current();self.dispose();self.page=None;self.expected_signature=None
        self.open()  # New browser/session: prior human verification is never reused.

    def focus(self):
        if not self.page or self.page.is_closed():
            self._set(EXPIRED,'BROWSER_CLOSED','RECONSTRUIR_CAMPOS_Y_VERIFICACION')
        else:self.page.bring_to_front()

    def dispose(self):
        try:
            if self.browser:self.browser.close()
        finally:
            try:
                if self.pw:self.pw.stop()
            finally:
                self.driver=None;self.pw=None;self.browser=None;self.context=None
                for key,value in self.environs.items():
                    if value is None:os.environ.pop(key,None)
                    else:os.environ[key]=value
                self.environs={}
