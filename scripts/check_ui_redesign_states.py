"""Owned local challenge + empty/long/error states in the new shell. Synthetic only."""
from contextlib import contextmanager
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.parse import urlsplit
import httpx
import pytest
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'tests')]
from corkjobradar.config import ROOT,now,load_profile
from corkjobradar.db import Database
from corkjobradar import runtime as rt
from scripts.check_ui_redesign import navigate,idle,layout


@contextmanager
def owned_dashboard(db):
    script=db.path.parent/'visual_app.py'
    script.write_text('import streamlit as st\nfrom corkjobradar.db import Database\nfrom corkjobradar.ui.shell import render\n'
        'st.set_page_config(page_title="SYNTHETIC UI QA",layout="wide")\nrender(Database('+repr(str(db.path))+'))\n',encoding='utf-8')
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    origin='http://127.0.0.1:'+str(port)
    env={**os.environ,'PYTHONPATH':str(ROOT),'PYTHONIOENCODING':'utf-8','TEMP':str(db.path.parent),'TMP':str(db.path.parent)}
    log=(db.path.parent/'server.log').open('w',encoding='utf-8')
    child=subprocess.Popen([sys.executable,'-m','streamlit','run',str(script),'--server.address','127.0.0.1','--server.port',str(port),'--server.headless','true','--browser.gatherUsageStats','false'],cwd=ROOT,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        until=time.monotonic()+35
        while True:
            try:
                if httpx.get(origin+'/_stcore/health',timeout=1,trust_env=False).status_code==200:break
            except httpx.HTTPError:pass
            assert child.poll() is None and time.monotonic()<until
            time.sleep(.15)
        yield origin
    finally:
        if child.poll() is None:subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        log.close()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--label',default='additional-states');args=parser.parse_args()
    if not args.label.replace('-','').isalnum():raise ValueError('SAFE_LABEL_REQUIRED')
    from playwright.sync_api import sync_playwright,expect
    from test_human_interventions import fixture_setup,manual_complete
    from corkjobradar.autoapply.human_sessions import create_intervention,session_row,PAUSED
    from corkjobradar.autoapply.interactive_browser import InteractiveBrowser
    from corkjobradar.models import Job
    from corkjobradar.repository import save_job
    from conftest import source
    folder=ROOT/'data/ui-redesign'/args.label
    folder.mkdir(parents=True,exist_ok=False)
    os.environ['PLAYWRIGHT_BROWSERS_PATH']=str(ROOT/'data/playwright-browsers')
    temp=ROOT/'data/browser-temp';temp.mkdir(exist_ok=True)
    os.environ['TEMP']=os.environ['TMP']=str(temp)
    blocked=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(args=['--disable-background-networking'])
        def context_for(origin):
            context=browser.new_context(viewport={'width':390,'height':844},service_workers='block')
            def allowed(url):
                a=urlsplit(origin);b=urlsplit(url);return a.hostname==b.hostname and a.port==b.port
            def guard(route):
                if allowed(route.request.url):route.continue_()
                else:blocked.append(True);route.abort()
            context.route('**/*',guard);context.route_web_socket('**/*',lambda ws:ws.connect_to_server() if allowed(ws.url) else ws.close())
            return context
        empty_db=Database(folder/'empty.sqlite3')
        with owned_dashboard(empty_db) as origin:
            context=context_for(origin);page=context.new_page();page.goto(origin)
            page.get_by_role('heading',name='Tu próxima oportunidad IT',exact=True).wait_for(timeout=45000);idle(page)
            page.screenshot(path=str(folder/'empty-home-390.png'))
            # The native labelled mobile control is operated by keyboard.
            combo=page.get_by_test_id('stSelectbox').filter(has=page.get_by_text('Ir a sección',exact=True)).get_by_role('combobox')
            combo.focus();combo.press('ArrowDown')
            page.keyboard.type('Ofertas');page.keyboard.press('Enter')
            page.get_by_role('heading',name='Ofertas de empleo',exact=True).wait_for();idle(page)
            assert 'No hay resultados' in page.locator('body').inner_text()
            assert page.get_by_role('button',name='Iniciar o revisar búsqueda',exact=True).is_visible()
            page.screenshot(path=str(folder/'empty-offers-keyboard-390.png'))
            rt.update(empty_db,last_error_code='SYNTHETIC_CONTROLLED_ERROR')
            navigate(page,'Inicio');assert page.get_by_role('alert').count()
            page.screenshot(path=str(folder/'error-390.png'))
            assert layout(page)['document_width']<=392 and not page.get_by_test_id('stException').count()
            context.close()
        browser.close()
    human_folder=folder/'human';human_folder.mkdir()
    db=Database(human_folder/'test.sqlite3');profile=load_profile()
    with pytest.MonkeyPatch.context() as monkeypatch:
        aid,job,inspection,receiver=fixture_setup(db,profile,monkeypatch)
        with receiver as fixture:
            sid=create_intervention(db,aid,inspection['inspection_id'],_fixture_url=fixture['url'])
            with InteractiveBrowser(db,sid,headless=True) as actor:
                actor.open();assert session_row(db,sid)['status']==PAUSED and fixture['stats']['posts']==0
                browser=actor.pw.chromium.launch(args=['--disable-background-networking'])
                with owned_dashboard(db) as origin:
                    # This process really owns the open fixture browser. Register
                    # its current heartbeat for the UI, without a background sender.
                    db.execute('UPDATE autoapply_interventions SET worker_pid=?,heartbeat=? WHERE id=?',(os.getpid(),now(),sid))
                    context=context_for(origin);page=context.new_page();page.goto(origin)
                    page.get_by_role('heading',name='Tu próxima oportunidad IT',exact=True).wait_for(timeout=45000);idle(page)
                    navigate(page,'AutoApply')
                    expect(page.get_by_role('heading',name='Intervenciones pendientes',exact=True)).to_be_visible()
                    assert 'INTERVENCION_HUMANA_REQUERIDA' in page.locator('body').inner_text()
                    page.get_by_test_id('stMain').evaluate('(e)=>e.scrollTop=420')
                    page.screenshot(path=str(folder/'human-pause-390.png'))
                    manual_complete(actor);actor.continue_after_human()
                    assert fixture['stats']['posts']==1 and session_row(db,sid)['status']=='PRUEBA_LOCAL_CONFIRMADA'
                    navigate(page,'Inicio')
                    assert page.locator('.cjr-metric').filter(has_text='Recepciones externas confirmadas').inner_text().strip().endswith('0')
                    page.screenshot(path=str(folder/'local-receipt-not-external-390.png'))
                    # A long public record tests wrapping without inventing any production vacancy.
                    source(db,'html',sid='long-ui-only')
                    save_job(db,'long-ui-only',Job(external_id='long-ui-only',title='SYNTHETIC UI ONLY IT Support '+('very long public title '*15),company='SYNTHETIC UI ONLY '+('long company '*8),location='Cork City',url='https://synthetic.invalid/long-ui',description=('Provide technical IT support and troubleshoot Windows desktop incidents. '*80),detail_complete=True),profile=profile)
                    navigate(page,'Ofertas de empleo')
                    assert layout(page)['document_width']<=392 and not page.get_by_test_id('stException').count()
                    title_box=page.locator('.cjr-job-title').first
                    assert title_box.evaluate('(e)=>getComputedStyle(e).webkitLineClamp')=='2'
                    assert title_box.bounding_box()['height']<=55
                    page.get_by_test_id('stMain').evaluate('(e)=>e.scrollTop=600')
                    page.screenshot(path=str(folder/'long-record-390.png'))
                    context.close()
                browser.close()
            assert not db.rows('SELECT * FROM application_receipt_evidence')
    assert not blocked
    result={'checked_at':now(),'status':'PASS','synthetic_only':True,'keyboard_navigation':True,'empty_state':True,'error_state':True,'long_record_wrapping':True,
            'real_owned_captcha_simulation':True,'paused_before_post':True,'local_fixture_posts':1,'external_receipts':0,'external_requests':0,'no_external_captcha':True,'production_changed':False,
            'long_title_limited_to_two_lines':True,'empty_state_direct_action':True,'live_enabled':False}
    output=ROOT/'logs'/('ui-redesign-'+args.label+'.json')
    if output.exists():raise ValueError('PRESERVE_PREVIOUS_REPORT')
    output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))


if __name__=='__main__':main()
