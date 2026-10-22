"""Actual Windows Streamlit process/browser closure/parent restart. Local only."""
import json
import os
import socket
import subprocess
import sys
import time
from urllib.parse import urlsplit
import httpx
from playwright.sync_api import sync_playwright
from corkjobradar.config import ROOT,now
from corkjobradar import runtime as rt
from test_local_runtime import wait_until


def test_browser_closed_parent_lives_then_restart_recovers_without_external_requests(db,tmp_path,monkeypatch):
    app=tmp_path/'runtime_app.py'
    app.write_text('from corkjobradar.db import Database\nfrom corkjobradar.runtime_ui import bootstrap,render\n'
                   'db=Database('+repr(str(db.path))+')\nbootstrap(db)\nrender(db)\n',encoding='utf-8')
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    origin='http://127.0.0.1:'+str(port)
    monkeypatch.setenv('PLAYWRIGHT_BROWSERS_PATH',str(ROOT/'data/playwright-browsers'))
    monkeypatch.setenv('TEMP',str(tmp_path));monkeypatch.setenv('TMP',str(tmp_path))
    env=os.environ.copy();env.update(PYTHONPATH=str(ROOT),PYTHONIOENCODING='utf-8')
    children=[];logs=[];blocked=[]
    def start_server():
        log=(tmp_path/('server-'+str(len(children))+'.log')).open('w',encoding='utf-8');logs.append(log)
        child=subprocess.Popen([sys.executable,'-m','streamlit','run',str(app),'--server.address','127.0.0.1','--server.port',str(port),
             '--server.headless','true','--browser.gatherUsageStats','false'],cwd=ROOT,env=env,stdout=log,stderr=log,
             creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        children.append(child)
        def healthy():
            try:return httpx.get(origin+'/_stcore/health',timeout=1,trust_env=False).status_code==200
            except httpx.HTTPError:return False
        wait_until(healthy,30)
    def guarded_context(browser):
        context=browser.new_context(service_workers='block')
        def allowed(url):
            p=urlsplit(url);return p.hostname=='127.0.0.1' and p.port==port
        def guard(route):
            if allowed(route.request.url):route.continue_()
            else:blocked.append(True);route.abort()
        context.route('**/*',guard);context.route_web_socket('**/*',lambda ws:ws.connect_to_server() if allowed(ws.url) else ws.close())
        return context
    try:
        start_server()
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,args=['--disable-background-networking'])
            context=guarded_context(browser);page=context.new_page();page.goto(origin,wait_until='domcontentloaded')
            page.get_by_role('heading',name='Actividad local continua · Windows · LIVE OFF',exact=True).wait_for(timeout=30000)
            # Production controls are driven, but schedule is deferred in this isolated test.
            rt.command(db,'START',search_now=False);rt.update(db,last_prepare_fingerprint=rt.input_fingerprint(db))
            wait_until(lambda:rt.state(db)['supervisor_pid'] is not None)
            first=rt.state(db)['supervisor_pid'];before=rt.state(db)['heartbeat']
            context.close()
            wait_until(lambda:rt.state(db)['heartbeat']!=before)
            assert rt.alive(first,rt.state(db)['supervisor_stamp'])
            # Terminate only our isolated Streamlit server, never the user's server.
            owner=rt.state(db);pid=owner['owner_pid'];stamp=owner['owner_stamp']
            assert rt.alive(pid,stamp) and port!=8501
            os.kill(pid,15);wait_until(lambda:rt.lock_free(db,'.runtime.lock'),25)
            children[-1].wait(timeout=10)
            assert rt.state(db)['desired']=='RUNNING'
            start_server();context=guarded_context(browser);page=context.new_page();page.goto(origin,wait_until='domcontentloaded')
            page.get_by_role('heading',name='Actividad local continua · Windows · LIVE OFF',exact=True).wait_for(timeout=30000)
            wait_until(lambda:rt.state(db)['supervisor_pid'] not in {None,first})
            page.wait_for_function("() => document.querySelector('[data-test-script-state]')?.getAttribute('data-test-script-state') === 'notRunning'")
            page.get_by_role('button',name='Pausar actividad',exact=True).click()
            page.wait_for_function("() => document.body.innerText.includes('Actividad solicitada: PAUSED')")
            assert rt.state(db)['desired']=='PAUSED'
            page.wait_for_function("() => document.querySelector('[data-test-script-state]')?.getAttribute('data-test-script-state') === 'notRunning'")
            page.get_by_role('button',name='Reanudar actividad',exact=True).click()
            page.wait_for_function("() => document.body.innerText.includes('Actividad solicitada: RUNNING')")
            assert rt.state(db)['desired']=='RUNNING'
            page.wait_for_function("() => document.querySelector('[data-test-script-state]')?.getAttribute('data-test-script-state') === 'notRunning'")
            page.get_by_role('button',name='Detener actividad',exact=True).click()
            page.wait_for_function("() => document.body.innerText.includes('Actividad solicitada: STOPPED')")
            assert rt.state(db)['desired']=='STOPPED'
            wait_until(lambda:rt.lock_free(db,'.runtime.lock'))
            assert not page.get_by_test_id('stException').count() and not blocked
            context.close();browser.close()
        report={'checked_at':now(),'real_chromium':True,'browser_closed_supervisor_continues':True,
                'owned_parent_terminated_supervisor_exits':True,'app_restarted_same_database_recovers':True,
                'pause_resume_stop_buttons':True,'external_requests':len(blocked),'windows_reboot_performed':False,'live_enabled':False}
        (tmp_path/'browser-proof.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    except Exception:
        try:
            debug={'script_state':page.locator('[data-test-script-state]').get_attribute('data-test-script-state'),
                   'connection':page.locator('[data-test-connection-state]').get_attribute('data-test-connection-state'),
                   'body':page.locator('body').inner_text()[:2000],
                   'events':db.rows('SELECT kind,code FROM local_runtime_events')}
            (tmp_path/'failure-state.json').write_text(json.dumps(debug,indent=2),encoding='utf-8')
        except Exception:pass
        raise
    finally:
        rt.command(db,'STOP')
        wait_until(lambda:rt.lock_free(db,'.runtime.lock'),30)
        for child in children:
            if child.poll() is None:
                # Owned Popen tree, verified above, all paths within this test directory.
                subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW)
        for log in logs:log.close()
