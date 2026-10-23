"""Chromium walkthrough with fictitious data and a server owned by this test."""
import io
import os
import socket
import subprocess
import sys
import time
import zipfile
from urllib.parse import urlsplit
import httpx
from corkjobradar.config import ROOT
from corkjobradar.autoapply.job_documents import review_file
from corkjobradar.autoapply.vault import candidate_snapshot
from test_per_job_documents import prepared


def test_per_job_browser_review_optional_letter_consent_zip_revocation(db,prepared,tmp_path,monkeypatch):
    from playwright.sync_api import sync_playwright,expect
    from scripts.check_ui_redesign import idle,layout
    job,_=prepared
    wrapper=tmp_path/'documents_app.py'
    wrapper.write_text('import streamlit as st\n'
        'st.set_page_config(page_title="Synthetic document test",layout="wide")\n'
        'from corkjobradar.db import Database\n'
        'db=Database('+repr(str(db.path))+')\n'
        'import corkjobradar.autoapply.handoff as handoff\nhandoff.validate_url=lambda value:value\n'
        'from corkjobradar.autoapply.job_documents_ui import render_job_documents\n'
        'job=db.rows("SELECT * FROM jobs WHERE id=?",('+repr(job['id'])+',))[0]\n'
        'render_job_documents(db,job)\n',encoding='utf-8')
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    origin=f'http://127.0.0.1:{port}'
    environment=os.environ.copy();environment.update(PYTHONPATH=str(ROOT),PYTHONIOENCODING='utf-8',TEMP=str(tmp_path),TMP=str(tmp_path),PLAYWRIGHT_BROWSERS_PATH=str(ROOT/'data/playwright-browsers'))
    monkeypatch.setenv('PLAYWRIGHT_BROWSERS_PATH',str(ROOT/'data/playwright-browsers'))
    monkeypatch.setenv('TEMP',str(tmp_path));monkeypatch.setenv('TMP',str(tmp_path))
    blocked=[]
    with (tmp_path/'server.log').open('w',encoding='utf-8') as log:
        child=subprocess.Popen([sys.executable,'-m','streamlit','run',str(wrapper),'--server.address','127.0.0.1','--server.port',str(port),'--server.headless','true','--browser.gatherUsageStats','false'],
            cwd=ROOT,env=environment,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        try:
            deadline=time.monotonic()+35
            while True:
                try:
                    if httpx.get(origin+'/_stcore/health',timeout=1,trust_env=False).status_code==200:break
                except httpx.HTTPError:pass
                assert child.poll() is None and time.monotonic()<deadline
                time.sleep(.15)
            with sync_playwright() as pw:
                browser=pw.chromium.launch(args=['--disable-background-networking'])
                context=browser.new_context(viewport={'width':1440,'height':900},accept_downloads=True,service_workers='block')
                def allowed(url):
                    parsed=urlsplit(url);return parsed.hostname=='127.0.0.1' and parsed.port==port
                def guard(route):
                    if allowed(route.request.url):route.continue_()
                    else:blocked.append(True);route.abort()
                context.route('**/*',guard)
                context.route_web_socket('**/*',lambda ws:ws.connect_to_server() if allowed(ws.url) else ws.close())
                page=context.new_page();page.goto(origin)
                page.get_by_role('heading',name='Documentos para esta oferta').wait_for(timeout=45000);idle(page)
                assert not db.rows('SELECT * FROM job_document_versions')
                page.get_by_role('button',name='Crear CV adaptado y carta para revisar',exact=True).click()
                approve=page.get_by_role('button',name='Aprobar paquete seleccionado para exportación',exact=True)
                approve.wait_for(timeout=45000);idle(page)
                expect(approve).to_be_disabled()
                expect(page.get_by_role('checkbox',name='Incluir mi carta de presentación en este paquete',exact=True)).not_to_be_checked()
                assert len(db.rows('SELECT * FROM job_document_versions'))==1
                assert not db.rows('SELECT * FROM candidate_documents')
                for width in (1440,390):
                    page.set_viewport_size({'width':width,'height':900});idle(page)
                    dimensions=layout(page)
                    assert dimensions['main_scroll']<=dimensions['main_width']+2 and dimensions['overflow_controls']==0
                page.set_viewport_size({'width':1440,'height':900});idle(page)
                labels=(
                    'He comprobado el formulario: admite el formato de CV y todos los documentos opcionales que he seleccionado',
                    'He revisado la selección, el resumen y la carta elegida; todo es veraz y no añade experiencia ni equivalencias',
                    'He revisado íntegramente el diseño del archivo elegido, incluidas todas sus páginas',
                    'Apruebo estos documentos exactos para este puesto y su exportación local; no autorizo un envío automático')
                for label in labels:
                    page.get_by_text(label,exact=True).click();idle(page)
                expect(approve).to_be_enabled()
                page.get_by_text('Incluir mi carta de presentación en este paquete',exact=True).click();idle(page)
                assert page.get_by_role('button',name='Descargar carta para revisar',exact=True).count()==1
                expect(approve).to_be_disabled()
                for label in labels:expect(page.get_by_role('checkbox',name=label,exact=True)).not_to_be_checked()
                for label in labels:
                    page.get_by_text(label,exact=True).click();idle(page)
                expect(approve).to_be_enabled();approve.click();idle(page)
                button=page.get_by_role('button',name='Preparar ZIP autorizado · paquete 1',exact=True)
                button.wait_for(timeout=20000);button.click();idle(page)
                download=page.get_by_role('button',name='Descargar candidatura preparada (ZIP privado)',exact=True)
                with page.expect_download() as item:download.click()
                target=tmp_path/'reviewed-bundle.zip';item.value.save_as(target)
                with zipfile.ZipFile(target) as archive:
                    assert archive.read('CV.pdf')==review_file(db,1)
                    assert archive.read('Cover-letter.pdf')==review_file(db,1,'COVER_LETTER')
                    assert not any(name.startswith('Reference') for name in archive.namelist())
                assert not candidate_snapshot(db).get('cv_document_id')
                assert not db.rows('SELECT * FROM application_attempts')
                assert not db.rows('SELECT * FROM application_receipt_evidence')
                page.get_by_text('Quiero revocar esta versión de documentos y sus paquetes',exact=True).click();idle(page)
                page.get_by_role('button',name='Revocar versión de esta oferta',exact=True).click();idle(page)
                expect(download).to_have_count(0)
                assert db.rows('SELECT revoked_at FROM job_document_bundles')[0]['revoked_at']
                assert not blocked
                browser.close()
        finally:
            child.terminate()
            try:child.wait(timeout=15)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
