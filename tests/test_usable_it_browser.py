"""Actual local Streamlit + Chromium, synthetic identity only, no external requests."""
import io
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
from urllib.parse import urlsplit
import zipfile
import httpx
from corkjobradar.config import ROOT,now
from corkjobradar.autoapply.documents import create_cv_review,render_cv
from corkjobradar.autoapply.vault import candidate_snapshot,approve_fact
from test_usable_it_workspace import case
from test_assisted_delivery import message


def test_real_browser_manual_application_copy_cv_declaration_and_encrypted_proof(db,profile,tmp_path,monkeypatch):
    from playwright.sync_api import sync_playwright
    job=case(db,profile);approve_fact(db,'linkedin_url','https://www.linkedin.com/in/synthetic-only/','SYNTHETIC',True)
    create_cv_review(db,render_cv(candidate_snapshot(db),'pdf'),'pdf')
    app=tmp_path/'assisted_browser_app.py'
    app.write_text('from corkjobradar.db import Database\n'
                   'import corkjobradar.autoapply.handoff as handoff\n'
                   'handoff.validate_url=lambda url:url\n'
                   'from corkjobradar.autoapply.manual_workspace_ui import render_manual_workspace\n'
                   'from corkjobradar.autoapply.assisted_ui import render_manual_evidence\n'
                   'db=Database('+repr(str(db.path))+')\nrender_manual_workspace(db)\nrender_manual_evidence(db)\n',encoding='utf-8')
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    origin='http://127.0.0.1:'+str(port)
    env=os.environ.copy();env.update(PYTHONPATH=str(ROOT),PYTHONIOENCODING='utf-8',TEMP=str(tmp_path),TMP=str(tmp_path))
    monkeypatch.setenv('PLAYWRIGHT_BROWSERS_PATH',str(ROOT/'data/playwright-browsers'))
    monkeypatch.setenv('TEMP',str(tmp_path));monkeypatch.setenv('TMP',str(tmp_path))
    log=(tmp_path/'streamlit.log').open('w',encoding='utf-8')
    child=subprocess.Popen([sys.executable,'-m','streamlit','run',str(app),'--server.address','127.0.0.1','--server.port',str(port),
                            '--server.headless','true','--browser.gatherUsageStats','false'],cwd=ROOT,env=env,stdout=log,stderr=log,
                           creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    blocked=[]
    try:
        deadline=time.monotonic()+35
        with httpx.Client(trust_env=False,timeout=1) as health:
            while True:
                try:
                    if health.get(origin+'/_stcore/health').status_code==200:break
                except httpx.HTTPError:pass
                if child.poll() is not None or time.monotonic()>deadline:raise AssertionError('ISOLATED_STREAMLIT_NOT_READY')
                time.sleep(.15)
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,args=['--disable-background-networking','--disable-breakpad'])
            context=browser.new_context(accept_downloads=True,service_workers='block',permissions=['clipboard-read','clipboard-write'])
            def allowed(url):
                p=urlsplit(url);return p.hostname=='127.0.0.1' and p.port==port
            def guard(route):
                if allowed(route.request.url):route.continue_()
                else:blocked.append(True);route.abort()
            context.route('**/*',guard)
            context.route_web_socket('**/*',lambda ws:ws.connect_to_server() if allowed(ws.url) else ws.close())
            page=context.new_page()
            try:
                page.goto(origin,wait_until='domcontentloaded')
                page.get_by_role('button',name='Aprobar esta versión del CV',exact=True).wait_for(timeout=30000)
                assert page.get_by_role('button',name='Aprobar esta versión del CV',exact=True).is_disabled()
                page.get_by_text('He revisado íntegramente esta versión y apruebo este CV definitivo',exact=True).click()
                page.get_by_role('button',name='Aprobar esta versión del CV',exact=True).click()
                page.get_by_role('button',name='Preparar solicitud manual con mi CV aprobado',exact=True).wait_for()
                # st.code's real copy control must write the exact value, not a mock clipboard.
                block=page.get_by_test_id('stCode').filter(has_text='synthetic@example.invalid')
                block.hover()
                block.get_by_role('button',name=re.compile('copy',re.I)).click()
                assert page.evaluate('navigator.clipboard.readText()')=='synthetic@example.invalid'
                page.get_by_role('button',name='Preparar solicitud manual con mi CV aprobado',exact=True).click()
                page.get_by_role('button',name='Descargar CV y solicitud manual',exact=True).wait_for()
                with page.expect_download() as downloaded:page.get_by_role('button',name='Descargar CV y solicitud manual',exact=True).click()
                path=tmp_path/'application.zip';downloaded.value.save_as(path)
                with zipfile.ZipFile(path) as archive:
                    assert archive.read('CV.pdf').startswith(b'%PDF')
                    text=archive.read('CANDIDATURA.txt').decode('utf-8')
                    assert 'synthetic@example.invalid' in text and 'linkedin.com/in/synthetic-only/' in text
                assert not db.rows('SELECT * FROM user_actions')
                page.get_by_text('Confirmo que ya presenté esta solicitud manualmente; registrar para evitar duplicados',exact=True).click()
                page.get_by_role('button',name='Registrar candidatura presentada por mí',exact=True).click()
                page.locator('input[type=file]').wait_for(state='attached')
                summary=page.locator('summary').filter(has_text='Justificantes de candidaturas manuales')
                if not summary.evaluate('(el) => el.parentElement.open'):summary.click()
                page.locator('input[type=file]').set_input_files({'name':'synthetic-receipt.eml','mimeType':'message/rfc822','buffer':message(job)})
                if not summary.evaluate('(el) => el.parentElement.open'):summary.click()
                page.get_by_text('Autorizo conservar este justificante cifrado; entiendo que no autentica al remitente ni activa AutoApply',exact=True).click()
                page.get_by_role('button',name='Guardar justificante cifrado',exact=True).click()
                page.get_by_role('button',name='Descargar justificante original',exact=True).wait_for()
                assert page.get_by_role('button',name='Registrar mi revisión del justificante',exact=True).is_disabled()
                assert not page.locator('[data-testid="stException"]').count()
                assert len(db.rows('SELECT * FROM manual_application_declarations'))==1
                assert len(db.rows('SELECT * FROM user_actions'))==1
                assert len(db.rows('SELECT * FROM manual_application_evidence'))==1
                assert not db.rows('SELECT * FROM application_receipt_evidence') and not db.rows('SELECT * FROM application_attempts')
                assert not db.rows('SELECT * FROM autoapply_policies')
                assert db.rows('SELECT live_enabled FROM autoapply_control')[0]['live_enabled']==0
                (tmp_path/'browser-result.json').write_text(json.dumps({'checked_at':now(),'real_clipboard':True,'pdf_and_zip':True,
                    'explicit_cv_review':True,'manual_declaration':True,'encrypted_eml':True,'external_receipt_authenticated':False,
                    'external_requests_blocked':len(blocked),'external_posts':0,'live_enabled':False}),encoding='utf-8')
            finally:context.close();browser.close()
    finally:
        if child.poll() is None:
            if os.name=='nt':subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],capture_output=True,timeout=20)
            else:child.terminate()
            child.wait(timeout=20)
        log.close()
