"""Chromium: locally generated draft -> filtered list -> exact CV review."""
import os
import socket
import subprocess
import sys
import time
from urllib.parse import urlsplit
import httpx
from corkjobradar.config import ROOT
from corkjobradar import runtime as rt
from test_per_job_documents import prepared


def test_automatic_draft_notifications_open_cv_without_export_or_approval(db,prepared,tmp_path,monkeypatch):
    from playwright.sync_api import sync_playwright,expect
    from scripts.check_ui_redesign import navigate,idle,layout
    rt.command(db,'START',search_now=False);rt.run_work(db,'PREPARE')
    assert len(db.rows('SELECT * FROM job_document_versions'))==1
    before={t:db.rows('SELECT * FROM '+t) for t in ('candidate_facts','candidate_documents','job_document_versions','job_document_bundles','manual_application_handoffs','application_attempts')}
    wrapper=tmp_path/'draft_activity_app.py'
    wrapper.write_text('import streamlit as st\nfrom corkjobradar.db import Database\n'
        'st.set_page_config(page_title="Synthetic draft test",layout="wide")\n'
        'db=Database('+repr(str(db.path))+')\n'
        'import corkjobradar.autoapply.handoff as handoff\nhandoff.validate_url=lambda value:value\n'
        'from corkjobradar.ui.shell import render\nrender(db)\n',encoding='utf-8')
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    origin=f'http://127.0.0.1:{port}'
    env=os.environ.copy();env.update(PYTHONPATH=str(ROOT),PYTHONIOENCODING='utf-8',TEMP=str(tmp_path),TMP=str(tmp_path))
    monkeypatch.setenv('PLAYWRIGHT_BROWSERS_PATH',str(ROOT/'data/playwright-browsers'))
    blocked=[]
    with (tmp_path/'browser-server.log').open('w',encoding='utf-8') as log:
        child=subprocess.Popen([sys.executable,'-m','streamlit','run',str(wrapper),'--server.address','127.0.0.1','--server.port',str(port),'--server.headless','true','--browser.gatherUsageStats','false'],cwd=ROOT,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
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
                context=browser.new_context(viewport={'width':1440,'height':900},service_workers='block')
                def allowed(url):
                    p=urlsplit(url);return p.hostname=='127.0.0.1' and p.port==port
                def guard(route):
                    if allowed(route.request.url):route.continue_()
                    else:blocked.append(True);route.abort()
                context.route('**/*',guard)
                context.route_web_socket('**/*',lambda ws:ws.connect_to_server() if allowed(ws.url) else ws.close())
                page=context.new_page();page.goto(origin)
                page.get_by_role('button',name='Revisar borradores de CV y carta',exact=True).wait_for(timeout=45000)
                idle(page)
                assert 'synthetic.perjob@example.invalid' not in page.locator('body').inner_text()
                page.get_by_role('button',name='Revisar borradores de CV y carta',exact=True).click();idle(page)
                expect(page.get_by_test_id('stSelectbox').filter(has_text='Estado de candidatura')).to_contain_text('Borradores por revisar')
                page.get_by_role('button',name='Abrir candidatura',exact=True).click();idle(page)
                navigate(page,'Actividad y notificaciones')
                page.get_by_role('button',name='Revisar CV y carta',exact=True).click();idle(page)
                page.get_by_role('heading',name='Documentos para esta oferta',exact=True).wait_for()
                approve=page.get_by_role('button',name='Aprobar paquete seleccionado para exportación',exact=True)
                expect(approve).to_be_disabled()
                expect(page.get_by_role('checkbox',name='Incluir mi carta de presentación en este paquete',exact=True)).not_to_be_checked()
                for width in (1440,390):
                    page.set_viewport_size({'width':width,'height':900});idle(page)
                    dimensions=layout(page)
                    assert dimensions['main_scroll']<=dimensions['main_width']+2 and dimensions['overflow_controls']==0
                assert not page.get_by_test_id('stException').count() and not blocked
                browser.close()
        finally:
            child.terminate()
            try:child.wait(timeout=15)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
    for table,rows in before.items():assert db.rows('SELECT * FROM '+table)==rows
