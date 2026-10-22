"""Read a public Greenhouse DOM with Playwright. No candidate data, fill, upload or POST."""
from contextlib import contextmanager
import os
import re
import time
from urllib.parse import urlsplit
from ..config import ROOT,load_profile,now,digest
from ..http import WebClient,validate_url
from .platforms import GREENHOUSE_HOSTS


def allowed_probe_get(url,source_url,method='GET'):
    try:
        source=urlsplit(source_url);target=urlsplit(url)
        if method!='GET' or target.scheme!='https' or target.username or target.password or target.port not in {None,443}:return False
        identity=re.fullmatch(r'/([A-Za-z0-9_-]+)/jobs/(\d+)/?',source.path)
        if source.hostname not in GREENHOUSE_HOSTS or not identity:return False
        if target.hostname in {source.hostname,'boards-api.greenhouse.io'} and target.path=='/robots.txt' and not target.query:return True
        if target.hostname==source.hostname:
            return target.path==source.path and not target.query or target.path.startswith('/_next/static/') and target.path.endswith(('.js','.css'))
        return target.hostname=='boards-api.greenhouse.io' and target.path==f'/v1/boards/{identity[1]}/jobs/{identity[2]}' and target.query in {'','questions=true'}
    except ValueError:return False


@contextmanager
def project_browser():
    from playwright.sync_api import sync_playwright
    temp=ROOT/'data/browser-temp';temp.mkdir(exist_ok=True)
    previous={k:os.environ.get(k) for k in ('PLAYWRIGHT_BROWSERS_PATH','TEMP','TMP')}
    environ={**os.environ,'PLAYWRIGHT_BROWSERS_PATH':str(ROOT/'data/playwright-browsers'),'TEMP':str(temp),'TMP':str(temp)}
    for key in previous:os.environ[key]=environ[key]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,env=environ,args=['--disable-background-networking','--disable-breakpad','--no-first-run'])
            context=browser.new_context(service_workers='block',accept_downloads=False,offline=True)
            try:yield context
            finally:context.close();browser.close()
    finally:
        for key,value in previous.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value


def inspect_hosted_greenhouse(source_url):
    if not allowed_probe_get(source_url,source_url):raise ValueError('PUBLIC_GREENHOUSE_POSTING_REQUIRED')
    def validator(url):
        if not allowed_probe_get(url,source_url):raise ValueError('PROBE_DESTINATION_NOT_ALLOWED')
        return validate_url(url)
    profile=load_profile();profile.update(http_retries=0,http_timeout=6)
    started=time.monotonic();traffic={'get_resources':0,'blocked_requests':0,'errors':0,'error_types':[],'limited':False,'captcha_declared':False}
    with WebClient(profile,validator=validator) as client,project_browser() as context:
        def route(handler):
            request=handler.request
            if traffic['captcha_declared'] and request.url!=source_url:
                traffic['blocked_requests']+=1;handler.abort();return
            if not allowed_probe_get(request.url,source_url,request.method):
                traffic['blocked_requests']+=1;handler.abort();return
            if traffic['get_resources']>=50 or time.monotonic()-started>45:
                traffic['limited']=True;handler.abort();return
            try:
                traffic['get_resources']+=1
                response=client.get(request.url,check_robots=True)
                if request.url==source_url and re.search(r'recaptcha|hcaptcha|cf-chl-',response.text,re.I):traffic['captcha_declared']=True
                headers={key:value for key,value in response.headers.items() if key in {'content-type','content-security-policy','referrer-policy'}}
                handler.fulfill(status=response.status_code,headers=headers,body=response.content)
            except Exception as exc:
                traffic['errors']+=1;traffic['error_types'].append(type(exc).__name__);handler.abort()
        context.route('**/*',route)
        context.route_web_socket('**/*',lambda ws:ws.close())
        page=context.new_page();page.set_default_timeout(8000)
        page.goto(source_url,wait_until='domcontentloaded',timeout=60000)
        page.wait_for_timeout(1000)
        captcha=page.locator('iframe[src*="captcha"], [class*="captcha"], [id*="captcha"], input[type="password"]').count()>0
        fields=page.locator('form input, form textarea, form select').evaluate_all('''elements=>elements.filter(e=>!['hidden','submit','button'].includes(e.type)).map(e=>({
            id:e.id,type:e.type,required:e.required,disabled:e.disabled,
            label:(e.labels?[...e.labels].map(l=>l.innerText).join(' '):'')||e.getAttribute('aria-label')||'',
            options:e.options?[...e.options].map(o=>({value:o.value,text:o.text})):[]}))''')
        return {'checked_at':now(),'source_url':source_url,'mode':'HOSTED_DOM_GET_ONLY_NO_CANDIDATE_DATA',
                'fields':fields,'dom_hash':digest(fields),'captcha_element_detected':captcha,'captcha_detected':captcha or traffic['captcha_declared'],'traffic':traffic,
                'hold_reason':'CAPTCHA_DECLARED_OR_DETECTED' if captcha or traffic['captcha_declared'] else 'READ_ONLY_IS_NOT_INTERACTIVE_COMPLETION',
                'filled':False,'uploaded':False,'submissions':0,'interactive_completion_verified':False,
                'automation_permission_verified':False,'limitations':['No se introduce información personal','No se pulsa enviar','Recursos de terceros bloqueados','La lectura del DOM no verifica el rellenado alojado']}
