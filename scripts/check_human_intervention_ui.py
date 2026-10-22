"""Read-only Chromium check of the real local dashboard. No candidate uploads."""
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
    db=Database();control=db.rows('SELECT * FROM autoapply_control')
    docs=db.rows('SELECT id,approved_at,revoked_at FROM candidate_documents')
    tables=('jobs','candidate_facts','autoapply_policies','application_attempts','user_actions','autoapply_interventions','autoapply_intervention_commands')
    before={t:db.rows('SELECT COUNT(*) n FROM '+t)[0]['n'] for t in tables}
    temp=ROOT/'data/browser-temp';temp.mkdir(exist_ok=True)
    os.environ.update(PLAYWRIGHT_BROWSERS_PATH=str(ROOT/'data/playwright-browsers'),TEMP=str(temp),TMP=str(temp))
    blocked=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=['--disable-background-networking','--disable-breakpad'])
        context=browser.new_context(service_workers='block',accept_downloads=False)
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
            page.get_by_role('heading',name='Intervenciones pendientes',exact=True).wait_for(timeout=45000)
            page.get_by_role('button',name='Actualizar intervenciones',exact=True).click()
            page.get_by_role('heading',name='Intervenciones pendientes',exact=True).wait_for()
            page.locator('summary').filter(has_text='Preparar paquete para intervención manual').click()
            assert page.get_by_text('LINKEDIN_MANUAL:',exact=False).is_visible()
            assert page.get_by_text('INDEED_MANUAL:',exact=False).is_visible()
            assert not page.locator('[data-testid="stException"]').count()
            after={t:db.rows('SELECT COUNT(*) n FROM '+t)[0]['n'] for t in tables}
            assert before==after and db.rows('SELECT * FROM autoapply_control')==control
            assert db.rows('SELECT id,approved_at,revoked_at FROM candidate_documents')==docs
            report={'checked_at':now(),'pending_interventions_section':True,'refresh_verified':True,
                    'manual_modes_visible':True,'counts_unchanged':True,'jobs':after['jobs'],'facts':after['candidate_facts'],
                    'external_requests_blocked':len(blocked),'external_posts':0,'live_enabled':False}
            output=ROOT/'logs/human-intervention-browser.json'
            if output.exists():raise FileExistsError('PRESERVE_PRIOR_BROWSER_RESULT')
            output.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
        finally:context.close();browser.close()


if __name__=='__main__':main()
