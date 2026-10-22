"""Real dashboard Chromium check, loopback only; no approval or private uploads."""
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.db import Database


def main():
    from playwright.sync_api import sync_playwright
    db=Database()
    tables=('jobs','candidate_facts','autoapply_policies','application_attempts','user_actions',
            'manual_application_declarations','manual_application_evidence','manual_application_evidence_reviews')
    before={t:db.rows('SELECT COUNT(*) n FROM '+t)[0]['n'] for t in tables}
    control=db.rows('SELECT * FROM autoapply_control');docs=db.rows('SELECT id,approved_at,revoked_at FROM candidate_documents')
    temp=ROOT/'data/browser-temp';temp.mkdir(exist_ok=True)
    os.environ.update(PLAYWRIGHT_BROWSERS_PATH=str(ROOT/'data/playwright-browsers'),TEMP=str(temp),TMP=str(temp))
    output=ROOT/'logs/assisted-delivery-browser.json'
    if output.exists():raise FileExistsError('PRESERVE_PRIOR_BROWSER_RESULT')
    blocked=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=['--disable-background-networking','--disable-breakpad'])
        context=browser.new_context(service_workers='block',accept_downloads=True)
        def allowed(url):
            p=urlsplit(url);return p.hostname=='127.0.0.1' and p.port==8501
        def guard(route):
            if allowed(route.request.url):route.continue_()
            else:blocked.append(True);route.abort()
        context.route('**/*',guard)
        context.route_web_socket('**/*',lambda ws:ws.connect_to_server() if allowed(ws.url) else ws.close())
        page=context.new_page()
        try:
            page.goto('http://127.0.0.1:8501',wait_until='domcontentloaded')
            page.get_by_role('tab',name='Candidaturas automáticas',exact=True).click()
            page.locator('summary').filter(has_text='Diagnóstico independiente y gestiones de cada canal').wait_for(timeout=45000)
            page.locator('summary').filter(has_text='Diagnóstico independiente y gestiones de cada canal').click()
            page.get_by_role('button',name='Diagnosticar todos los bloqueos por separado',exact=True).click()
            page.get_by_role('button',name='Descargar diagnóstico separado',exact=True).wait_for(timeout=45000)
            with page.expect_download() as download:
                page.get_by_role('button',name='Descargar diagnóstico separado',exact=True).click()
            saved=ROOT/'logs/assisted-delivery-browser-blockers.json'
            if saved.exists():raise FileExistsError('PRESERVE_PRIOR_DIAGNOSTIC_DOWNLOAD')
            download.value.save_as(saved)
            report=json.loads(saved.read_text(encoding='utf-8'))
            assert report['jobs_processed']==before['jobs'] and len(report['axes'])==7
            assert all(not row['ready_to_submit'] for row in report['offers'])
            page.locator('summary').filter(has_text='Justificantes de candidaturas manuales').click()
            page.get_by_text('No hay candidaturas manuales declaradas.',exact=False).wait_for()
            assert not page.locator('[data-testid="stException"]').count()
            after={t:db.rows('SELECT COUNT(*) n FROM '+t)[0]['n'] for t in tables}
            assert before==after and db.rows('SELECT * FROM autoapply_control')==control
            assert db.rows('SELECT id,approved_at,revoked_at FROM candidate_documents')==docs
            result={'checked_at':now(),'browser':'Chromium real','diagnosis_downloaded':True,
                    'independent_axes':7,'offers_diagnosed':report['jobs_processed'],'evidence_section_empty_without_demo':True,
                    'counts_and_approvals_unchanged':True,'external_requests_blocked':len(blocked),
                    'external_posts':0,'live_enabled':False,'limit':'No external form or submission validated.'}
            output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
        finally:context.close();browser.close()


if __name__=='__main__':main()
