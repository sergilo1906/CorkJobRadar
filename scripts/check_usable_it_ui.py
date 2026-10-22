"""Real dashboard smoke, public metadata only. No CV consent or clipboard use."""
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.db import Database


def main(report_name='usable-it-production-browser.json',check_radius=False,check_runtime=False):
    from playwright.sync_api import sync_playwright
    import re
    if not re.fullmatch('[a-z0-9-]+\\.json',report_name):raise ValueError('SAFE_REPORT_NAME_REQUIRED')
    db=Database();output=ROOT/'logs'/report_name
    if output.exists():raise FileExistsError('PRESERVE_PREVIOUS_BROWSER_RESULT')
    tables=('jobs','candidate_facts','candidate_documents','autoapply_policies','application_attempts','user_actions',
            'autoapply_form_inspections','manual_application_handoffs','manual_application_declarations','manual_application_evidence','manual_requirement_reviews')
    if check_radius:tables+=('it_selection_origins','it_worksite_evidence','it_application_queue','it_application_queue_events')
    if check_runtime:tables+=('local_runtime','local_runtime_notifications')
    before={t:db.rows('SELECT COUNT(*) n FROM '+t)[0]['n'] for t in tables};control=db.rows('SELECT * FROM autoapply_control')
    docs=db.rows('SELECT id,file_hash,approved_at,revoked_at FROM candidate_documents')
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
        context.route('**/*',guard);context.route_web_socket('**/*',lambda ws:ws.connect_to_server() if allowed(ws.url) else ws.close())
        page=context.new_page()
        try:
            page.goto('http://127.0.0.1:8501',wait_until='domcontentloaded')
            if check_runtime:
                page.get_by_role('heading',name='Actividad local continua · Windows · LIVE OFF',exact=True).wait_for(timeout=45000)
                for label in ['Iniciar actividad local','Pausar actividad','Reanudar actividad','Detener actividad','Buscar IT ahora']:
                    page.get_by_role('button',name=label,exact=True).wait_for(timeout=45000)
            page.get_by_role('tab',name='Candidaturas automáticas',exact=True).click()
            page.get_by_role('heading',name='Candidaturas IT asistidas',exact=True).wait_for(timeout=45000)
            if check_radius:
                page.get_by_role('heading',name='Política de selección IT · 50 km · mínimo solicitado hasta 3 años',exact=True).wait_for(timeout=60000)
                page.get_by_text('Centro de trabajo y distancia geográfica',exact=True).wait_for(timeout=60000)
                assert page.get_by_role('button',name='Descargar evaluación completa IT 50 km (JSON)',exact=True).is_enabled()
            search=page.get_by_role('textbox',name='Buscar puesto o empresa IT',exact=True)
            search.fill('SolarWinds');search.press('Enter')
            page.wait_for_timeout(1000)
            picker=page.get_by_test_id('stSelectbox').filter(has_text='Elegir candidatura IT asistida').get_by_role('combobox')
            picker.click()
            page.get_by_role('option').filter(has_text='Support & Operations Internship').click()
            link=page.get_by_role('link',name='Abrir anuncio oficial y solicitar manualmente',exact=True)
            page.wait_for_function('''() => [...document.querySelectorAll('a')].some(a => a.textContent.includes('Abrir anuncio oficial') && a.href.includes('gh_jid=4739548005'))''',timeout=60000)
            href=link.get_attribute('href')
            assert href=='https://jobs.solarwinds.com/job-detail/?gh_jid=4739548005'
            assert page.get_by_role('button',name='Preparar solicitud manual con mi CV aprobado',exact=True).is_disabled()
            assert page.get_by_role('button',name='Aprobar esta versión del CV',exact=True).is_disabled()
            page.locator('summary').filter(has_text='Descubrir más ofertas IT junior y canales oficiales').click()
            assert page.get_by_role('link',name='Buscar en LinkedIn con sus funciones oficiales',exact=True).get_attribute('href').startswith('https://www.linkedin.com/jobs/search/')
            assert page.get_by_role('link',name='Buscar en Indeed con sus funciones oficiales',exact=True).get_attribute('href').startswith('https://ie.indeed.com/jobs?')
            assert not page.locator('[data-testid="stException"]').count()
            after={t:db.rows('SELECT COUNT(*) n FROM '+t)[0]['n'] for t in tables}
            assert before==after and db.rows('SELECT * FROM autoapply_control')==control
            assert docs==db.rows('SELECT id,file_hash,approved_at,revoked_at FROM candidate_documents')
            report={'checked_at':now(),'browser':'Chromium real','assisted_workspace_visible':True,'public_gh_job_id_preserved':True,
                    'manual_official_search_links':True,'unapproved_cv_cannot_prepare_package':True,'no_cv_consent_given':True,
                    'counts_and_control_unchanged':True,'jobs':after['jobs'],'approved_facts':after['candidate_facts'],
                    'external_requests_blocked':len(blocked),'private_values_logged':False,'external_posts':0,'live_enabled':False,
                    'radius_policy_visible':check_radius,'runtime_controls_visible':check_runtime}
            output.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
        finally:context.close();browser.close()


if __name__=='__main__':main()
