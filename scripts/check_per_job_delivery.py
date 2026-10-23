"""Read-only Chromium check of the existing real installation. No screenshots/consent."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.db import Database
from corkjobradar import runtime as rt
from scripts.check_ui_redesign import navigate,select,idle,layout


def main():
    from playwright.sync_api import sync_playwright,expect
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--label',required=True)
    parser.add_argument('--check-background-drafts',action='store_true')
    args=parser.parse_args()
    if not re.fullmatch(r'per-job-[a-z0-9-]+',args.label):raise ValueError('SAFE_LABEL_REQUIRED')
    path=ROOT/'logs'/(args.label+'.json')
    if path.exists():raise ValueError('PRESERVE_PREVIOUS_EVIDENCE')
    db=Database();critical=('candidate_facts','candidate_documents','autoapply_control','application_attempts',
        'autoapply_policies','job_document_versions','job_document_bundles','reference_originals','reference_review_events','manual_application_handoffs')
    def signatures():return {t:hashlib.sha256(repr(db.rows('SELECT * FROM '+t+' ORDER BY id')).encode()).hexdigest() for t in critical}
    before=signatures();runtime=rt.state(db);assert rt.alive(runtime['supervisor_pid'],runtime['supervisor_stamp'])
    environment=ROOT/'data/browser-temp';environment.mkdir(exist_ok=True)
    os.environ.update(TEMP=str(environment),TMP=str(environment),PLAYWRIGHT_BROWSERS_PATH=str(ROOT/'data/playwright-browsers'))
    blocked=[];checks=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(args=['--disable-background-networking'])
        context=browser.new_context(viewport={'width':1440,'height':900},service_workers='block')
        def allowed(url):
            p=urlsplit(url);return p.hostname=='127.0.0.1' and p.port==8501
        def guard(route):
            if allowed(route.request.url):route.continue_()
            else:blocked.append(True);route.abort()
        context.route('**/*',guard);context.route_web_socket('**/*',lambda ws:ws.connect_to_server() if allowed(ws.url) else ws.close())
        page=context.new_page();page.goto('http://127.0.0.1:8501')
        page.get_by_role('heading',name='Tu próxima oportunidad IT',exact=True).wait_for(timeout=45000);idle(page)
        draft_count=rt.snapshot(db)['document_drafts_for_review']
        if args.check_background_drafts:
            assert draft_count>0
            page.get_by_role('button',name='Revisar borradores de CV y carta',exact=True).click();idle(page)
            expect(page.get_by_test_id('stSelectbox').filter(has_text='Estado de candidatura')).to_contain_text('Borradores por revisar')
            navigate(page,'Actividad y notificaciones')
            page.get_by_role('button',name='Revisar CV y carta',exact=True).first.click();idle(page)
            page.get_by_role('heading',name='Documentos para esta oferta',exact=True).wait_for(timeout=30000)
            expect(page.get_by_role('button',name='Aprobar paquete seleccionado para exportación',exact=True)).to_be_disabled()
        navigate(page,'Perfil y configuración')
        expect(page.get_by_role('button',name='Aprobar esta versión del CV',exact=True)).to_be_disabled()
        assert 'retenida por la revisión de calidad' in page.locator('body').inner_text()
        page.get_by_text('Biblioteca de referencias y originales',exact=True).click();idle(page)
        assert page.get_by_text('Documentos originales y referencias',exact=True).count()==1
        assert page.get_by_text('Carriage · confirmación de empleo · pendiente de revisión',exact=True).count()==1
        navigate(page,'Ofertas de empleo')
        search=page.get_by_role('textbox',name='Buscar puesto, empresa o ubicación',exact=True)
        search.fill('IT Support Specialist');search.press('Enter');idle(page)
        page.get_by_role('button',name='Ver oferta',exact=True).first.click();idle(page)
        page.get_by_role('button',name='Preparar candidatura',exact=True).click();idle(page)
        page.get_by_role('heading',name='Documentos para esta oferta',exact=True).wait_for(timeout=30000)
        expect(page.get_by_role('button',name='Aprobar paquete seleccionado para exportación',exact=True)).to_be_disabled()
        expect(page.get_by_role('checkbox',name='Incluir mi carta de presentación en este paquete',exact=True)).not_to_be_checked()
        assert page.get_by_role('img').count()>=1
        for width in (1440,390):
            page.set_viewport_size({'width':width,'height':900});idle(page)
            value=layout(page);checks.append(value)
            assert value['main_scroll']<=value['main_width']+2 and value['overflow_controls']==0
        assert not page.get_by_test_id('stException').count()
        assert not blocked
        browser.close()
    assert signatures()==before
    current=rt.state(db);assert current['supervisor_pid']==runtime['supervisor_pid'] and rt.alive(current['supervisor_pid'],current['supervisor_stamp'])
    report={'created_at':now(),'status':'PASS','layout':checks,'quality_hold_visible':True,'pending_references_visible':True,
            'per_job_preview_visible':True,'default_optional_documents_unselected':True,'approval_disabled_without_consent':True,
            'critical_tables_unchanged':True,'same_supervisor_alive':True,'external_requests':0,'applications_sent':0,'private_screenshots_saved':0}
    if args.check_background_drafts:report.update(background_draft_count=draft_count,background_draft_navigation='PASS')
    path.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))


if __name__=='__main__':main()
