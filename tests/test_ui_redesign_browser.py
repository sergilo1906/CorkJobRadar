"""Real Chromium across the new workflow. Synthetic person and isolated SQLite only."""
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from corkjobradar.config import ROOT,now
from corkjobradar.autoapply.documents import create_cv_review,render_cv
from corkjobradar.autoapply.vault import candidate_snapshot,approve_fact
from test_usable_it_workspace import case
from test_assisted_delivery import message


def test_new_navigation_cv_copy_package_registration_proof_and_form_stability(db,profile,tmp_path,monkeypatch):
    from playwright.sync_api import sync_playwright,expect
    from scripts.check_ui_redesign import navigate,select,idle,layout
    from corkjobradar import runtime as rt
    job=case(db,profile)
    approve_fact(db,'linkedin_url','https://www.linkedin.com/in/synthetic-only/','SYNTHETIC',True)
    create_cv_review(db,render_cv(candidate_snapshot(db),'pdf'),'pdf')
    wrapper=tmp_path/'new_ui_app.py'
    wrapper.write_text('import streamlit as st\nfrom corkjobradar.db import Database\n'
        'st.set_page_config(page_title="Cork Job Radar",layout="wide")\n'
        'db=Database('+repr(str(db.path))+')\n'
        'import corkjobradar.autoapply.handoff as handoff\nhandoff.validate_url=lambda url:url\n'
        'from corkjobradar.ui.shell import render\nrender(db)\n',encoding='utf-8')
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    origin='http://127.0.0.1:'+str(port)
    env=os.environ.copy();env.update(PYTHONPATH=str(ROOT),PYTHONIOENCODING='utf-8',TEMP=str(tmp_path),TMP=str(tmp_path))
    monkeypatch.setenv('PLAYWRIGHT_BROWSERS_PATH',str(ROOT/'data/playwright-browsers'))
    monkeypatch.setenv('TEMP',str(tmp_path));monkeypatch.setenv('TMP',str(tmp_path))
    log=(tmp_path/'new-ui-server.log').open('w',encoding='utf-8')
    child=subprocess.Popen([sys.executable,'-m','streamlit','run',str(wrapper),'--server.address','127.0.0.1','--server.port',str(port),'--server.headless','true','--browser.gatherUsageStats','false'],cwd=ROOT,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    blocked=[];captures=tmp_path/'screens';captures.mkdir()
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
            context=browser.new_context(viewport={'width':1440,'height':900},permissions=['clipboard-read','clipboard-write'],accept_downloads=True,service_workers='block')
            def allowed(url):
                p=urlsplit(url);return p.hostname=='127.0.0.1' and p.port==port
            def guard(route):
                if allowed(route.request.url):route.continue_()
                else:blocked.append(True);route.abort()
            context.route('**/*',guard);context.route_web_socket('**/*',lambda ws:ws.connect_to_server() if allowed(ws.url) else ws.close())
            page=context.new_page();page.goto(origin)
            page.get_by_role('heading',name='Tu próxima oportunidad IT',exact=True).wait_for(timeout=45000);idle(page)
            assert 'synthetic@example.invalid' not in page.locator('body').inner_text()
            navigate(page,'Perfil y configuración')
            expect(page.get_by_role('button',name='Aprobar esta versión del CV',exact=True)).to_be_disabled()
            page.get_by_text('He revisado íntegramente esta versión y apruebo este CV definitivo',exact=True).click()
            page.get_by_role('button',name='Aprobar esta versión del CV',exact=True).click()
            page.get_by_role('button',name='Descargar CV definitivo aprobado',exact=True).wait_for();idle(page)
            assert candidate_snapshot(db).get('cv_document_id')
            page.screenshot(path=str(captures/'cv-approved.png'))  # Synthetic identity only.
            navigate(page,'Ofertas de empleo')
            page.get_by_role('textbox',name='Buscar puesto, empresa o ubicación').fill('Support')
            page.get_by_role('textbox',name='Buscar puesto, empresa o ubicación').press('Enter');idle(page)
            page.get_by_role('button',name='Ver oferta',exact=True).first.click()
            page.get_by_role('heading',name='Requisitos deseables',exact=True).wait_for();idle(page)
            assert 'Linux experience preferred.' in page.locator('body').inner_text()
            page.get_by_role('button',name='Preparar candidatura',exact=True).click()
            page.get_by_role('button',name='Preparar solicitud manual con mi CV aprobado',exact=True).wait_for();idle(page)
            select(page,'Paso de la candidatura','Respuestas')
            code=page.get_by_test_id('stCode').filter(has_text='synthetic@example.invalid').first;code.hover()
            code.get_by_role('button',name=re.compile('copy',re.I)).click()
            assert page.evaluate('navigator.clipboard.readText()')=='synthetic@example.invalid'
            # Transport is a genuine form in the new single-job screen, unaffected by timers.
            select(page,'Paso de la candidatura','Transporte')
            destination=page.get_by_role('textbox',name='Centro exacto de trabajo que has confirmado',exact=True)
            destination.fill('SYNTHETIC unsaved destination')
            page.wait_for_timeout(6500)
            assert destination.input_value()=='SYNTHETIC unsaved destination'
            assert not db.rows('SELECT * FROM commute_checks')
            select(page,'Paso de la candidatura','Solicitud')
            page.get_by_role('button',name='Preparar solicitud manual con mi CV aprobado',exact=True).click()
            page.get_by_role('button',name='Descargar CV y solicitud manual',exact=True).wait_for();idle(page)
            with page.expect_download() as downloaded:page.get_by_role('button',name='Descargar CV y solicitud manual',exact=True).click()
            downloaded.value.save_as(tmp_path/'new-workflow.zip')
            assert len(db.rows('SELECT * FROM manual_application_handoffs'))==1
            assert not db.rows('SELECT * FROM user_actions')
            page.get_by_text('Confirmo que ya presenté esta solicitud manualmente; registrar para evitar duplicados',exact=True).click()
            page.get_by_role('button',name='Registrar candidatura presentada por mí',exact=True).click();idle(page)
            expect(page.get_by_role('button',name='Adjuntar justificante',exact=True)).to_be_visible(timeout=15000)
            assert len(db.rows('SELECT * FROM manual_application_declarations'))==1
            assert not page.get_by_role('button',name='Preparar solicitud manual con mi CV aprobado',exact=True).count()
            select(page,'Paso de la candidatura','Justificantes')
            page.locator('input[type=file]').set_input_files({'name':'synthetic.eml','mimeType':'message/rfc822','buffer':message(job)})
            page.get_by_text('Autorizo conservar este justificante cifrado; entiendo que no autentica al remitente ni activa AutoApply',exact=True).click()
            page.get_by_role('button',name='Guardar justificante cifrado',exact=True).click();idle(page)
            assert len(db.rows('SELECT * FROM manual_application_evidence'))==1
            page.screenshot(path=str(captures/'manual-evidence.png'))
            navigate(page,'Inicio')
            assert 'synthetic@example.invalid' not in page.locator('body').inner_text()
            metrics=page.locator('.cjr-metric')
            assert metrics.filter(has_text='Recepciones externas confirmadas').inner_text().strip().endswith('0')
            assert metrics.filter(has_text='Envíos declarados manualmente').inner_text().strip().endswith('1')
            navigate(page,'Actividad y notificaciones')
            expect(page.get_by_role('button',name='Iniciar actividad local',exact=True)).to_be_visible()
            assert not page.get_by_role('button',name='Pausar actividad',exact=True).count()
            page.get_by_role('button',name='Iniciar actividad local',exact=True).click();idle(page)
            expect(page.get_by_role('button',name='Pausar actividad',exact=True)).to_be_visible()
            assert not page.get_by_role('button',name='Iniciar actividad local',exact=True).count()
            page.get_by_role('button',name='Pausar actividad',exact=True).click();idle(page)
            expect(page.get_by_role('button',name='Reanudar actividad',exact=True)).to_be_visible()
            assert not page.get_by_role('button',name='Pausar actividad',exact=True).count()
            page.get_by_role('button',name='Detener actividad',exact=True).click();idle(page)
            expect(page.get_by_role('button',name='Iniciar actividad local',exact=True)).to_be_visible()
            rt.update(db,state='STOPPING')
            page.wait_for_timeout(5500)
            assert not page.get_by_role('button',name='Iniciar actividad local',exact=True).count()
            page.screenshot(path=str(captures/'stopping.png'))
            rt.update(db,state='STOPPED')
            assert not page.get_by_test_id('stException').count() and not blocked
            context.close();browser.close()
        assert not db.rows('SELECT * FROM application_attempts') and not db.rows('SELECT * FROM application_receipt_evidence')
        assert db.rows('SELECT live_enabled FROM autoapply_control')[0]['live_enabled']==0
        (tmp_path/'new-ui-browser-proof.json').write_text(json.dumps({'checked_at':now(),'synthetic_only':True,'cv_approved_by_test_user':True,'copy_clipboard_exact':True,'manual_package_count':1,'declaration_count':1,'encrypted_evidence_count':1,'external_receipt_count':0,'forms_survive_timer':True,'state_dependent_controls':True,'external_requests':0,'live_enabled':False},indent=2),encoding='utf-8')
    finally:
        if child.poll() is None:subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        log.close()
