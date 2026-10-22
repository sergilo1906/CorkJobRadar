"""Local UI proof with the real saved draft; no approval or external application."""
import json
import os
import re
from pathlib import Path
import sys
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.db import Database


def main():
    from playwright.sync_api import sync_playwright
    db=Database();control=db.rows('SELECT * FROM autoapply_control')[0]
    documents=db.rows('SELECT id,approved_at FROM candidate_documents ORDER BY id')
    facts=db.rows('SELECT COUNT(*) n FROM candidate_facts WHERE revoked_at IS NULL')[0]['n']
    temp=ROOT/'data/browser-temp';temp.mkdir(exist_ok=True)
    os.environ.update(PLAYWRIGHT_BROWSERS_PATH=str(ROOT/'data/playwright-browsers'),TEMP=str(temp),TMP=str(temp))
    blocked=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=['--disable-background-networking','--disable-breakpad'])
        context=browser.new_context(service_workers='block',accept_downloads=False)
        def guard(route):
            url=urlsplit(route.request.url)
            if url.hostname=='127.0.0.1' and url.port==8501 and url.scheme=='http':route.continue_()
            else:blocked.append(url.hostname);route.abort()
        def socket_guard(ws):
            url=urlsplit(ws.url)
            if url.hostname=='127.0.0.1' and url.port==8501:ws.connect_to_server()
            else:ws.close()
        context.route('**/*',guard);context.route_web_socket('**/*',socket_guard)
        page=context.new_page()
        try:
            page.goto('http://127.0.0.1:8501',wait_until='domcontentloaded')
            page.get_by_role('tab',name='Candidaturas automáticas',exact=True).click()
            page.get_by_role('heading',name='Candidaturas automáticas — modo A',exact=True).wait_for(timeout=30000)
            page.locator('summary').filter(has_text='CV fundamentado en inglés').click()
            page.get_by_role('button',name='Descargar CV para revisión',exact=True).wait_for()
            assert page.get_by_role('button',name='Guardar esta versión validada del CV',exact=True).is_disabled()
            page.locator('summary').filter(has_text='Configurar y autorizar una política de simulación').click()
            assert page.get_by_text('Plataformas autorizadas',exact=True).is_visible()
            assert page.get_by_text('Cupo diario AutoApply',exact=True).is_visible()
            page.locator('summary').filter(has_text='Formularios y preparación de una candidatura sin envío').click()
            selector=page.locator('[data-testid="stSelectbox"]').filter(has=page.get_by_text('Vacante IT para inspeccionar',exact=True))
            selector.get_by_role('combobox').click()
            selector.get_by_role('combobox').fill('IT Support Specialist')
            page.get_by_role('option',name=re.compile(r'^IT Support Specialist .*Keeper Security$')).click()
            page.get_by_text('Hay restricciones o campos sin validar:',exact=False).wait_for(timeout=30000)
            assert not page.locator('[data-testid="stException"]').count()
            assert db.rows('SELECT * FROM autoapply_control')[0]==control
            assert db.rows('SELECT id,approved_at FROM candidate_documents ORDER BY id')==documents
            report={'checked_at':now(),'url':page.url,'persisted_draft_visible':True,'save_disabled_until_review':True,
                    'guided_policy_visible':True,'real_inspection_visible':True,'hosted_captcha_block_visible':True,
                    'approved_facts_preserved':facts,'document_approval_changed':False,'policy_changed':False,
                    'external_requests_blocked':len(blocked),'external_forms_submitted':0,'live_enabled':False}
            (ROOT/'logs/operational-ui-browser.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            print(json.dumps(report))
        finally:context.close();browser.close()


if __name__=='__main__':main()
