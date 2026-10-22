"""Read-only local UI verification; never approves CV, policy or applications.

Requires a running app at 127.0.0.1:8501 and an explicitly selected pending CV.
No screenshots of the private profile are persisted. Evidence contains metadata.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.db import Database
from corkjobradar import runtime as rt
from corkjobradar.autoapply.documents import cv_review_bytes
from corkjobradar.autoapply.cv_preview import pdf_preview
from scripts.check_ui_redesign import navigate,idle,layout,select


def main():
    from playwright.sync_api import sync_playwright,expect
    from pypdf import PdfReader
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cv-id',required=True,type=int)
    parser.add_argument('--label',required=True)
    args=parser.parse_args()
    if not re.fullmatch(r'[a-z0-9-]+',args.label):raise ValueError('SAFE_LABEL_REQUIRED')
    output=ROOT/'logs'/(args.label+'-browser.json')
    if output.exists():raise ValueError('PRESERVE_PREVIOUS_EVIDENCE')
    db=Database();raw,ext,sha,_=cv_review_bytes(db,args.cv_id)
    if ext!='pdf' or db.rows('SELECT approved_at FROM candidate_documents WHERE id=?',(args.cv_id,))[0]['approved_at']:
        raise ValueError('EXPLICIT_PENDING_PDF_REQUIRED')
    critical=('candidate_facts','candidate_documents','application_attempts','autoapply_control','autoapply_policies','manual_application_handoffs','manual_application_declarations')
    def signatures():
        return {t:hashlib.sha256(repr(db.rows('SELECT * FROM '+t+' ORDER BY rowid')).encode()).hexdigest() for t in critical}
    before=signatures();refused=[];sizes=[]
    os.environ['PLAYWRIGHT_BROWSERS_PATH']=str(ROOT/'data/playwright-browsers')
    os.environ['TEMP']=os.environ['TMP']=str(ROOT/'data/browser-temp')
    with sync_playwright() as pw:
        browser=pw.chromium.launch(args=['--disable-background-networking'])
        context=browser.new_context(viewport={'width':1440,'height':900},service_workers='block',accept_downloads=True)
        def allowed(url):
            p=urlsplit(url);return p.hostname=='127.0.0.1' and p.port==8501
        def guard(route):
            if allowed(route.request.url):route.continue_()
            else:refused.append(True);route.abort()
        context.route('**/*',guard)
        context.route_web_socket('**/*',lambda ws:ws.connect_to_server() if allowed(ws.url) else ws.close())
        page=context.new_page();page.goto('http://127.0.0.1:8501')
        page.get_by_role('heading',name='Tu próxima oportunidad IT',exact=True).wait_for(timeout=60000);idle(page)
        navigate(page,'Ofertas de empleo')
        assert page.get_by_role('button',name='Ver oferta',exact=True).count()>0
        navigate(page,'Mis candidaturas')
        # Revoked old packets are correctly moved out of Prepared/Pending. The
        # current CV-review holds remain available in the intervention filter.
        select(page,'Estado de candidatura','Requieren intervención')
        page.get_by_role('button',name='Abrir candidatura',exact=True).first.wait_for()
        for width,height in ((1440,900),(390,844)):
            page.set_viewport_size({'width':width,'height':height})
            navigate(page,'Perfil y configuración')
            expect(page.get_by_text('Vista previa del PDF exacto que estás revisando',exact=True)).to_be_visible()
            # The list must show the selected draft, never a revoked approval.
            expect(page.get_by_role('button',name='Aprobar esta versión del CV',exact=True)).to_be_disabled()
            expect(page.get_by_role('checkbox',name='He revisado íntegramente esta versión y apruebo este CV definitivo',exact=True)).not_to_be_checked()
            dims=layout(page);assert dims['document_width']<=width+2 and dims['overflow_controls']==0
            sizes.append({'width':width,'layout':dims})
        from PIL import Image
        from urllib.parse import urljoin
        picture_url=urljoin('http://127.0.0.1:8501/',page.get_by_test_id('stImage').locator('img').first.get_attribute('src'))
        if not allowed(picture_url):raise ValueError('PREVIEW_NOT_LOCAL')
        response=context.request.get(picture_url);assert response.status==200
        with Image.open(io.BytesIO(response.body())) as actual,Image.open(io.BytesIO(pdf_preview(raw))) as expected:
            assert actual.size==expected.size and actual.convert('RGB').tobytes()==expected.convert('RGB').tobytes()
        with page.expect_download() as downloaded:
            page.get_by_role('button',name='Descargar esta versión para revisar',exact=True).click()
        path=Path(downloaded.value.path()).resolve()
        if not path.is_relative_to(ROOT.resolve()):raise ValueError('DOWNLOAD_OUTSIDE_PROJECT')
        assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
        assert len(PdfReader(io.BytesIO(path.read_bytes())).pages)==1
        path.unlink()  # Only this explicit, verified temporary download.
        options=page.get_by_text('Opciones de documento: DOCX, importar CV o carta',exact=True)
        options.click();idle(page)
        select(page,'Formato CV','docx')
        expect(page.get_by_role('button',name='Preparar CV inglés para revisar',exact=True)).to_be_visible()
        options.click();idle(page)
        assert not page.get_by_test_id('stException').count()
        context.close();browser.close()
    assert signatures()==before and not refused
    first=rt.state(db)
    assert rt.alive(first['supervisor_pid'],first['supervisor_stamp'])
    heartbeat=first['heartbeat'];time.sleep(6)
    second=rt.state(db)
    assert second['heartbeat']!=heartbeat and rt.alive(second['owner_pid'],second['owner_stamp'])
    # The existing launcher must reuse the healthy process, not start a second.
    result=subprocess.run([sys.executable,str(ROOT/'scripts/iniciar_local.py')],cwd=ROOT,
        capture_output=True,timeout=40,creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode==0
    final=rt.state(db)
    assert (final['supervisor_pid'],final['supervisor_stamp'])==(first['supervisor_pid'],first['supervisor_stamp'])
    assert signatures()==before
    report={'checked_at':now(),'status':'PASS','cv_document_id':args.cv_id,'cv_sha256':sha,
        'pending_cv_preview_and_exact_download':True,'consent_unchecked':True,'critical_tables_unchanged':True,
        'preview_pixels_match_exact_pdf':True,'docx_option_available':True,
        'viewports':sizes,'private_screenshots_saved':False,'browser_closed_worker_continues':True,
        'second_launcher_reuses_supervisor':True,'supervisor_pid':final['supervisor_pid'],
        'interval_hours':final['interval_hours'],'next_search_at':final['next_search_at'],
        'external_requests_from_browser':len(refused),'applications_sent':0,'live_enabled':False}
    output.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))


if __name__=='__main__':main()
